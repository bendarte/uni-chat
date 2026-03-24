import pytest

from app.config import Settings


def test_production_requires_backend_api_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="BACKEND_API_KEY"):
        Settings()


def test_development_allows_missing_backend_api_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)

    settings = Settings()

    assert settings.backend_api_key == ""
