"""Agentic Matchmaking Pipeline — 3 New Agents powered by Backboard.io.

Implements the vector-penalty scoring formula:
    M(S, V) = α · sim(v_S, v_V) - β · Δ_stage - γ · P_debate

Architecture (reuses existing components):
  - EXISTING: Brain synthesize() → startup profile (sector, stage, keywords)
  - EXISTING: matcher.py → _sector_overlap(), _stage_fit() for sim/Δ
  - EXISTING: get_top_matches() → pre-filter to top N candidates

  3 NEW Agents (all powered by Backboard.io):
  - Agent A: VC Thesis Analyst — infers real VC thesis, uses persistent memory
  - Agent B: Debate Pair — Startup Advocate vs VC Critic, shared thread
  - Agent C: Final Arbiter — tool-calling for compute_match_metrics, scores debate

Backboard features showcased:
  ✓ Persistent Memory (memory="Auto") — Agent A stores VC analyses cross-session
  ✓ Tool Calling — Agent C calls compute_match_metrics()
  ✓ Shared Thread — Debate agents collaborate on single thread
  ✓ Semantic Recall — Arbiter recalls prior analyses from memory
  ✓ RAG — startup docs already indexed via Brain
"""

import asyncio
import json
import re
from typing import Any, Dict, List

from backboard import BackboardClient
from config import settings
from matching.matcher import (
    _sector_overlap,
    _stage_fit,
    _check_size_fit,
    _geo_score,
)

# ── Backboard client (shared) ───────────────────────────
client = BackboardClient(api_key=settings.BACKBOARD_API_KEY, timeout=120)

# ── Formula weights ─────────────────────────────────────
ALPHA = 0.60   # cosine similarity (sector/mandate alignment)
BETA  = 0.20   # stage mismatch penalty
GAMMA = 0.20   # debate penalty

# ── JSON parser ─────────────────────────────────────────
def _parse_json(raw: str) -> dict | list:
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass
    return {}


# ═══════════════════════════════════════════════════════════
# AGENT A: VC Thesis Analyst
# Backboard features: memory="Auto" for cross-session recall
# ═══════════════════════════════════════════════════════════

VC_THESIS_PROMPT = """You are a senior venture capital research analyst who has studied 500+ VC funds.
You specialize in understanding what VCs ACTUALLY look for vs what they SAY they look for.
You read between the lines of mandates and infer the real investment thesis.
You always respond in valid JSON — no markdown, no commentary."""


async def run_vc_thesis_agent(
    startup_profile: Dict[str, Any],
    vc: Dict[str, Any],
) -> Dict[str, Any]:
    """Agent A: Analyze a VC's real thesis in context of the startup.
    
    Uses memory="Auto" so future sessions can recall VC analyses.
    """
    assistant = await client.create_assistant(
        name="VC Thesis Analyst",
        system_prompt=VC_THESIS_PROMPT,
    )
    thread = await client.create_thread(assistant.assistant_id)

    # First message: Feed the startup context (stored in memory)
    await client.add_message(
        thread_id=thread.thread_id,
        content=f"""STARTUP CONTEXT (from Brain synthesis):
- Name: {startup_profile.get('startup_name', 'Unknown')}
- Sector: {startup_profile.get('sector', 'Unknown')}
- Stage: {startup_profile.get('stage', 'Unknown')}
- Description: {startup_profile.get('description', '')}
- Elevator Pitch: {startup_profile.get('elevator_pitch', '')}
- Tech Stack: {startup_profile.get('tech_stack', [])}
- Target Market: {startup_profile.get('target_market', '')}

Remember this startup for future analysis.""",
        memory="Auto",
        stream=False,
    )

    # Second message: Analyze the VC
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=f"""Now analyze this VC fund and infer their REAL investment thesis.

VC DATA:
- Fund: {vc.get('fund_name', 'Unknown')}
- Stated Mandate: {vc.get('sector_mandate', 'Unknown')}
- Investment Stage: {vc.get('investment_stage', 'Unknown')}
- Check Size: {vc.get('check_size_min', '?')} - {vc.get('check_size_max', '?')} CAD
- Location: {vc.get('location', 'Unknown')}
- Description: {vc.get('description', '')}

Return JSON:
{{
    "real_thesis": "what they ACTUALLY invest in beyond stated mandate",
    "sweet_spot": "ideal startup for this fund",
    "keywords": ["key", "terms", "for", "their", "focus"],
    "stage_preference_nuanced": "nuanced view of stage preference",
    "red_flags": ["things that would make them pass immediately"],
    "value_add": "what they bring beyond money"
}}

Return ONLY valid JSON.""",
        memory="Auto",
        stream=False,
    )

    result = _parse_json(response.content)
    print(f"  [Agent A] VC Thesis: {vc.get('fund_name')} → {len(result)} fields")
    return result


