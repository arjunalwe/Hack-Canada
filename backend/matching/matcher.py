"""Algorithmic matchmaking — scores startup profiles against the VC database."""

from typing import Any, Dict, List


# ── Sector keyword mapping for fuzzy matching ───────────────
SECTOR_SYNONYMS = {
    "ai": ["artificial intelligence", "machine learning", "ml", "deep learning", "nlp", "computer vision"],
    "fintech": ["financial technology", "payments", "banking", "insurtech", "defi"],
    "healthtech": ["health", "healthcare", "medtech", "biotech", "digital health", "pharma"],
    "cleantech": ["clean energy", "sustainability", "climate", "greentech", "renewable"],
    "saas": ["software as a service", "enterprise software", "b2b software", "cloud"],
    "edtech": ["education", "e-learning", "learning"],
    "proptech": ["real estate", "property technology"],
    "agtech": ["agriculture", "agritech", "farming"],
    "cybersecurity": ["security", "infosec", "cyber"],
    "robotics": ["automation", "drones", "hardware"],
}

STAGE_ORDER = ["pre-seed", "seed", "series-a", "series-b", "growth", "late-stage"]


def _normalise(text: str) -> str:
    return (text or "").strip().lower()


def _sector_overlap(startup_sector: str, vc_mandate: str) -> float:
    """Compute a 0–1 sector alignment score using keyword overlap."""
    s = _normalise(startup_sector)
    v = _normalise(vc_mandate)

    if not s or not v:
        return 0.2  # unknown → small base score

    # Direct substring match
    if s in v or v in s:
        return 1.0

    # Expand synonyms
    s_keywords = {s}
    v_keywords = set(v.replace(",", " ").split())
    for canonical, syns in SECTOR_SYNONYMS.items():
        if s in syns or s == canonical:
            s_keywords.update(syns)
            s_keywords.add(canonical)

    overlap = s_keywords & v_keywords
    if overlap:
        return min(1.0, 0.5 + 0.1 * len(overlap))

    return 0.1


def _stage_fit(startup_stage: str, vc_stages: str) -> float:
    """Score how well the startup stage matches the VC's investment stages."""
    s = _normalise(startup_stage)
    v = _normalise(vc_stages)

    if not s or not v:
        return 0.3

    if s in v:
        return 1.0

    # Partial credit for adjacent stages
    try:
        s_idx = STAGE_ORDER.index(s)
    except ValueError:
        return 0.3

    for stage in STAGE_ORDER:
        if stage in v:
            try:
                v_idx = STAGE_ORDER.index(stage)
                distance = abs(s_idx - v_idx)
                if distance == 1:
                    return 0.6
                elif distance == 2:
                    return 0.3
            except ValueError:
                continue

    return 0.1


def _check_size_fit(funding_ask: float | None, vc_min: float | None, vc_max: float | None) -> float:
    """Score how well the funding ask fits the VC's cheque size range."""
    if funding_ask is None:
        return 0.5  # unknown — neutral
    if vc_min is None and vc_max is None:
        return 0.5

    if vc_min and vc_max:
        if vc_min <= funding_ask <= vc_max:
            return 1.0
        elif funding_ask < vc_min:
            ratio = funding_ask / vc_min
            return max(0.1, ratio)
        else:
            ratio = vc_max / funding_ask
            return max(0.1, ratio)
    elif vc_max:
        return 1.0 if funding_ask <= vc_max else max(0.1, vc_max / funding_ask)
    elif vc_min:
        return 1.0 if funding_ask >= vc_min else max(0.1, funding_ask / vc_min)

    return 0.5


def _geo_score(startup_location: str, vc_location: str) -> float:
    """Bonus for geographic proximity."""
    s = _normalise(startup_location)
    v = _normalise(vc_location)
    if not s or not v:
        return 0.5
    if s in v or v in s:
        return 1.0
    # Same country
    if "canada" in s and "canada" in v:
        return 0.7
    return 0.3


def compute_match_score(startup: Dict[str, Any], vc: Dict[str, Any]) -> float:
    """Compute a weighted match score (0–100) between a startup and a VC."""
    weights = {
        "sector": 0.40,
        "stage": 0.25,
        "check_size": 0.20,
        "geo": 0.15,
    }

    sector = _sector_overlap(startup.get("sector", ""), vc.get("sector_mandate", ""))
    stage = _stage_fit(startup.get("stage", ""), vc.get("investment_stage", ""))
    check = _check_size_fit(
        startup.get("funding_ask"),
        vc.get("check_size_min"),
        vc.get("check_size_max"),
    )
    geo = _geo_score(startup.get("location", ""), vc.get("location", ""))

    raw = (
        weights["sector"] * sector
        + weights["stage"] * stage
        + weights["check_size"] * check
        + weights["geo"] * geo
    )

    return round(raw * 100, 1)


def get_top_matches(
    startup: Dict[str, Any],
    vc_database: List[Dict[str, Any]],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Return the top-N VC matches with scores, sorted descending."""
    scored = []
    for vc in vc_database:
        score = compute_match_score(startup, vc)
        scored.append({**vc, "match_score": score})

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:top_n]
