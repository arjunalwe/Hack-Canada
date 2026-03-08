"""VC Simulator API routes — adversarial pitch practice with AI audio."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

from auth.auth0 import get_current_user
from simulator.vc_persona import generate_vc_question, stream_audio_response, evaluate_response
from simulator.interview_session import (
    create_session,
    get_session,
    generate_interview_question,
    score_user_response,
    check_end_conditions,
    generate_dual_feedback,
    TranscriptEntry,
)
from brain.document_analyzer import analyzer as brain_analyzer

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Existing models ─────────────────────────────────────────────
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


# ── Interview models ────────────────────────────────────────────
class InterviewStartRequest(BaseModel):
    """Start a new mock interview session.
    
    startup_pitch is optional — if omitted, the backend pulls it
    from the brain's synthesized documents automatically.
    """
    vc_name: str
    vc_mandate: str
    vc_style: Optional[str] = "aggressive"
    startup_pitch: Optional[str] = None


class InterviewRespondRequest(BaseModel):
    """Submit user's transcribed response."""
    response_text: str


# ══════════════════════════════════════════════════════════════════
#  EXISTING SINGLE-SHOT ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@router.post("/question")
async def get_vc_question(req: QuestionRequest, user: dict = Depends(get_current_user)):
    """Generate a tough VC question based on the pitch and investor profile."""
    question_text = await generate_vc_question(req.model_dump())
    return {"question": question_text}


@router.post("/question/audio")
async def get_vc_question_audio(req: QuestionRequest, user: dict = Depends(get_current_user)):
    """Generate a VC question and stream it as audio via ElevenLabs."""
    try:
        question_text = await generate_vc_question(req.model_dump())
    except Exception as exc:
        logger.exception("Failed to generate VC question via Backboard")
        return JSONResponse(
            status_code=502,
            content={"detail": f"Question generation failed: {exc}"},
        )

    try:
        audio_stream = stream_audio_response(question_text, req.vc_name)
        return StreamingResponse(audio_stream, media_type="audio/mpeg", headers={
            "X-Question-Text": question_text[:200],
        })
    except Exception as exc:
        logger.exception("Failed to stream ElevenLabs audio")
        return JSONResponse(
            status_code=502,
            content={"detail": f"Audio streaming failed: {exc}"},
        )


@router.post("/evaluate")
async def evaluate_pitch_response(req: EvaluateRequest, user: dict = Depends(get_current_user)):
    """Evaluate the founder's response to the VC question."""
    evaluation = await evaluate_response(req.model_dump())
    return {"evaluation": evaluation}


# ══════════════════════════════════════════════════════════════════
#  MULTI-TURN INTERVIEW ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@router.post("/interview/start")
async def start_interview(req: InterviewStartRequest, user: dict = Depends(get_current_user)):
    """Create a new interview session and generate the first VC question.
    
    If startup_pitch is omitted, the backend automatically pulls the
    synthesized pitch from uploaded brain documents.
    """
    startup_pitch = req.startup_pitch

    # Auto-pull from brain if no pitch provided
    if not startup_pitch:
        docs = brain_analyzer.get_uploaded_documents()
        if not docs:
            return JSONResponse(
                status_code=400,
                content={"detail": "No startup pitch provided and no documents uploaded to Brain. Upload your startup documents first or provide a pitch manually."},
            )
        try:
            synthesis = await brain_analyzer.synthesize()
            concept = synthesis.get("synthesis", {}).get("pitchable_concept", {})
            profile = synthesis.get("synthesis", {}).get("startup_profile", {})
            startup_pitch = (
                f"{concept.get('elevator_pitch', '')} "
                f"Problem: {concept.get('problem', '')}. "
                f"Solution: {concept.get('solution', '')}. "
                f"Secret sauce: {concept.get('secret_sauce', '')}. "
                f"Sector: {profile.get('sector', '')}. "
                f"Stage: {profile.get('stage', '')}. "
                f"Target market: {profile.get('target_market', '')}."
            )
        except Exception as exc:
            logger.warning("Brain synthesis failed, using fallback: %s", exc)
            return JSONResponse(
                status_code=502,
                content={"detail": f"Failed to synthesize startup pitch from documents: {exc}"},
            )

    session = create_session(
        vc_name=req.vc_name,
        vc_mandate=req.vc_mandate,
        vc_style=req.vc_style or "aggressive",
        startup_pitch=startup_pitch,
    )

    try:
        question_text = await generate_interview_question(session)
    except Exception as exc:
        logger.exception("Failed to generate opening question")
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    # Record in transcript
    session.transcript.append(TranscriptEntry(role="vc", text=question_text))
    session.current_round = 1

    return {
        "session_id": session.session_id,
        "round": session.current_round,
        "question_text": question_text,
        "should_end": False,
        "end_reason": None,
    }


