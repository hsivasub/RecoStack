"""
apply_feast.py — Phase 7: Apply Feast Feature Definitions

Registers all entities, data sources, and feature views with the
Feast registry (SQLite). Must be run from the project root so that
the feature_store.yaml is discoverable.

Usage:
    cd <project-root>
    python scripts/apply_feast.py

Prerequisites:
    - Feature Parquet files exist in data/features/
      (run scripts/generate_feature_data.py first)
    - feature_store.yaml is at config/feast/feature_store.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so that src.feast.* imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from feast import FeatureStore

from src.feast.entities import movie, user
from src.feast.feature_views import interaction_fv, movie_stats_fv, user_stats_fv


def main() -> None:
    print("=" * 60)
    print("RecoStack — Feast Feature Store Apply")
    print("=" * 60)

    # Point Feast to our config directory
    repo_path = str(PROJECT_ROOT / "config" / "feast")
    print(f"\nRepo config path: {repo_path}")

    store = FeatureStore(repo_path=repo_path)

    print("\nCurrent feature views (before apply):")
    for fv in store.list_feature_views():
        print(f"  • {fv.name}")

    objects = [user, movie, user_stats_fv, movie_stats_fv, interaction_fv]

    print(f"\nApplying {len(objects)} objects to registry ...")
    store.apply(objects)

    print("\nFeature views (after apply):")
    for fv in store.list_feature_views():
        print(f"  • {fv.name} — {len(fv.schema)} features")

    print("\nEntities:")
    for ent in store.list_entities():
        print(f"  • {ent.name} ({ent.value_type.name})")

    print("\n✓ Feast registry updated successfully.")
    print(f"  Registry: {repo_path}/data/feast/registry.db")


if __name__ == "__main__":
    main()