"""Tests para los endpoints de health check."""

import pytest
from ninja.testing import TestClient


@pytest.fixture
def client():
    from api.v1.health import router
    return TestClient(router)


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


def test_readiness_returns_structure(client):
    response = client.get("/health/readiness")
    assert response.status_code == 200
    body = response.json()
    assert "ready" in body
    assert "environment" in body
    assert "telnyx_configured" in body
