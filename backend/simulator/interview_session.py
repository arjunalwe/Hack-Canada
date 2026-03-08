"""Multi-turn mock interview session manager.

Manages interview state, context-aware follow-up questions,
inline response scoring, and dual-agent Backboard feedback.
"""

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import settings

logger = logging.getLogger(__name__)

# ── AI backends ────────────────────────────────────────────────
try:
    from backboard import BackboardClient
    backboard_client = BackboardClient(api_key=settings.BACKBOARD_API_KEY)
except Exception:
    backboard_client = None
    logger.warning("Backboard SDK not available for interview sessions.")

try:
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.0-flash")
except Exception:
    gemini_model = None
    logger.warning("Gemini SDK not available for interview sessions.")


MAX_ROUNDS = 5
FAIL_THRESHOLD = 3          # score ≤ this = "bad"
CONSECUTIVE_FAILS_TO_END = 2


# ── Data classes ───────────────────────────────────────────────
@dataclass
class TranscriptEntry:
    role: str          # "vc" or "user"
    text: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    score: Optional[int] = None   # only for user entries


@dataclass
class InterviewSession:
    session_id: str
    vc_name: str
    vc_mandate: str
    vc_style: str
    startup_pitch: str
    transcript: List[TranscriptEntry] = field(default_factory=list)
    current_round: int = 0
    status: str = "active"          # active | ended
    end_reason: Optional[str] = None
    consecutive_low_scores: int = 0


# ── Session store (in-memory) ─────────────────────────────────
_sessions: Dict[str, InterviewSession] = {}


def create_session(vc_name: str, vc_mandate: str, vc_style: str, startup_pitch: str) -> InterviewSession:
    sid = uuid.uuid4().hex[:12]
    session = InterviewSession(
        session_id=sid,
        vc_name=vc_name,
        vc_mandate=vc_mandate,
        vc_style=vc_style,
        startup_pitch=startup_pitch,
    )
    _sessions[sid] = session
    return session


def get_session(session_id: str) -> Optional[InterviewSession]:
    return _sessions.get(session_id)


# ── Transcript formatting ─────────────────────────────────────
def _format_transcript(session: InterviewSession) -> str:
    lines = []
    for entry in session.transcript:
        label = f"VC ({session.vc_name})" if entry.role == "vc" else "Founder"
        lines.append(f"{label}: {entry.text}")
    return "\n".join(lines)


# ── Question generation ───────────────────────────────────────
async def _ai_generate(prompt: str) -> str:
    """Generate text via Backboard (15 s timeout) or Gemini fallback."""
    if backboard_client:
        try:
            async def _via_bb():
                a = await backboard_client.create_assistant(
                    name="VC Interviewer", system_prompt="You are a VC interviewer.")
                t = await backboard_client.create_thread(a.assistant_id)
                r = await backboard_client.add_message(
                    thread_id=t.thread_id, content=prompt, stream=False)
                return r.content.strip()
            return await asyncio.wait_for(_via_bb(), timeout=15.0)
        except Exception as exc:
            logger.warning("Backboard failed (%s), falling back.", exc)
    if gemini_model:
        r = await asyncio.to_thread(gemini_model.generate_content, prompt)
        return r.text.strip()
    raise RuntimeError("No AI backend available.")


async def generate_interview_question(session: InterviewSession) -> str:
    """Generate the next context-aware VC question."""
    transcript_so_far = _format_transcript(session)

    if session.current_round == 0:
        context_block = "This is the OPENING question. You have not spoken yet."
    else:
        context_block = f"""CONVERSATION SO FAR:
{transcript_so_far}

This is round {session.current_round + 1} of {MAX_ROUNDS}. Build on what was said.
Do NOT repeat a topic you already covered. Escalate difficulty."""

    prompt = f"""You are role-playing as a HIGHLY CRITICAL venture capital partner at {session.vc_name}.

INVESTOR PROFILE:
- Fund: {session.vc_name}
- Mandate: {session.vc_mandate}
- Style: {session.vc_style}

FOUNDER'S PITCH:
{session.startup_pitch}

{context_block}

Ask ONE devastatingly specific, challenging question (2-3 sentences max).
Target weaknesses, reference specifics, be confrontational but professional.
Return ONLY the question — no preamble."""

    return await _ai_generate(prompt)


