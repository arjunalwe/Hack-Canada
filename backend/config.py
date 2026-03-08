"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central settings object — reads .env once at import time."""

    # ── Gemini ──────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # ── ElevenLabs ──────────────────────────────────────────
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "")



    # ── Backboard.io ────────────────────────────────────────
    BACKBOARD_API_KEY: str = os.getenv("BACKBOARD_API_KEY", "")

    # ── Paths ───────────────────────────────────────────────
    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "data")
    VC_DATABASE_PATH: str = os.path.join(DATA_DIR, "vc_database.json")


settings = Settings()