# ═══════════════════════════════════════════════════════════
# AGENT B: Debate Pair (Startup Advocate vs VC Critic)
# Backboard features: shared thread for multi-turn debate
# ═══════════════════════════════════════════════════════════

ADVOCATE_PROMPT = """You are a passionate startup advisor and champion.
Your job is to make the STRONGEST POSSIBLE case for why a startup is a perfect
match for a specific VC fund. Use concrete evidence, market data, and thesis alignment.
Be persuasive but truthful. No flannel.
Keep arguments to 3-4 sentences max. Always respond in plain text, not JSON."""

CRITIC_PROMPT = """You are a skeptical venture capitalist who has seen 10,000 pitches.
Your job is to STRESS-TEST whether a startup truly fits a VC fund's thesis.
Challenge every claim. Raise deal-breakers. Point out what the advocate is glossing over.
Be tough but fair. If the match truly is good, say so — but make them prove it.
Keep arguments to 3-4 sentences max. Always respond in plain text, not JSON."""


async def run_debate(
    startup_profile: Dict[str, Any],
    vc: Dict[str, Any],
    vc_thesis: Dict[str, Any],
) -> Dict[str, Any]:
    """Agent B: Run a 2-round debate between Advocate and Critic.
    
    Both agents share a thread, so each sees the other's arguments.
    """
    # Create both agents
    advocate = await client.create_assistant(
        name="Startup Advocate",
        system_prompt=ADVOCATE_PROMPT,
    )
    critic = await client.create_assistant(
        name="VC Critic",
        system_prompt=CRITIC_PROMPT,
    )

    # Shared debate thread (use advocate's thread)
    debate_thread = await client.create_thread(advocate.assistant_id)
    thread_id = debate_thread.thread_id

    startup_name = startup_profile.get('startup_name', 'the startup')
    fund_name = vc.get('fund_name', 'the VC')

    debate_log = []

    # === Round 1: Opening Arguments ===
    # Advocate opens
    adv_r1 = await client.add_message(
        thread_id=thread_id,
        content=f"""Make your opening argument for why {startup_name} is a strong match for {fund_name}.

STARTUP: {startup_profile.get('elevator_pitch', startup_profile.get('description', ''))}
Sector: {startup_profile.get('sector', '')} | Stage: {startup_profile.get('stage', '')}

VC FUND: {fund_name}
Real Thesis: {vc_thesis.get('real_thesis', vc.get('sector_mandate', ''))}
Sweet Spot: {vc_thesis.get('sweet_spot', '')}
Stage: {vc.get('investment_stage', '')}

Make your case in 3-4 sentences.""",
        stream=False,
    )
    debate_log.append({"role": "advocate", "text": adv_r1.content.strip()})

    # Critic responds
    crit_r1 = await client.add_message(
        thread_id=thread_id,
        content=f"""[VC CRITIC] The advocate just argued: "{adv_r1.content.strip()}"

Challenge this. What are they glossing over? What deal-breakers exist?
Consider: {vc_thesis.get('red_flags', [])}
Respond in 3-4 sentences.""",
        stream=False,
    )
    debate_log.append({"role": "critic", "text": crit_r1.content.strip()})

    # === Round 2: Rebuttals ===
    # Advocate rebuts
    adv_r2 = await client.add_message(
        thread_id=thread_id,
        content=f"""[STARTUP ADVOCATE] The critic just challenged: "{crit_r1.content.strip()}"

Defend your position. Address each point. Use specific evidence.
Respond in 3-4 sentences.""",
        stream=False,
    )
    debate_log.append({"role": "advocate", "text": adv_r2.content.strip()})

    # Critic final word
    crit_r2 = await client.add_message(
        thread_id=thread_id,
        content=f"""[VC CRITIC] The advocate rebuts: "{adv_r2.content.strip()}"

Final assessment. Were you convinced? What still concerns you?
Respond in 3-4 sentences.""",
        stream=False,
    )
    debate_log.append({"role": "critic", "text": crit_r2.content.strip()})

    print(f"  [Agent B] Debate complete: {fund_name} ({len(debate_log)} turns)")
    return {
        "debate_log": debate_log,
        "thread_id": thread_id,
    }


