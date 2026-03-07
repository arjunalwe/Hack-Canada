"""Adversarial VC Simulator — Gemini persona + ElevenLabs TTS."""

from typing import Any, AsyncIterator, Dict
import hashlib

import json
import re
from backboard import BackboardClient
import httpx

from config import settings

# ── Backboard setup ────────────────────────────────────────────
client = BackboardClient(api_key=settings.BACKBOARD_API_KEY)


async def generate_vc_question(data: Dict[str, Any]) -> str:
    """Generate a brutal, adversarial VC question based on the investor profile and startup pitch."""
    prompt = f"""You are role-playing as a HIGHLY CRITICAL venture capital partner at {data.get('vc_name', 'a top-tier fund')}.

YOUR INVESTOR PROFILE:
- Fund: {data.get('vc_name', 'Unknown Fund')}
- Investment Mandate: {data.get('vc_mandate', 'general technology')}
- Style: {data.get('vc_style', 'aggressive')}

THE FOUNDER'S PITCH:
{data.get('startup_pitch', '')}

YOUR TASK:
Ask ONE devastatingly specific, technical, and challenging question that would make
an unprepared founder stumble. Your question should:

1. Target the WEAKEST part of their pitch (unit economics, defensibility, market size, team gaps, technical feasibility).
2. Reference specific numbers, competitors, or market dynamics.
3. Be confrontational but professional — like a real partner meeting.
4. Be 2-3 sentences maximum.

Do NOT be generic. Do NOT ask "tell me about your team." Ask something that shows you
deeply understand their space and see a SPECIFIC flaw.

Return ONLY the question. No preamble, no commentary.
"""
    assistant = await client.create_assistant(name="VC Simulator", system_prompt="You are a VC.")
    thread = await client.create_thread(assistant.assistant_id)
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        stream=False
    )
    return response.content.strip()


# ── ElevenLabs Standard Voices ──────────────────────────────
# A curated list of distinct ElevenLabs voices (male and female)
AVAILABLE_VOICES = [
    "21m00Tcm4TlvDq8ikWAM",  # Rachel (calm, American)
    "29vD33N1CtxCmqQRPOHJ",  # Drew (news, American)
    "2EiwWnXFnvU5JabPnv8n",  # Clyde (deep, authoritative)
    "5Q0t7uMcjvnagumLfvZi",  # Paul (ground reporter)
    "AZnzlk1XvdvUeBnXmlld",  # Domi (strong, emotional)
    "CYw3kZ02Hs0563khs1Fj",  # Dave (conversational, British)
    "D38z5RcWu1voky8WS1ja",  # Fin (old, sailor, Irish)
    "EXAVITQu4vr4xnSDxMaL",  # Sarah (calm, measured)
    "ErXwobaYiN019PkySvjV",  # Antoni (well-rounded)
    "VR6AewLTigWG4xSOukaG",  # Thomas (calm)
    "pNInz6obpgDQGcFmaJgB",  # Adam (deep)
    "yoZ06aMxZJJ28mfd3POQ",  # Sam (trustworthy)
]

def _get_voice_for_vc(vc_name: str) -> str:
    """Deterministically pick a consistent voice ID for a given VC name."""
    if not vc_name:
        return AVAILABLE_VOICES[0]
    # Hash the VC name to get a consistent integer, then modulo by list length
    hash_int = int(hashlib.sha256(vc_name.encode('utf-8')).hexdigest(), 16)
    return AVAILABLE_VOICES[hash_int % len(AVAILABLE_VOICES)]

async def stream_audio_response(text: str, vc_name: str = "") -> AsyncIterator[bytes]:
    """Stream TTS audio from ElevenLabs for the given text.

    Deterministically selects a voice ID based on the vc_name, ensuring
    each VC sounds consistent every time you pitch them.
    """
    if not settings.ELEVENLABS_API_KEY:
        raise ValueError(
            "ElevenLabs API key not configured. "
            "Set ELEVENLABS_API_KEY in .env"
        )

    voice_id = _get_voice_for_vc(vc_name)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            url,
            json={
                "text": text,
                "model_id": "eleven_turbo_v2",
                "voice_settings": {
                    "stability": 0.6,
                    "similarity_boost": 0.85,
                    "style": 0.4,
                    "use_speaker_boost": True,
                },
            },
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            timeout=30.0,
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(chunk_size=4096):
                yield chunk


async def evaluate_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate the founder's response to the adversarial VC question."""
    prompt = f"""You are an expert pitch coach evaluating a founder's response during a VC pitch meeting.

THE VC'S QUESTION:
{data.get('vc_question', '')}

THE FOUNDER'S RESPONSE:
{data.get('founder_response', '')}

STARTUP CONTEXT:
{data.get('startup_context', '')}

Evaluate the response on these dimensions (score each 1-10):

1. **Directness** — Did they answer the actual question head-on?
2. **Specificity** — Did they use concrete data, metrics, or examples?
3. **Confidence** — Did they project conviction without being defensive?
4. **Strategic thinking** — Did they show awareness of the underlying concern?
5. **Honesty** — Did they acknowledge weaknesses rather than dodge?

Return a JSON object:
```json
{{
    "overall_score": <1-10>,
    "directness": <1-10>,
    "specificity": <1-10>,
    "confidence": <1-10>,
    "strategic_thinking": <1-10>,
    "honesty": <1-10>,
    "feedback": "<2-3 sentences of specific coaching advice>",
    "suggested_response": "<a model answer the founder could study>"
}}
```

Return ONLY valid JSON.
"""
    assistant = await client.create_assistant(name="Pitch Coach", system_prompt="You evaluate pitches.")
    thread = await client.create_thread(assistant.assistant_id)
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        stream=False
    )
    raw = response.content.strip()

    # Parse JSON from response
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "overall_score": 0,
            "feedback": raw,
            "error": "Failed to parse structured evaluation",
        }
