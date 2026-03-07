"""Phase 2: Deep IP Ingestion — Backboard.io RAG-powered document analysis.

Accepts ANY documents — research papers, slides, patents, code, data, notes —
and synthesizes them into a pitchable startup concept + structured profile
ready for VC matching and outreach generation.

Architecture:
  1. User uploads anything (papers, slides, patents, financials, code)
  2. Backboard.io indexes all documents (auto-chunking + embedding)
  3. "IP Synthesizer" agent reads across ALL docs via RAG
  4. Produces a pitchable concept, structured profile, and VC-ready materials

Supported formats: .pdf, .docx, .pptx, .csv, .json, .txt, .png, .jpg, code files
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional

from backboard import BackboardClient

from config import settings

# ── Uploads directory ───────────────────────────────────────
UPLOADS_DIR = os.path.join(settings.DATA_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ── Supported file types ────────────────────────────────────
ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx",
    ".csv", ".json", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".webp",
    ".py", ".js", ".ts", ".cpp", ".java", ".go", ".rs",
}


def _parse_json(raw: str) -> dict:
    """Parse JSON from LLM response."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


# ── System prompt ───────────────────────────────────────────
IP_SYNTHESIZER_PROMPT = """You are an elite startup strategist, IP analyst, and pitch architect.

Your superpower: you can take ANY raw materials — academic papers, research notes,
patent filings, code repositories, slide decks, data analyses, financial spreadsheets,
or even scattered ideas — and synthesize them into a compelling, pitchable startup concept.

You think like a VC partner evaluating deal flow, but you also think like a founder
crafting their narrative. You connect dots between technical innovation and market opportunity.

When analyzing documents, you:
- Identify the core INNOVATION buried in technical or academic content
- Translate research into market opportunities ("this paper shows X, which means a startup could...")
- Spot defensible IP and technical moats (even when the author doesn't frame it that way)
- Identify the most fundable angle for the underlying technology
- Assess what stage the idea is at and what it needs to become investable
- Flag risks honestly but constructively

You are NOT just extracting — you are SYNTHESIZING and CREATING a pitchable narrative
from raw intellectual property.

When asked for JSON output, return ONLY valid JSON — no markdown, no commentary.
"""


