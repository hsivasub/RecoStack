"""
Integration tests — Training Pipeline (src/recommenders/training_pipeline.py)

Tests the training pipeline orchestrator with synthetic data.
Uses a temporary Feast repo to avoid touching the real registry.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.recommenders.training_pipeline import (
    TrainingConfig,
    prepare_ranking_features,
)


class TestPrepareRankingFeatures:
    def test_prepare_ranking_features_returns_expected_shape(
        self, sample_training_data: pd.DataFrame
    ):
        """Should split data and return feature columns."""
        train_df, val_df, feature_cols = prepare_ranking_features(
            sample_training_data, label_col="interactions__rating"
        )

        # Check derived features exist
        assert "user_deviation" in train_df.columns
        assert "movie_popularity_log" in train_df.columns
        assert "user_activity_log" in train_df.columns
        assert "genre_count" in train_df.columns
        assert "recency_days" in train_df.columns

        # Check feature columns are returned
        assert len(feature_cols) > 0
        assert "user_deviation" in feature_cols

    def test_prepare_ranking_features_split_ratio(
        self, sample_training_data: pd.DataFrame
    ):
        """80/20 split should be approximately correct."""
        train_df, val_df, _ = prepare_ranking_features(
            sample_training_data, label_col="interactions__rating"
        )
        total = len(train_df) + len(val_df)
        assert len(train_df) == pytest.approx(total * 0.8, abs=1)
        assert len(val_df) == pytest.approx(total * 0.2, abs=1)

    def test_prepare_ranking_features_drops_nan(
        self, sample_training_data: pd.DataFrame
    ):
        """Rows with NaN in feature columns should be dropped."""
        df = sample_training_data.copy()
        df.loc[0, "user_stats__avg_rating"] = np.nan

        train_df, val_df, _ = prepare_ranking_features(
            df, label_col="interactions__rating"
        )
        total = len(train_df) + len(val_df)
        assert total == len(df) - 1  # one row dropped

    def test_prepare_ranking_features_time_based_split(
        self, sample_training_data: pd.DataFrame
    ):
        """Split should be time-based (sorted by timestamp)."""
        train_df, val_df, _ = prepare_ranking_features(
            sample_training_data, label_col="interactions__rating"
        )
        # Training timestamps should all be <= validation timestamps
        train_max_ts = train_df["interactions__timestamp"].max()
        val_min_ts = val_df["interactions__timestamp"].min()
        assert train_max_ts <= val_min_ts


class TestTrainingConfig:
    def test_default_values(self):
        config = TrainingConfig()
        assert config.svd_n_factors == 50
        assert config.lgb_num_boost_round == 200
        assert config.n_candidates == 100
        assert config.test_ratio == 0.2

    def test_custom_values(self):
        config = TrainingConfig(svd_n_factors=20, lgb_num_boost_round=50)
        assert config.svd_n_factors == 20
        assert config.lgb_num_boost_round == 50