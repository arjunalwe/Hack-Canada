"""Scraper API routes — trigger scrapes and query the VC database."""

from fastapi import APIRouter, Depends

from auth.auth0 import get_current_user
from scraper.scraper import run_scrape_pipeline, load_vc_database

router = APIRouter()


@router.post("/run")
@router.get("/run")
async def trigger_scrape(user: dict = Depends(get_current_user)):
    """Trigger a full scrape of VC directories and return results."""
    results = await run_scrape_pipeline()
    return {"scraped": len(results), "vcs": results}


@router.get("/vcs")
async def list_vcs(user: dict = Depends(get_current_user)):
    """Return all VCs from the local database."""
    vcs = load_vc_database()
    return {"count": len(vcs), "vcs": vcs}
