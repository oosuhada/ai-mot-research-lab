from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from research_lab.main import app, settings


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


def test_production_mode_blocks_shared_mutations(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "read_only_mode", False)
    client = TestClient(app)

    response = client.post(
        "/api/v1/saved-searches",
        json={"name": "should-not-save", "query_text": "AI capability", "filters": {}},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "This deployment is a public read-only research demo. Mutations are disabled."


def test_public_api_host_blocks_shared_mutations(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "read_only_mode", False)
    monkeypatch.setattr(settings, "public_api_hosts", "aimot.oosu.dev")
    client = TestClient(app, base_url="https://aimot.oosu.dev")

    response = client.post(
        "/api/v1/saved-searches",
        json={"name": "should-not-save", "query_text": "AI capability", "filters": {}},
    )

    assert response.status_code == 403

