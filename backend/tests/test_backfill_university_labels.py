from types import SimpleNamespace
from uuid import uuid4

from scripts.backfill_university_labels import plan_university_backfill


def make_row(**kwargs):
    defaults = {
        "id": uuid4(),
        "name": "Datateknik",
        "university": "Chalmers University of Technology",
        "city": "Gothenburg",
        "country": "Sweden",
        "level": "master",
        "language": "English",
        "duration_years": 2,
        "study_pace": "100%",
        "field": "Computer Science",
        "description": "Program description",
        "career_paths": "Engineer",
        "tuition_eu": None,
        "tuition_non_eu": None,
        "source_url": "https://example.com/programs/datateknik",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_plan_university_backfill_flags_alias_updates():
    updates, programs = plan_university_backfill([make_row()])

    assert len(updates) == 1
    assert updates[0]["from"] == "Chalmers University of Technology"
    assert updates[0]["to"] == "Chalmers tekniska högskola"
    assert programs[0]["university"] == "Chalmers tekniska högskola"


def test_plan_university_backfill_skips_already_canonical_values():
    updates, programs = plan_university_backfill(
        [make_row(university="Chalmers tekniska högskola")]
    )

    assert updates == []
    assert programs[0]["university"] == "Chalmers tekniska högskola"
