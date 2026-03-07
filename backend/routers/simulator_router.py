"""VC Simulator API routes — adversarial pitch practice with AI audio."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from auth.auth0 import get_current_user
from simulator.vc_persona import generate_vc_question, stream_audio_response, evaluate_response

router = APIRouter()


class QuestionRequest(BaseModel):
    """Request for an adversarial VC question."""
    vc_name: str
    vc_mandate: str
    vc_style: Optional[str] = "aggressive"
    startup_pitch: str


class EvaluateRequest(BaseModel):
    """Request to evaluate a founder's response."""
    vc_question: str
    founder_response: str
    startup_context: str


@router.post("/question")
async def get_vc_question(req: QuestionRequest, user: dict = Depends(get_current_user)):
    """Generate a tough VC question based on the pitch and investor profile."""
    question_text = await generate_vc_question(req.model_dump())
    return {"question": question_text}


@router.post("/question/audio")
async def get_vc_question_audio(req: QuestionRequest, user: dict = Depends(get_current_user)):
    """Generate a VC question and stream it as audio via ElevenLabs."""
    question_text = await generate_vc_question(req.model_dump())
    audio_stream = await stream_audio_response(question_text)
    return StreamingResponse(audio_stream, media_type="audio/mpeg", headers={
        "X-Question-Text": question_text[:200],  # also send text in header
    })


@router.post("/evaluate")
async def evaluate_pitch_response(req: EvaluateRequest, user: dict = Depends(get_current_user)):
    """Evaluate the founder's response to the VC question."""
    evaluation = await evaluate_response(req.model_dump())
    return {"evaluation": evaluation}
