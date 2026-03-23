"""Embed programs that exist in Postgres but are missing from the active Qdrant collection."""
import sys
import uuid
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI
from qdrant_client.models import PointStruct

from app.config import settings
from app.db import SessionLocal
from app.models import Program
from app.qdrant_client import PROGRAMS_COLLECTION_NAME, get_qdrant_client
from app.services.guidance_tagging import annotate_guidance_item
from app.services.language_normalization import build_topic_bridge, infer_topics_from_text
from app.services.metadata_normalization import normalize_city, normalize_language, normalize_study_pace
from app.services.source_validation import normalize_source_url


def get_qdrant_ids() -> set:
    client = get_qdrant_client()
    ids = set()
    offset = None
    while True:
        result, next_offset = client.scroll(
            collection_name=PROGRAMS_COLLECTION_NAME,
            limit=1000,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        for point in result:
            ids.add(str(point.id))
        if next_offset is None:
            break
        offset = next_offset
    return ids


def build_embedding_text(item: Dict) -> str:
    topic_bridge = build_topic_bridge(
        infer_topics_from_text(
            item.get("name", ""),
            item.get("field", ""),
            item.get("description", ""),
            item.get("career_paths", ""),
        )
    )
    return (
        f"Program: {item.get('name', '')}. "
        f"University: {item.get('university', '')}. "
        f"City: {item.get('city', '')}. "
        f"Level: {item.get('level', '')}. "
        f"Language: {item.get('language', '')}. "
        f"Study pace: {item.get('study_pace', '')}. "
        f"Description: {item.get('description', '')}. "
        f"Career paths: {item.get('career_paths', '')}. "
        f"Field: {item.get('field', '')}. "
        f"Topic bridge: {topic_bridge}."
    )


def embed_missing() -> int:
    if not settings.openai_api_key:
        print("OPENAI_API_KEY missing; cannot embed.")
        return 0

    qdrant_ids = get_qdrant_ids()
    print(f"Qdrant currently has {len(qdrant_ids)} programs.")

    with SessionLocal() as db:
        all_programs = db.query(Program).all()

    missing = [p for p in all_programs if str(p.id) not in qdrant_ids and p.source_url]
    print(f"Found {len(missing)} programs in Postgres not yet in Qdrant.")

    if not missing:
        print("Nothing to embed.")
        return 0

    client = OpenAI(api_key=settings.openai_api_key, timeout=30.0, max_retries=0)
    qdrant = get_qdrant_client()

    BATCH = 50
    embedded = 0
    for i in range(0, len(missing), BATCH):
        batch = missing[i : i + BATCH]
        items = [
            {
                "id": str(p.id),
                "name": p.name or "",
                "university": p.university or "",
                "city": normalize_city(p.city) or p.city or "",
                "country": p.country or "",
                "level": (p.level or "").lower(),
                "language": normalize_language(p.language) or "",
                "study_pace": normalize_study_pace(p.study_pace) or "",
                "field": p.field or "",
                "description": p.description or "",
                "career_paths": p.career_paths or "",
                "source_url": normalize_source_url(p.source_url) or p.source_url or "",
            }
            for p in batch
        ]
        texts = [build_embedding_text(item) for item in items]

        response = client.embeddings.create(model=settings.openai_embedding_model, input=texts)
        vectors = [x.embedding for x in response.data]

        points: List[PointStruct] = []
        for item, vector, text in zip(items, vectors, texts):
            annotated = annotate_guidance_item(item)
            payload = {
                "program_id": item["id"],
                "name": item["name"],
                "university": item["university"],
                "city": item["city"],
                "country": item["country"],
                "level": item["level"],
                "language": item["language"],
                "study_pace": item["study_pace"],
                "field": item["field"],
                "description": item["description"],
                "career_paths": item["career_paths"],
                "source_url": item["source_url"],
                "domains": annotated.get("domains", []),
                "tracks": annotated.get("tracks", []),
                "text": text,
            }
            points.append(PointStruct(id=item["id"], vector=vector, payload=payload))

        qdrant.upsert(collection_name=PROGRAMS_COLLECTION_NAME, points=points)
        embedded += len(points)
        print(f"  Embedded {embedded}/{len(missing)} programs...")

    print(f"Done. Embedded {embedded} new programs into Qdrant.")
    return embedded


if __name__ == "__main__":
    embed_missing()
