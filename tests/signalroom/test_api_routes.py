"""Tests for API routes and ledger verification."""

from fastapi.testclient import TestClient


def test_project_crud(client: TestClient):
    create_payload = {
        "id": "PRJ-API-01",
        "name": "API Test Project",
        "slug": "api-test-project",
        "description": "Created via API test",
        "target_domains": ["incubrix.com"],
        "default_markets": ["US", "UK"],
    }
    res = client.post("/api/v1/projects", json=create_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "PRJ-API-01"
    assert data["name"] == "API Test Project"

    list_res = client.get("/api/v1/projects")
    assert list_res.status_code == 200
    assert any(p["id"] == "PRJ-API-01" for p in list_res.json())


def test_question_crud(client: TestClient):
    create_payload = {
        "id": "Q-API-01",
        "text": "How do creators monetize repurposed short clips?",
        "journey_stage": "Grow",
        "search_intent": "commercial",
        "source_type": "google_autocomplete",
        "source_url": "https://google.com/search?q=monetize+short+clips",
        "target_market": "US",
        "language": "en",
        "is_demo": True,
    }
    res = client.post("/api/v1/questions", json=create_payload)
    assert res.status_code == 201
    assert res.json()["id"] == "Q-API-01"

    get_res = client.get("/api/v1/questions/Q-API-01")
    assert get_res.status_code == 200
    assert get_res.json()["journey_stage"] == "Grow"


def test_run_and_ledger_verify(client: TestClient):
    run_payload = {
        "id": "RUN-API-01",
        "run_type": "full_discovery",
        "status": "completed",
        "markets": ["US"],
        "assistants": ["google_search"],
    }
    run_res = client.post("/api/v1/runs", json=run_payload)
    assert run_res.status_code == 201

    ledger_res = client.get("/api/v1/evidence/ledger")
    assert ledger_res.status_code == 200
    assert isinstance(ledger_res.json(), list)

    verify_res = client.get("/api/v1/evidence/verify")
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["is_valid"] is True
    assert verify_data["chain_breaks_detected"] == 0
