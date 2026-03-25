import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from app.services.language_normalization import infer_primary_field
from app.services.metadata_normalization import (
    normalize_city,
    normalize_country,
    normalize_language,
    normalize_study_pace,
    normalize_university,
)

RAW_OUTPUT = Path(__file__).resolve().parent / "programs_raw.json"

SOURCE_CONFIGS = [
    {
        "source": "universityadmissions.se",
        "type": "api",
        "api_url": "https://www.universityadmissions.se/intl/api/sok",
        "language_default": "English",
    },
    {
        "source": "antagning.se",
        "type": "api",
        "api_url": "https://www.antagning.se/se/api/sok",
        "language_default": "Swedish",
    },
    {
        "source": "bachelorsportal.com",
        "type": "html",
        "seed_url": "https://www.bachelorsportal.com/search/bachelor",
        "default_level": "bachelor",
    },
    {
        "source": "mastersportal.com",
        "type": "html",
        "seed_url": "https://www.mastersportal.com/search/master",
        "default_level": "master",
    },
]

REQUEST_TIMEOUT_SECONDS = int(os.getenv("CRAWL_TIMEOUT_SECONDS", "30"))
MAX_API_PAGES_PER_SOURCE = int(os.getenv("MAX_API_PAGES_PER_SOURCE", "25"))
TARGET_RECORDS = int(os.getenv("CRAWL_TARGET_RECORDS", "400"))
MIN_PROGRAM_CREDITS = float(os.getenv("MIN_PROGRAM_CREDITS", "60"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
}


def clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def strip_xssi_prefix(text: str) -> str:
    t = text.strip()
    if t.startswith(")]}'"):
        return t.split("\n", 1)[1] if "\n" in t else "{}"
    return t


def normalize_level(value: str) -> str:
    v = value.lower()
    if "bachelor" in v or "undergraduate" in v:
        return "bachelor"
    if "master" in v or "graduate" in v:
        return "master"
    if "phd" in v or "doctoral" in v:
        return "phd"
    return "unknown"


def credits_to_duration(credits: Optional[str]) -> str:
    if not credits:
        return ""
    try:
        value = float(str(credits).replace(",", "."))
    except Exception:
        return ""

    years = value / 60.0
    if years <= 1:
        return "1 year"
    if years <= 2:
        return "2 years"
    if years <= 3:
        return "3 years"
    return f"{round(years)} years"


def credits_to_float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def is_listing_or_homepage(source_url: str) -> bool:
    parsed = urlparse(source_url)
    path = parsed.path.lower().rstrip("/")
    if not path or path in {"", "/en", "/study", "/studies", "/education"}:
        return True
    if parsed.query and any(key in parsed.query.lower() for key in ["code=", "query="]):
        return True
    return False


def looks_like_course(name: str, source_url: str, credits: Optional[float]) -> bool:
    lower_name = name.lower()
    lower_url = source_url.lower()

    if any(marker in lower_url for marker in ["/course/", "/courses/", "/kurs/", "coursecatalogue"]):
        return True
    if any(marker in lower_name for marker in ["course", "kurs", "part i", "part ii", "module"]):
        return True
    if credits is not None and credits < MIN_PROGRAM_CREDITS:
        return True
    return False


def looks_like_program(name: str, source_url: str, credits: Optional[float], duration: str) -> bool:
    lower_name = name.lower()
    lower_url = source_url.lower()

    if is_listing_or_homepage(source_url):
        return False

    if any(marker in lower_name for marker in ["programme", "program", "degree", "bachelor", "master"]):
        return True
    if any(marker in lower_url for marker in ["/programme", "/program", "/programmes", "/utbildning"]):
        return True
    if credits is not None and credits >= MIN_PROGRAM_CREDITS:
        return True
    if duration and any(marker in duration for marker in ["1 year", "2 years", "3 years"]):
        return True

    return False


def parse_api_item(item: Dict, source: str, default_language: str) -> Optional[Dict[str, str]]:
    alt = item.get("anmalningsalternativ", {}) or {}
    source_url = clean_text(alt.get("kursbeskrivningUrl"))
    if not source_url.startswith("http"):
        return None

    name = clean_text(alt.get("titel"))
    university_raw = clean_text(alt.get("organisation"))
    university = normalize_university(university_raw) or university_raw
    city = normalize_city(clean_text(alt.get("studieort")))
    level_raw = clean_text(alt.get("utbildningsniva"))
    level = normalize_level(level_raw)
    language = normalize_language(clean_text(alt.get("undervisningssprak")) or default_language)
    field_candidates = alt.get("valdaAmnesNamn") or []
    subjects_text = ", ".join(clean_text(s) for s in field_candidates if clean_text(s))

    delivery = clean_text(alt.get("undervisningsform"))
    pace = clean_text(alt.get("studietakt"))
    study_time = clean_text(alt.get("undervisningstid"))
    credits = clean_text(alt.get("poang"))
    credits_value = credits_to_float(credits)
    study_pace = normalize_study_pace(pace or study_time)

    description_parts = [
        f"{name} at {university}." if name and university else name or university,
        f"Level: {level_raw}." if level_raw else "",
        f"Subject areas: {subjects_text}." if subjects_text else "",
        f"Pace: {pace}% {delivery}." if pace or delivery else "",
        f"Teaching time: {study_time}." if study_time else "",
    ]
    description = clean_text(" ".join(part for part in description_parts if part))

    field = infer_primary_field(name, subjects_text, description)
    duration = credits_to_duration(credits)

    parsed_url = urlparse(source_url)
    country = normalize_country("Sweden" if parsed_url.netloc.endswith(".se") else "")

    if not name or not university:
        return None
    if looks_like_course(name=name, source_url=source_url, credits=credits_value):
        return None
    if not looks_like_program(name=name, source_url=source_url, credits=credits_value, duration=duration):
        return None

    return {
        "source": source,
        "source_url": source_url,
        "name": name,
        "university": university,
        "city": city,
        "country": country,
        "level": level,
        "language": language,
        "description": description,
        "duration": duration,
        "study_pace": study_pace,
        "field": field,
        "career_paths": "",
    }


def crawl_api_source(config: Dict[str, str], target_records: int) -> Dict[str, List[Dict]]:
    programs: List[Dict] = []
    errors: List[Dict] = []
    api_url = config["api_url"]

    for page in range(1, MAX_API_PAGES_PER_SOURCE + 1):
        try:
            response = requests.post(
                api_url,
                headers=HEADERS,
                json={"sida": page},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = json.loads(strip_xssi_prefix(response.text))
            items = payload.get("sokresultatItems", [])
            if not items:
                break

            for item in items:
                parsed = parse_api_item(
                    item=item,
                    source=config["source"],
                    default_language=config.get("language_default", ""),
                )
                if parsed:
                    programs.append(parsed)

            if len(programs) >= target_records:
                break
        except Exception as exc:
            errors.append({"source": config["source"], "page": page, "error": str(exc)})
            break

    return {"programs": programs, "errors": errors}


def crawl_html_source(config: Dict[str, str]) -> Dict[str, List[Dict]]:
    # Best effort only: these sources often block scripted requests.
    errors: List[Dict] = []
    try:
        response = requests.get(
            config["seed_url"],
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        # If we can reach the page, the dedicated parser can be added later.
        return {"programs": [], "errors": errors}
    except Exception as exc:
        errors.append({"source": config["source"], "url": config["seed_url"], "error": str(exc)})
        return {"programs": [], "errors": errors}


def dedupe_programs(programs: List[Dict]) -> List[Dict]:
    unique: Dict[str, Dict] = {}
    for item in programs:
        key = clean_text(item.get("source_url", "")).lower()
        if not key:
            key = "|".join(
                [
                    clean_text(item.get("name", "")).lower(),
                    clean_text(item.get("university", "")).lower(),
                    clean_text(item.get("source", "")).lower(),
                ]
            )
        if key and key not in unique:
            unique[key] = item
    return list(unique.values())


def crawl() -> List[Dict]:
    all_programs: List[Dict] = []
    all_errors: List[Dict] = []

    remaining_target = TARGET_RECORDS
    for config in SOURCE_CONFIGS:
        if remaining_target <= 0:
            break

        if config.get("type") == "api":
            result = crawl_api_source(config, target_records=remaining_target)
        else:
            result = crawl_html_source(config)

        all_programs.extend(result["programs"])
        all_errors.extend(result["errors"])

        remaining_target = max(0, TARGET_RECORDS - len(all_programs))

    deduped_programs = dedupe_programs(all_programs)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [c["source"] for c in SOURCE_CONFIGS],
        "count": len(deduped_programs),
        "programs": deduped_programs,
        "errors": all_errors,
    }

    RAW_OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved {len(deduped_programs)} structured program records to {RAW_OUTPUT}")
    if all_errors:
        print(f"Encountered {len(all_errors)} crawl errors")

    return deduped_programs


if __name__ == "__main__":
    crawl()