@router.get("/interview/context")
async def get_interview_context(user: dict = Depends(get_current_user)):
    """Get the startup context from uploaded brain documents.
    
    Returns the synthesized pitch and profile so the frontend can
    show the user what info the AI already knows about their startup.
    """
    docs = brain_analyzer.get_uploaded_documents()
    if not docs:
        return {
            "has_context": False,
            "document_count": 0,
            "startup_name": None,
            "elevator_pitch": None,
            "sector": None,
        }

    try:
        synthesis = await brain_analyzer.synthesize()
        concept = synthesis.get("synthesis", {}).get("pitchable_concept", {})
        profile = synthesis.get("synthesis", {}).get("startup_profile", {})
        return {
            "has_context": True,
            "document_count": len(docs),
            "startup_name": concept.get("startup_name"),
            "elevator_pitch": concept.get("elevator_pitch"),
            "tagline": concept.get("tagline"),
            "problem": concept.get("problem"),
            "solution": concept.get("solution"),
            "sector": profile.get("sector"),
            "stage": profile.get("stage"),
            "description": profile.get("description"),
        }
    except Exception as exc:
        logger.warning("Failed to get context: %s", exc)
        return {
            "has_context": False,
            "document_count": len(docs),
            "error": str(exc),
        }



@router.post("/interview/{session_id}/respond")
async def interview_respond(session_id: str, req: InterviewRespondRequest, user: dict = Depends(get_current_user)):
    """Accept user's response, score it, generate next question or end."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Interview already ended")

    # Score the response
    try:
        score = await score_user_response(session, req.response_text)
    except Exception:
        score = 5  # fallback

    # Record user response
    session.transcript.append(
        TranscriptEntry(role="user", text=req.response_text, score=score)
    )

    # Update consecutive low-score tracker
    if score <= 3:
        session.consecutive_low_scores += 1
    else:
        session.consecutive_low_scores = 0

    # Check end conditions
    should_end, end_reason = check_end_conditions(session)

    if should_end:
        session.status = "ended"
        session.end_reason = end_reason
        return {
            "session_id": session.session_id,
            "round": session.current_round,
            "question_text": None,
            "should_end": True,
            "end_reason": end_reason,
            "response_score": score,
        }

    # Generate next question
    try:
        next_question = await generate_interview_question(session)
    except Exception as exc:
        logger.exception("Failed to generate follow-up question")
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    session.transcript.append(TranscriptEntry(role="vc", text=next_question))
    session.current_round += 1

    return {
        "session_id": session.session_id,
        "round": session.current_round,
        "question_text": next_question,
        "should_end": False,
        "end_reason": None,
        "response_score": score,
    }


@router.post("/interview/{session_id}/audio")
async def interview_audio(session_id: str, user: dict = Depends(get_current_user)):
    """Stream TTS audio for the latest VC question in the session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Find last VC entry
    last_vc_text = None
    for entry in reversed(session.transcript):
        if entry.role == "vc":
            last_vc_text = entry.text
            break

    if not last_vc_text:
        raise HTTPException(status_code=400, detail="No VC question to speak")

    try:
        audio_stream = stream_audio_response(last_vc_text, session.vc_name)
        return StreamingResponse(audio_stream, media_type="audio/mpeg")
    except Exception as exc:
        logger.exception("Failed to stream interview audio")
        return JSONResponse(status_code=502, content={"detail": str(exc)})


@router.post("/interview/{session_id}/end")
async def end_interview(session_id: str, user: dict = Depends(get_current_user)):
    """Force-end the interview and generate dual-agent feedback."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "ended":
        session.status = "ended"
        session.end_reason = session.end_reason or "user_ended"

    try:
        feedback = await generate_dual_feedback(session)
    except Exception as exc:
        logger.exception("Failed to generate feedback")
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    return feedback


@router.get("/interview/{session_id}/status")
async def interview_status(session_id: str, user: dict = Depends(get_current_user)):
    """Get current session state."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "status": session.status,
        "current_round": session.current_round,
        "vc_name": session.vc_name,
        "end_reason": session.end_reason,
        "transcript": [
            {"role": e.role, "text": e.text, "score": e.score, "timestamp": e.timestamp}
            for e in session.transcript
        ],
    }
