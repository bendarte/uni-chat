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
