"""Exercise FastAPI endpoints against the validated PostgreSQL marts."""

from fastapi.testclient import TestClient

from nascente_brasil.api.app import app


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200 and health.json()["database"] == "ok"

        mortality = client.get("/api/v1/mortalidade", params={"nivel": "brasil"})
        assert mortality.status_code == 200
        payload = mortality.json()
        assert payload["pagination"]["total"] == 1
        assert payload["items"][0]["obitos_infantis"] == 30020
        assert payload["items"][0]["nascidos_vivos"] == 2389325

        births = client.get("/api/v1/nascimentos", params={"nivel": "brasil"})
        assert births.status_code == 200
        assert births.json()["items"][0]["nascidos_vivos"] == 2389325

        morbidity = client.get("/api/v1/morbidades", params={"nivel": "brasil", "limit": 500})
        assert morbidity.status_code == 200
        assert morbidity.json()["pagination"]["total"] == 240

        states = client.get("/api/v1/mortalidade", params={"nivel": "estado", "limit": 100})
        assert states.status_code == 200 and states.json()["pagination"]["total"] == 27

        municipalities = client.get("/api/v1/territorios/municipios", params={"uf": "RO", "limit": 100})
        assert municipalities.status_code == 200
        assert all(item["uf"] == "RO" for item in municipalities.json()["items"])

        assert client.get("/api/v1/mortalidade", params={"nivel": "municipio"}).status_code == 422
    print("Phase 14 validation succeeded: health, births, mortality, morbidity, territories, privacy boundary")


if __name__ == "__main__":
    main()
