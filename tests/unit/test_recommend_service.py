"""
Unit tests — Recommend Service (src/api/recommend_service.py)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.api.recommend_service import RecommendService


class TestRecommendService:
    def test_initialize_without_model_files(self):
        """Should not crash when model files don't exist."""
        service = RecommendService()
        service.initialize()
        assert service.svd is None
        assert service.ranker is None
        assert service.is_ready is False

    def test_recommend_without_models_raises(self):
        service = RecommendService()
        with pytest.raises(RuntimeError, match="not loaded"):
            service.recommend(user_id=1)

    def test_model_info_empty_when_not_loaded(self):
        service = RecommendService()
        service.initialize()
        assert service.model_info == {}

    def test_get_movie_info_returns_empty_when_no_movies(self):
        service = RecommendService()
        service._movies_df = None
        info = service._get_movie_info(1)
        assert info == {}

    def test_get_movie_info_with_data(self, sample_movies_csv: Path):
        service = RecommendService()
        service._movies_df = pd.read_csv(sample_movies_csv)
        service._movies_df["movieId"] = service._movies_df["movieId"].astype(np.int64)

        info = service._get_movie_info(1)
        assert info["title"] == "Toy Story (1995)"
        assert "Animation" in info["genres"]

        info = service._get_movie_info(999)
        assert info == {}


class TestRecommendServiceWithMocks:
    @patch("src.api.recommend_service.SVDCandidateGenerator")
    @patch("src.api.recommend_service.LightGBMRanker")
    @patch("src.api.recommend_service.FeatureService")
    def test_recommend_flow(
        self,
        mock_feature_cls,
        mock_ranker_cls,
        mock_svd_cls,
    ):
        """Test the recommend flow with mocked models."""
        # Mock SVD
        mock_svd = MagicMock()
        mock_svd.get_candidates.return_value = [1, 2, 3]
        mock_svd.n_factors = 50
        mock_svd_cls.load.return_value = mock_svd

        # Mock Ranker
        mock_ranker = MagicMock()
        mock_ranker.feature_names = [
            "user_stats__avg_rating",
            "movie_stats__avg_rating",
            "user_deviation",
            "movie_popularity_log",
            "user_activity_log",
            "genre_count",
            "recency_days",
        ]
        mock_ranker.params = {"objective": "regression"}
        mock_ranker.predict.return_value = np.array([0.9, 0.8, 0.7])
        mock_ranker_cls.load.return_value = mock_ranker

        # Mock FeatureService
        mock_feat = MagicMock()
        movie_df = pd.DataFrame({
            "avg_rating": [3.5, 4.0, 3.0],
            "rating_count": [100, 50, 200],
            "rating_stddev": [1.0, 0.8, 1.2],
            "genres": ["Comedy", "Drama", "Action"],
        }, index=pd.Index([1, 2, 3], name="movie_id"))
        mock_feat.get_movies_batch.return_value = movie_df
        mock_feat.get_user_features.return_value = {
            "user_stats:avg_rating": 4.0,
            "user_stats:rating_count": 50.0,
            "user_stats:rating_stddev": 0.5,
            "user_stats:unique_genres_rated": 10.0,
        }
        mock_feat.is_available = True
        mock_feat_cls.return_value = mock_feat

        # Mock movies CSV
        service = RecommendService()
        service._movies_df = pd.DataFrame({
            "movieId": pd.array([1, 2, 3], dtype="int64"),
            "title": ["Movie A", "Movie B", "Movie C"],
            "genres": ["Comedy", "Drama", "Action"],
        })

        # Wire mocks
        service.svd = mock_svd
        service.ranker = mock_ranker
        service.features = mock_feat
        service._model_info = {"svd_factors": 50}

        # Run recommendation
        results = service.recommend(user_id=1, top_k=2)
        assert len(results) == 2
        assert results[0]["score"] >= results[1]["score"]  # sorted descending
        assert all(r["movie_id"] in [1, 2, 3] for r in results)
        assert all("title" in r for r in results)