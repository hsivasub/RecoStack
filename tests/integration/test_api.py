"""
Integration tests — FastAPI Serving API (src/api/app.py)

Tests the full HTTP layer: health check, recommend, rate, and metrics endpoints.
Uses FastAPI's TestClient for in-process testing without a live server.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.app import app


@pytest.fixture
def client():
    """FastAPI TestClient with mocked external dependencies."""
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client: TestClient):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "models_loaded" in data
        assert "redpanda_connected" in data
        assert "feast_available" in data

    def test_health_defaults(self, client: TestClient):
        """Without models or services, health should report False."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"
        # Models won't be loaded in test env (no trained artifacts)
        assert data["models_loaded"] is False


class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client: TestClient):
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type(self, client: TestClient):
        response = client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_contains_recostack_prefix(self, client: TestClient):
        response = client.get("/metrics")
        text = response.text
        assert "recostack_" in text


class TestRecommendEndpoint:
    def test_recommend_without_models_returns_503(self, client: TestClient):
        """Without trained models, /recommend should return 503."""
        response = client.get("/recommend?user_id=1&top_k=5")
        assert response.status_code == 503

    def test_recommend_missing_user_id_returns_422(self, client: TestClient):
        response = client.get("/recommend")
        assert response.status_code == 422

    def test_recommend_invalid_top_k_returns_422(self, client: TestClient):
        response = client.get("/recommend?user_id=1&top_k=0")
        assert response.status_code == 422

    def test_recommend_top_k_too_high_returns_422(self, client: TestClient):
        response = client.get("/recommend?user_id=1&top_k=101")
        assert response.status_code == 422


class TestRateEndpoint:
    def test_rate_valid_event_returns_200(self, client: TestClient):
        """A valid rating event should return 200 (event is logged locally)."""
        payload = {"user_id": 1, "movie_id": 42, "rating": 4.5}
        response = client.post("/rate", json=payload)
        assert response.status_code == 200

    def test_rate_response_structure(self, client: TestClient):
        payload = {"user_id": 1, "movie_id": 42, "rating": 4.5}
        response = client.post("/rate", json=payload)
        data = response.json()
        assert data["status"] == "ok"
        assert "event" in data
        assert data["event"]["user_id"] == 1
        assert data["event"]["movie_id"] == 42
        assert data["event"]["rating"] == 4.5

    def test_rate_missing_fields_returns_422(self, client: TestClient):
        response = client.post("/rate", json={})
        assert response.status_code == 422

    def test_rate_invalid_rating_returns_422(self, client: TestClient):
        payload = {"user_id": 1, "movie_id": 42, "rating": 6.0}
        response = client.post("/rate", json=payload)
        assert response.status_code == 422

    def test_rate_with_timestamp(self, client: TestClient):
        payload = {"user_id": 1, "movie_id": 42, "rating": 3.0, "timestamp": 1_000_000}
        response = client.post("/rate", json=payload)
        data = response.json()
        assert data["event"]["timestamp"] == 1_000_000

    def test_rate_negative_user_id_returns_422(self, client: TestClient):
        payload = {"user_id": -1, "movie_id": 42, "rating": 4.0}
        response = client.post("/rate", json=payload)
        assert response.status_code == 422


class TestDocsEndpoint:
    def test_docs_returns_200(self, client: TestClient):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json(self, client: TestClient):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "RecoStack Serving API"
        assert "/recommend" in data["paths"]
        assert "/rate" in data["paths"]
        assert "/health" in data["paths"]
        assert "/metrics" in data["paths"]