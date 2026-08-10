from fastapi.testclient import TestClient

from research_lab.main import app


def test_health_is_available_even_when_database_is_offline() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "api"
    assert payload["database"] in {"ok", "unavailable"}


def test_root_exposes_discovery_links() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"

