import json
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI
from qdrant_client.models import PointStruct
from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import Base, SessionLocal, engine
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
    normalize_country,
    normalize_language,
    normalize_study_pace,
    normalize_university,
)
from app.services.source_validation import is_valid_source_url, normalize_source_url
from ingestion.crawl_study_programs import crawl as crawl_programs
from ingestion.parse_programs import parse as parse_programs

DATASET_PATH = ROOT / "datasets" / "programs_dataset.json"
PARSED_PATH = ROOT / "ingestion" / "programs_parsed.json"
DB_BATCH_SIZE = 500
EMBED_BATCH_SIZE = 100
QDRANT_BATCH_SIZE = 256
MIN_PROGRAMS = int(os.getenv("INGEST_MIN_PROGRAMS", "100"))
TARGET_PROGRAMS = int(os.getenv("INGEST_TARGET_PROGRAMS", "400"))
ALLOW_SAMPLE_DATASET = os.getenv("ALLOW_SAMPLE_DATASET", "false").lower() == "true"
STALE_DELETE_MIN_RATIO = float(os.getenv("STALE_DELETE_MIN_RATIO", "0.80"))
QDRANT_PUBLISH_MIN_RATIO = float(os.getenv("QDRANT_PUBLISH_MIN_RATIO", "0.80"))


