import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.crawl_study_programs import crawl
from ingestion.parse_programs import parse
from scripts.load_dataset import load_dataset


def ingest_all() -> Dict[str, int]:
    crawled_records = crawl()
    parsed_records = parse()
    result = load_dataset()
    return {
        "crawled": len(crawled_records),
        "parsed": len(parsed_records),
        "stored_in_postgres": result["inserted_rows"],
        "embedded_in_qdrant": result["embedded_rows"],
        "total_programs": result["total_programs"],
        "db_count": result["db_count"],
    }


if __name__ == "__main__":
    print(ingest_all())
