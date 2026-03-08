"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import scraper_router, matching_router, generation_router, simulator_router, brain_router

app = FastAPI(
    title="Fundraising Co-Pilot API",
    description="AI-powered fundraising pipeline: scrape VCs, match startups, generate outreach, simulate pitches.",
    version="0.1.0",
)

# ── CORS (wide-open for hackathon dev) ──────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers ───────────────────────────────────────────
app.include_router(scraper_router.router, prefix="/api/scraper", tags=["Scraper"])
app.include_router(matching_router.router, prefix="/api/match", tags=["Matching"])
app.include_router(generation_router.router, prefix="/api/generate", tags=["Generation"])
app.include_router(simulator_router.router, prefix="/api/simulator", tags=["Simulator"])
app.include_router(brain_router.router, prefix="/api/brain", tags=["Brain (Document Analysis)"])


@app.get("/")
async def root():
    return {
        "name": "Fundraising Co-Pilot API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