def chunks(items: List[Dict], size: int) -> Iterable[List[Dict]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def build_program_id(item: Dict) -> str:
    source_url = normalize_source_url(item.get("source_url"))
    key = source_url or "|".join(
        [
            str(item.get("name", "")).strip(),
            str(item.get("university", "")).strip(),
            str(item.get("city", "")).strip(),
            str(item.get("level", "")).strip(),
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key.lower()))


def to_duration_years(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
        if numeric <= 0:
            return None
        return max(1, round(numeric))
    except Exception:
        return None


def normalize_level(value, name: str = "", description: str = "") -> Optional[str]:
    text = " ".join(
        part.strip().lower()
        for part in [str(value or ""), str(name or ""), str(description or "")]
        if str(part or "").strip()
    )
    if not text:
        return None

    if any(marker in text for marker in ["master", "masterprogram", "master's", "avancerad nivå", "graduate"]):
        return "master"
    if any(marker in text for marker in ["bachelor", "kandidat", "kandidatprogram", "grundnivå", "undergraduate"]):
        return "bachelor"
    if any(marker in text for marker in ["phd", "doktor", "doctoral"]):
        return "phd"
    return None


def normalize_program(item: Dict) -> Dict:
    source_url = normalize_source_url(item.get("source_url"))
    name = str(item.get("name", "")).strip()
    description = str(item.get("description", "")).strip()
    return {
        "id": item.get("id") or build_program_id(item),
        "name": name,
        "university": normalize_university(str(item.get("university", "")).strip()) or str(item.get("university", "")).strip(),
        "city": normalize_city(str(item.get("city", "")).strip() or None),
        "country": normalize_country(str(item.get("country", "")).strip() or None),
        "level": normalize_level(item.get("level"), name=name, description=description),
        "language": normalize_language(str(item.get("language", "")).strip() or None),
        "duration_years": to_duration_years(item.get("duration_years")),
        "study_pace": normalize_study_pace(item.get("study_pace")),
        "field": infer_primary_field(
            name,
            description,
            str(item.get("career_paths", "")).strip(),
        ),
        "description": description or None,
        "career_paths": str(item.get("career_paths", "")).strip() or None,
        "tuition_eu": item.get("tuition_eu"),
        "tuition_non_eu": item.get("tuition_non_eu"),
        "source_url": source_url,
    }


def load_static_dataset() -> List[Dict]:
    if not ALLOW_SAMPLE_DATASET:
        return []
    if not DATASET_PATH.exists():
        return []
    raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [normalize_program(item) for item in raw]


def load_crawled_dataset() -> List[Dict]:
    crawl_programs()
    parsed = parse_programs()
    return [normalize_program(item) for item in parsed]


def combine_programs() -> List[Dict]:
    programs: List[Dict] = []

    if PARSED_PATH.exists():
        try:
            parsed_cached = json.loads(PARSED_PATH.read_text(encoding="utf-8"))
            programs.extend(normalize_program(item) for item in parsed_cached if isinstance(item, dict))
        except Exception:
            pass

    valid_count = sum(1 for p in programs if is_valid_source_url(p.get("source_url")))
    if valid_count < MIN_PROGRAMS:
        crawled = load_crawled_dataset()
        programs.extend(crawled)

    if not programs:
        programs.extend(load_static_dataset())

    deduped: Dict[str, Dict] = {}
    for row in programs:
        if not row.get("name") or not row.get("university"):
            continue
        if not is_valid_source_url(row.get("source_url")):
            continue
        deduped[row["id"]] = row

    merged = list(deduped.values())
    merged.sort(key=lambda x: (x.get("source_url") or "", x.get("name") or ""))

    if TARGET_PROGRAMS > 0:
        merged = merged[:TARGET_PROGRAMS]

    return merged


def upsert_programs(programs: List[Dict]) -> int:
    inserted_rows = 0
    with SessionLocal() as db:
        for batch in chunks(programs, DB_BATCH_SIZE):
            rows = []
            for item in batch:
                row = {**item}
                row["id"] = uuid.UUID(item["id"])
                rows.append(row)

            stmt = insert(Program).values(rows)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=[Program.id],
                set_={
                    "name": stmt.excluded.name,
                    "university": stmt.excluded.university,
                    "city": stmt.excluded.city,
                    "country": stmt.excluded.country,
                    "level": stmt.excluded.level,
                    "language": stmt.excluded.language,
                    "duration_years": stmt.excluded.duration_years,
                    "study_pace": stmt.excluded.study_pace,
                    "field": stmt.excluded.field,
                    "description": stmt.excluded.description,
                    "career_paths": stmt.excluded.career_paths,
                    "tuition_eu": stmt.excluded.tuition_eu,
                    "tuition_non_eu": stmt.excluded.tuition_non_eu,
                    "source_url": stmt.excluded.source_url,
                },
            )
            db.execute(upsert_stmt)
            inserted_rows += len(rows)
        db.commit()

    return inserted_rows


def delete_stale_programs(programs: List[Dict]) -> int:
    current_count = get_program_count()
    if not current_count:
        return 0

    min_expected = max(1, int(current_count * STALE_DELETE_MIN_RATIO))
    if len(programs) < min_expected:
        print(
            f"Safety guard active: skipping deletion of stale rows. "
            f"Incoming programs ({len(programs)}) < {int(STALE_DELETE_MIN_RATIO * 100)}% of current DB rows ({current_count})."
        )
        return 0

    retained_ids = [uuid.UUID(item["id"]) for item in programs]
    with SessionLocal() as db:
        if retained_ids:
            result = db.execute(delete(Program).where(Program.id.not_in(retained_ids)))
        else:
            result = db.execute(delete(Program))
        db.commit()
    return int(result.rowcount or 0)


def embed_programs(programs: List[Dict]) -> tuple[str, int]:
    if not settings.openai_api_key:
        print("OPENAI_API_KEY missing; skipped embeddings")
        return "", 0

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
        vectors = [x.embedding for x in response.data]

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


def get_program_count() -> int:
    with SessionLocal() as db:
        count = db.query(func.count(Program.id)).scalar() or 0
    return int(count)


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


def load_dataset() -> Dict[str, int]:
    Base.metadata.create_all(bind=engine)

    programs = combine_programs()
    inserted_rows = upsert_programs(programs)
    previous_collection = get_active_program_collection_name()
    target_collection, embedded_rows = embed_programs(programs)
    deleted_rows = 0
    published = False

    min_publishable_rows = max(1, int(len(programs) * QDRANT_PUBLISH_MIN_RATIO)) if programs else 0
    if target_collection and embedded_rows >= min_publishable_rows:
        publish_program_collection(target_collection)
        published = True
        deleted_rows = delete_stale_programs(programs)
        if previous_collection and previous_collection != target_collection:
            delete_program_collection(previous_collection)
    elif target_collection:
        print(
            f"Skipping alias publish: embedded_rows={embedded_rows}, "
            f"required_minimum={min_publishable_rows}."
        )
        delete_program_collection(target_collection)

    print(f"Programs inserted/updated in PostgreSQL: {inserted_rows}")
    print(f"Embeddings stored in Qdrant: {embedded_rows}")
    print(f"Qdrant alias published: {published}")
    print(f"Stale PostgreSQL rows deleted: {deleted_rows}")

    return {
        "total_programs": len(programs),
        "inserted_rows": inserted_rows,
        "embedded_rows": embedded_rows,
        "db_count": get_program_count(),
    }


if __name__ == "__main__":
    load_dataset()
