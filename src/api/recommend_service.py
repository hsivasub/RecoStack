"""
Recommend Service — Inference Orchestrator

Loads the trained SVD candidate generator and LightGBM ranker from disk,
then orchestrates the two-stage recommendation pipeline for a single user:

  1. SVD → retrieve top-N candidate movie IDs
  2. FeatureService → fetch user & movie features for candidates
  3. LightGBM → score each candidate
  4. Return top-K ranked results with movie metadata
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.feature_service import FeatureService
from src.api.metrics import (
    FEATURE_LOOKUP_DURATION_SECONDS,
    FEATURE_LOOKUP_ERRORS,
    RECOMMEND_CANDIDATES,
    RECOMMEND_ERRORS,
    RECOMMEND_LATENCY_SECONDS,
    RECOMMEND_RESULTS,
)
from src.recommenders.candidate_generation import SVDCandidateGenerator
from src.recommenders.ranking import LightGBMRanker

MODEL_DIR = PROJECT_ROOT / "data" / "model-artifacts"
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / "ml-latest-small"

SVD_PATH = MODEL_DIR / "svd_candidate_generator.pkl"
LGB_PATH = MODEL_DIR / "lightgbm_ranker.txt"


class RecommendService:
    """
    Orchestrates the two-stage recommendation pipeline for inference.

    Usage:
        service = RecommendService()
        service.initialize()
        recs = service.recommend(user_id=42, top_k=10)
    """

    def __init__(self) -> None:
        self.svd: SVDCandidateGenerator | None = None
        self.ranker: LightGBMRanker | None = None
        self.features: FeatureService | None = None
        self._movies_df: pd.DataFrame | None = None
        self._model_info: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Load models from disk and initialize the feature service."""
        print("[RecommendService] Loading SVD candidate generator ...")
        if SVD_PATH.exists():
            self.svd = SVDCandidateGenerator.load(str(SVD_PATH))
            self._model_info["svd_factors"] = self.svd.n_factors
            print(f"  ✓ SVD loaded ({self.svd.n_factors} factors)")
        else:
            print(f"  ✗ SVD model not found at {SVD_PATH}")

        print("[RecommendService] Loading LightGBM ranker ...")
        if LGB_PATH.exists():
            self.ranker = LightGBMRanker.load(str(LGB_PATH))
            self._model_info["lgb_feature_names"] = self.ranker.feature_names
            self._model_info["lgb_params"] = self.ranker.params
            print(f"  ✓ LightGBM loaded ({len(self.ranker.feature_names)} features)")
        else:
            print(f"  ✗ LightGBM model not found at {LGB_PATH}")

        print("[RecommendService] Initializing feature service ...")
        self.features = FeatureService()
        self.features.initialize()

        print("[RecommendService] Loading movie metadata ...")
        self._load_movies()

        print("[RecommendService] Ready")

    def _load_movies(self) -> None:
        """Load movie metadata (title, genres) from CSV."""
        movies_path = RAW_DATA_DIR / "movies.csv"
        if movies_path.exists():
            self._movies_df = pd.read_csv(movies_path)
            self._movies_df["movieId"] = self._movies_df["movieId"].astype(np.int64)
        else:
            print(f"  ✗ Movies CSV not found at {movies_path}")
            self._movies_df = pd.DataFrame(columns=["movieId", "title", "genres"])

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------

    def recommend(self, user_id: int, top_k: int = 10) -> list[dict[str, Any]]:
        """
        Generate top-K recommendations for a user.

        Args:
            user_id: The user to recommend for.
            top_k: Number of recommendations to return (1–100).

        Returns:
            List of dicts with keys: movie_id, title, genres, score.
        """
        start_time = time.monotonic()

        if self.svd is None or self.ranker is None or self.features is None:
            RECOMMEND_ERRORS.labels(reason="models_not_loaded").inc()
            raise RuntimeError(
                "Models not loaded. Call initialize() before recommend()."
            )

        # ------------------------------------------------------------------
        # Stage 1: Candidate generation via SVD
        # ------------------------------------------------------------------
        try:
            candidates = self.svd.get_candidates(user_id, n_candidates=100)
        except Exception:
            RECOMMEND_ERRORS.labels(reason="svd_candidate_generation").inc()
            raise

        if not candidates:
            RECOMMEND_LATENCY_SECONDS.observe(time.monotonic() - start_time)
            return []

        RECOMMEND_CANDIDATES.observe(len(candidates))

        # ------------------------------------------------------------------
        # Stage 2: Feature assembly & ranking
        # ------------------------------------------------------------------

        # Fetch movie features for all candidates
        movie_features = self.features.get_movies_batch(candidates)
        if movie_features.empty:
            RECOMMEND_LATENCY_SECONDS.observe(time.monotonic() - start_time)
            return []

        # Fetch user features
        user_features = self.features.get_user_features(user_id)
        if not user_features:
            # Cold-start: use average user features
            user_features = {
                "user_stats:avg_rating": 3.5,
                "user_stats:rating_count": 0.0,
                "user_stats:rating_stddev": 0.0,
                "user_stats:unique_genres_rated": 0.0,
            }

        # Build feature DataFrame for the ranker
        feature_rows = []
        for mid in candidates:
            if mid not in movie_features.index:
                continue

            mf = movie_features.loc[mid]

            # Derived features (same logic as training_pipeline.py)
            user_deviation = (
                user_features.get("user_stats:avg_rating", 3.5)
                - mf.get("avg_rating", 3.5)
            )
            movie_popularity_log = np.log1p(mf.get("rating_count", 1))
            user_activity_log = np.log1p(user_features.get("user_stats:rating_count", 0))
            genre_count_str = str(mf.get("genres", ""))
            genre_count = genre_count_str.count("|") + 1 if genre_count_str != "nan" else 1

            row = {
                "user_stats__avg_rating": user_features.get("user_stats:avg_rating", 3.5),
                "user_stats__rating_count": user_features.get("user_stats:rating_count", 0),
                "user_stats__rating_stddev": user_features.get("user_stats:rating_stddev", 0),
                "user_stats__unique_genres_rated": user_features.get("user_stats:unique_genres_rated", 0),
                "movie_stats__avg_rating": mf.get("avg_rating", 3.5),
                "movie_stats__rating_count": mf.get("rating_count", 1),
                "movie_stats__rating_stddev": mf.get("rating_stddev", 0),
                "user_deviation": user_deviation,
                "movie_popularity_log": movie_popularity_log,
                "user_activity_log": user_activity_log,
                "genre_count": genre_count,
                "recency_days": 0.0,  # No recency info at inference time
            }
            feature_rows.append((mid, row))

        if not feature_rows:
            RECOMMEND_LATENCY_SECONDS.observe(time.monotonic() - start_time)
            return []

        mids = [fr[0] for fr in feature_rows]
        feature_df = pd.DataFrame([fr[1] for fr in feature_rows])

        # Score with LightGBM
        try:
            scores = self.ranker.predict(feature_df)
        except Exception:
            RECOMMEND_ERRORS.labels(reason="lgbm_prediction").inc()
            raise

        # Sort by score descending
        ranked_indices = np.argsort(-scores)

        results: list[dict[str, Any]] = []
        for idx in ranked_indices[:top_k]:
            mid = mids[idx]
            score = float(scores[idx])
            movie_info = self._get_movie_info(mid)
            results.append({
                "movie_id": mid,
                "title": movie_info.get("title", f"Movie {mid}"),
                "genres": movie_info.get("genres", ""),
                "score": round(score, 4),
            })

        # Record metrics
        RECOMMEND_RESULTS.observe(len(results))
        RECOMMEND_LATENCY_SECONDS.observe(time.monotonic() - start_time)

        return results

    def _get_movie_info(self, movie_id: int) -> dict[str, Any]:
        """Look up movie title and genres by ID."""
        if self._movies_df is None:
            return {}
        row = self._movies_df[self._movies_df["movieId"] == movie_id]
        if row.empty:
            return {}
        return {
            "title": row.iloc[0]["title"],
            "genres": row.iloc[0]["genres"],
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return (
            self.svd is not None
            and self.ranker is not None
            and self.features is not None
            and self.features.is_available
        )

    @property
    def model_info(self) -> dict[str, Any]:
        return self._model_info