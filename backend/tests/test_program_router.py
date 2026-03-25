from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.routers import program_router


def create_test_client(mock_db):
    app = FastAPI()
    app.include_router(program_router.router)
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app)


def test_get_programs_does_not_require_admin_key(mocker, monkeypatch):
    mock_db = mocker.MagicMock()
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    monkeypatch.setattr(
        program_router,
        "settings",
        SimpleNamespace(admin_api_key="admin-secret", app_env="development"),
    )

    client = create_test_client(mock_db)

    response = client.get("/programs")

    assert response.status_code == 200
    assert response.json() == []


def test_post_ingest_requires_admin_key(mocker, monkeypatch):
    monkeypatch.setattr(
        program_router,
        "settings",
        SimpleNamespace(admin_api_key="admin-secret", app_env="development"),
    )
    ingest = mocker.patch("app.routers.program_router.run_ingestion_pipeline")
    client = create_test_client(mocker.MagicMock())

    response = client.post("/ingest")

    assert response.status_code == 401
    ingest.assert_not_called()


def test_post_ingest_allows_valid_admin_key(mocker, monkeypatch):
    monkeypatch.setattr(
        program_router,
        "settings",
        SimpleNamespace(admin_api_key="admin-secret", app_env="development"),
    )
    ingest = mocker.patch(
        "app.routers.program_router.run_ingestion_pipeline",
        return_value={"crawled": 1, "stored_in_postgres": 1, "embedded_in_qdrant": 1},
    )
    client = create_test_client(mocker.MagicMock())

    response = client.post("/ingest", headers={"X-Admin-API-Key": "admin-secret"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "crawled": 1,
        "stored_in_postgres": 1,
        "embedded_in_qdrant": 1,
    }
    ingest.assert_called_once()


def test_post_republish_requires_admin_key(mocker, monkeypatch):
    monkeypatch.setattr(
        program_router,
        "settings",
        SimpleNamespace(admin_api_key="admin-secret", app_env="development"),
    )
    apply_backfill = mocker.patch("app.routers.program_router.apply_backfill")
    republish = mocker.patch("app.routers.program_router.republish_qdrant_from_db")
    client = create_test_client(mocker.MagicMock())

    response = client.post("/republish")

    assert response.status_code == 401
    apply_backfill.assert_not_called()
    republish.assert_not_called()


def test_post_republish_allows_valid_admin_key(mocker, monkeypatch):
    monkeypatch.setattr(
        program_router,
        "settings",
        SimpleNamespace(admin_api_key="admin-secret", app_env="development"),
    )
    apply_backfill = mocker.patch(
        "app.routers.program_router.apply_backfill",
        return_value={"checked": 3560, "updated": 0, "programs": [{"id": "1"}]},
    )
    republish = mocker.patch(
        "app.routers.program_router.republish_qdrant_from_db",
        return_value={
            "embedded_rows": 3560,
            "published": True,
            "previous_collection": "programs_old",
            "target_collection": "programs_new",
        },
    )
    client = create_test_client(mocker.MagicMock())

    response = client.post("/republish", headers={"X-Admin-API-Key": "admin-secret"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checked": 3560,
        "updated": 0,
        "embedded_in_qdrant": 3560,
        "published": True,
        "previous_collection": "programs_old",
        "target_collection": "programs_new",
    }
    apply_backfill.assert_called_once_with(include_university=True, include_city=True)
    republish.assert_called_once_with([{"id": "1"}])


def test_post_program_normalizes_university_aliases(mocker, monkeypatch):
    monkeypatch.setattr(
        program_router,
        "settings",
        SimpleNamespace(admin_api_key="admin-secret", app_env="development"),
    )
    mock_db = mocker.MagicMock()

    def refresh_program(program):
        program.id = uuid4()
        program.last_updated = datetime.now(timezone.utc)

    mock_db.refresh.side_effect = refresh_program
    client = create_test_client(mock_db)

    response = client.post(
        "/programs",
        headers={"X-Admin-API-Key": "admin-secret"},
        json={
            "name": "Datateknik",
            "university": "Chalmers University of Technology",
            "city": "Gothenburg",
            "source_url": "https://example.com/programs/datateknik",
        },
    )

    assert response.status_code == 200
    assert response.json()["university"] == "Chalmers tekniska högskola"


def test_get_program_cities_normalizes_labels_and_excludes_countries(mocker, monkeypatch):
    mock_db = mocker.MagicMock()
    mock_db.query.return_value.filter.return_value.distinct.return_value.order_by.return_value.all.return_value = [
        ("Belgien",),
        ("Gothenburg",),
        ("Göteborg",),
        ("Malmo",),
        ("Online",),
        ("Uppsala",),
    ]
    monkeypatch.setattr(
        program_router,
        "settings",
        SimpleNamespace(admin_api_key="admin-secret", app_env="development"),
    )

    client = create_test_client(mock_db)

    response = client.get("/programs/cities")

    assert response.status_code == 200
    assert response.json() == ["Göteborg", "Malmö", "Distans", "Uppsala"]
