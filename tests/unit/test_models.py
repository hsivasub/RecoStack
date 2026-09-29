"""
Unit tests — Pydantic models (src/api/models.py)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.models import (
    HealthResponse,
    MovieInfo,
    RatingEvent,
    RatingResponse,
    RecommendRequest,
    RecommendResponse,
)


class TestRatingEvent:
    def test_valid_rating(self):
        event = RatingEvent(user_id=1, movie_id=42, rating=4.5)
        assert event.user_id == 1
        assert event.movie_id == 42
        assert event.rating == 4.5
        assert event.timestamp is None  # defaults to None

    def test_valid_rating_with_timestamp(self):
        event = RatingEvent(user_id=1, movie_id=42, rating=3.0, timestamp=1_000_000)
        assert event.timestamp == 1_000_000

    def test_invalid_user_id_zero(self):
        with pytest.raises(ValidationError):
            RatingEvent(user_id=0, movie_id=42, rating=4.0)

    def test_invalid_movie_id_zero(self):
        with pytest.raises(ValidationError):
            RatingEvent(user_id=1, movie_id=0, rating=4.0)

    def test_invalid_rating_too_low(self):
        with pytest.raises(ValidationError):
            RatingEvent(user_id=1, movie_id=42, rating=0.0)

    def test_invalid_rating_too_high(self):
        with pytest.raises(ValidationError):
            RatingEvent(user_id=1, movie_id=42, rating=5.5)

    def test_boundary_ratings(self):
        """0.5 and 5.0 are valid boundaries."""
        low = RatingEvent(user_id=1, movie_id=42, rating=0.5)
        assert low.rating == 0.5
        high = RatingEvent(user_id=1, movie_id=42, rating=5.0)
        assert high.rating == 5.0


class TestRecommendRequest:
    def test_default_top_k(self):
        req = RecommendRequest(user_id=1)
        assert req.top_k == 10

    def test_custom_top_k(self):
        req = RecommendRequest(user_id=1, top_k=25)
        assert req.top_k == 25

    def test_invalid_top_k_zero(self):
        with pytest.raises(ValidationError):
            RecommendRequest(user_id=1, top_k=0)

    def test_invalid_top_k_too_high(self):
        with pytest.raises(ValidationError):
            RecommendRequest(user_id=1, top_k=101)


class TestMovieInfo:
    def test_valid_movie_info(self):
        info = MovieInfo(movie_id=1, title="Toy Story", genres="Animation", score=0.95)
        assert info.movie_id == 1
        assert info.title == "Toy Story"
        assert info.score == 0.95


class TestRecommendResponse:
    def test_valid_response(self):
        recs = [
            MovieInfo(movie_id=1, title="A", genres="X", score=0.9),
            MovieInfo(movie_id=2, title="B", genres="Y", score=0.8),
        ]
        resp = RecommendResponse(user_id=1, recommendations=recs)
        assert len(resp.recommendations) == 2
        assert resp.model_info == {}

    def test_with_model_info(self):
        resp = RecommendResponse(
            user_id=1,
            recommendations=[],
            model_info={"svd_factors": 50, "lgb_features": 12},
        )
        assert resp.model_info["svd_factors"] == 50


class TestRatingResponse:
    def test_valid_response(self):
        event = RatingEvent(user_id=1, movie_id=42, rating=4.0)
        resp = RatingResponse(event=event)
        assert resp.status == "ok"
        assert resp.event.rating == 4.0

    def test_custom_status(self):
        event = RatingEvent(user_id=1, movie_id=42, rating=4.0)
        resp = RatingResponse(status="error", detail="Failed", event=event)
        assert resp.status == "error"


class TestHealthResponse:
    def test_defaults(self):
        resp = HealthResponse()
        assert resp.status == "ok"
        assert resp.models_loaded is False
        assert resp.redpanda_connected is False
        assert resp.feast_available is False

    def test_all_healthy(self):
        resp = HealthResponse(
            status="ok",
            models_loaded=True,
            redpanda_connected=True,
            feast_available=True,
        )
        assert resp.models_loaded
        assert resp.redpanda_connected
        assert resp.feast_available