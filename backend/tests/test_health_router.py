import json

from app.routers import health_router


def test_readiness_check_returns_200_when_all_dependencies_are_ok(mocker):
    mocker.patch("app.routers.health_router._check_postgres", return_value=health_router.DependencyStatus(ok=True))
    mocker.patch("app.routers.health_router._check_redis", return_value=health_router.DependencyStatus(ok=True))
    mocker.patch("app.routers.health_router._check_qdrant", return_value=health_router.DependencyStatus(ok=True))

    response = health_router.readiness_check()
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["ready"] is True
    assert payload["status"] == "ok"


def test_readiness_check_returns_503_when_dependency_fails(mocker):
    mocker.patch("app.routers.health_router._check_postgres", return_value=health_router.DependencyStatus(ok=False, detail="db down"))
    mocker.patch("app.routers.health_router._check_redis", return_value=health_router.DependencyStatus(ok=True))
    mocker.patch("app.routers.health_router._check_qdrant", return_value=health_router.DependencyStatus(ok=True))

    response = health_router.readiness_check()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["ready"] is False
    assert payload["dependencies"]["postgres"]["detail"] == "db down"
