"""Unit tests for RecommendationService guardrails.

These are the pure classification functions that decide whether a program
passes topic and track filters. No database or external API calls needed.
"""

import pytest

from app.services.recommendation_service import RecommendationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_program(**kwargs) -> dict:
    defaults = {
        "program_id": "test-id",
        "name": "Test Program",
        "field": "Computer Science",
        "description": "",
        "career_paths": "",
        "domains": [],
        "tracks": [],
        "source_url": "https://example.com/programs/test",
        "rerank_score": 0.8,
        "alignment_score": 0.5,
    }
    defaults.update(kwargs)
    return defaults


def make_profile(**kwargs) -> dict:
    defaults = {
        "interests": [],
        "career_goals": [],
        "current_domain": None,
        "current_domains": [],
        "current_tracks": [],
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# _passes_track_guardrails
# ---------------------------------------------------------------------------

class TestTrackGuardrailAiData:
    def test_ai_program_passes(self):
        program = make_program(name="MSc Artificial Intelligence", field="AI")
        assert RecommendationService._passes_track_guardrails(program, {"ai_data"})

    def test_data_science_program_passes(self):
        program = make_program(name="Data Science Master", field="Data Science")
        assert RecommendationService._passes_track_guardrails(program, {"ai_data"})

    def test_unrelated_program_blocked(self):
        program = make_program(name="Bachelor of Arts in History", field="Humanities")
        assert not RecommendationService._passes_track_guardrails(program, {"ai_data"})

    def test_no_tracks_always_passes(self):
        program = make_program(name="Anything", field="Anything")
        assert RecommendationService._passes_track_guardrails(program, set())

    def test_psychology_blocked_by_ai_data_track(self):
        program = make_program(name="MSc Psychology", field="Psychology")
        assert not RecommendationService._passes_track_guardrails(program, {"ai_data"})

    def test_analytics_in_name_passes_ai_data(self):
        program = make_program(name="Business Analytics", field="Analytics")
        assert RecommendationService._passes_track_guardrails(program, {"ai_data"})


class TestTrackGuardrailBusinessAnalytics:
    def test_economics_passes(self):
        program = make_program(name="MSc Economics", field="Economics")
        assert RecommendationService._passes_track_guardrails(program, {"business_analytics"})

    def test_finance_program_passes(self):
        program = make_program(name="MSc Finance", field="Finance")
        assert RecommendationService._passes_track_guardrails(program, {"business_analytics"})

    def test_fashion_program_blocked(self):
        program = make_program(name="Fashion Design", field="Fashion")
        assert not RecommendationService._passes_track_guardrails(program, {"business_analytics"})

    def test_fine_arts_blocked(self):
        program = make_program(name="Fine Arts Bachelor", field="Fine Arts")
        assert not RecommendationService._passes_track_guardrails(program, {"business_analytics"})

    def test_unrelated_general_program_blocked(self):
        program = make_program(name="Theatre Studies", field="Theatre")
        assert not RecommendationService._passes_track_guardrails(program, {"business_analytics"})


class TestTrackGuardrailProductManagement:
    def test_product_management_program_passes(self):
        program = make_program(name="MSc Product Management", field="Technology Management")
        assert RecommendationService._passes_track_guardrails(program, {"product_management"})

    def test_digital_transformation_passes(self):
        program = make_program(name="Digital Transformation Leadership", field="Innovation")
        assert RecommendationService._passes_track_guardrails(program, {"product_management"})

    def test_retail_blocked(self):
        program = make_program(name="Retail Management", field="Retail")
        assert not RecommendationService._passes_track_guardrails(program, {"product_management"})

    def test_accounting_blocked(self):
        program = make_program(name="Bachelor of Accounting", field="Accounting")
        assert not RecommendationService._passes_track_guardrails(program, {"product_management"})


# ---------------------------------------------------------------------------
# _passes_topic_guardrails
# ---------------------------------------------------------------------------

class TestTopicGuardrails:
    def test_empty_profile_topics_always_passes(self):
        profile = make_profile(interests=[])
        program = make_program(name="Random Program", field="Random")
        # No interests → no guardrail
        assert RecommendationService._passes_topic_guardrails(profile, program, alignment=0.0)

    def test_topic_overlap_passes(self):
        profile = make_profile(interests=["artificial intelligence"])
        program = make_program(
            name="MSc Artificial Intelligence",
            field="AI",
            description="Deep learning and machine learning.",
        )
        assert RecommendationService._passes_topic_guardrails(profile, program, alignment=0.5)

    def test_low_alignment_without_overlap_blocked(self):
        profile = make_profile(interests=["artificial intelligence"])
        program = make_program(name="Bachelor of Music", field="Music", description="")
        # No topic overlap and alignment below threshold
        assert not RecommendationService._passes_topic_guardrails(profile, program, alignment=0.05)

    def test_sufficient_alignment_without_topic_overlap_passes(self):
        profile = make_profile(interests=["economics"])
        program = make_program(name="Business Studies", field="Business", description="")
        # alignment ≥ 0.12 should pass even without direct topic overlap
        assert RecommendationService._passes_topic_guardrails(profile, program, alignment=0.15)

    def test_tech_topics_blocked_outside_tech_domain(self):
        """With AI interests and explicit tech domain, non-tech programs with no topic overlap are blocked."""
        profile = make_profile(interests=["artificial intelligence"], current_domain="tech")
        # Nursing has no tech topics → no profile/program topic overlap → falls into tech guardrail
        program = make_program(name="Nursing Bachelor", field="Nursing", description="")
        result = RecommendationService._passes_topic_guardrails(profile, program, alignment=0.08)
        assert not result

    def test_tech_topics_in_business_domain_not_blocked(self):
        """AI-interest signal should not block business programs when domain=business."""
        profile = make_profile(interests=["data science", "analytics"], current_domain="business")
        program = make_program(name="MSc Finance", field="Finance", description="")
        # business domain → tech-topic guardrail skipped → falls through to alignment check
        assert RecommendationService._passes_topic_guardrails(profile, program, alignment=0.15)

    def test_specific_topics_require_specific_overlap(self):
        profile = make_profile(interests=["psychology"])
        program = make_program(name="Occupational Therapy", field="Health Sciences", description="")
        assert not RecommendationService._passes_topic_guardrails(profile, program, alignment=0.5)

    def test_specific_topic_overlap_passes_even_with_generic_domain_overlap(self):
        profile = make_profile(interests=["design", "engineering"])
        program = make_program(name="Interaction Design", field="Design", description="UX and user experience")
        assert RecommendationService._passes_topic_guardrails(profile, program, alignment=0.05)


# ---------------------------------------------------------------------------
# _looks_like_course
# ---------------------------------------------------------------------------

class TestLooksLikeCourse:
    def test_course_catalogue_url(self):
        program = make_program(name="Programming Fundamentals")
        assert RecommendationService._looks_like_course(program, "https://uni.se/coursecatalogue/123")

    def test_slash_course_url(self):
        program = make_program(name="Linear Algebra")
        assert RecommendationService._looks_like_course(program, "https://uni.se/course/MATH101")

    def test_english_i_name(self):
        program = make_program(name="Academic English I")
        assert RecommendationService._looks_like_course(program, "https://uni.se/programs/ae")

    def test_program_url_not_course(self):
        program = make_program(name="MSc Computer Science")
        assert not RecommendationService._looks_like_course(program, "https://uni.se/programs/msc-cs")

    def test_master_programme_not_course(self):
        program = make_program(name="Master Programme in Data Science")
        assert not RecommendationService._looks_like_course(program, "https://uni.se/programmes/ds")


def test_generate_normalizes_city_labels_in_recommendations(mocker):
    service = RecommendationService()
    mocker.patch.object(
        service.explainer,
        "generate_program_explanation",
        return_value={
            "program": "Datateknik",
            "university": "Chalmers tekniska högskola",
            "explanation": ["Bra match"],
            "source_id": "ref-1",
        },
    )
    programs = [
        make_program(
            program_id="1",
            name="Datateknik",
            university="Chalmers tekniska högskola",
            city="Gothenburg",
        )
    ]

    recommendations = service.generate(make_profile(), programs, limit=1)

    assert len(recommendations) == 1
    assert recommendations[0].city == "Göteborg"


def test_generate_normalizes_university_labels_in_recommendations(mocker):
    service = RecommendationService()
    mocker.patch.object(
        service.explainer,
        "generate_program_explanation",
        return_value={
            "program": "Datateknik",
            "university": "Chalmers University of Technology",
            "explanation": ["Bra match"],
            "source_id": "ref-1",
        },
    )

    recommendations = service.generate(
        make_profile(),
        [
            make_program(
                program_id="1",
                name="Datateknik",
                university="Chalmers University of Technology",
                city="Gothenburg",
            )
        ],
        limit=1,
    )

    assert len(recommendations) == 1
    assert recommendations[0].university == "Chalmers tekniska högskola"


def test_generate_dedupes_mixed_university_aliases(mocker):
    service = RecommendationService()
    mocker.patch.object(
        service.explainer,
        "generate_program_explanation",
        side_effect=[
            {
                "program": "Datateknik",
                "university": "Chalmers tekniska högskola",
                "explanation": ["Bra match"],
                "source_id": "ref-1",
            }
        ],
    )

    recommendations = service.generate(
        make_profile(),
        [
            make_program(
                program_id="1",
                name="Datateknik",
                university="Chalmers University of Technology",
                city="Gothenburg",
            ),
            make_program(
                program_id="2",
                name="Datateknik",
                university="Chalmers tekniska högskola",
                city="Gothenburg",
            ),
        ],
        limit=5,
    )

    assert len(recommendations) == 1
    assert recommendations[0].university == "Chalmers tekniska högskola"
