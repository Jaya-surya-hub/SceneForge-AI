"""Tests for health check endpoint."""

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ("healthy", "degraded")
    assert data["app"] == "IncuBrix Signal Room"
    assert data["version"] == "0.1.0"
    assert data["demo_mode"] is True
    assert "timestamp" in data
    assert data["database"]["connected"] is True
    assert "latency_ms" in data["database"]
    assert data["storage"]["writable"] is True
    assert "total_records" in data["ledger"]
