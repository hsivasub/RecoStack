"""
Shared Test Fixtures — RecoStack

Provides pytest fixtures used across unit and integration tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Small synthetic datasets for unit tests
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_ratings() -> pd.DataFrame:
    """A tiny rating matrix: 3 users × 4 movies, 10 ratings."""
    return pd.DataFrame({
        "user_id": pd.array([1, 1, 1, 2, 2, 2, 2, 3, 3, 3], dtype="int64"),
        "movie_id": pd.array([1, 2, 3, 1, 2, 3, 4, 1, 3, 4], dtype="int64"),
        "rating": [5.0, 3.0, 4.0, 4.0, 2.0, 5.0, 3.5, 1.0, 2.0, 4.0],
    })


@pytest.fixture
def sample_user_features() -> pd.DataFrame:
    """User stats features for 3 users."""
    return pd.DataFrame({
        "user_id": pd.array([1, 2, 3], dtype="int64"),
        "avg_rating": [4.0, 3.625, 2.333],
        "rating_count": [3, 4, 3],
        "rating_stddev": [0.8165, 1.1087, 1.2472],
        "unique_genres_rated": [3, 4, 2],
    })


@pytest.fixture
def sample_movie_features() -> pd.DataFrame:
    """Movie stats features for 4 movies."""
    return pd.DataFrame({
        "movie_id": pd.array([1, 2, 3, 4], dtype="int64"),
        "avg_rating": [3.333, 2.5, 3.667, 3.75],
        "rating_count": [3, 2, 3, 2],
        "rating_stddev": [1.6997, 0.5, 1.2472, 0.3536],
        "genres": [
            "Adventure|Animation|Children|Comedy|Fantasy",
            "Comedy|Romance",
            "Action|Crime|Thriller",
            "Drama",
        ],
    })


@pytest.fixture
def sample_training_data() -> pd.DataFrame:
    """Pre-joined training data with Feast-style prefixed columns."""
    return pd.DataFrame({
        "user_stats__avg_rating": [4.0, 4.0, 3.625, 3.625, 2.333],
        "user_stats__rating_count": [3, 3, 4, 4, 3],
        "user_stats__rating_stddev": [0.8165, 0.8165, 1.1087, 1.1087, 1.2472],
        "user_stats__unique_genres_rated": [3, 3, 4, 4, 2],
        "movie_stats__avg_rating": [3.333, 2.5, 3.667, 3.75, 3.333],
        "movie_stats__rating_count": [3, 2, 3, 2, 3],
        "movie_stats__rating_stddev": [1.6997, 0.5, 1.2472, 0.3536, 1.6997],
        "movie_stats__genres": [
            "Adventure|Animation|Children|Comedy|Fantasy",
            "Comedy|Romance",
            "Action|Crime|Thriller",
            "Drama",
            "Adventure|Animation|Children|Comedy|Fantasy",
        ],
        "interactions__rating": [5.0, 3.0, 2.0, 3.5, 2.0],
        "interactions__timestamp": [1_000_000, 1_000_100, 1_000_200, 1_000_300, 1_000_400],
    })


@pytest.fixture
def sample_movies_csv(tmp_path: Path) -> Path:
    """Write a small movies.csv to a temp directory and return the path."""
    path = tmp_path / "ml-latest-small" / "movies.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "movieId,title,genres\n"
        "1,Toy Story (1995),Adventure|Animation|Children|Comedy|Fantasy\n"
        "2,Jumanji (1995),Adventure|Children|Fantasy\n"
        "3,Grumpier Old Men (1995),Comedy|Romance\n"
        "4,Waiting to Exhale (1995),Comedy|Drama|Romance\n"
    )
    return path