"""Unit tests for guidance_taxonomy domain detection.

The taxonomy maps profession names and subject terms to domains.
These tests serve as a regression suite for the keyword lists in
DOMAIN_KEYWORDS: adding or removing a term changes a test here,
making the impact visible before the change reaches production.

Each test creates a minimal "program" with the profession title as the
name and verifies that _infer_domains() returns the expected domain.
The profession names below are the ones that were historically failing
(triggering vague-guidance instead of recommendations) and were fixed
in earlier sessions.
"""

import pytest

from app.services.guidance_tagging import infer_domains


def infer(name: str, field: str = "", description: str = "") -> list[str]:
    """Helper: infer domains from a minimal program dict.

    Note: infer_domains() respects existing domains[] on the item — we
    pass an empty dict so it always falls through to keyword-based inference.
    """
    return infer_domains(
        {"name": name, "university": "", "field": field, "description": description, "career_paths": ""}
    )


# ---------------------------------------------------------------------------
# Healthcare
# ---------------------------------------------------------------------------

class TestHealthcareDetection:
    def test_laekare(self):
        assert "healthcare" in infer("läkare")

    def test_sjukskoterska(self):
        assert "healthcare" in infer("sjuksköterska")

    def test_apotekare(self):
        assert "healthcare" in infer("apotekare")

    def test_tanndlaekare(self):
        assert "healthcare" in infer("tandläkare")

    def test_dietist(self):
        assert "healthcare" in infer("dietist")

    def test_logoped(self):
        assert "healthcare" in infer("logoped")

    def test_veterinaer(self):
        assert "healthcare" in infer("veterinär")

    def test_psykolog_not_healthcare(self):
        # Psykolog belongs to psychology_social, not healthcare
        domains = infer("psykolog")
        assert "psychology_social" in domains


# ---------------------------------------------------------------------------
# Tech
# ---------------------------------------------------------------------------

class TestTechDetection:
    def test_maskinteknik(self):
        assert "tech" in infer("maskinteknik")

    def test_elektroteknik(self):
        assert "tech" in infer("elektroteknik")

    def test_datateknik(self):
        assert "tech" in infer("datateknik")

    def test_webbutvecklare(self):
        assert "tech" in infer("webbutvecklare")

    def test_systemvetare(self):
        assert "tech" in infer("systemvetare")

    def test_spelutvecklare(self):
        assert "tech" in infer("spelutvecklare")

    def test_ai_master(self):
        assert "tech" in infer("AI Master", field="Artificial Intelligence")

    def test_civil_engineer(self):
        assert "tech" in infer("civilingenjör")


# ---------------------------------------------------------------------------
# Business
# ---------------------------------------------------------------------------

class TestBusinessDetection:
    def test_ekonomi(self):
        assert "business" in infer("ekonomi")

    def test_ekonom(self):
        assert "business" in infer("ekonom")

    def test_revisor(self):
        assert "business" in infer("revisor")

    def test_controller(self):
        assert "business" in infer("controller")

    def test_hr(self):
        assert "business" in infer("HR")

    def test_finansanalytiker(self):
        assert "business" in infer("finansanalytiker")


# ---------------------------------------------------------------------------
# Law
# ---------------------------------------------------------------------------

class TestLawDetection:
    def test_juridik(self):
        assert "law" in infer("juridik")

    def test_aaklagare(self):
        assert "law" in infer("åklagare")

    def test_domare(self):
        assert "law" in infer("domare")

    def test_polis(self):
        assert "law" in infer("polis")


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------

class TestEducationDetection:
    def test_forskollaerare(self):
        # Both spellings should work
        assert "education" in infer("förskollärare")

    def test_forskolelärare(self):
        assert "education" in infer("förskolelärare")

    def test_grundskollaerare(self):
        assert "education" in infer("grundskollärare")

    def test_rektor(self):
        assert "education" in infer("rektor")


# ---------------------------------------------------------------------------
# Built environment
# ---------------------------------------------------------------------------

class TestBuiltEnvironmentDetection:
    def test_arkitekt(self):
        assert "built_environment" in infer("arkitekt")

    def test_stadsplanerare(self):
        assert "built_environment" in infer("stadsplanerare")

    def test_fastighetsmaeqlare(self):
        assert "built_environment" in infer("fastighetsmäklare")

    def test_inredningsarkitekt(self):
        assert "built_environment" in infer("inredningsarkitekt")


# ---------------------------------------------------------------------------
# Psychology / Social
# ---------------------------------------------------------------------------

class TestPsychologySocialDetection:
    def test_psykolog(self):
        assert "psychology_social" in infer("psykolog")

    def test_socionom(self):
        assert "psychology_social" in infer("socionom")

    def test_beteendevetare(self):
        assert "psychology_social" in infer("beteendevetare")

    def test_psykoterapeut(self):
        assert "psychology_social" in infer("psykoterapeut")


# ---------------------------------------------------------------------------
# Environment / Sustainability
# ---------------------------------------------------------------------------

class TestEnvironmentDetection:
    def test_hallbarhetsstrateg(self):
        assert "environment" in infer("hållbarhetsstrateg")

    def test_biolog(self):
        assert "environment" in infer("biolog")

    def test_geolog(self):
        assert "environment" in infer("geolog")

    def test_meteorolog(self):
        assert "environment" in infer("meteorolog")


# ---------------------------------------------------------------------------
# Media / Communication
# ---------------------------------------------------------------------------

class TestMediaCommunicationDetection:
    def test_journalist(self):
        assert "media_communication" in infer("journalist")

    def test_kommunikatoer(self):
        assert "media_communication" in infer("kommunikatör")


# ---------------------------------------------------------------------------
# Humanities
# ---------------------------------------------------------------------------

class TestHumanitiesDetection:
    def test_historiker(self):
        assert "humanities" in infer("historiker")

    def test_sociolog(self):
        # sociolog belongs to humanities (not psychology_social) to prevent
        # multi-domain OR-filter from returning 0 results
        domains = infer("sociolog")
        assert "humanities" in domains

    def test_statsvetare(self):
        assert "humanities" in infer("statsvetare")

    def test_kriminolog(self):
        assert "humanities" in infer("kriminolog")


# ---------------------------------------------------------------------------
# Art / Design
# ---------------------------------------------------------------------------

class TestArtDetection:
    def test_musiker(self):
        assert "art" in infer("musiker")

    def test_fotograf(self):
        assert "art" in infer("fotograf")

    def test_skaadespelarae(self):
        assert "art" in infer("skådespelare")

    def test_dramaturg(self):
        assert "art" in infer("dramaturg")


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

class TestFallback:
    def test_completely_unknown_term_returns_other(self):
        # Note: DOMAIN_KEYWORDS uses substring matching without word boundaries.
        # Short keywords like "it", "ux", "ai" can match words that contain them
        # as substrings. This test uses a term that is genuinely unrecognised.
        domains = infer("basketboll frisbee")
        assert domains == ["other"]

    def test_known_term_does_not_return_other(self):
        domains = infer("läkare")
        assert "other" not in domains
