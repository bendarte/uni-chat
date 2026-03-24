from app.services.chat_service import ChatService


def test_missing_fields_skips_follow_up_for_explicit_sidebar_filters():
    profile = {
        "interests": [],
        "career_goals": [],
        "current_domain": None,
        "current_tracks": [],
        "preferred_cities": ["Gothenburg"],
        "study_level": "master",
        "language": None,
        "study_pace": None,
    }

    assert ChatService._missing_fields(profile, "visa program") == []


def test_build_active_filters_uses_request_filters_when_present():
    profile = {
        "preferred_cities": [],
        "preferred_universities": [],
        "excluded_universities": [],
        "study_level": None,
        "language": None,
        "study_pace": None,
        "locked_fields": [],
    }

    active = ChatService._build_active_filters(
        profile,
        {"cities": ["Gothenburg"], "level": "master", "language": "swedish"},
    )

    assert active == {
        "city": "Gothenburg",
        "level": "Master",
        "language": "Swedish",
        "study_pace": "",
    }


def test_energy_queries_enrich_profile_with_environment_track():
    profile = {
        "interests": [],
        "current_domain": "tech",
        "current_domains": ["tech"],
        "current_tracks": ["engineering"],
    }

    enriched = ChatService._enrich_energy_context(
        profile,
        "Jag vill läsa civilingenjör inom hållbar energi",
    )

    assert "energy systems" in enriched["interests"]
    assert "environment" in enriched["current_domains"]
    assert "energy_transition" in enriched["current_tracks"]


def test_subject_switch_detection_resets_for_new_domain():
    profile = {
        "interests": ["music production"],
        "career_goals": ["musician"],
        "current_domain": "art",
        "current_domains": ["art"],
        "current_tracks": ["creative_production"],
        "selected_guidance_option": {"label": "Kreativt & Media", "domains": ["art"]},
    }
    extracted = {
        "interests": ["medicine"],
        "career_goals": [],
        "preferred_cities": ["Stockholm"],
    }
    intent = {
        "domain": "healthcare",
        "domains": ["healthcare"],
        "career_track_candidates": ["patient_care"],
        "matched_role_terms": ["läkare"],
    }

    assert ChatService._should_reset_for_subject_switch(
        profile,
        "Jag vill bli läkare i Stockholm",
        extracted,
        intent,
    ) is True


def test_subject_switch_detection_skips_place_follow_up():
    profile = {
        "interests": ["medicine"],
        "career_goals": ["läkare"],
        "current_domain": "healthcare",
        "current_domains": ["healthcare"],
        "current_tracks": ["patient_care"],
        "selected_guidance_option": {"label": "Vård & Medicin", "domains": ["healthcare"]},
    }
    extracted = {
        "interests": [],
        "career_goals": [],
        "preferred_cities": ["Stockholm"],
        "preferred_universities": [],
        "excluded_universities": [],
    }
    intent = {
        "domain": None,
        "domains": [],
        "career_track_candidates": [],
        "matched_role_terms": [],
    }

    assert ChatService._should_reset_for_subject_switch(
        profile,
        "och i Stockholm",
        extracted,
        intent,
    ) is False


def test_reset_subject_context_preserves_existing_filters_without_sidebar_input():
    service = ChatService.__new__(ChatService)
    profile = {
        "interests": ["music production"],
        "career_goals": ["musician"],
        "preferred_cities": ["Stockholm"],
        "preferred_country": ["Sweden"],
        "preferred_universities": ["KTH"],
        "excluded_universities": ["SU"],
        "language": "english",
        "study_level": "master",
        "study_pace": "full-time",
        "locked_fields": ["preferred_cities", "study_level"],
        "current_domain": "art",
        "current_domains": ["art"],
        "current_tracks": ["creative_production"],
        "clarification_stage": "awaiting_domain_specific_choice",
        "current_question_type": "option_choice",
        "clarification_options": [{"label": "Kreativt & Media"}],
        "selected_guidance_option": {"label": "Kreativt & Media", "domains": ["art"]},
    }

    reset = service._reset_subject_context(profile, filters=None)

    assert reset["interests"] == []
    assert reset["career_goals"] == []
    assert reset["current_domain"] is None
    assert reset["current_domains"] == []
    assert reset["current_tracks"] == []
    assert reset["clarification_stage"] is None
    assert reset["current_question_type"] is None
    assert reset["clarification_options"] == []
    assert reset["selected_guidance_option"] is None

    assert reset["preferred_cities"] == ["Stockholm"]
    assert reset["preferred_country"] == ["Sweden"]
    assert reset["preferred_universities"] == ["KTH"]
    assert reset["excluded_universities"] == ["SU"]
    assert reset["language"] == "english"
    assert reset["study_level"] == "master"
    assert reset["study_pace"] == "full-time"
    assert reset["locked_fields"] == ["preferred_cities", "study_level"]


def test_explicit_goal_replaces_old_goal_terms():
    extracted = {
        "interests": ["artificial intelligence"],
        "career_goals": [],
    }
    intent = {"matched_role_terms": []}

    goals = ChatService._extract_explicit_goals(
        "Jag vill jobba med AI",
        extracted,
        intent,
    )

    assert goals == ["artificial intelligence"]


def test_explicit_role_goal_prefers_role_terms():
    extracted = {
        "interests": ["medicine"],
        "career_goals": [],
    }
    intent = {"matched_role_terms": ["läkare"]}

    goals = ChatService._extract_explicit_goals(
        "Jag vill bli läkare",
        extracted,
        intent,
    )

    assert goals == ["läkare"]
