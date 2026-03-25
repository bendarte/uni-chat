import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import Program
from app.services.metadata_normalization import (
    normalize_city,
    normalize_country,
    normalize_language,
    normalize_study_pace,
    normalize_university,
)
from app.services.source_validation import normalize_source_url
from scripts.load_dataset import (
    delete_program_collection,
    embed_programs,
    get_active_program_collection_name,
    publish_program_collection,
)


def _serialize_program(row: Any) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "name": str(row.name or "").strip(),
        "university": normalize_university(row.university) or str(row.university or "").strip(),
        "city": normalize_city(row.city),
        "country": normalize_country(row.country),
        "level": str(row.level or "").strip().lower() or None,
        "language": normalize_language(row.language),
        "duration_years": row.duration_years,
        "study_pace": normalize_study_pace(row.study_pace),
        "field": str(row.field or "").strip() or None,
        "description": str(row.description or "").strip() or None,
        "career_paths": str(row.career_paths or "").strip() or None,
        "tuition_eu": row.tuition_eu,
        "tuition_non_eu": row.tuition_non_eu,
        "source_url": normalize_source_url(row.source_url),
    }


def plan_university_backfill(rows: Iterable[Any]) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    updates: List[Dict[str, str]] = []
    programs: List[Dict[str, Any]] = []

    for row in rows:
        current = str(row.university or "").strip()
        normalized = normalize_university(current) or current
        if current and normalized and current != normalized:
            updates.append(
                {
                    "program_id": str(row.id),
                    "from": current,
                    "to": normalized,
                }
            )
        programs.append(_serialize_program(row))

    return updates, programs


def apply_university_backfill() -> Dict[str, Any]:
    with SessionLocal() as db:
        rows = db.query(Program).all()
        updates, programs = plan_university_backfill(rows)
        if updates:
            update_map = {item["program_id"]: item["to"] for item in updates}
            for row in rows:
                replacement = update_map.get(str(row.id))
                if replacement:
                    row.university = replacement
            db.commit()
        return {
            "checked": len(rows),
            "updated": len(updates),
            "updates": updates,
            "programs": programs,
        }


def republish_qdrant_from_db(programs: List[Dict[str, Any]]) -> Dict[str, Any]:
    previous_collection = get_active_program_collection_name()
    target_collection, embedded_rows = embed_programs(programs)
    published = False

    if target_collection and embedded_rows:
        publish_program_collection(target_collection)
        published = True
        if previous_collection and previous_collection != target_collection:
            delete_program_collection(previous_collection)

    return {
        "previous_collection": previous_collection,
        "target_collection": target_collection,
        "embedded_rows": embedded_rows,
        "published": published,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill canonical university labels in Postgres and optionally republish Qdrant.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned updates without writing to Postgres.")
    parser.add_argument("--republish-qdrant", action="store_true", help="Re-embed and republish Qdrant from the normalized Postgres data.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args()

    with SessionLocal() as db:
        rows = db.query(Program).all()
        updates, programs = plan_university_backfill(rows)

    result: Dict[str, Any] = {
        "checked": len(programs),
        "updated": len(updates),
        "updates": updates,
    }

    if not args.dry_run:
        applied = apply_university_backfill()
        result["checked"] = applied["checked"]
        result["updated"] = applied["updated"]
        result["updates"] = applied["updates"]
        programs = applied["programs"]

    if args.republish_qdrant:
        result["qdrant"] = republish_qdrant_from_db(programs)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    mode = "dry-run" if args.dry_run else "applied"
    print(f"University backfill {mode}: {result['updated']} updates across {result['checked']} programs.")
    for item in result["updates"][:10]:
        print(f"  {item['from']} -> {item['to']} ({item['program_id']})")
    if len(result["updates"]) > 10:
        print(f"  ... {len(result['updates']) - 10} more")
    if "qdrant" in result:
        q = result["qdrant"]
        print(
            "Qdrant republish: "
            f"published={q['published']}, embedded_rows={q['embedded_rows']}, "
            f"target_collection={q['target_collection']}"
        )


if __name__ == "__main__":
    main()
