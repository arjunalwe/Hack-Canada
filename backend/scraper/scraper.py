"""VC Data Engine — Pulls Canadian VC data from public sources.

No Gemini dependency. Uses a combination of:
1. Curated seed data (30+ real Canadian VCs)
2. Live scraping from accessible public directories
3. User-submitted custom VC profiles

The Gemini-powered extraction is still available as an optional enhancement
when the API quota allows.
"""

import asyncio
import json
import os
import re
from typing import List, Dict, Any

import httpx
from bs4 import BeautifulSoup

from config import settings

# ── HTTP client ─────────────────────────────────────────────
HTTP_CLIENT = httpx.AsyncClient(
    timeout=30.0,
    follow_redirects=True,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    },
)

# ── Seed database path ──────────────────────────────────────
SEED_DATA_PATH = os.path.join(os.path.dirname(__file__), "seed_data.json")


def _load_seed_data() -> List[Dict[str, Any]]:
    """Load the curated seed database of Canadian VCs."""
    if os.path.exists(SEED_DATA_PATH):
        with open(SEED_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


async def _scrape_angel_list_canada() -> List[Dict[str, Any]]:
    """Try to scrape AngelList/Wellfound for Canadian investors."""
    profiles = []
    try:
        resp = await HTTP_CLIENT.get("https://wellfound.com/investors/canada")
        if resp.status_code != 200:
            print(f"[scraper] Wellfound returned {resp.status_code} — skipping")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        # Look for investor cards/links
        for link in soup.select("a[href*='/i/']"):
            name = link.get_text(strip=True)
            if name and len(name) > 2:
                profiles.append({
                    "fund_name": name,
                    "website": f"https://wellfound.com{link.get('href', '')}",
                    "investment_stage": None,
                    "sector_mandate": None,
                    "check_size_min": None,
                    "check_size_max": None,
                    "location": "Canada",
                    "contact_email": None,
                    "description": f"Investor found on Wellfound (AngelList)",
                    "source": "wellfound",
                })
        print(f"[scraper] Found {len(profiles)} investors from Wellfound")
    except Exception as exc:
        print(f"[scraper] Wellfound scrape failed: {exc}")
    return profiles


async def _scrape_innovationfactory() -> List[Dict[str, Any]]:
    """Try to scrape Innovation Factory's Canadian VC list."""
    profiles = []
    try:
        resp = await HTTP_CLIENT.get(
            "https://innovationfactory.ca/resource/list-of-canadian-venture-capital-funds/"
        )
        if resp.status_code != 200:
            print(f"[scraper] InnovationFactory returned {resp.status_code} — skipping")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        # This page typically has a list of VC names with links
        content = soup.select_one(".entry-content, .post-content, article, main")
        if content:
            for link in content.select("a[href]"):
                name = link.get_text(strip=True)
                href = link.get("href", "")
                if name and len(name) > 3 and "http" in href and "innovationfactory" not in href:
                    profiles.append({
                        "fund_name": name,
                        "website": href,
                        "investment_stage": None,
                        "sector_mandate": None,
                        "check_size_min": None,
                        "check_size_max": None,
                        "location": "Canada",
                        "contact_email": None,
                        "description": f"Canadian VC fund listed on Innovation Factory",
                        "source": "innovationfactory",
                    })
        print(f"[scraper] Found {len(profiles)} investors from Innovation Factory")
    except Exception as exc:
        print(f"[scraper] Innovation Factory scrape failed: {exc}")
    return profiles


def _deduplicate(profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate profiles by fund_name (case-insensitive)."""
    seen = set()
    unique = []
    for p in profiles:
        key = (p.get("fund_name") or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _save_database(profiles: List[Dict[str, Any]]) -> None:
    """Persist profiles to the JSON database file."""
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    with open(settings.VC_DATABASE_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    print(f"[scraper] Saved {len(profiles)} VCs to {settings.VC_DATABASE_PATH}")


def load_vc_database() -> List[Dict[str, Any]]:
    """Load the VC database from disk. Returns empty list if not yet scraped."""
    if not os.path.exists(settings.VC_DATABASE_PATH):
        # Auto-initialize from seed data on first access
        seed = _load_seed_data()
        if seed:
            _save_database(seed)
            return seed
        return []
    with open(settings.VC_DATABASE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def add_vc_profile(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Add a single VC profile to the database (user-submitted)."""
    existing = load_vc_database()
    existing.append(profile)
    unique = _deduplicate(existing)
    _save_database(unique)
    return unique


async def run_scrape_pipeline() -> List[Dict[str, Any]]:
    """Run the full data pipeline:

    1. Start with curated seed data (always reliable)
    2. Try live scraping from accessible public directories
    3. Merge, deduplicate, and save

    This approach works without any API keys — pure web scraping.
    """
    all_profiles: List[Dict[str, Any]] = []

    # Phase 1: Load curated seed data
    seed = _load_seed_data()
    all_profiles.extend(seed)
    print(f"[scraper] Loaded {len(seed)} VCs from seed data")

    # Phase 2: Try live scraping (best effort — failures are fine)
    scraped = []
    try:
        results = await asyncio.gather(
            _scrape_angel_list_canada(),
            _scrape_innovationfactory(),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, list):
                scraped.extend(result)
    except Exception as exc:
        print(f"[scraper] Live scraping error: {exc}")

    all_profiles.extend(scraped)
    print(f"[scraper] Scraped {len(scraped)} additional VCs from public directories")

    # Merge with existing database
    existing = load_vc_database()
    combined = existing + all_profiles
    unique = _deduplicate(combined)

    _save_database(unique)
    return unique


# ── CLI entry point for quick testing ───────────────────────
if __name__ == "__main__":
    async def main():
        results = await run_scrape_pipeline()
        print(f"\nTotal unique VCs: {len(results)}")
        for vc in results[:5]:
            print(f"  - {vc.get('fund_name')}: {vc.get('sector_mandate')}")

    asyncio.run(main())
