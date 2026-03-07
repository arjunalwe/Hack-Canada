"""Generation API routes — AI-powered email, pitch, and summary generation."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from auth.auth0 import get_current_user
from generation.generator import generate_cold_email, generate_elevator_pitch, generate_exec_summary

router = APIRouter()


class EmailRequest(BaseModel):
    """Request to generate a cold outreach email."""
    startup_name: str
    startup_description: str
    startup_sector: str
    vc_name: str
    vc_mandate: str
    vc_contact: Optional[str] = ""
    tone: Optional[str] = "professional"


class PitchRequest(BaseModel):
    """Request to generate an elevator pitch."""
    startup_name: str
    startup_description: str
    startup_sector: str
    tech_stack: Optional[str] = ""
    target_market: Optional[str] = ""
    funding_ask: Optional[str] = ""


class SummaryRequest(BaseModel):
    """Request to generate an executive summary."""
    startup_name: str
    startup_description: str
    startup_sector: str
    tech_stack: Optional[str] = ""
    target_market: Optional[str] = ""
    traction: Optional[str] = ""
    team: Optional[str] = ""


@router.post("/email")
async def create_email(req: EmailRequest, user: dict = Depends(get_current_user)):
    """Generate a personalized cold outreach email."""
    email = await generate_cold_email(req.model_dump())
    return {"email": email}


@router.post("/pitch")
async def create_pitch(req: PitchRequest, user: dict = Depends(get_current_user)):
    """Generate a 60-second elevator pitch."""
    pitch = await generate_elevator_pitch(req.model_dump())
    return {"pitch": pitch}


@router.post("/summary")
async def create_summary(req: SummaryRequest, user: dict = Depends(get_current_user)):
    """Generate a one-page executive summary."""
    summary = await generate_exec_summary(req.model_dump())
    return {"summary": summary}
