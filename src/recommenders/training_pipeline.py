"""
Training Pipeline Orchestrator — RecoStack

Orchestrates the end-to-end training workflow:
  1. Retrieve historical features from Feast
  2. Train SVD candidate generation model
  3. Build ranking feature set (user stats + movie stats + interaction features)
  4. Train LightGBM ranking model
  5. Log params, metrics, and artifacts to MLflow
  6. Save model artifacts to disk

Usage (via CLI):
    python scripts/train_models.py
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Fix Windows cp1252 terminal for MLflow emoji and Unicode arrows
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

# Ensure project root is on sys.path
# training_pipeline.py is at src/recommenders/training_pipeline.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from feast import FeatureStore
from src.recommenders.candidate_generation import SVDCandidateGenerator
from src.recommenders.ranking import LightGBMRanker


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEAST_REPO_PATH = PROJECT_ROOT / "config" / "feast"
MODEL_DIR = PROJECT_ROOT / "data" / "model-artifacts"
TRAINING_DATA_DIR = PROJECT_ROOT / "data" / "training"


@dataclass
class TrainingConfig:
    """Central configuration for the training pipeline."""

    # SVD parameters
    svd_n_factors: int = 50
    svd_n_iter: int = 10

    # LightGBM parameters
    lgb_num_boost_round: int = 200
    lgb_early_stopping: int = 20
    lgb_params: dict = field(
        default_factory=lambda: {
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
        }
    )

    # Data split
    test_ratio: float = 0.2
    val_ratio_from_train: float = 0.1  # 10% of training set → validation

    # MLflow — local file-based tracking (no server needed)
    mlflow_tracking_uri: str = ""
    experiment_name: str = "recostack-training"

    # Candidate generation
    n_candidates: int = 100

    # Random seed
    random_state: int = 42


# ---------------------------------------------------------------------------
# Data loading & preparation
# ---------------------------------------------------------------------------


def load_feast_features(
    store: FeatureStore,
    ratings_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Retrieve historical features from Feast for all user-movie interactions.

    Args:
        store: A connected Feast FeatureStore.
        ratings_df: DataFrame with columns [user_id, movie_id, rating, event_timestamp].

    Returns:
        DataFrame with all features joined (user_stats + movie_stats + interactions).
    """
    # Build entity DataFrame for historical retrieval
    entity_df = ratings_df[["user_id", "movie_id", "event_timestamp"]].copy()

    # Retrieve features
    feature_refs = [
        "user_stats:avg_rating",
        "user_stats:rating_count",
        "user_stats:rating_stddev",
        "user_stats:unique_genres_rated",
        "movie_stats:avg_rating",
        "movie_stats:rating_count",
        "movie_stats:rating_stddev",
        "movie_stats:genres",
        "interactions:rating",
        "interactions:timestamp",
    ]

    training_data = store.get_historical_features(
        entity_df=entity_df,
        features=feature_refs,
        full_feature_names=True,
    ).to_df()

    return training_data


