import logging
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    Distance,
    PayloadSchemaType,
    VectorParams,
)

from app.config import settings
from app.logging_utils import log_event

PROGRAMS_COLLECTION_NAME = "programs_active"
PROGRAMS_COLLECTION_PREFIX = "programs"
OPENAI_EMBEDDING_VECTOR_SIZE = 1536


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def _collection_exists(client: QdrantClient, collection_name: str) -> bool:
    try:
        client.get_collection(collection_name)
        return True
    except UnexpectedResponse:
        return False


def _ensure_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    for field_name in ("city", "level", "language", "study_pace", "field", "domains", "tracks"):
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            continue


def create_program_collection(
    collection_name: str,
    vector_size: int = OPENAI_EMBEDDING_VECTOR_SIZE,
) -> None:
    client = get_qdrant_client()
    if not _collection_exists(client, collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    _ensure_payload_indexes(client, collection_name)


def ensure_program_collection(vector_size: int = OPENAI_EMBEDDING_VECTOR_SIZE) -> None:
    client = get_qdrant_client()
    if _collection_exists(client, PROGRAMS_COLLECTION_NAME):
        return

    bootstrap_collection = f"{PROGRAMS_COLLECTION_PREFIX}_bootstrap"
    create_program_collection(bootstrap_collection, vector_size=vector_size)
    client.update_collection_aliases(
        change_aliases_operations=[
            CreateAliasOperation(
                create_alias=CreateAlias(
                    collection_name=bootstrap_collection,
                    alias_name=PROGRAMS_COLLECTION_NAME,
                )
            )
        ]
    )


def publish_program_collection(collection_name: str) -> None:
    client = get_qdrant_client()
    operations = []
    if _collection_exists(client, PROGRAMS_COLLECTION_NAME):
        operations.append(
            DeleteAliasOperation(
                delete_alias=DeleteAlias(alias_name=PROGRAMS_COLLECTION_NAME)
            )
        )
    operations.append(
        CreateAliasOperation(
            create_alias=CreateAlias(
                collection_name=collection_name,
                alias_name=PROGRAMS_COLLECTION_NAME,
            )
        )
    )
    client.update_collection_aliases(change_aliases_operations=operations)


def delete_program_collection(collection_name: str) -> None:
    if not collection_name or collection_name == PROGRAMS_COLLECTION_NAME:
        return
    client = get_qdrant_client()
    try:
        client.delete_collection(collection_name=collection_name)
    except Exception as exc:
        log_event(
            logging.getLogger(__name__),
            "warning",
            "qdrant_delete_collection_failed",
            collection_name=collection_name,
            error=str(exc),
        )
