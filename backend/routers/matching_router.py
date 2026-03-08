"""Matching API routes — match a startup profile to the best VCs."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List, Optional

from auth.auth0 import get_current_user
from matching.matcher import get_top_matches
from matching.agentic_matcher import run_agentic_matching
from scraper.scraper import load_vc_database

router = APIRouter()


class StartupProfile(BaseModel):
    """Startup profile submitted for matching."""

    name: str = Field("My Startup", examples=["My Startup"])
    sector: str = Field("AI", examples=["AI", "fintech", "healthtech", "cleantech"])
    stage: str = Field("seed", examples=["pre-seed", "seed", "series-a"])
    description: str = Field(
        "An AI-powered platform for automating business workflows",
        examples=["An AI-powered platform for automating business workflows"],
    )
    tech_stack: Optional[List[str]] = Field(
        default=[], examples=[["python", "react", "gemini"]]
    )
    location: Optional[str] = Field(default="Canada", examples=["Toronto, Ontario"])
    funding_ask: Optional[float] = Field(default=None, examples=[500000])


@router.post("/")
async def match_startup(
    profile: StartupProfile,
    top_n: int = 10,
    user: dict = Depends(get_current_user),
):
    """Fast algorithmic matching — returns top-N VCs using weighted scoring."""
    vc_database = load_vc_database()
    matches = get_top_matches(profile.model_dump(), vc_database, top_n=top_n)
    return {"mode": "fast", "matches": matches}


@router.post("/smart")
async def match_startup_smart(
    profile: StartupProfile,
    top_n: int = 5,
    user: dict = Depends(get_current_user),
):
    """Smart hybrid matching — fast pre-filter + single AI reasoning call.

    Much faster than full agentic (10-15s vs 60-90s) while still providing
    AI-powered reasoning and verdicts for the top results.
    """
    import json, re, httpx
    from config import settings

    vc_database = load_vc_database()
    # Step 1: Fast pre-filter (instant)
    candidates = get_top_matches(profile.model_dump(), vc_database, top_n=top_n)

    # Step 2: Single AI call to reason about all candidates at once
    startup_desc = (
        f"Name: {profile.name}, Sector: {profile.sector}, Stage: {profile.stage}, "
        f"Description: {profile.description}, Location: {profile.location}, "
        f"Funding Ask: {profile.funding_ask or 'Not specified'}"
    )
    vc_summaries = "\n".join(
        f"- {c.get('fund_name','?')}: mandate={c.get('sector_mandate','?')}, "
        f"stage={c.get('investment_stage','?')}, "
        f"check={c.get('check_size_min','?')}-{c.get('check_size_max','?')} CAD, "
        f"location={c.get('location','?')}"
        for c in candidates
    )

    prompt = f"""You are a senior VC matching analyst. Evaluate how well this startup matches each VC fund.

STARTUP: {startup_desc}

CANDIDATE VCS:
{vc_summaries}

For each VC, return a JSON array with objects containing:
- "fund_name": exact fund name
- "match_score": 0-100 integer (be honest — gibberish or bad fits should get <30)
- "verdict": "strong match" / "good match" / "weak match" / "poor match"
- "confidence": "high" / "medium" / "low"
- "reasoning": 2-3 sentence explanation
- "suggested_approach": 1 sentence on how to approach this VC

Return ONLY a valid JSON array, no markdown."""

    try:
        from backboard import BackboardClient
        client = BackboardClient(api_key=settings.BACKBOARD_API_KEY)
        assistant = await client.create_assistant(
            name="Match Analyst",
            system_prompt="You evaluate startup-VC fit with brutal honesty. Always respond in valid JSON."
        )
        thread = await client.create_thread(assistant.assistant_id)
        response = await client.add_message(
            thread_id=thread.thread_id,
            content=prompt,
            stream=False,
        )
        raw = response.content.strip()
        # Parse JSON
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        ai_results = json.loads(cleaned)

        # Merge AI reasoning into candidates
        ai_by_name = {r.get("fund_name", "").lower(): r for r in ai_results}
        for c in candidates:
            ai = ai_by_name.get(c.get("fund_name", "").lower(), {})
            c["match_score"] = ai.get("match_score", c.get("match_score", 50))
            c["verdict"] = ai.get("verdict", "")
            c["confidence"] = ai.get("confidence", "")
            c["reasoning"] = ai.get("reasoning", "")
            c["suggested_approach"] = ai.get("suggested_approach", "")

        candidates.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    except Exception as exc:
        # If AI call fails, fall back to fast scores with no reasoning
        import logging
        logging.warning("Smart match AI call failed, using fast scores: %s", exc)
        for c in candidates:
            c["verdict"] = ""
            c["reasoning"] = "AI reasoning unavailable — showing algorithmic score."

    return {"mode": "smart", "matches": candidates[:top_n]}


@router.post("/agentic")
async def match_startup_agentic(
    profile: StartupProfile,
    top_n: int = 5,
    user: dict = Depends(get_current_user),
):
    """Agentic AI matching — runs a multi-agent pipeline with Backboard.io.

    Uses 3 specialized AI agents:
    1. Startup Analyst — deep analysis of the startup
    2. VC Profiler — analyzes each candidate VC's real thesis
    3. Match Reasoner — produces detailed match justifications

    Note: This takes 30-90 seconds due to multiple LLM calls.
    """
    vc_database = load_vc_database()
    result = await run_agentic_matching(
        profile.model_dump(), vc_database, top_n=top_n
    )
    return {"mode": "agentic", **result}


@router.get("/demo")
async def match_demo(user: dict = Depends(get_current_user)):
    """Quick demo — fast-matches a sample AI startup to the VC database."""
    sample = {
        "name": "Demo AI Startup",
        "sector": "AI",
        "stage": "seed",
        "description": "AI-powered analytics platform",
        "tech_stack": ["python", "tensorflow"],
        "location": "Toronto, Ontario",
        "funding_ask": 500000,
    }
    vc_database = load_vc_database()
    matches = get_top_matches(sample, vc_database, top_n=10)
    return {"mode": "fast", "startup": sample, "matches": matches}


@router.get("/agentic/demo")
async def match_demo_agentic(user: dict = Depends(get_current_user)):
    """Agentic demo — runs the full multi-agent pipeline on a sample startup.

    Takes 30-90 seconds. Watch the server logs to see each agent working.
    """
    sample = {
        "name": "NeuralMed",
        "sector": "healthtech",
        "stage": "seed",
        "description": (
            "NeuralMed uses transformer-based models to analyze medical imaging data, "
            "detecting early-stage cancers with 94% accuracy. Our proprietary dataset "
            "of 2M annotated scans gives us a defensible data moat."
        ),
        "tech_stack": ["python", "pytorch", "FHIR", "AWS"],
        "location": "Toronto, Ontario",
        "funding_ask": 1500000,
    }
    vc_database = load_vc_database()
    result = await run_agentic_matching(sample, vc_database, top_n=3, pre_filter_n=3)
    return {"mode": "agentic", "startup": sample, **result}

