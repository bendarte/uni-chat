from app.services.explanation_service import ExplanationService


def test_energy_transition_track_gets_explanation_from_program_text():
    service = ExplanationService()
    profile = {"current_tracks": ["energy_transition"]}
    program = {
        "name": "Energy and Management for Sustainable Development",
        "field": "sustainability",
        "description": "A master's programme focused on sustainable energy systems.",
        "tracks": [],
    }

    explanation = service._guidance_match(profile, program)

    assert "energi" in explanation.lower() or "hållbar" in explanation.lower()


def test_display_city_normalizes_known_aliases():
    assert ExplanationService._display_city("Gothenburg") == "Göteborg"
    assert ExplanationService._display_city("Online") == "distans"
