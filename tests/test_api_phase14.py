from fastapi.testclient import TestClient

from nascente_brasil.api import app as api_module
from nascente_brasil.api.app import DatabaseUnavailable, app


client = TestClient(app)


def test_health_checks_only_the_api_process():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_database_is_available(monkeypatch):
    monkeypatch.setattr(api_module, "_database_ready", lambda: None)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_ready_when_database_is_unavailable(monkeypatch):
    def unavailable() -> None:
        raise DatabaseUnavailable

    monkeypatch.setattr(api_module, "_database_ready", unavailable)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    assert "postgresql://" not in response.text


def test_openapi_and_level_validation():
    assert client.get("/openapi.json").status_code == 200
    response = client.get("/api/v1/mortalidade", params={"nivel": "municipio"})
    assert response.status_code == 422


def test_pagination_validation():
    assert client.get("/api/v1/morbidades", params={"limit": 501}).status_code == 422
    assert client.get("/api/v1/morbidades", params={"competencia": 202500}).status_code == 422
