"""
Unit tests — LightGBM Ranker (src/recommenders/ranking.py)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.recommenders.ranking import LightGBMRanker


class TestLightGBMRanker:
    def test_fit_with_default_params(self, sample_training_data: pd.DataFrame):
        ranker = LightGBMRanker()
        feature_cols = [c for c in sample_training_data.columns if c != "interactions__rating"]
        ranker.fit(
            sample_training_data,
            label_col="interactions__rating",
            feature_cols=feature_cols,
            num_boost_round=10,
            early_stopping_rounds=5,
        )
        assert ranker.model is not None
        assert len(ranker.feature_names) == len(feature_cols)

    def test_predict_returns_array(self, sample_training_data: pd.DataFrame):
        ranker = LightGBMRanker()
        feature_cols = [c for c in sample_training_data.columns if c != "interactions__rating"]
        ranker.fit(
            sample_training_data,
            label_col="interactions__rating",
            feature_cols=feature_cols,
            num_boost_round=10,
        )
        preds = ranker.predict(sample_training_data)
        assert isinstance(preds, np.ndarray)
        assert preds.shape == (len(sample_training_data),)

    def test_predict_before_fit_raises(self):
        ranker = LightGBMRanker()
        with pytest.raises(RuntimeError, match="not fitted"):
            ranker.predict(pd.DataFrame({"a": [1.0]}))

    def test_rank_candidates_returns_top_k(self, sample_training_data: pd.DataFrame):
        ranker = LightGBMRanker()
        feature_cols = [c for c in sample_training_data.columns if c != "interactions__rating"]
        ranker.fit(
            sample_training_data,
            label_col="interactions__rating",
            feature_cols=feature_cols,
            num_boost_round=10,
        )
        result = ranker.rank_candidates(sample_training_data, top_k=3)
        assert len(result) == 3
        assert "score" in result.columns
        # Scores should be sorted descending
        scores = result["score"].values
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    def test_feature_importance(self, sample_training_data: pd.DataFrame):
        ranker = LightGBMRanker()
        feature_cols = [c for c in sample_training_data.columns if c != "interactions__rating"]
        ranker.fit(
            sample_training_data,
            label_col="interactions__rating",
            feature_cols=feature_cols,
            num_boost_round=10,
        )
        importance = ranker.feature_importance("gain")
        assert isinstance(importance, dict)
        assert set(importance.keys()) == set(feature_cols)
        assert all(v >= 0 for v in importance.values())

    def test_feature_importance_before_fit_raises(self):
        ranker = LightGBMRanker()
        with pytest.raises(RuntimeError, match="not fitted"):
            ranker.feature_importance()

    def test_save_and_load_roundtrip(self, sample_training_data: pd.DataFrame, tmp_path: Path):
        ranker = LightGBMRanker()
        feature_cols = [c for c in sample_training_data.columns if c != "interactions__rating"]
        ranker.fit(
            sample_training_data,
            label_col="interactions__rating",
            feature_cols=feature_cols,
            num_boost_round=10,
        )

        model_path = tmp_path / "lgb_test.txt"
        ranker.save(str(model_path))

        loaded = LightGBMRanker.load(str(model_path))
        assert loaded.model is not None
        assert loaded.feature_names == feature_cols
        assert loaded.params == ranker.params

        # Predictions should match
        orig_preds = ranker.predict(sample_training_data)
        loaded_preds = loaded.predict(sample_training_data)
        np.testing.assert_array_almost_equal(orig_preds, loaded_preds)

    def test_auto_feature_detection(self, sample_training_data: pd.DataFrame):
        """When feature_cols is None, should auto-detect non-id columns."""
        ranker = LightGBMRanker()
        df = sample_training_data.copy()
        df["user_id"] = [1, 1, 2, 2, 3]
        df["movie_id"] = [1, 2, 3, 4, 1]

        ranker.fit(df, label_col="interactions__rating", num_boost_round=10)
        # Should exclude user_id, movie_id, and the label
        assert "user_id" not in ranker.feature_names
        assert "movie_id" not in ranker.feature_names
        assert "interactions__rating" not in ranker.feature_names