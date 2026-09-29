"""
Unit tests — Prometheus Metrics (src/api/metrics.py)
"""

from __future__ import annotations

import time

import pytest
from prometheus_client import generate_latest, REGISTRY

from src.api.metrics import (
    FEATURE_LOOKUP_DURATION_SECONDS,
    FEATURE_LOOKUP_ERRORS,
    FEAST_AVAILABLE,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    MODELS_LOADED,
    MODELS_READY,
    RATE_EVENTS_TOTAL,
    RECOMMEND_CANDIDATES,
    RECOMMEND_ERRORS,
    RECOMMEND_LATENCY_SECONDS,
    RECOMMEND_RESULTS,
    REDPANDA_CONNECTED,
)


class TestMetricsRegistry:
    """Verify all metrics are properly registered and incrementable."""

    def test_http_requests_total(self):
        HTTP_REQUESTS_TOTAL.labels(method="GET", endpoint="/health", status="200").inc()
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_http_requests_total" in metric_names

    def test_http_request_duration(self):
        HTTP_REQUEST_DURATION_SECONDS.labels(method="GET", endpoint="/health").observe(0.05)
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_http_request_duration_seconds" in metric_names

    def test_recommend_latency(self):
        RECOMMEND_LATENCY_SECONDS.observe(0.1)
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_recommend_latency_seconds" in metric_names

    def test_recommend_candidates(self):
        RECOMMEND_CANDIDATES.observe(100)
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_recommend_candidates" in metric_names

    def test_recommend_results(self):
        RECOMMEND_RESULTS.observe(10)
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_recommend_results" in metric_names

    def test_recommend_errors(self):
        RECOMMEND_ERRORS.labels(reason="svd_failed").inc()
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_recommend_errors_total" in metric_names

    def test_rate_events(self):
        RATE_EVENTS_TOTAL.labels(status="published").inc()
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_rate_events_total" in metric_names

    def test_models_loaded(self):
        MODELS_LOADED.set(2)
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_models_loaded" in metric_names

    def test_models_ready(self):
        MODELS_READY.set(1)
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_models_ready" in metric_names

    def test_feast_available(self):
        FEAST_AVAILABLE.set(1)
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_feast_available" in metric_names

    def test_redpanda_connected(self):
        REDPANDA_CONNECTED.set(1)
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_redpanda_connected" in metric_names

    def test_feature_lookup_duration(self):
        FEATURE_LOOKUP_DURATION_SECONDS.labels(entity_type="user").observe(0.01)
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_feature_lookup_duration_seconds" in metric_names

    def test_feature_lookup_errors(self):
        FEATURE_LOOKUP_ERRORS.labels(entity_type="movie").inc()
        sample = list(REGISTRY.collect())
        metric_names = {m.name for m in sample}
        assert "recostack_feature_lookup_errors_total" in metric_names

    def test_generate_latest_returns_bytes(self):
        output = generate_latest()
        assert isinstance(output, bytes)
        text = output.decode("utf-8")
        assert text.startswith("# HELP") or text.startswith("# TYPE")

    def test_all_metrics_in_output(self):
        """All recostack metrics should appear in the /metrics output."""
        output = generate_latest().decode("utf-8")
        assert "recostack_" in output
        assert "recostack_http_requests_total" in output
        assert "recostack_recommend_latency_seconds" in output
        assert "recostack_models_loaded" in output