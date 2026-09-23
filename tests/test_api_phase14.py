from fastapi.testclient import TestClient

from nascente_brasil.api.app import app


client = TestClient(app)


def test_openapi_and_level_validation():
    assert client.get("/openapi.json").status_code == 200
    response = client.get("/api/v1/mortalidade", params={"nivel": "municipio"})
    assert response.status_code == 422


def test_pagination_validation():
    assert client.get("/api/v1/morbidades", params={"limit": 501}).status_code == 422
    assert client.get("/api/v1/morbidades", params={"competencia": 202500}).status_code == 422
