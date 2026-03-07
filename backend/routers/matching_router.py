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


@router.post("/agentic")
async def match_startup_agentic(
    profile: StartupProfile,
    top_n: int = 5,
    user: dict = Depends(get_current_user),
):
    """Agentic AI matching — runs a multi-agent pipeline with Gemini.

    Uses 3 specialized AI agents:
    1. Startup Analyst — deep analysis of the startup
    2. VC Profiler — analyzes each candidate VC's real thesis
    3. Match Reasoner — produces detailed match justifications

    Note: This takes 30-90 seconds due to multiple Gemini API calls.
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

