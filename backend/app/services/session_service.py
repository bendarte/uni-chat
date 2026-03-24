import json
import logging
import time
from functools import lru_cache
from typing import Any, Dict, Optional

import redis

from app.config import settings
from app.logging_utils import log_event

SESSION_TTL_SECONDS = 24 * 60 * 60


@lru_cache(maxsize=1)
def _get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        health_check_interval=30,
        retry_on_timeout=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


class SessionService:
    def __init__(self) -> None:
        self._fallback_store: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("uvicorn.error")
        self.client = _get_redis_client()

    @staticmethod
    def default_profile() -> Dict[str, Any]:
        return {
            "interests": [],
            "preferred_cities": [],
            "preferred_country": [],
            "language": None,
            "study_level": None,
            "study_pace": None,
            "career_goals": [],
            "locked_fields": [],
            "current_domain": None,
            "current_domains": [],
            "current_tracks": [],
            "clarification_stage": None,
            "current_question_type": None,
            "clarification_options": [],
            "selected_guidance_option": None,
        }

    @staticmethod
    def _key(conversation_id: str) -> str:
        return f"chat_profile:{conversation_id}"

    def load_profile(self, conversation_id: Optional[str]) -> Dict[str, Any]:
        if not conversation_id:
            return self.default_profile()

        key = self._key(conversation_id)
        try:
            raw = self.client.get(key)
            if not raw:
                return self.default_profile()
            profile = json.loads(raw)
            merged = self.default_profile()
            merged.update(profile)
            return merged
        except Exception as exc:
            log_event(self.logger, "warning", "redis_load_profile_failed", error=str(exc))
            fallback = self._fallback_store.get(conversation_id)
            if not fallback:
                return self.default_profile()
            if fallback.get("expires_at", 0) < time.time():
                self._fallback_store.pop(conversation_id, None)
                return self.default_profile()
            merged = self.default_profile()
            merged.update(fallback.get("profile", {}))
            return merged

    def save_profile(self, conversation_id: Optional[str], profile: Dict[str, Any]) -> None:
        if not conversation_id:
            return

        key = self._key(conversation_id)
        try:
            self.client.setex(key, SESSION_TTL_SECONDS, json.dumps(profile))
        except Exception as exc:
            log_event(self.logger, "warning", "redis_save_profile_failed", error=str(exc))
            self._fallback_store[conversation_id] = {
                "profile": profile,
                "expires_at": time.time() + SESSION_TTL_SECONDS,
            }

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception:
            return False