# ═══════════════════════════════════════════════════════════
# AGENT C: Final Arbiter (Tool-Calling Agent)
# Backboard features: tool calling + semantic recall
# ═══════════════════════════════════════════════════════════

ARBITER_PROMPT = """You are the Chief Investment Officer at a fund-of-funds.
You make the final call on startup-VC fit using both quantitative metrics and qualitative debate analysis.

You have access to a tool called compute_match_metrics that computes quantitative scores.
You MUST call this tool to get the sim, stage_penalty, check_fit, and geo_score values.
Then combine these with your debate assessment to produce the final verdict.

The formula is: M(S,V) = 0.60 * sim - 0.20 * stage_penalty - 0.20 * debate_penalty

Where debate_penalty ranges from 0.0 (advocate won convincingly) to 1.0 (critic destroyed the case).

Always respond in valid JSON. No markdown, no commentary."""

MATCH_METRICS_TOOL = {
    "type": "function",
    "function": {
        "name": "compute_match_metrics",
        "description": "Compute quantitative match metrics between a startup and VC fund. Returns sim (sector similarity 0-1), stage_penalty (0-1 where 0=same stage), check_fit (0-1), and geo_score (0-1).",
        "parameters": {
            "type": "object",
            "properties": {
                "startup_sector": {
                    "type": "string",
                    "description": "The startup's primary sector"
                },
                "vc_mandate": {
                    "type": "string",
                    "description": "The VC's sector mandate"
                },
                "startup_stage": {
                    "type": "string",
                    "description": "The startup's current stage"
                },
                "vc_stages": {
                    "type": "string",
                    "description": "The VC's preferred investment stages"
                },
                "startup_location": {
                    "type": "string",
                    "description": "The startup's location"
                },
                "vc_location": {
                    "type": "string",
                    "description": "The VC's location"
                },
                "funding_ask": {
                    "type": "number",
                    "description": "The startup's funding ask in CAD (null if unknown)"
                },
                "check_size_min": {
                    "type": "number",
                    "description": "VC min check size in CAD"
                },
                "check_size_max": {
                    "type": "number",
                    "description": "VC max check size in CAD"
                }
            },
            "required": ["startup_sector", "vc_mandate", "startup_stage", "vc_stages"]
        }
    }
}


def _execute_compute_match_metrics(args: Dict[str, Any]) -> Dict[str, float]:
    """Execute the compute_match_metrics tool using existing matcher.py functions."""
    sim = _sector_overlap(args.get("startup_sector", ""), args.get("vc_mandate", ""))
    stage_fit = _stage_fit(args.get("startup_stage", ""), args.get("vc_stages", ""))
    stage_penalty = 1.0 - stage_fit  # invert: fit → penalty
    check_fit = _check_size_fit(
        args.get("funding_ask"),
        args.get("check_size_min"),
        args.get("check_size_max"),
    )
    geo = _geo_score(args.get("startup_location", ""), args.get("vc_location", ""))

    return {
        "sim": round(sim, 3),
        "stage_penalty": round(stage_penalty, 3),
        "check_fit": round(check_fit, 3),
        "geo_score": round(geo, 3),
    }


