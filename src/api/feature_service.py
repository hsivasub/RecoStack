"""
Feature Service — Online Feature Retrieval for Serving

Provides a unified interface for fetching user and movie features at
inference time. Supports two backends:

  1. **Feast online store** (Redis) — low-latency, used when Redis is running
  2. **Parquet fallback** — loads features from the Parquet files directly

The service auto-detects which backend is available and falls back gracefully.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FEAST_REPO_PATH = PROJECT_ROOT / "config" / "feast"
FEATURES_DIR = PROJECT_ROOT / "data" / "features"


class FeatureService:
    """
    Online feature retrieval for the serving layer.

    Provides user_stats and movie_stats features needed by the ranking model.
    """

    def __init__(self) -> None:
        self._store: Any = None  # Feast FeatureStore (lazy)
        self._user_df: pd.DataFrame | None = None
        self._movie_df: pd.DataFrame | None = None
        self._feast_available: bool = False

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Attempt to connect to Feast; fall back to Parquet on failure."""
        # Try Feast online store first
        try:
            from feast import FeatureStore

            store = FeatureStore(repo_path=str(FEAST_REPO_PATH))
            # Quick connectivity check: try to get online features for a known user
            _ = store.get_online_features(
                features=["user_stats:avg_rating"],
                entity_rows=[{"user_id": 1}],
            ).to_dict()
            self._store = store
            self._feast_available = True
            print("[FeatureService] Connected to Feast online store")
        except Exception as e:
            print(f"[FeatureService] Feast unavailable ({e}); using Parquet fallback")

        # Always load Parquet data as fallback / warm cache
        self._load_parquet_fallback()

    def _load_parquet_fallback(self) -> None:
        """Load feature DataFrames from Parquet files."""
        user_path = FEATURES_DIR / "user_stats.parquet"
        movie_path = FEATURES_DIR / "movie_stats.parquet"

        if user_path.exists():
            self._user_df = pd.read_parquet(user_path)
            # Ensure int64 dtype for join keys
            self._user_df["user_id"] = self._user_df["user_id"].astype(np.int64)
        else:
            print(f"[FeatureService] WARNING: {user_path} not found")

        if movie_path.exists():
            self._movie_df = pd.read_parquet(movie_path)
            self._movie_df["movie_id"] = self._movie_df["movie_id"].astype(np.int64)
        else:
            print(f"[FeatureService] WARNING: {movie_path} not found")

    # ------------------------------------------------------------------
    # Feature retrieval
    # ------------------------------------------------------------------

    def get_user_features(self, user_id: int) -> dict[str, float]:
        """
        Retrieve user stats features for a single user.

        Returns a dict of feature_name -> value, or an empty dict if the
        user is unknown (cold-start).
        """
        if self._feast_available and self._store is not None:
            return self._get_user_features_feast(user_id)
        return self._get_user_features_parquet(user_id)

    def get_movie_features(self, movie_id: int) -> dict[str, float]:
        """
        Retrieve movie stats features for a single movie.

        Returns a dict of feature_name -> value, or an empty dict if the
        movie is unknown (cold-start).
        """
        if self._feast_available and self._store is not None:
            return self._get_movie_features_feast(movie_id)
        return self._get_movie_features_parquet(movie_id)

    def get_movies_batch(self, movie_ids: list[int]) -> pd.DataFrame:
        """
        Retrieve movie features for a batch of movie IDs.

        Returns a DataFrame with movie_id as the index and feature columns.
        """
        if self._movie_df is not None:
            mask = self._movie_df["movie_id"].isin(movie_ids)
            return self._movie_df[mask].set_index("movie_id")
        return pd.DataFrame()

    def get_user_features_batch(self, user_ids: list[int]) -> pd.DataFrame:
        """Retrieve user features for a batch of user IDs."""
        if self._user_df is not None:
            mask = self._user_df["user_id"].isin(user_ids)
            return self._user_df[mask].set_index("user_id")
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Feast backend
    # ------------------------------------------------------------------

    def _get_user_features_feast(self, user_id: int) -> dict[str, float]:
        assert self._store is not None
        try:
            result = self._store.get_online_features(
                features=[
                    "user_stats:avg_rating",
                    "user_stats:rating_count",
                    "user_stats:rating_stddev",
                    "user_stats:unique_genres_rated",
                ],
                entity_rows=[{"user_id": user_id}],
            ).to_dict()
            return {
                k: (float(v[0]) if v[0] is not None else 0.0)
                for k, v in result.items()
            }
        except Exception:
            return self._get_user_features_parquet(user_id)

    def _get_movie_features_feast(self, movie_id: int) -> dict[str, float]:
        assert self._store is not None
        try:
            result = self._store.get_online_features(
                features=[
                    "movie_stats:avg_rating",
                    "movie_stats:rating_count",
                    "movie_stats:rating_stddev",
                ],
                entity_rows=[{"movie_id": movie_id}],
            ).to_dict()
            return {
                k: (float(v[0]) if v[0] is not None else 0.0)
                for k, v in result.items()
            }
        except Exception:
            return self._get_movie_features_parquet(movie_id)

    # ------------------------------------------------------------------
    # Parquet fallback backend
    # ------------------------------------------------------------------

    def _get_user_features_parquet(self, user_id: int) -> dict[str, float]:
        if self._user_df is None:
            return {}
        row = self._user_df[self._user_df["user_id"] == user_id]
        if row.empty:
            return {}
        row = row.iloc[0]
        return {
            "user_stats:avg_rating": float(row["avg_rating"]),
            "user_stats:rating_count": float(row["rating_count"]),
            "user_stats:rating_stddev": float(row["rating_stddev"]),
            "user_stats:unique_genres_rated": float(row["unique_genres_rated"]),
        }

    def _get_movie_features_parquet(self, movie_id: int) -> dict[str, float]:
        if self._movie_df is None:
            return {}
        row = self._movie_df[self._movie_df["movie_id"] == movie_id]
        if row.empty:
            return {}
        row = row.iloc[0]
        return {
            "movie_stats:avg_rating": float(row["avg_rating"]),
            "movie_stats:rating_count": float(row["rating_count"]),
            "movie_stats:rating_stddev": float(row["rating_stddev"]),
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return self._user_df is not None or self._feast_available

    @property
    def feast_available(self) -> bool:
        return self._feast_available