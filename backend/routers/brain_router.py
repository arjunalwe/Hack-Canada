"""Brain API routes — Document upload, RAG analysis, and IP-to-pitch synthesis."""

import os
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel, Field

from auth.auth0 import get_current_user
from brain.document_analyzer import analyzer, UPLOADS_DIR, ALLOWED_EXTENSIONS

router = APIRouter()


class QuestionRequest(BaseModel):
    """Free-form question about uploaded documents."""
    question: str = Field(
        ...,
        examples=["What is the core technical innovation in these documents?"],
    )


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload any document for analysis.

    Accepts research papers, slides, patents, code, data, notes — anything.
    Supported: PDF, DOCX, PPTX, CSV, JSON, TXT, images, code files.
    Documents are automatically indexed by Backboard.io for RAG.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    filepath = os.path.join(UPLOADS_DIR, file.filename)
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    result = await analyzer.upload_document(filepath, file.filename)
    return result


@router.post("/synthesize")
async def synthesize_pitch(user: dict = Depends(get_current_user)):
    """The main event: turn uploaded raw materials into a pitchable startup concept.

    Takes ALL uploaded documents — research papers, code, slides, patents,
    notes, data — and synthesizes them into:
    - A pitchable concept (startup name, tagline, elevator pitch)
    - Structured startup profile (for VC matching)
    - IP analysis (technical moat, maturity, assets)
    - VC readiness score with actionable next steps

    This is NOT simple data extraction. The AI CREATES a fundable narrative
    from your raw intellectual property.
    """
    result = await analyzer.synthesize()
    return result


@router.post("/analyze")
async def analyze_documents(user: dict = Depends(get_current_user)):
    """Extract a structured startup profile from uploaded documents.

    More focused than /synthesize — just extracts facts and data
    without creating a narrative. Good for feeding into the matching engine.
    """
    result = await analyzer.analyze_documents()
    return result


@router.post("/ask")
async def ask_about_documents(
    request: QuestionRequest,
    user: dict = Depends(get_current_user),
):
    """Ask any question about your uploaded documents.

    Uses RAG to search through ALL indexed documents and provide
    contextual, evidence-grounded answers.
    """
    answer = await analyzer.ask_about_documents(request.question)
    return {"question": request.question, "answer": answer}


@router.get("/documents")
async def list_documents(user: dict = Depends(get_current_user)):
    """List all uploaded documents and their indexing status."""
    docs = analyzer.get_uploaded_documents()
    return {"count": len(docs), "documents": docs}


@router.post("/reset")
async def reset_analyzer(user: dict = Depends(get_current_user)):
    """Reset the Brain for a new session — clears all uploaded documents."""
    analyzer.reset()
    return {"status": "reset", "message": "Ready for new document uploads"}
