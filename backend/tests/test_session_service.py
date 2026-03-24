"""Unit tests for SessionService.

Uses pytest-mock to stub out the Redis client so tests run without
a live Redis instance.
"""

import time

import pytest

from app.services.session_service import SESSION_TTL_SECONDS, SessionService, _get_redis_client


@pytest.fixture
def svc(mocker):
    """SessionService with a mocked Redis client."""
    mock_redis = mocker.MagicMock()
    mocker.patch("app.services.session_service.redis.Redis.from_url", return_value=mock_redis)
    _get_redis_client.cache_clear()
    service = SessionService()
    yield service, mock_redis
    _get_redis_client.cache_clear()


class TestDefaultProfile:
    def test_has_required_keys(self):
        profile = SessionService.default_profile()
        required = {
            "interests", "preferred_cities", "language", "study_level",
            "study_pace", "career_goals", "locked_fields", "current_domain",
            "current_domains", "current_tracks", "clarification_stage",
        }
        assert required <= profile.keys()

    def test_lists_are_empty(self):
        profile = SessionService.default_profile()
        assert profile["interests"] == []
        assert profile["current_tracks"] == []
        assert profile["locked_fields"] == []

    def test_strings_are_none(self):
        profile = SessionService.default_profile()
        assert profile["language"] is None
        assert profile["current_domain"] is None

    def test_reuses_shared_redis_client_across_instances(self, mocker):
        mock_redis = mocker.MagicMock()
        constructor = mocker.patch(
            "app.services.session_service.redis.Redis.from_url",
            return_value=mock_redis,
        )
        _get_redis_client.cache_clear()
        try:
            first = SessionService()
            second = SessionService()
        finally:
            _get_redis_client.cache_clear()

        assert first.client is mock_redis
        assert second.client is mock_redis
        constructor.assert_called_once()


class TestLoadProfile:
    def test_returns_default_when_no_conversation_id(self, svc):
        service, _ = svc
        profile = service.load_profile(None)
        assert profile == SessionService.default_profile()

    def test_returns_default_when_redis_miss(self, svc):
        service, mock_redis = svc
        mock_redis.get.return_value = None
        profile = service.load_profile("sess-abc")
        assert profile == SessionService.default_profile()

    def test_merges_stored_profile_with_defaults(self, svc):
        service, mock_redis = svc
        import json
        stored = {"interests": ["AI", "data science"], "language": "english"}
        mock_redis.get.return_value = json.dumps(stored)
        profile = service.load_profile("sess-abc")
        # Stored values should override defaults
        assert profile["interests"] == ["AI", "data science"]
        assert profile["language"] == "english"
        # Default keys not in stored dict should still be present
        assert "current_tracks" in profile

    def test_falls_back_to_memory_when_redis_raises(self, svc):
        service, mock_redis = svc
        mock_redis.get.side_effect = Exception("redis down")
        profile = service.load_profile("sess-xyz")
        assert profile == SessionService.default_profile()


class TestSaveProfile:
    def test_saves_to_redis_with_ttl(self, svc):
        service, mock_redis = svc
        profile = {"interests": ["machine learning"]}
        service.save_profile("sess-123", profile)
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "chat_profile:sess-123"
        assert args[1] == SESSION_TTL_SECONDS

    def test_noop_when_no_conversation_id(self, svc):
        service, mock_redis = svc
        service.save_profile(None, {"interests": []})
        mock_redis.setex.assert_not_called()

    def test_falls_back_to_memory_when_redis_raises(self, svc):
        service, mock_redis = svc
        mock_redis.setex.side_effect = Exception("redis down")
        profile = {"interests": ["economics"]}
        service.save_profile("sess-fallback", profile)
        # Should not raise; data stored in fallback dict
        loaded = service._fallback_store.get("sess-fallback")
        assert loaded is not None
        assert loaded["profile"]["interests"] == ["economics"]

    def test_fallback_entry_has_expiry(self, svc):
        service, mock_redis = svc
        mock_redis.setex.side_effect = Exception("redis down")
        before = time.time()
        service.save_profile("sess-exp", {"interests": []})
        entry = service._fallback_store["sess-exp"]
        assert entry["expires_at"] > before + SESSION_TTL_SECONDS - 5
