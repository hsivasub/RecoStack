"""
Prometheus Metrics — RecoStack Serving API

Defines and exposes Prometheus metrics for the FastAPI serving layer.

Metrics available at the `/metrics` endpoint (auto-collected by
prometheus-client's middleware).

Key metrics:
  - HTTP request count & latency (by method, endpoint, status)
  - Recommendation latency & candidate count
  - Rate event count
  - Model health (models loaded, ready state)
  - Feature service health (Feast available, fallback active)
  - Redpanda connection status
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

# ---------------------------------------------------------------------------
# HTTP request metrics
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "recostack_http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "recostack_http_request_duration_seconds",
    "HTTP request latency (seconds)",
    labelnames=["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ---------------------------------------------------------------------------
# Recommendation-specific metrics
# ---------------------------------------------------------------------------

RECOMMEND_LATENCY_SECONDS = Histogram(
    "recostack_recommend_latency_seconds",
    "End-to-end /recommend latency (seconds)",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

RECOMMEND_CANDIDATES = Histogram(
    "recostack_recommend_candidates",
    "Number of candidates retrieved by SVD before ranking",
    buckets=(1, 5, 10, 25, 50, 100, 200),
)

RECOMMEND_RESULTS = Histogram(
    "recostack_recommend_results",
    "Number of recommendations returned (top-K)",
    buckets=(1, 5, 10, 25, 50, 100),
)

RECOMMEND_ERRORS = Counter(
    "recostack_recommend_errors_total",
    "Total recommendation errors",
    labelnames=["reason"],
)

# ---------------------------------------------------------------------------
# Event/Rate metrics
# ---------------------------------------------------------------------------

RATE_EVENTS_TOTAL = Counter(
    "recostack_rate_events_total",
    "Total rating events received",
    labelnames=["status"],  # "published", "logged", "failed"
)

# ---------------------------------------------------------------------------
# System health gauges
# ---------------------------------------------------------------------------

MODELS_LOADED = Gauge(
    "recostack_models_loaded",
    "Number of models loaded (0–2: SVD + LightGBM)",
)

MODELS_READY = Gauge(
    "recostack_models_ready",
    "1 if all models are loaded and ready, 0 otherwise",
)

FEAST_AVAILABLE = Gauge(
    "recostack_feast_available",
    "1 if Feast online store is connected, 0 if on Parquet fallback",
)

REDPANDA_CONNECTED = Gauge(
    "recostack_redpanda_connected",
    "1 if connected to Redpanda, 0 if logging events locally",
)

# ---------------------------------------------------------------------------
# Feature service metrics
# ---------------------------------------------------------------------------

FEATURE_LOOKUP_DURATION_SECONDS = Histogram(
    "recostack_feature_lookup_duration_seconds",
    "Feature retrieval latency (seconds)",
    labelnames=["entity_type"],  # "user" or "movie"
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

FEATURE_LOOKUP_ERRORS = Counter(
    "recostack_feature_lookup_errors_total",
    "Total feature lookup errors",
    labelnames=["entity_type"],
)

# ---------------------------------------------------------------------------
# Helper: serve metrics endpoint
# ---------------------------------------------------------------------------

from starlette.requests import Request
from starlette.responses import Response


async def metrics_endpoint(request: Request) -> Response:
    """Serve Prometheus metrics at GET /metrics."""
    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# ASGI middleware for automatic HTTP metrics
# ---------------------------------------------------------------------------

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that records HTTP request count, latency, and status codes.

    Attaches to the FastAPI app as:
        app.add_middleware(PrometheusMiddleware)

    Excludes the /metrics endpoint itself from recording.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Skip metrics for the /metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = request.url.path

        start = time.monotonic()
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        except Exception as exc:
            status = "500"
            raise
        finally:
            duration = time.monotonic() - start
            HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)