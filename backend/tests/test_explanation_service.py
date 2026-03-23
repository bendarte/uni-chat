"""Unit tests for ExplanationService.

The explanation generator is deterministic (hash-based variant selection)
and has no external dependencies. These tests verify the contract: always
returns exactly 3 bullets, bullets are non-empty strings, and interest/
city/level/language matches are reflected when present.
"""

import pytest

from app.services.explanation_service import ExplanationService


def make_program(**kwargs) -> dict:
    defaults = {
        "program_id": "aaaa-bbbb",
        "name": "MSc Data Science",
        "university": "KTH Royal Institute of Technology",
        "city": "Stockholm",
        "level": "master",
        "language": "english",
        "study_pace": "full-time",
        "field": "Data Science",
        "description": "Learn machine learning and statistics.",
        "career_paths": "Data scientist, ML engineer",
        "tracks": [],
        "domains": ["tech"],
    }
    defaults.update(kwargs)
    return defaults


def make_profile(**kwargs) -> dict:
    defaults = {
        "interests": [],
        "career_goals": [],
        "preferred_cities": [],
        "study_level": None,
        "language": None,
        "study_pace": None,
        "current_tracks": [],
        "selected_guidance_option": None,
    }
    defaults.update(kwargs)
    return defaults


class TestBuildBullets:
    def test_always_returns_three_bullets(self):
        profile = make_profile()
        program = make_program()
        bullets = ExplanationService._build_bullets(profile, program)
        assert len(bullets) == 3

    def test_bullets_are_non_empty_strings(self):
        profile = make_profile()
        program = make_program()
        bullets = ExplanationService._build_bullets(profile, program)
        assert all(isinstance(b, str) and b.strip() for b in bullets)

    def test_no_duplicate_bullets(self):
        profile = make_profile()
        program = make_program()
        bullets = ExplanationService._build_bullets(profile, program)
        assert len(bullets) == len(set(b.lower() for b in bullets))

    def test_interest_match_included_when_relevant(self):
        profile = make_profile(interests=["machine learning"])
        program = make_program(description="Advanced machine learning techniques.")
        bullets = ExplanationService._build_bullets(profile, program)
        full_text = " ".join(bullets).lower()
        assert "machine learning" in full_text

    def test_city_match_included(self):
        profile = make_profile(preferred_cities=["Stockholm"])
        program = make_program(city="Stockholm")
        bullets = ExplanationService._build_bullets(profile, program)
        full_text = " ".join(bullets).lower()
        assert "stockholm" in full_text

    def test_level_match_included(self):
        profile = make_profile(study_level="master")
        program = make_program(level="master")
        bullets = ExplanationService._build_bullets(profile, program)
        full_text = " ".join(bullets).lower()
        assert "master" in full_text

    def test_language_match_included(self):
        profile = make_profile(language="english")
        program = make_program(language="english")
        bullets = ExplanationService._build_bullets(profile, program)
        full_text = " ".join(bullets).lower()
        assert "engelska" in full_text

    def test_deterministic_output(self):
        profile = make_profile(interests=["AI"])
        program = make_program()
        first = ExplanationService._build_bullets(profile, program)
        second = ExplanationService._build_bullets(profile, program)
        assert first == second


class TestGenerateProgramExplanation:
    def test_returns_required_keys(self):
        svc = ExplanationService()
        result = svc.generate_program_explanation(
            user_profile=make_profile(),
            program=make_program(),
        )
        assert "program_id" in result
        assert "source_id" in result
        assert "program" in result
        assert "university" in result
        assert "explanation" in result

    def test_explanation_has_three_items(self):
        svc = ExplanationService()
        result = svc.generate_program_explanation(
            user_profile=make_profile(),
            program=make_program(),
        )
        assert len(result["explanation"]) == 3

    def test_source_id_format(self):
        svc = ExplanationService()
        result = svc.generate_program_explanation(
            user_profile=make_profile(),
            program=make_program(program_id="aaaa-bbbb-cccc"),
        )
        assert result["source_id"].startswith("ref-")
