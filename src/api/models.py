"""
Pydantic Models — RecoStack Serving API

Defines the request/response schemas for the FastAPI endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RatingEvent(BaseModel):
    """A user rating event submitted via POST /rate."""

    user_id: int = Field(..., ge=1, description="ID of the user submitting the rating")
    movie_id: int = Field(..., ge=1, description="ID of the movie being rated")
    rating: float = Field(..., ge=0.5, le=5.0, description="Rating value (0.5–5.0)")
    timestamp: int | None = Field(None, description="Unix timestamp (defaults to now)")


class RecommendRequest(BaseModel):
    """Query parameters for GET /recommend."""

    user_id: int = Field(..., ge=1, description="ID of the user to recommend for")
    top_k: int = Field(10, ge=1, le=100, description="Number of recommendations to return")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MovieInfo(BaseModel):
    """Minimal movie information returned in recommendations."""

    movie_id: int
    title: str
    genres: str
    score: float = Field(..., description="Predicted relevance score from the ranker")


class RecommendResponse(BaseModel):
    """Response from GET /recommend."""

    user_id: int
    recommendations: list[MovieInfo]
    model_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the models used (SVD factors, LGB rounds, etc.)",
    )


class RatingResponse(BaseModel):
    """Response from POST /rate."""

    status: str = "ok"
    detail: str = "Rating recorded"
    event: RatingEvent


class HealthResponse(BaseModel):
    """Response from GET /health."""

    status: str = "ok"
    models_loaded: bool = False
    redpanda_connected: bool = False
    feast_available: bool = False