"""
Ranking Model — LightGBM Ranker

Takes candidate items (from Stage 1) along with user and item features,
and scores them with a gradient-boosted tree model. This is Stage 2 of
the two-stage retrieval + ranking architecture.

The model is trained with a pointwise regression objective (RMSE) since
we have explicit ratings. For implicit feedback, a pairwise ranking
objective (lambdarank) would be more appropriate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd


class LightGBMRanker:
    """
    LightGBM-based ranking model.

    Attributes:
        params: LightGBM training parameters.
        model: The fitted Booster instance.
        feature_names: List of feature column names used during training.
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {
            "objective": "regression",
            "metric": "rmse",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "seed": 42,
            "num_threads": -1,  # use all cores
        }
        self.model: lgb.Booster | None = None
        self.feature_names: list[str] = []

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(
        self,
        train_df: pd.DataFrame,
        label_col: str = "rating",
        feature_cols: list[str] | None = None,
        valid_df: pd.DataFrame | None = None,
        num_boost_round: int = 200,
        early_stopping_rounds: int = 20,
    ) -> "LightGBMRanker":
        """
        Train the LightGBM ranking model.

        Args:
            train_df: Training DataFrame with features and label.
            label_col: Name of the target column.
            feature_cols: List of feature column names. If None, all
                          columns except label_col and id columns are used.
            valid_df: Optional validation DataFrame for early stopping.
            num_boost_round: Maximum number of boosting rounds.
            early_stopping_rounds: Early stopping patience.
        """
        # Determine feature columns
        id_cols = {"user_id", "movie_id", label_col}
        if feature_cols is None:
            feature_cols = [c for c in train_df.columns if c not in id_cols]

        self.feature_names = feature_cols

        X_train = train_df[feature_cols].values
        y_train = train_df[label_col].values

        # Create LightGBM datasets
        train_data = lgb.Dataset(X_train, label=y_train)

        valid_sets: list[lgb.Dataset] = [train_data]
        valid_names: list[str] = ["train"]

        if valid_df is not None:
            X_valid = valid_df[feature_cols].values
            y_valid = valid_df[label_col].values
            valid_data = lgb.Dataset(X_valid, label=y_valid, reference=train_data)
            valid_sets.append(valid_data)
            valid_names.append("valid")

        # Train
        self.model = lgb.train(
            self.params,
            train_data,
            num_boost_round=num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=[lgb.early_stopping(early_stopping_rounds)],
        )

        return self

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """
        Score candidate items.

        Args:
            features: DataFrame with the same feature columns used in training.

        Returns:
            Array of predicted scores (higher = better recommendation).
        """
        if self.model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        X = features[self.feature_names].values
        return self.model.predict(X)

    def rank_candidates(
        self,
        candidates_df: pd.DataFrame,
        top_k: int = 10,
    ) -> pd.DataFrame:
        """
        Score and rank candidate items.

        Args:
            candidates_df: DataFrame with features for candidate items.
            top_k: Number of top items to return.

        Returns:
            DataFrame with candidates sorted by predicted score descending,
            with an added 'score' column.
        """
        scores = self.predict(candidates_df)
        result = candidates_df.copy()
        result["score"] = scores
        result = result.sort_values("score", ascending=False).head(top_k)
        return result

    # ------------------------------------------------------------------
    # Feature importance
    # ------------------------------------------------------------------

    def feature_importance(self, importance_type: str = "gain") -> dict[str, float]:
        """
        Return feature importance as a dict.

        Args:
            importance_type: 'gain' (default) or 'split'.

        Returns:
            Dict mapping feature names to importance values.
        """
        if self.model is None:
            raise RuntimeError("Model not fitted.")
        importances = self.model.feature_importance(importance_type=importance_type)
        return dict(zip(self.feature_names, map(float, importances)))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Serialize the model to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.model is None:
            raise RuntimeError("No model to save.")
        self.model.save_model(str(path))
        # Also save feature names as sidecar JSON
        meta_path = path.with_suffix(".json")
        with open(meta_path, "w") as f:
            json.dump(
                {
                    "feature_names": self.feature_names,
                    "params": self.params,
                },
                f,
                indent=2,
            )

    @staticmethod
    def load(path: str | Path) -> "LightGBMRanker":
        """Load a serialized model from disk."""
        path = Path(path)
        ranker = LightGBMRanker()
        ranker.model = lgb.Booster(model_file=str(path))
        # Restore feature names from sidecar
        meta_path = path.with_suffix(".json")
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            ranker.feature_names = meta.get("feature_names", [])
        return ranker