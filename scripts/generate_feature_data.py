"""
generate_feature_data.py — Phase 7: Feast Feature Store

Computes user-level and movie-level aggregate features from the raw
MovieLens ratings and movies CSV files, then writes them as Parquet
files in data/features/ for Feast to ingest.

Outputs:
    data/features/user_stats.parquet   — Per-user aggregate features
    data/features/movie_stats.parquet  — Per-movie aggregate features
    data/features/interactions.parquet — Raw ratings as a Feast data source

Usage:
    python scripts/generate_feature_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw" / "ml-latest-small"
FEATURES_DIR = DATA_DIR / "features"

RATINGS_PATH = RAW_DIR / "ratings.csv"
MOVIES_PATH = RAW_DIR / "movies.csv"

USER_STATS_OUT = FEATURES_DIR / "user_stats.parquet"
MOVIE_STATS_OUT = FEATURES_DIR / "movie_stats.parquet"
INTERACTIONS_OUT = FEATURES_DIR / "interactions.parquet"


def load_ratings() -> pd.DataFrame:
    """Load and preprocess the ratings CSV."""
    df = pd.read_csv(RATINGS_PATH)
    df.columns = df.columns.str.strip()
    df["timestamp"] = df["timestamp"].astype(int)
    return df


def load_movies() -> pd.DataFrame:
    """Load and preprocess the movies CSV."""
    df = pd.read_csv(MOVIES_PATH)
    df.columns = df.columns.str.strip()
    return df


def compute_user_stats(ratings: pd.DataFrame) -> pd.DataFrame:
    """Compute per-user aggregate features."""
    stats = (
        ratings.groupby("userId")
        .agg(
            avg_rating=("rating", "mean"),
            rating_count=("rating", "count"),
            rating_stddev=("rating", "std"),
        )
        .reset_index()
    )
    stats.columns = ["user_id", "avg_rating", "rating_count", "rating_stddev"]
    stats["avg_rating"] = stats["avg_rating"].astype(np.float32)
    stats["rating_stddev"] = stats["rating_stddev"].fillna(0.0).astype(np.float32)
    stats["rating_count"] = stats["rating_count"].astype(np.int32)
    stats["user_id"] = stats["user_id"].astype(np.int64)
    return stats


def compute_movie_stats(
    ratings: pd.DataFrame, movies: pd.DataFrame
) -> pd.DataFrame:
    """Compute per-movie aggregate features including genre labels."""
    stats = (
        ratings.groupby("movieId")
        .agg(
            avg_rating=("rating", "mean"),
            rating_count=("rating", "count"),
            rating_stddev=("rating", "std"),
        )
        .reset_index()
    )
    stats.columns = ["movie_id", "avg_rating", "rating_count", "rating_stddev"]
    stats["avg_rating"] = stats["avg_rating"].astype(np.float32)
    stats["rating_stddev"] = stats["rating_stddev"].fillna(0.0).astype(np.float32)
    stats["rating_count"] = stats["rating_count"].astype(np.int32)
    stats["movie_id"] = stats["movie_id"].astype(np.int64)

    # Merge genre information
    movies_subset = movies[["movieId", "genres"]].copy()
    movies_subset.columns = ["movie_id", "genres"]
    movies_subset["movie_id"] = movies_subset["movie_id"].astype(np.int64)
    stats = stats.merge(movies_subset, on="movie_id", how="left")
    stats["genres"] = stats["genres"].fillna("(no genres listed)")
    return stats


def compute_interactions(ratings: pd.DataFrame) -> pd.DataFrame:
    """Format raw ratings as a Feast-compatible interaction source."""
    df = ratings.rename(
        columns={
            "userId": "user_id",
            "movieId": "movie_id",
        }
    )
    df["user_id"] = df["user_id"].astype(np.int64)
    df["movie_id"] = df["movie_id"].astype(np.int64)
    df["rating"] = df["rating"].astype(np.float32)
    return df


def add_feast_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add event_timestamp and created_timestamp columns required by Feast."""
    now = pd.Timestamp.now(tz="UTC")
    df["event_timestamp"] = now
    df["created_timestamp"] = now
    return df


def main() -> None:
    print("=" * 60)
    print("RecoStack — Feature Data Generation")
    print("=" * 60)

    # Ensure output directory exists
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)

    # Load raw data
    print("\n[1/5] Loading ratings.csv ...")
    ratings = load_ratings()
    print(f"       {len(ratings):,} rows loaded")

    print("[2/5] Loading movies.csv ...")
    movies = load_movies()
    print(f"       {len(movies):,} rows loaded")

    # Compute features
    print("[3/5] Computing user stats ...")
    user_stats = compute_user_stats(ratings)
    user_stats = add_feast_columns(user_stats)
    user_stats.to_parquet(USER_STATS_OUT, index=False)
    print(f"       {len(user_stats):,} users → {USER_STATS_OUT}")

    print("[4/5] Computing movie stats ...")
    movie_stats = compute_movie_stats(ratings, movies)
    movie_stats = add_feast_columns(movie_stats)
    movie_stats.to_parquet(MOVIE_STATS_OUT, index=False)
    print(f"       {len(movie_stats):,} movies → {MOVIE_STATS_OUT}")

    print("[5/5] Formatting interactions ...")
    interactions = compute_interactions(ratings)
    interactions = add_feast_columns(interactions)
    interactions.to_parquet(INTERACTIONS_OUT, index=False)
    print(f"       {len(interactions):,} interactions → {INTERACTIONS_OUT}")

    print("\n✓ Feature data generation complete.")
    print(f"  Output directory: {FEATURES_DIR}")


if __name__ == "__main__":
    main()