"""Adversarial VC Simulator — Gemini persona + ElevenLabs TTS."""

from typing import Any, AsyncIterator, Dict

import google.generativeai as genai
import httpx

from config import settings

# ── Gemini setup ────────────────────────────────────────────
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")


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
    response = model.generate_content(prompt)
    return response.text.strip()


async def stream_audio_response(text: str) -> AsyncIterator[bytes]:
    """Stream TTS audio from ElevenLabs for the given text.

    Returns an async byte iterator suitable for FastAPI's StreamingResponse.
    Falls back to an error message if ElevenLabs is not configured.
    """
    if not settings.ELEVENLABS_API_KEY or not settings.ELEVENLABS_VOICE_ID:
        # Return a simple error indicator — frontend can handle gracefully
        raise ValueError(
            "ElevenLabs API key or voice ID not configured. "
            "Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in .env"
        )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}/stream"

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
    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Parse JSON from response
    import json
    import re
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
