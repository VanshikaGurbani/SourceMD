"""Registry of public medical guideline PDFs ingested into ChromaDB.

Each entry contains:
- name: short stable identifier used as the ``doc`` metadata field
- url: direct PDF download URL, or "local" if the file must be placed manually
- web_url: canonical guideline webpage shown as the citation link in the UI
- tag: broad clinical area for quick filtering
"""
from __future__ import annotations

from typing import TypedDict


class GuidelineSource(TypedDict):
    """One ingestable PDF guideline."""

    name: str
    url: str
    web_url: str
    tag: str


SOURCES: list[GuidelineSource] = [
    # NICE NG28 — Type 2 Diabetes (auto-download works)
    {
        "name": "NICE-NG28-Type2-Diabetes",
        "url": "https://www.nice.org.uk/guidance/ng28/resources/type-2-diabetes-in-adults-management-pdf-1837338615493",
        "web_url": "https://www.nice.org.uk/guidance/ng28",
        "tag": "endocrinology",
    },
    # AHA 2025 CPR/ECC Highlights — manually placed in ingestion/cache/
    {
        "name": "AHA-2025-CPR-ECC-Highlights",
        "url": "local",
        "web_url": "https://eccguidelines.heart.org",
        "tag": "emergency",
    },
    # NICE NG136 — Hypertension in Adults — manually placed in ingestion/cache/
    # Download from: https://www.nice.org.uk/guidance/ng136 → "View and download PDF"
    {
        "name": "NICE-NG136-Hypertension",
        "url": "local",
        "web_url": "https://www.nice.org.uk/guidance/ng136",
        "tag": "cardiology",
    },
    # NICE CG181 — Cardiovascular Risk — manually placed in ingestion/cache/
    # Download from: https://www.nice.org.uk/guidance/cg181 → "View and download PDF"
    {
        "name": "NICE-CG181-Cardiovascular-Risk",
        "url": "local",
        "web_url": "https://www.nice.org.uk/guidance/cg181",
        "tag": "cardiology",
    },
]