def prepare_ranking_features(
    training_data: pd.DataFrame,
    label_col: str = "interactions__rating",
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """
    Prepare feature matrix for the ranking model.

    Creates derived features from the raw Feast features and splits
    into train/validation sets.

    Returns:
        Tuple of (train_df, val_df, feature_names).
    """
    df = training_data.copy()

    # --- Derived features ---

    # User's rating deviation from movie average
    df["user_deviation"] = df["interactions__rating"] - df["movie_stats__avg_rating"]

    # Movie popularity tier (log transform of rating count)
    df["movie_popularity_log"] = np.log1p(df["movie_stats__rating_count"])

    # User activity tier
    df["user_activity_log"] = np.log1p(df["user_stats__rating_count"])

    # Genre match indicator
    df["genre_count"] = df["movie_stats__genres"].str.count(r"\|") + 1

    # Interaction recency (how recent is the rating in days)
    max_ts = df["interactions__timestamp"].max()
    df["recency_days"] = (max_ts - df["interactions__timestamp"]) / (24 * 3600)

    # --- Feature columns ---
    feature_cols = [
        # User stats
        "user_stats__avg_rating",
        "user_stats__rating_count",
        "user_stats__rating_stddev",
        "user_stats__unique_genres_rated",
        # Movie stats
        "movie_stats__avg_rating",
        "movie_stats__rating_count",
        "movie_stats__rating_stddev",
        # Derived
        "user_deviation",
        "movie_popularity_log",
        "user_activity_log",
        "genre_count",
        "recency_days",
    ]

    # Drop rows with NaN
    df = df.dropna(subset=feature_cols + [label_col]).reset_index(drop=True)

    # Train/validation split (time-based: sort by timestamp)
    df = df.sort_values("interactions__timestamp").reset_index(drop=True)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx].copy()
    val_df = df.iloc[split_idx:].copy()

    return train_df, val_df, feature_cols


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_training_pipeline(config: TrainingConfig | None = None) -> dict[str, any]:
    """
    Execute the full training pipeline.

    Args:
        config: Training configuration. Uses defaults if None.

    Returns:
        Dict with training results (metrics, model paths, etc.).
    """
    if config is None:
        config = TrainingConfig()

    # Ensure directories exist
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("RecoStack — Training Pipeline (Phase 8)")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Connect to Feast & retrieve features
    # ------------------------------------------------------------------
    print("\n[1/6] Connecting to Feast feature store ...")
    store = FeatureStore(repo_path=str(FEAST_REPO_PATH))

    print("[2/6] Retrieving historical features ...")
    # Load raw ratings to build entity DataFrame
    raw_ratings = pd.read_csv(
        PROJECT_ROOT / "data" / "raw" / "ml-latest-small" / "ratings.csv"
    )
    raw_ratings.columns = raw_ratings.columns.str.strip()
    raw_ratings = raw_ratings.rename(
        columns={"userId": "user_id", "movieId": "movie_id"}
    )
    raw_ratings["user_id"] = raw_ratings["user_id"].astype(np.int64)
    raw_ratings["movie_id"] = raw_ratings["movie_id"].astype(np.int64)
    raw_ratings["event_timestamp"] = pd.Timestamp.now(tz="UTC")

    training_data = load_feast_features(store, raw_ratings)
    print(f"       Retrieved {len(training_data):,} rows with {len(training_data.columns)} columns")

    # Save a copy for reproducibility
    training_data.to_parquet(TRAINING_DATA_DIR / "training_data.parquet", index=False)

    # ------------------------------------------------------------------
    # 2. Train SVD candidate generation model
    # ------------------------------------------------------------------
    print("\n[3/6] Training SVD candidate generation model ...")
    svd_model = SVDCandidateGenerator(
        n_factors=config.svd_n_factors,
        n_iter=config.svd_n_iter,
        random_state=config.random_state,
    )
    svd_start = time.time()
    svd_model.fit(raw_ratings[["user_id", "movie_id", "rating"]])
    svd_train_time = time.time() - svd_start
    print(f"       SVD trained in {svd_train_time:.2f}s ({config.svd_n_factors} factors)")

    # Evaluate SVD: compute reconstruction error on training data
    svd_rmse = _compute_svd_rmse(svd_model, raw_ratings)
    print(f"       SVD training RMSE: {svd_rmse:.4f}")

    # ------------------------------------------------------------------
    # 3. Prepare ranking features
    # ------------------------------------------------------------------
    print("\n[4/6] Preparing ranking features ...")
    train_df, val_df, feature_cols = prepare_ranking_features(training_data)
    print(f"       Train: {len(train_df):,} rows, Val: {len(val_df):,} rows")
    print(f"       Features: {len(feature_cols)}")

    # ------------------------------------------------------------------
    # 4. Train LightGBM ranking model
    # ------------------------------------------------------------------
    print("\n[5/6] Training LightGBM ranking model ...")
    ranker = LightGBMRanker(params=config.lgb_params)
    lgb_start = time.time()
    ranker.fit(
        train_df=train_df,
        label_col="interactions__rating",
        feature_cols=feature_cols,
        valid_df=val_df,
        num_boost_round=config.lgb_num_boost_round,
        early_stopping_rounds=config.lgb_early_stopping,
    )
    lgb_train_time = time.time() - lgb_start

    # Evaluate on validation set
    val_preds = ranker.predict(val_df)
    val_rmse = float(np.sqrt(np.mean((val_preds - val_df["interactions__rating"].values) ** 2)))
    val_mae = float(np.mean(np.abs(val_preds - val_df["interactions__rating"].values)))
    print(f"       LightGBM trained in {lgb_train_time:.2f}s")
    print(f"       Val RMSE: {val_rmse:.4f}, Val MAE: {val_mae:.4f}")

    # Feature importance
    importance = ranker.feature_importance("gain")
    print("\n       Top-5 feature importance (gain):")
    for name, imp in sorted(importance.items(), key=lambda x: -x[1])[:5]:
        print(f"         {name}: {imp:.2f}")

    # ------------------------------------------------------------------
    # 5. Save models to disk
    # ------------------------------------------------------------------
    print("\n[5b/6] Saving model artifacts ...")
    svd_path = MODEL_DIR / "svd_candidate_generator.pkl"
    lgb_path = MODEL_DIR / "lightgbm_ranker.txt"

    svd_model.save(svd_path)
    ranker.save(lgb_path)
    print(f"       SVD model -> {svd_path}")
    print(f"       LightGBM model -> {lgb_path}")

    # ------------------------------------------------------------------
    # 6. Log to MLflow
    # ------------------------------------------------------------------
    print("\n[6/6] Logging to MLflow ...")
    _log_to_mlflow(
        config=config,
        svd_model=svd_model,
        ranker=ranker,
        svd_rmse=svd_rmse,
        svd_train_time=svd_train_time,
        val_rmse=val_rmse,
        val_mae=val_mae,
        lgb_train_time=lgb_train_time,
        feature_cols=feature_cols,
        importance=importance,
    )

    print("\n" + "=" * 60)
    print("✓ Training pipeline complete!")
    print("=" * 60)

    return {
        "svd_rmse": svd_rmse,
        "svd_train_time": svd_train_time,
        "val_rmse": val_rmse,
        "val_mae": val_mae,
        "lgb_train_time": lgb_train_time,
        "n_train_rows": len(train_df),
        "n_val_rows": len(val_df),
        "n_features": len(feature_cols),
        "svd_model_path": str(svd_path),
        "lgb_model_path": str(lgb_path),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_svd_rmse(
    svd: SVDCandidateGenerator, ratings: pd.DataFrame
) -> float:
    """Compute RMSE of SVD reconstruction on the training ratings."""
    preds = []
    actuals = []
    for _, row in ratings.iterrows():
        uid = int(row["user_id"])
        mid = int(row["movie_id"])
        u_idx = svd.user_map.get(uid)
        i_idx = svd.item_map.get(mid)
        if u_idx is None or i_idx is None:
            continue
        pred = float(
            svd.user_embeddings[u_idx] @ svd.item_embeddings[i_idx]
            + svd.global_mean
        )
        preds.append(pred)
        actuals.append(row["rating"])
    if not preds:
        return 0.0
    return float(np.sqrt(np.mean((np.array(preds) - np.array(actuals)) ** 2)))


def _log_to_mlflow(
    config: TrainingConfig,
    svd_model: SVDCandidateGenerator,
    ranker: LightGBMRanker,
    svd_rmse: float,
    svd_train_time: float,
    val_rmse: float,
    val_mae: float,
    lgb_train_time: float,
    feature_cols: list[str],
    importance: dict[str, float],
) -> None:
    """Log all params, metrics, and artifacts to MLflow."""
    import os

    import mlflow

    # Use local SQLite tracking (no server needed)
    mlflow_dir = PROJECT_ROOT / "data" / "mlflow"
    mlflow_dir.mkdir(parents=True, exist_ok=True)
    tracking_uri = f"sqlite:///{mlflow_dir / 'mlflow.db'}"
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(config.experiment_name)

    with mlflow.start_run(run_name=f"train-{pd.Timestamp.now():%Y%m%d-%H%M}") as run:
        run_id = run.info.run_id

        # --- Params ---
        mlflow.log_param("svd_n_factors", config.svd_n_factors)
        mlflow.log_param("svd_n_iter", config.svd_n_iter)
        mlflow.log_param("lgb_num_boost_round", config.lgb_num_boost_round)
        mlflow.log_param("lgb_num_leaves", config.lgb_params["num_leaves"])
        mlflow.log_param("lgb_learning_rate", config.lgb_params["learning_rate"])
        mlflow.log_param("test_ratio", config.test_ratio)
        mlflow.log_param("n_candidates", config.n_candidates)
        mlflow.log_param("feature_cols", ",".join(feature_cols))

        # --- Metrics ---
        mlflow.log_metric("svd_rmse", svd_rmse)
        mlflow.log_metric("svd_train_time_sec", svd_train_time)
        mlflow.log_metric("val_rmse", val_rmse)
        mlflow.log_metric("val_mae", val_mae)
        mlflow.log_metric("lgb_train_time_sec", lgb_train_time)

        # Log feature importances as individual metrics
        for name, imp in importance.items():
            mlflow.log_metric(f"lgb_importance_gain_{name}", imp)

        # --- Artifacts ---
        svd_path = MODEL_DIR / "svd_candidate_generator.pkl"
        lgb_path = MODEL_DIR / "lightgbm_ranker.txt"
        training_data_path = TRAINING_DATA_DIR / "training_data.parquet"

        mlflow.log_artifact(str(svd_path), artifact_path="models")
        mlflow.log_artifact(str(lgb_path), artifact_path="models")
        mlflow.log_artifact(str(training_data_path), artifact_path="data")

        # --- Tags ---
        mlflow.set_tag("phase", "8")
        mlflow.set_tag("pipeline", "training")
        mlflow.set_tag("dataset", "movielens-100k")

        print(f"       MLflow run ID: {run_id}")
        print(f"       Experiment: {config.experiment_name}")
        print(f"       Tracking DB: {tracking_uri}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_training_pipeline()