class DocumentAnalyzer:
    """Manages document uploads, RAG-powered analysis, and pitch synthesis via Backboard.io."""

    def __init__(self):
        self.client = BackboardClient(api_key=settings.BACKBOARD_API_KEY)
        self._assistant_id: Optional[str] = None
        self._thread_id: Optional[str] = None
        self._documents: Dict[str, Dict[str, Any]] = {}  # doc_id -> metadata

    async def _ensure_assistant(self) -> str:
        """Create or reuse the IP Synthesizer assistant."""
        if self._assistant_id:
            return self._assistant_id

        assistant = await self.client.create_assistant(
            name="IP Synthesizer",
            system_prompt=IP_SYNTHESIZER_PROMPT,
        )
        self._assistant_id = assistant.assistant_id
        print(f"[brain] Created IP Synthesizer assistant: {self._assistant_id}")
        return self._assistant_id

    async def _ensure_thread(self) -> str:
        """Create or reuse an analysis thread."""
        if self._thread_id:
            return self._thread_id

        assistant_id = await self._ensure_assistant()
        thread = await self.client.create_thread(assistant_id)
        self._thread_id = thread.thread_id
        print(f"[brain] Created thread: {self._thread_id}")
        return self._thread_id

    async def upload_document(self, filepath: str, original_filename: str) -> Dict[str, Any]:
        """Upload a document to Backboard.io for RAG indexing.

        Accepts research papers, code, slides, patents — anything.
        Backboard.io handles chunking, embedding, and indexing automatically.
        """
        assistant_id = await self._ensure_assistant()

        print(f"[brain] Uploading '{original_filename}'...")
        document = await self.client.upload_document_to_assistant(
            assistant_id, filepath
        )
        doc_id = document.document_id
        print(f"[brain] Upload complete. Document ID: {doc_id}")

        # Poll for indexing
        print(f"[brain] Waiting for indexing...")
        max_wait = 60
        elapsed = 0
        status = "processing"

        while elapsed < max_wait:
            doc_status = await self.client.get_document_status(doc_id)
            status = doc_status.status
            if status == "indexed":
                print(f"[brain] ✓ Indexed successfully!")
                break
            elif status == "failed":
                error = getattr(doc_status, "status_message", "Unknown error")
                print(f"[brain] ✗ Indexing failed: {error}")
                return {"document_id": doc_id, "status": "failed", "error": error, "filename": original_filename}
            await asyncio.sleep(2)
            elapsed += 2

        self._documents[doc_id] = {
            "document_id": doc_id,
            "filename": original_filename,
            "status": status,
            "filepath": filepath,
        }
        return self._documents[doc_id]

    async def synthesize(self) -> Dict[str, Any]:
        """The main event: synthesize ALL uploaded documents into a pitchable concept.

        This is NOT simple extraction. The agent reads across research papers,
        code, slides, patents — whatever you uploaded — and CREATES a cohesive
        startup narrative that a VC would want to fund.

        Returns:
            Structured pitch concept with startup profile ready for matching
        """
        thread_id = await self._ensure_thread()
        doc_count = len(self._documents)

        if doc_count == 0:
            return {"error": "No documents uploaded yet. Upload research papers, slides, code, or any materials first."}

        filenames = [d["filename"] for d in self._documents.values()]
        print(f"[brain] Synthesizing pitchable concept from {doc_count} document(s): {filenames}")

        prompt = f"""I've uploaded {doc_count} document(s): {', '.join(filenames)}

Read through ALL of them carefully. These might be research papers, code, slides,
patents, data, notes, or anything else. Your job is to SYNTHESIZE everything into
a compelling, pitchable startup concept.

Think like a founder turning their research/work into a fundable startup.

Return a JSON object:
{{
    "pitchable_concept": {{
        "startup_name": "a catchy, memorable name you'd suggest for this startup",
        "tagline": "one line that captures the essence — something a VC remembers",
        "elevator_pitch": "3-4 sentences that explain what this is, why it matters, and why now",
        "problem": "the specific pain point this addresses",
        "solution": "how the technology/IP solves it",
        "why_now": "why this is the right time for this startup to exist",
        "secret_sauce": "what makes this defensible and hard to replicate"
    }},
    "startup_profile": {{
        "sector": "primary sector (AI, healthtech, fintech, cleantech, etc.)",
        "stage": "best guess at current stage (pre-seed, seed, etc.)",
        "description": "2-3 sentence description for a VC database",
        "tech_stack": ["technologies", "mentioned", "or", "implied"],
        "target_market": "who would pay for this",
        "market_size": "estimated TAM if you can infer it, otherwise null",
        "business_model": "how this could make money",
        "competitive_advantage": "what defensible moats exist",
        "location": "if mentioned, otherwise null",
        "funding_ask": null
    }},
    "ip_analysis": {{
        "core_innovation": "the fundamental technical breakthrough or insight",
        "technical_moat": "what's defensible (proprietary data, algorithms, patents)",
        "ip_assets": ["list of identifiable IP: patents, datasets, models, algorithms"],
        "maturity": "how far along is the tech (concept, prototype, production-ready)",
        "key_risks": ["top 3 technical or market risks"]
    }},
    "vc_readiness": {{
        "score": "<1-10 integer — how ready is this for VC funding>",
        "strengths": ["top 3 things a VC would love"],
        "gaps": ["top 3 things that need work before pitching"],
        "recommended_next_steps": ["what to do next to become more fundable"],
        "ideal_investor_type": "what kind of VC should they target"
    }}
}}

Be creative with the startup name and tagline. Make it something a VC would remember.
Be honest about readiness — if the materials are early-stage research, say so.
Return ONLY valid JSON."""

        response = await self.client.add_message(
            thread_id=thread_id,
            content=prompt,
            stream=False,
        )

        result = _parse_json(response.content)
        print(f"[brain] Synthesis complete — {len(result)} top-level sections")

        return {
            "synthesis": result,
            "documents_analyzed": doc_count,
            "document_ids": list(self._documents.keys()),
            "filenames": filenames,
        }

    async def analyze_documents(self) -> Dict[str, Any]:
        """Extract a structured startup profile from uploaded documents.

        More focused than synthesize() — just pulls out facts and data
        without creating a narrative. Good for feeding into the matching engine.
        """
        thread_id = await self._ensure_thread()
        doc_count = len(self._documents)

        if doc_count == 0:
            return {"error": "No documents uploaded yet"}

        print(f"[brain] Extracting structured profile from {doc_count} document(s)...")

        prompt = """Read ALL uploaded documents and extract a structured startup profile.
These could be research papers, slides, code, patents, or anything else.
Extract what you can find and infer what you can from the materials.

Return JSON:
{
    "company_name": "string or null",
    "sector": "primary sector",
    "stage": "current stage",
    "description": "2-3 sentence description",
    "value_proposition": "core value prop",
    "technical_moat": "defensible tech",
    "target_market": "customers",
    "business_model": "revenue model if apparent",
    "tech_stack": ["technologies"],
    "traction": "any metrics or progress indicators",
    "funding_ask": null,
    "location": "if mentioned",
    "risk_factors": ["key risks"],
    "ip_assets": ["patents", "data", "algorithms"]
}

Use null for anything not found or inferable. Return ONLY valid JSON."""

        response = await self.client.add_message(
            thread_id=thread_id, content=prompt, stream=False
        )

        profile = _parse_json(response.content)
        print(f"[brain] Extracted profile with {len(profile)} fields")

        return {
            "profile": profile,
            "documents_analyzed": doc_count,
            "document_ids": list(self._documents.keys()),
        }

    async def ask_about_documents(self, question: str) -> str:
        """Ask any question about the uploaded documents via RAG."""
        thread_id = await self._ensure_thread()
        print(f"[brain] Query: '{question[:60]}...'")
        response = await self.client.add_message(
            thread_id=thread_id, content=question, stream=False
        )
        return response.content

    def get_uploaded_documents(self) -> List[Dict[str, Any]]:
        """Return metadata for all uploaded documents."""
        return list(self._documents.values())

    def reset(self):
        """Reset for a new session."""
        self._assistant_id = None
        self._thread_id = None
        self._documents.clear()
        print("[brain] Reset — ready for new session")


# ── Singleton ───────────────────────────────────────────────
analyzer = DocumentAnalyzer()
