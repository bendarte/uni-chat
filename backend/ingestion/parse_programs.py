import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.source_validation import is_valid_source_url, normalize_source_url
from app.services.language_normalization import infer_primary_field
from app.services.metadata_normalization import (
    normalize_city,
    normalize_country,
    normalize_language,
    normalize_study_pace,
)

RAW = Path(__file__).resolve().parent / "programs_raw.json"
OUT = Path(__file__).resolve().parent / "programs_parsed.json"

CAREER_HINTS = {
    "artificial intelligence": "AI Engineer, Data Scientist, ML Engineer",
    "computer science": "Software Developer, Systems Engineer, Data Engineer",
    "engineering": "Engineer, Project Engineer, Technical Specialist",
    "business": "Business Analyst, Consultant, Product Manager",
    "entrepreneurship": "Founder, Innovation Manager, Venture Analyst",
    "sustainability": "Sustainability Analyst, Policy Advisor, Environmental Consultant",
    "social sciences": "Policy Analyst, Researcher, Public Sector Specialist",
    "history": "Researcher, Archivist, Educator",
    "general": "Specialist roles related to the programme focus",
}


def clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def parse_duration_years(value: Optional[str]) -> Optional[int]:
    if not value:
        return None

    t = value.lower()
    year_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:year|years|yr|yrs)", t)
    if year_match:
        return max(1, round(float(year_match.group(1))))

    month_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:month|months)", t)
    if month_match:
        months = float(month_match.group(1))
        return max(1, round(months / 12))

    iso_match = re.search(r"p(\d+)y", t)
    if iso_match:
        return int(iso_match.group(1))

    return None


def normalize_level(level: Optional[str]) -> Optional[str]:
    if not level:
        return None
    l = level.strip().lower()
    if "bachelor" in l or "undergraduate" in l:
        return "bachelor"
    if "master" in l or "graduate" in l:
        return "master"
    if "phd" in l or "doctor" in l:
        return "phd"
    return l


def build_program_id(source_url: str, name: Optional[str], university: Optional[str]) -> str:
    key = source_url or f"{name or ''}|{university or ''}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key.strip().lower()))


def infer_career_paths(field: Optional[str]) -> str:
    key = (field or "general").strip().lower()
    return CAREER_HINTS.get(key, CAREER_HINTS["general"])


def is_listing_or_homepage(source_url: str) -> bool:
    parsed = urlparse(source_url)
    path = parsed.path.lower().rstrip("/")
    if not path or path in {"", "/en", "/study", "/studies", "/education"}:
        return True
    if parsed.query and any(key in parsed.query.lower() for key in ["code=", "query="]):
        return True
    return False


def looks_like_course(name: str, source_url: str) -> bool:
    lower_name = name.lower()
    lower_url = source_url.lower()
    if any(marker in lower_url for marker in ["/course/", "/courses/", "/kurs/", "coursecatalogue"]):
        return True
    if any(marker in lower_name for marker in ["course", "kurs", "part i", "part ii", "module"]):
        return True
    return False


def looks_like_program(name: str, source_url: str) -> bool:
    lower_name = name.lower()
    lower_url = source_url.lower()
    if is_listing_or_homepage(source_url):
        return False
    if any(marker in lower_name for marker in ["programme", "program", "degree", "bachelor", "master"]):
        return True
    if any(marker in lower_url for marker in ["/programme", "/program", "/programmes", "/utbildning"]):
        return True
    return not looks_like_course(name, source_url)


def to_db_record(item: Dict) -> Optional[Dict]:
    name = clean_text(item.get("name"))
    university = clean_text(item.get("university"))
    source_url = normalize_source_url(clean_text(item.get("source_url")))

    if not name or not university or not is_valid_source_url(source_url):
        return None
    if looks_like_course(name, source_url):
        return None
    if not looks_like_program(name, source_url):
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    field = infer_primary_field(
        name or "",
        clean_text(item.get("description")) or "",
        clean_text(item.get("career_paths")) or "",
    )

    return {
        "id": build_program_id(source_url, name, university),
        "name": name,
        "university": university,
        "city": normalize_city(clean_text(item.get("city"))),
        "country": normalize_country(clean_text(item.get("country")) or "Sweden"),
        "level": normalize_level(clean_text(item.get("level"))),
        "language": normalize_language(clean_text(item.get("language")) or "English"),
        "duration_years": parse_duration_years(clean_text(item.get("duration"))),
        "study_pace": normalize_study_pace(clean_text(item.get("study_pace"))),
        "field": field,
        "description": clean_text(item.get("description")),
        "career_paths": clean_text(item.get("career_paths")) or infer_career_paths(field),
        "tuition_eu": clean_text(item.get("tuition_eu")),
        "tuition_non_eu": clean_text(item.get("tuition_non_eu")),
        "source_url": source_url,
        "last_updated": now_iso,
    }


def parse() -> List[Dict]:
    if not RAW.exists():
        raise FileNotFoundError(f"Missing input file: {RAW}")

    raw_payload = json.loads(RAW.read_text(encoding="utf-8"))
    if isinstance(raw_payload, dict):
        raw_programs = raw_payload.get("programs", [])
    elif isinstance(raw_payload, list):
        raw_programs = raw_payload
    else:
        raw_programs = []

    programs: List[Dict] = []
    seen_ids = set()

    for item in raw_programs:
        record = to_db_record(item)
        if not record:
            continue

        if record["id"] in seen_ids:
            continue

        seen_ids.add(record["id"])
        programs.append(record)

    OUT.write_text(json.dumps(programs, indent=2), encoding="utf-8")
    print(f"Saved {len(programs)} database-ready programs to {OUT}")
    return programs


if __name__ == "__main__":
    parse()
