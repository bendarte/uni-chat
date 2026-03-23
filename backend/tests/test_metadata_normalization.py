"""Unit tests for metadata_normalization — the alias layer that converts user
input (e.g. "gbg", "su", "heltid") into canonical values used throughout the
retrieval pipeline."""

import pytest

from app.services.metadata_normalization import (
    normalize_city,
    normalize_language,
    normalize_study_pace,
    normalize_university,
)


class TestNormalizeCity:
    def test_known_alias_lowercase(self):
        assert normalize_city("stockholm") == "Stockholm"

    def test_known_alias_swedish_spelling(self):
        assert normalize_city("göteborg") == "Gothenburg"

    def test_canonical_value_passthrough(self):
        assert normalize_city("Gothenburg") == "Gothenburg"

    def test_unknown_city_returned_as_is(self):
        # Unknown cities pass through unchanged (normalization is best-effort, not a validator)
        assert normalize_city("atlantis") == "atlantis"

    def test_empty_string_returns_none(self):
        assert normalize_city("") is None

    def test_whitespace_only_returns_none(self):
        assert normalize_city("   ") is None

    def test_malmo_alias(self):
        assert normalize_city("malmö") == "Malmo"

    def test_linkoping_alias(self):
        result = normalize_city("linköping")
        assert result == "Linkoping"


class TestNormalizeLanguage:
    def test_english_variants(self):
        assert normalize_language("English") == "english"
        assert normalize_language("ENGLISH") == "english"
        assert normalize_language("engelska") == "english"

    def test_swedish_variants(self):
        assert normalize_language("Swedish") == "swedish"
        assert normalize_language("svenska") == "swedish"

    def test_unrecognized_returned_as_lowercase(self):
        # Unrecognized language values pass through lowercased, not as None
        assert normalize_language("mandarin") == "mandarin"

    def test_empty_returns_none(self):
        assert normalize_language("") is None


class TestNormalizeStudyPace:
    def test_full_time_variants(self):
        assert normalize_study_pace("full-time") == "full-time"
        assert normalize_study_pace("heltid") == "full-time"
        assert normalize_study_pace("100%") == "full-time"
        assert normalize_study_pace("full_time") == "full-time"

    def test_part_time_variants(self):
        assert normalize_study_pace("part-time") == "part-time"
        assert normalize_study_pace("deltid") == "part-time"
        assert normalize_study_pace("50%") == "part-time"
        assert normalize_study_pace("part_time") == "part-time"

    def test_unrecognized_returned_as_lowercase(self):
        # Unrecognized paces pass through lowercased
        assert normalize_study_pace("whenever") == "whenever"

    def test_empty_returns_none(self):
        assert normalize_study_pace("") is None


class TestNormalizeUniversity:
    def test_known_abbreviation(self):
        result = normalize_university("su")
        assert result is not None
        assert "Stockholm" in result

    def test_case_insensitive(self):
        result = normalize_university("KTH")
        assert result is not None

    def test_unrecognized_returned_as_is(self):
        # Unknown university names pass through unchanged
        assert normalize_university("harvard") == "harvard"

    def test_empty_returns_none(self):
        assert normalize_university("") is None
