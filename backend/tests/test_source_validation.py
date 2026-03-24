"""Unit tests for source_validation — URL filtering and normalization.

These guard against junk URLs (empty, relative, course-catalogue paths)
reaching the frontend as clickable links.
"""

import pytest

from app.services.source_validation import is_valid_source_url, normalize_source_url


class TestNormalizeSourceUrl:
    def test_strips_whitespace(self):
        assert normalize_source_url("  https://example.com  ") == "https://example.com"

    def test_upgrades_http_to_https(self):
        assert normalize_source_url("http://example.com/program") == "https://example.com/program"

    def test_none_returns_empty(self):
        assert normalize_source_url(None) == ""

    def test_empty_returns_empty(self):
        assert normalize_source_url("") == ""

    def test_valid_url_unchanged(self):
        url = "https://www.kth.se/en/studies/master/computer-science"
        assert normalize_source_url(url) == url


class TestIsValidSourceUrl:
    def test_valid_https_url(self):
        assert is_valid_source_url("https://www.kth.se/en/studies/master/computer-science")

    def test_valid_http_url(self):
        assert is_valid_source_url("http://www.hb.se/en/programs/bachelor")

    def test_empty_string_invalid(self):
        assert not is_valid_source_url("")

    def test_none_invalid(self):
        assert not is_valid_source_url(None)

    def test_relative_url_invalid(self):
        assert not is_valid_source_url("/programs/123")

    def test_no_scheme_invalid(self):
        assert not is_valid_source_url("www.kth.se/program")

    def test_ftp_scheme_invalid(self):
        assert not is_valid_source_url("ftp://example.com/file")