# ── Response scoring ──────────────────────────────────────────
async def score_user_response(session: InterviewSession, user_text: str) -> int:
    """Score the user's response 1-10 and return the score."""
    last_vc = ""
    for entry in reversed(session.transcript):
        if entry.role == "vc":
            last_vc = entry.text
            break

    prompt = f"""Rate this founder's response to a VC question on a scale of 1-10.

VC QUESTION: {last_vc}
FOUNDER RESPONSE: {user_text}

Scoring guide:
1-3 = Terrible (rambling, evasive, no substance, clearly unprepared)
4-5 = Below average (vague, generic, misses the point)
6-7 = Decent (addresses the question, some specifics)
8-10 = Excellent (direct, data-backed, shows deep understanding)

Return ONLY a single integer between 1 and 10. Nothing else."""

    raw = await _ai_generate(prompt)
    # Extract the number
    match = re.search(r'\b(\d+)\b', raw)
    if match:
        return max(1, min(10, int(match.group(1))))
    return 5  # default if parse fails


def check_end_conditions(session: InterviewSession) -> tuple[bool, Optional[str]]:
    """Check if the interview should end. Returns (should_end, reason)."""
    if session.current_round >= MAX_ROUNDS:
        return True, "complete"

    if session.consecutive_low_scores >= CONSECUTIVE_FAILS_TO_END:
        return True, "low_performance"

    return False, None


# ── Dual-agent feedback ───────────────────────────────────────
async def generate_dual_feedback(session: InterviewSession) -> Dict[str, Any]:
    """Generate feedback from two Backboard agents: Pros and Cons."""
    # Build Q&A pairs showing only what the founder said in response to each question
    qa_pairs = []
    for i, entry in enumerate(session.transcript):
        if entry.role == "user":
            # Find the VC question just before this user response
            prev_vc = ""
            for j in range(i - 1, -1, -1):
                if session.transcript[j].role == "vc":
                    prev_vc = session.transcript[j].text
                    break
            score_str = f" [Score: {entry.score}/10]" if entry.score else ""
            qa_pairs.append(f"Q: {prev_vc}\nFOUNDER'S ANSWER{score_str}: {entry.text}")

    qa_text = "\n\n".join(qa_pairs) if qa_pairs else "No responses recorded."

    pros_prompt = f"""You are an ENCOURAGING pitch coach. Review ONLY the FOUNDER's answers below.
Do NOT evaluate the VC's questions — only analyze how well the founder responded.

STARTUP PITCH:
{session.startup_pitch}

FOUNDER'S RESPONSES TO VC QUESTIONS:
{qa_text}

Find EVERY STRENGTH in the founder's answers. Be specific — quote their exact words
when they said something well. Focus on:
- Answers with specific data, metrics, or concrete examples
- Good handling of tough or confrontational questions
- Effective storytelling or framing of their startup
- Genuine honesty that built credibility
- Moments showing deep domain expertise

Return a JSON object:
```json
{{
    "strengths": ["Specific strength 1", "Specific strength 2", ...],
    "best_moment": "Quote the founder's single best answer or phrase",
    "overall": "2-3 sentence encouraging summary of the FOUNDER's performance"
}}
```
Return ONLY valid JSON."""

    cons_prompt = f"""You are a BRUTALLY HONEST pitch critic. Review ONLY the FOUNDER's answers below.
Do NOT evaluate the VC's questions — only analyze weaknesses in how the founder responded.

STARTUP PITCH:
{session.startup_pitch}

FOUNDER'S RESPONSES TO VC QUESTIONS:
{qa_text}

Find EVERY WEAKNESS in the founder's answers. Be specific — quote their exact words
when they stumbled. Focus on:
- Evasive, vague, or rambling answers
- Missing data or unsubstantiated claims
- Defensive or dismissive reactions to valid concerns
- Missed opportunities to address the VC's underlying concern
- Weak closings or lack of confidence
- Factual errors or contradictions

Return a JSON object:
```json
{{
    "weaknesses": ["Specific weakness 1", "Specific weakness 2", ...],
    "worst_moment": "Quote the founder's single weakest answer or phrase",
    "overall": "2-3 sentence brutally honest summary of the FOUNDER's performance"
}}
```
Return ONLY valid JSON."""

    scores = [e.score for e in session.transcript if e.role == "user" and e.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0

    # Run both agents in parallel
    pros_raw, cons_raw = await asyncio.gather(
        _ai_generate(pros_prompt),
        _ai_generate(cons_prompt),
    )

    def _parse_json(raw: str) -> dict:
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw": raw, "error": "Failed to parse"}

    return {
        "pros_feedback": _parse_json(pros_raw),
        "cons_feedback": _parse_json(cons_raw),
        "transcript": [
            {"role": e.role, "text": e.text, "score": e.score, "timestamp": e.timestamp}
            for e in session.transcript
        ],
        "total_rounds": session.current_round,
        "average_score": round(avg_score, 1),
        "end_reason": session.end_reason,
    }
