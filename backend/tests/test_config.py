import pytest

from app.config import Settings


def test_production_requires_backend_api_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)
    monkeypatch.setenv("ADMIN_API_KEY", "admin-secret")

    with pytest.raises(RuntimeError, match="BACKEND_API_KEY"):
        Settings()


def test_production_requires_admin_api_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BACKEND_API_KEY", "backend-secret")
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ADMIN_API_KEY"):
        Settings()


def test_development_allows_missing_backend_api_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)

    settings = Settings()

    assert settings.backend_api_key == ""
    assert settings.admin_api_key == ""
