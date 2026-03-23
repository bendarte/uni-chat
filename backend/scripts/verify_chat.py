import json
import os
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000").rstrip("/")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "").strip()


def request_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if BACKEND_API_KEY:
        headers["X-API-Key"] = BACKEND_API_KEY
    return headers


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def get_json(path: str) -> Dict:
    response = requests.get(f"{BASE_URL}{path}", headers=request_headers(), timeout=120)
    response.raise_for_status()
    return response.json()


def post_json(path: str, payload: Dict) -> Dict:
    response = requests.post(
        f"{BASE_URL}{path}",
        json=payload,
        headers=request_headers(),
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def looks_like_deep_program_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")
    if not parsed.scheme or not parsed.netloc or not path:
        return False
    if any(marker in path for marker in ["/course/", "/courses/", "/kurs/", "coursecatalogue"]):
        return False
    if path in {"", "/en", "/study", "/studies", "/education"}:
        return False
    if parsed.query and any(key in parsed.query.lower() for key in ["code=", "query="]):
        return False
    return True


def build_program_index() -> Dict[str, Dict]:
    response = requests.get(f"{BASE_URL}/programs", headers=request_headers(), timeout=120)
    response.raise_for_status()
    rows = response.json()
    return {row["source_url"]: row for row in rows if row.get("source_url")}


def validate_city_filter(response: Dict, expected_city: str, program_index: Dict[str, Dict]) -> None:
    for citation in response.get("citations", []):
        program = program_index.get(citation.get("url"))
        assert_true(program is not None, f"Missing program metadata for URL {citation.get('url')}")
        assert_true(
            program.get("city") == expected_city,
            f"Expected city {expected_city}, got {program.get('city')} for {citation.get('url')}",
        )


def validate_links(response: Dict) -> None:
    for citation in response.get("citations", []):
        url = citation.get("url") or ""
        assert_true(looks_like_deep_program_url(url), f"Non-deep or invalid URL returned: {url}")


def assert_ai_like_recommendations(response: Dict) -> None:
    haystacks = []
    for recommendation in response.get("recommendations", []):
        haystacks.append(
            " ".join(
                [
                    str(recommendation.get("program") or ""),
                    str(recommendation.get("university") or ""),
                    " ".join(str(part) for part in recommendation.get("explanation", []) if part),
                ]
            ).lower()
        )
    for citation in response.get("citations", []):
        haystacks.append(
            " ".join(
                [
                    str(citation.get("title") or ""),
                    str(citation.get("snippet") or ""),
                ]
            ).lower()
        )

    markers = [
        "artificial intelligence",
        "machine learning",
        "ai",
        "data science",
        "computer science",
        "analytics",
    ]
    assert_true(
        any(any(marker in haystack for marker in markers) for haystack in haystacks),
        "Expected widened AI flow to return AI-like recommendations",
    )


def main() -> None:
    status = get_json("/api/system/status")
    assert_true(status.get("status") == "ok", "System status is not ok")
    assert_true(int(status.get("programs", 0)) > 0, "No programs loaded")
    assert_true(int(status.get("vector_chunks", 0)) == int(status.get("programs", 0)), "Vector count mismatch")

    program_index = build_program_index()
    assert_true(program_index, "Program index is empty")

    sv_stockholm = post_json(
        "/api/chat",
        {
            "message": "Jag vill studera hållbarhet eller miljö i Stockholm på engelska, helst bachelor och heltid.",
            "session_id": "verify-sv-stockholm",
            "preferences": {
                "city": "Stockholm",
                "studyLevel": "bachelor",
                "language": "english",
                "studyPace": "full-time",
            },
        },
    )
    validate_links(sv_stockholm)
    validate_city_filter(sv_stockholm, "Stockholm", program_index)

    ai_stockholm = post_json(
        "/api/chat",
        {
            "message": "I want an AI or machine learning master in Stockholm taught in English full-time.",
            "session_id": "verify-en-ai",
            "preferences": {
                "city": "Stockholm",
                "studyLevel": "master",
                "language": "english",
                "studyPace": "full-time",
            },
        },
    )
    validate_links(ai_stockholm)
    validate_city_filter(ai_stockholm, "Stockholm", program_index)

    broad = post_json(
        "/api/chat",
        {
            "message": "Jag vill plugga hållbarhet eller miljö på engelska, helst master.",
            "session_id": "verify-followup",
        },
    )
    validate_links(broad)

    follow_up = post_json(
        "/api/chat",
        {
            "message": "Och i Stockholm?",
            "session_id": "verify-followup",
            "preferences": {"city": "Stockholm"},
        },
    )
    validate_links(follow_up)
    validate_city_filter(follow_up, "Stockholm", program_index)

    strict_ai = post_json(
        "/chat",
        {
            "message": "I want an AI or machine learning master in Stockholm taught in English full-time.",
            "conversation_id": "verify-strict-ai",
            "filters": {
                "cities": ["Stockholm"],
                "level": "master",
                "language": "english",
                "study_pace": "full-time",
            },
        },
    )
    # System now auto-widens to all of Sweden when no results exist in the requested city.
    validate_links(strict_ai)
    assert_true(strict_ai.get("recommendations"), "Expected strict AI query to return auto-widened recommendations from all of Sweden")
    assert_ai_like_recommendations(strict_ai)
    active_filters = strict_ai.get("active_filters") or {}
    assert_true(active_filters.get("city") == "Stockholm", "Expected strict AI flow to keep Stockholm as active city filter")

    widened_ai = post_json(
        "/chat",
        {
            "message": "hela sverige då",
            "conversation_id": "verify-strict-ai",
        },
    )
    validate_links(widened_ai)
    assert_true(widened_ai.get("recommendations"), "Expected widened AI flow to return recommendations")
    assert_ai_like_recommendations(widened_ai)

    strict_ai_snake = post_json(
        "/chat",
        {
            "message": "I want an AI or machine learning master in Stockholm taught in English full-time.",
            "conversation_id": "verify-strict-ai-snake",
            "filters": {
                "cities": ["Stockholm"],
                "level": "master",
                "language": "english",
                "study_pace": "full_time",
            },
        },
    )
    # System now auto-widens to all of Sweden when no results exist in the requested city.
    validate_links(strict_ai_snake)
    assert_true(strict_ai_snake.get("recommendations"), "Expected strict AI query (full_time) to return auto-widened recommendations")
    assert_ai_like_recommendations(strict_ai_snake)

    widened_ai_snake = post_json(
        "/chat",
        {
            "message": "hela sverige då",
            "conversation_id": "verify-strict-ai-snake",
        },
    )
    validate_links(widened_ai_snake)
    assert_true(
        widened_ai_snake.get("recommendations"),
        "Expected widened AI flow with full_time to return recommendations",
    )
    assert_ai_like_recommendations(widened_ai_snake)

    print(json.dumps({"status": "ok", "checked_programs": len(program_index)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
