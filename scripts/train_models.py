"""
train_models.py — Phase 8: Training Pipeline CLI

Entry point for running the full RecoStack training pipeline:
  1. Retrieves historical features from Feast
  2. Trains SVD candidate generation model
  3. Trains LightGBM ranking model
  4. Logs everything to MLflow
  5. Saves model artifacts to data/model-artifacts/

Usage:
    python scripts/train_models.py

Options:
    --svd-factors N     Number of SVD latent factors (default: 50)
    --lgb-rounds N      Number of LightGBM boosting rounds (default: 200)
    --dry-run           Load data and print shapes without training
    --help              Show this message

Prerequisites:
    - Redpanda running (not strictly required — uses Parquet data directly)
    - MLflow server running at http://localhost:5000
    - Feast registry applied (run scripts/apply_feast.py)
    - Feature Parquet files exist (run scripts/generate_feature_data.py)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.recommenders.training_pipeline import TrainingConfig, run_training_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RecoStack — Training Pipeline (Phase 8)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--svd-factors",
        type=int,
        default=50,
        help="Number of SVD latent factors (default: 50)",
    )
    parser.add_argument(
        "--lgb-rounds",
        type=int,
        default=200,
        help="Number of LightGBM boosting rounds (default: 200)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data and print shapes without training",
    )
    return parser.parse_args()


def dry_run() -> None:
    """Load data and print summary without training."""
    import pandas as pd

    print("=" * 60)
    print("RecoStack — Training Pipeline (DRY RUN)")
    print("=" * 60)

    raw_ratings = pd.read_csv(
        PROJECT_ROOT / "data" / "raw" / "ml-latest-small" / "ratings.csv"
    )
    raw_ratings.columns = raw_ratings.columns.str.strip()

    print(f"\nRaw ratings: {len(raw_ratings):,} rows")
    print(f"  Users: {raw_ratings['userId'].nunique():,}")
    print(f"  Movies: {raw_ratings['movieId'].nunique():,}")
    print(f"  Rating range: {raw_ratings['rating'].min()} – {raw_ratings['rating'].max()}")

    # Check feature files
    features_dir = PROJECT_ROOT / "data" / "features"
    print(f"\nFeature files in {features_dir}:")
    for f in sorted(features_dir.glob("*.parquet")):
        df = pd.read_parquet(f)
        print(f"  {f.name}: {len(df):,} rows, {list(df.columns)}")

    # Check MLflow is importable
    try:
        import mlflow
        print("\n✓ MLflow available (local file-based tracking)")
    except ImportError:
        print("\n⚠ MLflow not installed")

    print("\nDry run complete. Run without --dry-run to train models.")


def main() -> None:
    args = parse_args()

    if args.dry_run:
        dry_run()
        return

    config = TrainingConfig(
        svd_n_factors=args.svd_factors,
        lgb_num_boost_round=args.lgb_rounds,
    )

    results = run_training_pipeline(config)

    print("\nFinal Results:")
    for key, value in results.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()