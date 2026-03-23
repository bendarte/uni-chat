import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI
from qdrant_client.models import PointStruct

from app.config import settings
from app.qdrant_client import (
    PROGRAMS_COLLECTION_NAME,
    ensure_program_collection,
    get_qdrant_client,
)
from app.services.language_normalization import build_topic_bridge, infer_topics_from_text
from app.services.source_validation import is_valid_source_url, normalize_source_url

PARSED = Path(__file__).resolve().parent / "programs_parsed.json"
EMBED_BATCH_SIZE = int(os.getenv("OPENAI_EMBED_BATCH_SIZE", "100"))
QDRANT_BATCH_SIZE = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", "256"))


def chunks(items: List[Dict], size: int) -> Iterable[List[Dict]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def create_embeddings(client: OpenAI, texts: List[str]) -> List[List[float]]:
    result = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in result.data]


def to_embedding_text(program: Dict) -> str:
    topics = infer_topics_from_text(
        program.get("name", ""),
        program.get("field", ""),
        program.get("description", ""),
        program.get("career_paths", ""),
    )
    topic_bridge = build_topic_bridge(topics)
    return (
        f"Program: {program.get('name', '')}. "
        f"University: {program.get('university', '')}. "
        f"City: {program.get('city', '')}. "
        f"Level: {program.get('level', '')}. "
        f"Language: {program.get('language', '')}. "
        f"Study pace: {program.get('study_pace', '')}. "
        f"Description: {program.get('description', '')}. "
        f"Career paths: {program.get('career_paths', '')}. "
        f"Field: {program.get('field', '')}. "
        f"Topic bridge: {topic_bridge}."
    )


def embed_programs() -> int:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set.")
    if not PARSED.exists():
        raise FileNotFoundError(f"Missing input file: {PARSED}")

    programs = json.loads(PARSED.read_text(encoding="utf-8"))
    programs = [
        p for p in programs if is_valid_source_url(normalize_source_url(p.get("source_url")))
    ]
    if not programs:
        print("No programs found for embedding")
        return 0

    ensure_program_collection()
    qdrant = get_qdrant_client()
    openai_client = OpenAI(api_key=settings.openai_api_key)

    total_upserted = 0
    for program_batch in chunks(programs, EMBED_BATCH_SIZE):
        texts = [to_embedding_text(item) for item in program_batch]
        vectors = create_embeddings(openai_client, texts)

        points: List[PointStruct] = []
        for item, vector, text in zip(program_batch, vectors, texts):
            program_id = str(item["id"])
            payload = {
                "program_id": program_id,
                "university": item.get("university"),
                "country": item.get("country"),
                "city": item.get("city"),
                "level": item.get("level"),
                "language": item.get("language"),
                "study_pace": item.get("study_pace"),
                "field": item.get("field"),
                "text": text,
                "name": item.get("name"),
                "description": item.get("description"),
                "career_paths": item.get("career_paths"),
                "source_url": normalize_source_url(item.get("source_url")),
            }
            points.append(PointStruct(id=program_id, vector=vector, payload=payload))

        for upsert_batch in chunks(points, QDRANT_BATCH_SIZE):
            qdrant.upsert(collection_name=PROGRAMS_COLLECTION_NAME, points=upsert_batch)
            total_upserted += len(upsert_batch)

    print(f"Embedded and upserted {total_upserted} programs into Qdrant")
    return total_upserted


if __name__ == "__main__":
    embed_programs()
