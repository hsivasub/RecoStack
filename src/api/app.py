"""
FastAPI Application — RecoStack Serving API

Exposes three endpoints:
  - GET  /health      — Health check (models loaded, Redpanda, Feast)
  - GET  /recommend   — Top-K recommendations for a user
  - POST /rate        — Submit a rating event

Run with:
    uvicorn src.api.app:app --reload --port 8000
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, Query

from src.api.event_producer import EventProducer
from src.api.metrics import (
    FEAST_AVAILABLE,
    MODELS_LOADED,
    MODELS_READY,
    PrometheusMiddleware,
    RATE_EVENTS_TOTAL,
    REDPANDA_CONNECTED,
)
from src.api.models import (
    HealthResponse,
    RatingEvent,
    RatingResponse,
    RecommendResponse,
)
from src.api.recommend_service import RecommendService

# ---------------------------------------------------------------------------
# Global service instances (initialized at startup)
# ---------------------------------------------------------------------------

recommend_service = RecommendService()
event_producer = EventProducer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # --- Startup ---
    print("=" * 60)
    print("RecoStack — Serving API (Phase 9 + Phase 10 Monitoring)")
    print("=" * 60)
    recommend_service.initialize()
    event_producer.initialize()

    # Set Prometheus health gauges
    MODELS_LOADED.set(2 if recommend_service.is_ready else 0)
    MODELS_READY.set(1 if recommend_service.is_ready else 0)
    FEAST_AVAILABLE.set(
        1
        if recommend_service.features and recommend_service.features.feast_available
        else 0
    )
    REDPANDA_CONNECTED.set(1 if event_producer.is_connected else 0)

    print("\n✓ API ready at http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("  Metrics: http://localhost:8000/metrics")
    print("=" * 60)
    yield
    # --- Shutdown ---
    event_producer.close()
    print("API shut down")


app = FastAPI(
    title="RecoStack Serving API",
    description="Two-stage recommendation system (SVD candidate generation + LightGBM ranking)",
    version="0.1.0",
    lifespan=lifespan,
)

# Add Prometheus middleware (records HTTP request count & latency)
app.add_middleware(PrometheusMiddleware)


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint (scraped by Prometheus server)."""
    from starlette.responses import Response
    from prometheus_client import generate_latest
    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        models_loaded=recommend_service.is_ready,
        redpanda_connected=event_producer.is_connected,
        feast_available=recommend_service.features.feast_available
        if recommend_service.features
        else False,
    )


@app.get("/recommend", response_model=RecommendResponse)
async def recommend(
    user_id: int = Query(..., ge=1, description="User ID to recommend for"),
    top_k: int = Query(10, ge=1, le=100, description="Number of recommendations"),
):
    """
    Get top-K movie recommendations for a user.

    Uses a two-stage pipeline:
      1. SVD matrix factorization → top-100 candidate movies
      2. LightGBM ranker → score & rank candidates with user/movie features
    """
    if not recommend_service.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Models not loaded. Ensure trained models exist in data/model-artifacts/.",
        )

    try:
        recommendations = recommend_service.recommend(user_id, top_k=top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {e}")

    return RecommendResponse(
        user_id=user_id,
        recommendations=recommendations,
        model_info=recommend_service.model_info,
    )


@app.post("/rate", response_model=RatingResponse)
async def rate(event: RatingEvent):
    """
    Submit a user rating event.

    The event is published to the `user-events` Redpanda topic for downstream
    consumers (feature pipelines, analytics). If Redpanda is not running, the
    event is logged locally.
    """
    # Fill in timestamp if not provided
    ts = event.timestamp or int(datetime.now(tz=UTC).timestamp())
    payload = event.model_dump()
    payload["timestamp"] = ts

    success = event_producer.send_rating(
        user_id=event.user_id,
        movie_id=event.movie_id,
        rating=event.rating,
        timestamp=ts,
    )

    if not success:
        RATE_EVENTS_TOTAL.labels(status="failed").inc()
        raise HTTPException(
            status_code=502,
            detail="Failed to publish rating event to Redpanda",
        )

    # Record event status based on Redpanda connectivity
    status = "published" if event_producer.is_connected else "logged"
    RATE_EVENTS_TOTAL.labels(status=status).inc()

    return RatingResponse(
        status="ok",
        detail="Rating recorded",
        event=RatingEvent(**payload),
    )