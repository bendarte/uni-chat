import csv
import json
import math
import os
import re
import sys
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import requests
from openai import OpenAI
from qdrant_client.models import PointStruct
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import Base, SessionLocal, engine, ensure_program_schema
from app.models import Program
from app.qdrant_client import (
    PROGRAMS_COLLECTION_NAME,
    PROGRAMS_COLLECTION_PREFIX,
    create_program_collection,
    delete_program_collection,
    get_qdrant_client,
    publish_program_collection,
)
from app.services.guidance_tagging import annotate_guidance_item
from app.services.language_normalization import build_topic_bridge, infer_primary_field, infer_topics_from_text
from app.services.metadata_normalization import (
    normalize_city,
    normalize_language,
    normalize_study_pace,
    normalize_university,
)
from app.services.source_validation import is_valid_source_url, normalize_source_url

SEARCH_URL = "https://www.antagning.se/se/api/sok"
TERMS_URL = "https://www.antagning.se/se/api/sok/terminer"
RAW_DIR = ROOT / "ingestion" / "raw"
HTTP_TIMEOUT_SECONDS = int(os.getenv("ANTAGNING_TIMEOUT_SECONDS", "30"))
HTTP_RETRIES = int(os.getenv("ANTAGNING_HTTP_RETRIES", "3"))
HTTP_RETRY_DELAY_SECONDS = float(os.getenv("ANTAGNING_RETRY_DELAY_SECONDS", "1.5"))
HTTP_PAGE_DELAY_SECONDS = float(os.getenv("ANTAGNING_PAGE_DELAY_SECONDS", "0.05"))
DB_BATCH_SIZE = 500
EMBED_BATCH_SIZE = 100
QDRANT_BATCH_SIZE = 256

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def chunks(items: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def strip_xssi_prefix(text: str) -> str:
    payload = text.lstrip()
    if payload.startswith(")]}'"):
        return payload.split("\n", 1)[1] if "\n" in payload else "{}"
    return payload


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def clean_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    cleaned = []
    for value in values:
        text = clean_text(value)
        if text:
            cleaned.append(text)
    return cleaned


def format_sek(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        amount = int(float(value))
    except Exception:
        return clean_text(value)
    return f"{amount:,} SEK".replace(",", " ")


def fold_key_part(value: Optional[str]) -> str:
    text = clean_text(value) or ""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def build_canonical_key(
    name: Optional[str],
    university: Optional[str],
    level: Optional[str],
    city: Optional[str],
) -> str:
    return "|".join(
        [
            fold_key_part(name),
            fold_key_part(university),
            fold_key_part(level),
            fold_key_part(city),
        ]
    )


def build_program_id(source_url: Optional[str], canonical_key: str) -> str:
    stable_value = normalize_source_url(source_url) or f"antagning:{canonical_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, stable_value))


def parse_hp(value: Any) -> Optional[float]:
    text = clean_text(value)
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except Exception:
        return None


def hp_to_duration_years(value: Any) -> Optional[int]:
    hp_value = parse_hp(value)
    if not hp_value or hp_value <= 0:
        return None
    return max(1, round(hp_value / 60.0))


def normalize_level(value: Optional[str]) -> Optional[str]:
    text = (clean_text(value) or "").casefold()
    if not text:
        return None
    if "avancerad" in text or "master" in text:
        return "master"
    if "grund" in text or "kandidat" in text or "bachelor" in text:
        return "bachelor"
    if "forsk" in text or "doktor" in text or "phd" in text:
        return "phd"
    return None


def join_values(values: List[str]) -> Optional[str]:
    if not values:
        return None
    return ", ".join(values)


def build_description(raw: Dict[str, Any]) -> Optional[str]:
    subjects = clean_list(raw.get("valdaAmnesNamn"))
    degrees = clean_list(raw.get("examinaNamn"))
    prerequisites = clean_text((raw.get("forkunskapskrav") or {}).get("beskrivning"))
    level = clean_text(raw.get("utbildningsniva"))
    teaching = clean_text(raw.get("undervisningstid"))
    form = clean_text(raw.get("undervisningsform"))
    distance = clean_text(raw.get("distansBeskrivning"))
    hp_value = clean_text(raw.get("poang"))
    language = clean_text(raw.get("undervisningssprak"))
    term = clean_text(raw.get("antagningsomgangKod"))

    parts = []
    if level or hp_value or language:
        summary_bits = [bit for bit in [level, f"{hp_value} hp" if hp_value else None, language] if bit]
        parts.append(" / ".join(summary_bits))
    if subjects:
        parts.append(f"Ämnesområden: {', '.join(subjects)}.")
    if degrees:
        parts.append(f"Examina: {', '.join(degrees)}.")
    if teaching or form or distance:
        format_bits = [bit for bit in [teaching, form, distance] if bit]
        parts.append(f"Upplägg: {', '.join(format_bits)}.")
    if prerequisites:
        parts.append(f"Behörighet: {prerequisites}.")
    if term:
        parts.append(f"Antagningsomgång: {term}.")

    description = " ".join(parts).strip()
    return description or None


def build_career_paths(raw: Dict[str, Any]) -> Optional[str]:
    degrees = clean_list(raw.get("examinaNamn"))
    return join_values(degrees)


def quality_score(program: Dict[str, Any]) -> Tuple[int, int, int]:
    populated = sum(
        1
        for field in ("city", "level", "language", "study_pace", "field", "description", "career_paths")
        if program.get(field)
    )
    description_length = len(program.get("description") or "")
    url_score = 1 if is_valid_source_url(program.get("source_url")) else 0
    return (url_score, populated, description_length)


def flatten_raw_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    prerequisites = raw.get("forkunskapskrav") or {}
    return {
        "anmalningsalternativKod": clean_text(raw.get("anmalningsalternativKod")),
        "antagningsomgangKod": clean_text(raw.get("antagningsomgangKod")),
        "titel": clean_text(raw.get("titel")),
        "organisation": clean_text(raw.get("organisation")),
        "studieort": clean_text(raw.get("studieort")),
        "utbildningsniva": clean_text(raw.get("utbildningsniva")),
        "undervisningssprak": clean_text(raw.get("undervisningssprak")),
        "studietakt": raw.get("studietakt"),
        "undervisningstid": clean_text(raw.get("undervisningstid")),
        "undervisningsform": clean_text(raw.get("undervisningsform")),
        "poang": clean_text(raw.get("poang")),
        "poangEnhet": clean_text(raw.get("poangEnhet")),
        "valdaAmnesNamn": " | ".join(clean_list(raw.get("valdaAmnesNamn"))),
        "examinaNamn": " | ".join(clean_list(raw.get("examinaNamn"))),
        "forkunskapskrav": clean_text(prerequisites.get("beskrivning")),
        "studieavgiftTotal": raw.get("studieavgiftTotal"),
        "studieavgiftDelsumma": raw.get("studieavgiftDelsumma"),
        "kursbeskrivningUrl": clean_text(raw.get("kursbeskrivningUrl")),
        "distansBeskrivning": clean_text(raw.get("distansBeskrivning")),
        "program": raw.get("program"),
        "ar": raw.get("ar"),
        "startvecka": raw.get("startvecka"),
        "anmalningskod": clean_text(raw.get("anmalningskod")),
    }


def request_json(session: requests.Session, method: str, url: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    last_error = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            response = session.request(
                method=method,
                url=url,
                headers=HEADERS,
                json=payload,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return json.loads(strip_xssi_prefix(response.text))
        except Exception as exc:
            last_error = exc
            if attempt < HTTP_RETRIES:
                time.sleep(HTTP_RETRY_DELAY_SECONDS * attempt)
    raise RuntimeError(f"Antagning.se blockerade eller misslyckades: {last_error}") from last_error


def fetch_terms(session: requests.Session) -> List[Dict[str, Any]]:
    payload = request_json(session, "GET", TERMS_URL)
    terms = payload.get("terminer")
    return terms if isinstance(terms, list) else []


def fetch_raw_programs(session: requests.Session) -> Tuple[List[Dict[str, Any]], int]:
    first_page = request_json(session, "POST", SEARCH_URL, {"sida": 1})
    items = first_page.get("sokresultatItems") or []
    total_results = int(first_page.get("totaltAntalTraffar") or 0)
    per_page = max(1, len(items))
    total_pages = max(1, math.ceil(total_results / per_page))

    raw_programs: List[Dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        payload = first_page if page == 1 else request_json(session, "POST", SEARCH_URL, {"sida": page})
        page_items = payload.get("sokresultatItems") or []
        if not page_items:
            break

        for item in page_items:
            alternative = item.get("anmalningsalternativ") or {}
            if alternative.get("program") is True:
                raw_programs.append(alternative)

        print(f"Hämtade sida {page}/{total_pages} från antagning.se")
        time.sleep(HTTP_PAGE_DELAY_SECONDS)

    return raw_programs, total_results


def save_raw_snapshot(
    raw_programs: List[Dict[str, Any]],
    terms: List[Dict[str, Any]],
    total_results: int,
) -> Tuple[Path, Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    json_path = RAW_DIR / f"antagning_{timestamp}.json"
    csv_path = RAW_DIR / f"antagning_{timestamp}.csv"

    raw_payload = {
        "source": "antagning.se",
        "fetched_at": now_utc().isoformat(),
        "search_endpoint": SEARCH_URL,
        "terms_endpoint": TERMS_URL,
        "terms": terms,
        "total_search_results": total_results,
        "raw_program_records": raw_programs,
    }
    json_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = list(flatten_raw_row(raw_programs[0]).keys()) if raw_programs else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for raw in raw_programs:
            writer.writerow(flatten_raw_row(raw))

    return json_path, csv_path


def normalize_program(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = clean_text(raw.get("titel"))
    university_raw = clean_text(raw.get("organisation"))
    university = normalize_university(university_raw) or university_raw
    city = normalize_city(clean_text(raw.get("studieort")))
    level = normalize_level(clean_text(raw.get("utbildningsniva")))
    language = normalize_language(clean_text(raw.get("undervisningssprak")))
    study_pace = normalize_study_pace(clean_text(raw.get("studietakt")) or clean_text(raw.get("undervisningstid")))
    source_url = normalize_source_url(clean_text(raw.get("kursbeskrivningUrl")))
    description = build_description(raw)
    subjects_text = join_values(clean_list(raw.get("valdaAmnesNamn"))) or ""

    if not name or not university or not source_url:
        return None
    if not is_valid_source_url(source_url):
        return None

    canonical_key = build_canonical_key(name=name, university=university, level=level, city=city)
    return {
        "id": build_program_id(source_url=source_url, canonical_key=canonical_key),
        "canonical_key": canonical_key,
        "name": name,
        "university": university,
        "city": city,
        "country": "Sweden",
        "level": level,
        "language": language,
        "duration_years": hp_to_duration_years(raw.get("poang")),
        "study_pace": study_pace,
        "field": infer_primary_field(name, subjects_text, description or ""),
        "description": description,
        "career_paths": build_career_paths(raw),
        "tuition_eu": None,
        "tuition_non_eu": format_sek(raw.get("studieavgiftTotal")),
        "source_url": source_url,
    }


def dedupe_normalized(programs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    deduped: Dict[str, Dict[str, Any]] = {}
    duplicates_removed = 0
    for program in programs:
        key = program["canonical_key"]
        existing = deduped.get(key)
        if not existing:
            deduped[key] = program
            continue
        duplicates_removed += 1
        if quality_score(program) > quality_score(existing):
            deduped[key] = program
    return list(deduped.values()), duplicates_removed


def load_existing_signatures() -> Tuple[Set[str], Set[str]]:
    with SessionLocal() as db:
        rows = db.query(Program.id, Program.name, Program.university, Program.level, Program.city).all()
    canonical_keys = {
        build_canonical_key(name=name, university=university, level=level, city=city)
        for _, name, university, level, city in rows
    }
    existing_ids = {str(program_id) for program_id, _, _, _, _ in rows}
    return canonical_keys, existing_ids


def insert_programs(programs: List[Dict[str, Any]]) -> int:
    if not programs:
        return 0

    inserted_rows = 0
    with SessionLocal() as db:
        for batch in chunks(programs, DB_BATCH_SIZE):
            rows = []
            for item in batch:
                rows.append(
                    {
                        "id": uuid.UUID(item["id"]),
                        "name": item["name"],
                        "university": item["university"],
                        "city": item.get("city"),
                        "country": item.get("country"),
                        "level": item.get("level"),
                        "language": item.get("language"),
                        "duration_years": item.get("duration_years"),
                        "study_pace": item.get("study_pace"),
                        "field": item.get("field"),
                        "description": item.get("description"),
                        "career_paths": item.get("career_paths"),
                        "tuition_eu": item.get("tuition_eu"),
                        "tuition_non_eu": item.get("tuition_non_eu"),
                        "source_url": item.get("source_url"),
                    }
                )
            stmt = insert(Program).values(rows).on_conflict_do_nothing(index_elements=[Program.id])
            result = db.execute(stmt)
            inserted_rows += int(result.rowcount or 0)
        db.commit()
    return inserted_rows


def serialize_program(program: Program) -> Dict[str, Any]:
    return {
        "id": str(program.id),
        "name": program.name,
        "university": program.university,
        "country": program.country,
        "city": program.city,
        "level": program.level,
        "language": program.language,
        "study_pace": program.study_pace,
        "field": program.field,
        "description": program.description,
        "career_paths": program.career_paths,
        "source_url": program.source_url,
    }


def load_all_programs() -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.query(Program).order_by(Program.university.asc(), Program.name.asc()).all()
    return [serialize_program(row) for row in rows]


def get_program_count() -> int:
    with SessionLocal() as db:
        return int(db.query(func.count(Program.id)).scalar() or 0)


def get_active_program_collection_name() -> str:
    client = get_qdrant_client()
    try:
        aliases = client.get_aliases().aliases
    except Exception:
        return ""
    for alias in aliases:
        if alias.alias_name == PROGRAMS_COLLECTION_NAME:
            return str(alias.collection_name)
    return ""


def embed_programs(programs: List[Dict[str, Any]]) -> Tuple[str, int]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY saknas; kan inte embedda program till Qdrant.")

    target_collection = f"{PROGRAMS_COLLECTION_PREFIX}_{uuid.uuid4().hex[:12]}"
    create_program_collection(target_collection)
    qdrant = get_qdrant_client()
    client = OpenAI(api_key=settings.openai_api_key)

    embedded_rows = 0
    for batch in chunks(programs, EMBED_BATCH_SIZE):
        topic_bridges = [
            build_topic_bridge(
                infer_topics_from_text(
                    item["name"],
                    item.get("field") or "",
                    item.get("description") or "",
                    item.get("career_paths") or "",
                )
            )
            for item in batch
        ]
        texts = [
            (
                f"Program: {item['name']}. "
                f"University: {item.get('university') or ''}. "
                f"City: {item.get('city') or ''}. "
                f"Level: {item.get('level') or ''}. "
                f"Language: {item.get('language') or ''}. "
                f"Study pace: {item.get('study_pace') or ''}. "
                f"Description: {item.get('description') or ''}. "
                f"Career paths: {item.get('career_paths') or ''}. "
                f"Field: {item.get('field') or ''}. "
                f"Topic bridge: {topic_bridges[index]}."
            )
            for index, item in enumerate(batch)
        ]
        response = client.embeddings.create(
            model=settings.openai_embedding_model,
            input=texts,
        )
        vectors = [row.embedding for row in response.data]

        points: List[PointStruct] = []
        for item, vector, text in zip(batch, vectors, texts):
            guidance_item = annotate_guidance_item(item)
            payload = {
                "program_id": item["id"],
                "name": item["name"],
                "university": item["university"],
                "country": item.get("country"),
                "city": item.get("city"),
                "level": item.get("level"),
                "language": item.get("language"),
                "study_pace": item.get("study_pace"),
                "field": item.get("field"),
                "description": item.get("description"),
                "career_paths": item.get("career_paths"),
                "source_url": item.get("source_url"),
                "domains": guidance_item.get("domains", []),
                "tracks": guidance_item.get("tracks", []),
                "text": text,
            }
            points.append(PointStruct(id=item["id"], vector=vector, payload=payload))

        for point_batch in chunks(points, QDRANT_BATCH_SIZE):
            qdrant.upsert(collection_name=target_collection, points=point_batch)
            embedded_rows += len(point_batch)

    return target_collection, embedded_rows


def publish_embeddings(programs: List[Dict[str, Any]]) -> Tuple[int, str]:
    previous_collection = get_active_program_collection_name()
    target_collection, embedded_rows = embed_programs(programs)
    publish_program_collection(target_collection)
    if previous_collection and previous_collection != target_collection:
        delete_program_collection(previous_collection)

    count_response = get_qdrant_client().count(collection_name=PROGRAMS_COLLECTION_NAME, exact=True)
    return int(count_response.count or 0), target_collection


def run_import() -> Dict[str, Any]:
    Base.metadata.create_all(bind=engine)
    ensure_program_schema()

    session = requests.Session()
    terms = fetch_terms(session)
    raw_programs, total_results = fetch_raw_programs(session)
    if not raw_programs:
        raise RuntimeError("Antagning.se gav inga programposter att importera.")

    raw_json_path, raw_csv_path = save_raw_snapshot(raw_programs, terms, total_results)

    normalized_candidates = [normalize_program(raw) for raw in raw_programs]
    normalized = [item for item in normalized_candidates if item]
    deduped, batch_duplicates_removed = dedupe_normalized(normalized)

    existing_keys, existing_ids = load_existing_signatures()
    new_programs = [
        item
        for item in deduped
        if item["canonical_key"] not in existing_keys and item["id"] not in existing_ids
    ]
    existing_duplicates_removed = len(deduped) - len(new_programs)

    inserted_rows = insert_programs(new_programs)
    published_programs = load_all_programs()
    embeddings_in_qdrant, qdrant_collection = publish_embeddings(published_programs)
    total_in_postgres = get_program_count()

    summary = {
        "raw_json_path": str(raw_json_path.relative_to(ROOT)),
        "raw_csv_path": str(raw_csv_path.relative_to(ROOT)),
        "raw_records": len(raw_programs),
        "normalized_records": len(normalized),
        "batch_duplicates_removed": batch_duplicates_removed,
        "existing_duplicates_removed": existing_duplicates_removed,
        "duplicates_removed_total": batch_duplicates_removed + existing_duplicates_removed,
        "new_programs": inserted_rows,
        "total_in_postgres": total_in_postgres,
        "embeddings_in_qdrant": embeddings_in_qdrant,
        "qdrant_collection": qdrant_collection,
        "search_results_reported_by_antagning": total_results,
        "terms_discovered": len(terms),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    run_import()