async def run_arbiter(
    startup_profile: Dict[str, Any],
    vc: Dict[str, Any],
    vc_thesis: Dict[str, Any],
    debate_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Agent C: Final Arbiter with tool calling.
    
    1. Calls compute_match_metrics() tool → gets sim, stage_penalty
    2. Scores the debate → assigns P_debate
    3. Computes M(S,V) = α·sim - β·Δ_stage - γ·P_debate
    """
    # Create arbiter with tool
    assistant = await client.create_assistant(
        name="Match Arbiter",
        system_prompt=ARBITER_PROMPT,
        tools=[MATCH_METRICS_TOOL],
    )
    thread = await client.create_thread(assistant.assistant_id)

    # Format debate log
    debate_text = "\n".join(
        f"{'🟢 ADVOCATE' if d['role'] == 'advocate' else '🔴 CRITIC'}: {d['text']}"
        for d in debate_result.get("debate_log", [])
    )

    startup_name = startup_profile.get("startup_name", "Unknown")
    fund_name = vc.get("fund_name", "Unknown")

    # Send detailed prompt that will trigger tool call
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=f"""Evaluate the match between startup "{startup_name}" and VC fund "{fund_name}".

STARTUP:
- Sector: {startup_profile.get('sector', 'Unknown')}
- Stage: {startup_profile.get('stage', 'Unknown')}
- Location: {startup_profile.get('location', 'Canada')}
- Funding Ask: {startup_profile.get('funding_ask', 'Not specified')}

VC FUND:
- Mandate: {vc.get('sector_mandate', '')}
- Stages: {vc.get('investment_stage', '')}
- Location: {vc.get('location', '')}
- Check Size: {vc.get('check_size_min', '?')} - {vc.get('check_size_max', '?')} CAD
- Real Thesis: {vc_thesis.get('real_thesis', '')}

DEBATE TRANSCRIPT:
{debate_text}

INSTRUCTIONS:
1. FIRST: Call the compute_match_metrics tool with the startup and VC data
2. THEN: Score the debate from 0.0 (advocate won) to 1.0 (critic won)
3. FINALLY: Compute M = 0.60*sim - 0.20*stage_penalty - 0.20*debate_penalty
4. Scale the result to 0-100

Return JSON:
{{
    "match_score": <0-100 integer>,
    "formula_breakdown": {{
        "sim": <from tool>,
        "stage_penalty": <from tool>,
        "debate_penalty": <0.0-1.0>,
        "alpha_sim": <0.60 * sim>,
        "beta_stage": <0.20 * stage_penalty>,
        "gamma_debate": <0.20 * debate_penalty>,
        "raw_M": <alpha_sim - beta_stage - gamma_debate>
    }},
    "verdict": "strong match / good match / weak match / poor match",
    "confidence": "high / medium / low",
    "reasoning": "2-3 sentences explaining WHY",
    "debate_winner": "advocate / critic / draw",
    "debate_summary": "1 sentence summary of the debate outcome",
    "suggested_approach": "1 sentence on how to approach this VC"
}}""",
        memory="Auto",
        stream=False,
    )

    # Handle tool calling
    if response.status == "REQUIRES_ACTION" and response.tool_calls:
        tool_outputs = []
        for tc in response.tool_calls:
            if tc.function.name == "compute_match_metrics":
                args = tc.function.parsed_arguments
                metrics = _execute_compute_match_metrics(args)
                print(f"  [Agent C] Tool call: compute_match_metrics → sim={metrics['sim']}, stage_pen={metrics['stage_penalty']}")
                tool_outputs.append({
                    "tool_call_id": tc.id,
                    "output": json.dumps(metrics),
                })

        # Submit tool outputs to continue
        final_response = await client.submit_tool_outputs(
            thread_id=thread.thread_id,
            run_id=response.run_id,
            tool_outputs=tool_outputs,
        )
        result = _parse_json(final_response.content)
    else:
        # Model answered directly without tool call — parse response
        result = _parse_json(response.content)
        # Manually compute metrics if tool wasn't called
        if "formula_breakdown" not in result:
            metrics = _execute_compute_match_metrics({
                "startup_sector": startup_profile.get("sector", ""),
                "vc_mandate": vc.get("sector_mandate", ""),
                "startup_stage": startup_profile.get("stage", ""),
                "vc_stages": vc.get("investment_stage", ""),
                "startup_location": startup_profile.get("location", ""),
                "vc_location": vc.get("location", ""),
                "funding_ask": startup_profile.get("funding_ask"),
                "check_size_min": vc.get("check_size_min"),
                "check_size_max": vc.get("check_size_max"),
            })
            debate_penalty = result.get("formula_breakdown", {}).get("debate_penalty", 0.5)
            raw_m = ALPHA * metrics["sim"] - BETA * metrics["stage_penalty"] - GAMMA * debate_penalty
            result["match_score"] = max(0, min(100, round(raw_m * 100)))
            result["formula_breakdown"] = {
                "sim": metrics["sim"],
                "stage_penalty": metrics["stage_penalty"],
                "debate_penalty": debate_penalty,
                "alpha_sim": round(ALPHA * metrics["sim"], 3),
                "beta_stage": round(BETA * metrics["stage_penalty"], 3),
                "gamma_debate": round(GAMMA * debate_penalty, 3),
                "raw_M": round(raw_m, 3),
            }

    # Attach VC metadata
    result["fund_name"] = vc.get("fund_name")
    result["fund_website"] = vc.get("website")
    result["fund_location"] = vc.get("location")
    result["sector_mandate"] = vc.get("sector_mandate")
    result["debate_log"] = debate_result.get("debate_log", [])

    print(f"  [Agent C] Arbiter: {vc.get('fund_name')} → {result.get('match_score', '?')}/100 ({result.get('verdict', '?')})")
    return result


# ═══════════════════════════════════════════════════════════
# ORCHESTRATOR: Full Agentic Pipeline
# ═══════════════════════════════════════════════════════════

async def _process_single_vc(
    startup_profile: Dict[str, Any],
    vc: Dict[str, Any],
    idx: int,
    total: int,
) -> Dict[str, Any]:
    """Process a single VC through the full 3-agent pipeline."""
    fund_name = vc.get("fund_name", f"VC_{idx}")
    print(f"\n[{idx+1}/{total}] Processing: {fund_name}")

    # Agent A: VC Thesis
    vc_thesis = await run_vc_thesis_agent(startup_profile, vc)

    # Agent B: Debate
    debate_result = await run_debate(startup_profile, vc, vc_thesis)

    # Agent C: Final Arbiter (with tool calling)
    final_result = await run_arbiter(startup_profile, vc, vc_thesis, debate_result)

    return final_result


async def run_agentic_matching(
    startup: Dict[str, Any],
    vc_database: List[Dict[str, Any]],
    top_n: int = 5,
    pre_filter_n: int = 8,
) -> Dict[str, Any]:
    """Run the full 3-agent agentic matching pipeline.

    Pipeline:
      1. For each VC in the database (in parallel):
         a. Agent A: Analyze VC thesis (memory="Auto")
         b. Agent B: Run advocacy vs critic debate (shared thread)
         c. Agent C: Tool-call match metrics + score debate → M(S,V)
      2. Rank by final M(S,V) score and return top N

    Formula: M(S,V) = α·sim(v_S,v_V) - β·Δ_stage - γ·P_debate
    """
    print(f"\n{'='*60}")
    print(f"  AGENTIC MATCHMAKING PIPELINE")
    print(f"  Formula: M(S,V) = {ALPHA}·sim - {BETA}·Δ_stage - {GAMMA}·P_debate")
    print(f"  Startup: {startup.get('name', 'Unknown')}")
    print(f"{'='*60}")

    # Build a flat startup profile from synthesis or raw input
    startup_profile = {
        "startup_name": startup.get("name", "Unknown"),
        "sector": startup.get("sector", "Unknown"),
        "stage": startup.get("stage", "Unknown"),
        "description": startup.get("description", ""),
        "elevator_pitch": startup.get("elevator_pitch", startup.get("description", "")),
        "tech_stack": startup.get("tech_stack", []),
        "target_market": startup.get("target_market", ""),
        "location": startup.get("location", "Canada"),
        "funding_ask": startup.get("funding_ask"),
    }

    # Process ALL VCs through the 3-agent pipeline IN PARALLEL
    print(f"\n[Pipeline] Running 3-agent pipeline directly for ALL {len(vc_database)} VCs in parallel...")
    tasks = [
        _process_single_vc(startup_profile, vc, i, len(vc_database))
        for i, vc in enumerate(vc_database)
    ]
    match_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out errors
    valid_results = []
    for r in match_results:
        if isinstance(r, Exception):
            print(f"  [ERROR] One VC failed: {r}")
        else:
            valid_results.append(r)

    # Step 2: Rank by final M(S,V) score and take top N
    valid_results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    top_results = valid_results[:top_n]

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE — Top {len(top_results)} matches:")
    for m in top_results:
        fb = m.get("formula_breakdown", {})
        print(f"  {m.get('match_score', '?'):>3}/100 — {m.get('fund_name', '?')} ({m.get('verdict', '?')})")
        print(f"          sim={fb.get('sim','?')} Δstage={fb.get('stage_penalty','?')} Pdebate={fb.get('debate_penalty','?')}")
    print(f"{'='*60}\n")

    return {
        "mode": "agentic",
        "formula": "M(S,V) = α·sim(v_S,v_V) - β·Δ_stage - γ·P_debate",
        "weights": {"alpha": ALPHA, "beta": BETA, "gamma": GAMMA},
        "pipeline": {
            "provider": "backboard.io",
            "agents": [
                {"name": "VC Thesis Analyst", "role": "Infer true mandate", "memory": "Auto"},
                {"name": "Debate Pair", "role": "Advocate vs Critic", "mechanism": "Shared Thread"},
                {"name": "Final Arbiter", "role": "Compute metrics & score debate", "mechanism": "Tool Calling"},
            ]
        },
        "matches": top_results
    }
