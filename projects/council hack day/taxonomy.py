"""Deterministic topic taxonomy for council minutes text."""
import re

# Statutory notices (TROs, path orders) published as fake "committees" — Bradford does
# this at scale and it swamps the Transport topic. Used by both harvest.py (skip at
# source) and app.py (filter legacy rows).
NOTICE_PATTERN = r"(?i)\border\b|notice|traffic|speed limit|parking|prohibition|public path"

TOPICS = {
    "Housing & Planning": [
        "housing", "planning application", "affordable homes", "homelessness",
        "landlord", "tenants", "development site", "local plan", "green belt",
        "planning permission", "hmo", "housebuilding",
    ],
    "Social Care": [
        "social care", "adult care", "safeguarding adults", "care home",
        "carers", "domiciliary", "care provider", "care package",
    ],
    "Children & Education": [
        "children's services", "schools", "send", "education", "school places",
        "safeguarding children", "youth services", "childcare", "pupils",
        "looked after children", "special educational needs",
    ],
    "Climate & Environment": [
        "climate", "net zero", "carbon", "biodiversity", "recycling",
        "flood", "air quality", "renewable", "emissions", "tree planting",
    ],
    "Transport & Highways": [
        "highways", "transport", "bus service", "cycling", "pedestrian",
        "road safety", "parking", "20mph", "potholes", "ev charging",
        "active travel", "congestion",
    ],
    "Finance & Budget": [
        "budget", "council tax", "revenue", "capital programme", "reserves",
        "savings", "overspend", "medium term financial", "procurement",
        "treasury management", "funding gap",
    ],
    "Health": [
        "public health", "nhs", "health and wellbeing", "mental health",
        "gp", "health inequalities", "obesity", "vaccination",
    ],
    "Licensing & Regulation": [
        "licensing", "premises licence", "taxi", "gambling", "alcohol",
        "enforcement", "trading standards", "food hygiene",
    ],
    "Community Safety": [
        "community safety", "antisocial behaviour", "anti-social behaviour",
        "crime", "police", "domestic abuse", "cctv", "knife crime",
    ],
    "Local Economy": [
        "high street", "regeneration", "town centre", "local economy",
        "business rates", "tourism", "jobs", "levelling up", "markets",
        "employment", "skills",
    ],
}

_PATTERNS = {
    topic: re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")\b")
    for topic, kws in TOPICS.items()
}


def classify(text: str) -> dict:
    """Return {topic: keyword hit count} for a document's text."""
    low = text.lower()
    return {topic: len(pat.findall(low)) for topic, pat in _PATTERNS.items()}
