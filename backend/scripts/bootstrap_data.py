import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import Base, engine, ensure_program_schema
from app.qdrant_client import ensure_program_collection
from scripts.load_dataset import load_dataset


def bootstrap() -> dict:
    Base.metadata.create_all(bind=engine)
    ensure_program_schema()
    ensure_program_collection()
    result = load_dataset()
    return {
        "status": "ok",
        "stored_in_postgres": result.get("inserted_rows", 0),
        "embedded_in_qdrant": result.get("embedded_rows", 0),
        "total_programs": result.get("total_programs", 0),
        "db_count": result.get("db_count", 0),
    }


if __name__ == "__main__":
    print(json.dumps(bootstrap(), ensure_ascii=False))
