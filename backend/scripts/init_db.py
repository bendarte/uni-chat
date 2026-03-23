import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import Base, engine
from app import models  # noqa: F401
from app.qdrant_client import ensure_program_collection


def init() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_program_collection()
    print("Initialized PostgreSQL tables and Qdrant collection")


if __name__ == "__main__":
    init()
