"""Multi-Agent Agentic AI Matching Pipeline — powered by Backboard.io.

Uses Backboard.io's multi-agent orchestration with persistent shared memory.
Each agent is a Backboard Assistant with a specialized system prompt.
Agents share context through a common Thread, enabling true collaboration.

Architecture:
  1. Pre-filter (fast, no AI) — narrows 30+ VCs to top candidates
  2. Agent 1: Startup Analyst — deep analysis of the startup
  3. Agent 2: VC Profiler — analyzes each candidate VC's thesis
  4. Agent 3: Match Reasoner — produces detailed match justifications
  All agents share a Thread → enabling cross-agent memory and context.
"""

import json
import re
from typing import Any, Dict, List

import httpx

from config import settings
from matching.matcher import get_top_matches  # fast pre-filter

# ── Backboard.io config ─────────────────────────────────────
BASE_URL = "https://app.backboard.io/api"
HEADERS = {"X-API-Key": settings.BACKBOARD_API_KEY}

# ── HTTP client ─────────────────────────────────────────────
_client = httpx.AsyncClient(timeout=60.0)


def _parse_json(raw: str) -> dict | list:
    """Parse JSON from LLM response."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


# ═══════════════════════════════════════════════════════════
# BACKBOARD HELPERS
# ═══════════════════════════════════════════════════════════
async def _create_assistant(name: str, system_prompt: str) -> str:
    """Create a Backboard Assistant and return its ID."""
    resp = await _client.post(
        f"{BASE_URL}/assistants",
        headers=HEADERS,
        json={"name": name, "system_prompt": system_prompt},
    )
    resp.raise_for_status()
    data = resp.json()
    assistant_id = data.get("assistant_id") or data.get("id")
    print(f"[backboard] Created assistant '{name}' → {assistant_id}")
    return assistant_id


async def _create_thread(assistant_id: str) -> str:
    """Create a Thread on an Assistant and return its ID."""
    resp = await _client.post(
        f"{BASE_URL}/assistants/{assistant_id}/threads",
        headers=HEADERS,
        json={},
    )
    resp.raise_for_status()
    data = resp.json()
    thread_id = data.get("thread_id") or data.get("id")
    print(f"[backboard] Created thread → {thread_id}")
    return thread_id


async def _send_message(thread_id: str, content: str) -> str:
    """Send a message to a Thread and return the assistant's response."""
    resp = await _client.post(
        f"{BASE_URL}/threads/{thread_id}/messages",
        headers=HEADERS,
        data={"content": content, "stream": "false"},
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("content", "")


# ═══════════════════════════════════════════════════════════
# AGENT 1: Startup Analyst
# ═══════════════════════════════════════════════════════════
STARTUP_ANALYST_PROMPT = """You are a senior startup analyst at a top-tier accelerator.
You specialize in extracting the core technical moat, market positioning,
and investment readiness from raw startup descriptions.
You always respond in valid JSON — no markdown, no commentary."""


async def analyze_startup(thread_id: str, startup: Dict[str, Any]) -> Dict[str, Any]:
    """Agent 1: Deep analysis of the startup's profile."""
    prompt = f"""Analyze this startup deeply and extract structured intelligence.

STARTUP DATA:
- Name: {startup.get('name', 'Unknown')}
- Sector: {startup.get('sector', 'Unknown')}
- Stage: {startup.get('stage', 'Unknown')}
- Description: {startup.get('description', '')}
- Tech Stack: {startup.get('tech_stack', [])}
- Location: {startup.get('location', 'Canada')}
- Funding Ask: {startup.get('funding_ask', 'Not specified')}

Return a JSON object with:
{{
    "core_value_prop": "one sentence — what makes this startup unique",
    "technical_moat": "what's defensible about the technology",
    "target_market": "who are the primary customers",
    "market_category": ["list", "of", "relevant", "investment", "categories"],
    "stage_signals": "what stage indicators are present",
    "risk_factors": ["top 3 risks an investor would see"],
    "ideal_investor_profile": "description of the perfect VC for this startup",
    "keywords": ["key", "terms", "for", "matching"]
}}

Return ONLY valid JSON."""

    raw = await _send_message(thread_id, prompt)
    result = _parse_json(raw)
    print(f"[Agent 1: Startup Analyst] Analyzed '{startup.get('name')}' — {len(result)} fields")
    return result


# ═══════════════════════════════════════════════════════════
# AGENT 2: VC Profiler
# ═══════════════════════════════════════════════════════════
VC_PROFILER_PROMPT = """You are a venture capital research analyst who has studied hundreds of VC funds.
You specialize in understanding investment theses, portfolio patterns,
and what types of startups each fund is really looking for beyond their stated mandate.
You always respond in valid JSON — no markdown, no commentary."""


async def profile_vc(thread_id: str, vc: Dict[str, Any]) -> Dict[str, Any]:
    """Agent 2: Analyze a VC's real investment thesis."""
    prompt = f"""Analyze this venture capital fund and infer their real investment thesis.
Use the startup analysis from earlier in this conversation for context.

VC DATA:
- Fund: {vc.get('fund_name', 'Unknown')}
- Stage: {vc.get('investment_stage', 'Unknown')}
- Mandate: {vc.get('sector_mandate', 'Unknown')}
- Check Size: {vc.get('check_size_min', '?')} - {vc.get('check_size_max', '?')} CAD
- Location: {vc.get('location', 'Canada')}
- Description: {vc.get('description', '')}

Return a JSON object with:
{{
    "real_thesis": "what they ACTUALLY look for beyond the stated mandate",
    "sweet_spot": "the ideal startup profile for this fund",
    "stage_preference": "nuanced view of their stage preference",
    "geographic_bias": "any geographic preferences",
    "value_add": "what they bring beyond money",
    "red_flags": ["things that would make them pass"],
    "keywords": ["key", "terms", "describing", "their", "focus"]
}}

Return ONLY valid JSON."""

    raw = await _send_message(thread_id, prompt)
    result = _parse_json(raw)
    print(f"[Agent 2: VC Profiler] Profiled '{vc.get('fund_name')}'")
    return result


# ═══════════════════════════════════════════════════════════
# AGENT 3: Match Reasoner
# ═══════════════════════════════════════════════════════════
MATCH_REASONER_PROMPT = """You are the chief investment officer at a fund-of-funds.
You specialize in evaluating startup-VC fit with brutal honesty.
You consider sector alignment, stage fit, geographic proximity,
check size compatibility, and strategic value-add.
You always respond in valid JSON — no markdown, no commentary."""


async def reason_match(
    thread_id: str,
    vc_raw: Dict[str, Any],
) -> Dict[str, Any]:
    """Agent 3: Produce a detailed, reasoned match evaluation.

    NOTE: This agent leverages the SHARED THREAD MEMORY — it can see
    the startup analysis from Agent 1 and the VC profile from Agent 2,
    enabling truly contextual reasoning about the match.
    """
    prompt = f"""Based on the startup analysis and VC profile analysis earlier in this conversation,
evaluate whether the startup is a good match for {vc_raw.get('fund_name')}.

Produce a detailed match evaluation. Return JSON:
{{
    "match_score": <0-100 integer>,
    "confidence": "<high/medium/low>",
    "verdict": "<strong match / good match / weak match / poor match>",
    "reasoning": "2-3 sentence explanation of WHY this is or isn't a good match",
    "sector_fit": {{
        "score": <0-100>,
        "explanation": "one sentence"
    }},
    "stage_fit": {{
        "score": <0-100>,
        "explanation": "one sentence"
    }},
    "strategic_value": {{
        "score": <0-100>,
        "explanation": "one sentence — what value-add does the VC bring"
    }},
    "risks": ["top 2 risks for this specific pairing"],
    "suggested_approach": "one sentence — how the founder should approach this VC"
}}

Be brutally honest. Return ONLY valid JSON."""

    raw = await _send_message(thread_id, prompt)
    result = _parse_json(raw)
    result["fund_name"] = vc_raw.get("fund_name")
    result["fund_website"] = vc_raw.get("website")
    result["fund_location"] = vc_raw.get("location")
    print(f"[Agent 3: Match Reasoner] {vc_raw.get('fund_name')}: {result.get('verdict', '?')} ({result.get('match_score', '?')}/100)")
    return result


# ═══════════════════════════════════════════════════════════
# ORCHESTRATOR: Multi-Agent Pipeline
# ═══════════════════════════════════════════════════════════
async def run_agentic_matching(
    startup: Dict[str, Any],
    vc_database: List[Dict[str, Any]],
    top_n: int = 5,
    pre_filter_n: int = 10,
) -> Dict[str, Any]:
    """Run the full multi-agent matching pipeline via Backboard.io.

    Key architectural feature: All agents share a SINGLE THREAD,
    which means each agent can reference the work of previous agents.
    The VC Profiler sees the Startup Analyst's output, and the
    Match Reasoner sees both. This is true multi-agent collaboration.

    Steps:
      1. Pre-filter VCs using fast algorithmic scoring
      2. Create 3 Backboard Assistants (agents)
      3. Create a shared Thread for cross-agent memory
      4. Agent 1: Analyze the startup
      5. Agent 2: Profile each candidate VC (with startup context)
      6. Agent 3: Reason about each match (with full context)
      7. Return ranked results with detailed justifications
    """
    print(f"\n{'='*60}")
    print(f"BACKBOARD.IO AGENTIC MATCHING PIPELINE")
    print(f"Startup: {startup.get('name', 'Unknown')}")
    print(f"{'='*60}")

    # ── Step 1: Pre-filter ──────────────────────────────────
    print("\n[Step 1] Pre-filtering with fast algorithmic scorer...")
    candidates = get_top_matches(startup, vc_database, top_n=pre_filter_n)
    print(f"  → Narrowed {len(vc_database)} VCs to {len(candidates)} candidates")

    # ── Step 2: Create Backboard Agents ─────────────────────
    print("\n[Step 2] Creating Backboard.io Agents...")
    analyst_id = await _create_assistant("Startup Analyst", STARTUP_ANALYST_PROMPT)
    profiler_id = await _create_assistant("VC Profiler", VC_PROFILER_PROMPT)
    reasoner_id = await _create_assistant("Match Reasoner", MATCH_REASONER_PROMPT)

    # ── Step 3: Create shared thread ────────────────────────
    # Using the analyst's thread — all messages go here for shared context
    print("\n[Step 3] Creating shared Thread for cross-agent memory...")
    thread_id = await _create_thread(analyst_id)

    # ── Step 4: Agent 1 — Startup Analysis ──────────────────
    print("\n[Step 4] Agent 1: Analyzing startup...")
    startup_analysis = await analyze_startup(thread_id, startup)

    # ── Step 5: Agent 2 — VC Profiling ──────────────────────
    print(f"\n[Step 5] Agent 2: Profiling {len(candidates)} VC candidates...")
    vc_profiles = []
    for vc in candidates:
        profile = await profile_vc(thread_id, vc)
        vc_profiles.append(profile)

    # ── Step 6: Agent 3 — Match Reasoning ───────────────────
    print(f"\n[Step 6] Agent 3: Reasoning about {len(candidates)} matches...")
    match_results = []
    for vc in candidates:
        match = await reason_match(thread_id, vc)
        match_results.append(match)

    # ── Step 7: Rank and return ─────────────────────────────
    match_results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    final_matches = match_results[:top_n]

    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE — Top {len(final_matches)} matches:")
    for m in final_matches:
        print(f"  {m.get('match_score', '?')}/100 — {m.get('fund_name')} ({m.get('verdict', '?')})")
    print(f"{'='*60}\n")

    return {
        "startup_analysis": startup_analysis,
        "pipeline": {
            "provider": "backboard.io",
            "pre_filter_candidates": len(candidates),
            "agents_used": [
                {"name": "Startup Analyst", "id": analyst_id},
                {"name": "VC Profiler", "id": profiler_id},
                {"name": "Match Reasoner", "id": reasoner_id},
            ],
            "shared_thread_id": thread_id,
            "total_llm_calls": 1 + len(candidates) + len(candidates),
            "architecture": "shared-memory multi-agent orchestration",
        },
        "matches": final_matches,
    }
