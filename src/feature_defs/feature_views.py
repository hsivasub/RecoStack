"""
Feast Feature View Definitions — RecoStack

Defines three feature views:
  1. user_stats_fv      — Aggregated user behaviour features
  2. movie_stats_fv     — Aggregated movie popularity / content features
  3. interaction_fv     — Raw user-movie interaction features

Each feature view maps a set of feature columns to an entity via a data source.
"""

from feast import FeatureView, Field
from feast.types import Float32, Int32, Int64, String

from src.feature_defs.entities import movie, user
from src.feature_defs.sources import interaction_source, movie_stats_source, user_stats_source

# ---------------------------------------------------------------------------
# User stats feature view
# ---------------------------------------------------------------------------
user_stats_fv = FeatureView(
    name="user_stats",
    entities=[user],
    ttl=None,  # No expiry — batch features are static for this dataset
    schema=[
        Field(name="user_id", dtype=Int64),
        Field(name="avg_rating", dtype=Float32),
        Field(name="rating_count", dtype=Int32),
        Field(name="rating_stddev", dtype=Float32),
        Field(name="unique_genres_rated", dtype=Int32),
    ],
    source=user_stats_source,
    tags={"group": "user", "type": "aggregate"},
)

# ---------------------------------------------------------------------------
# Movie stats feature view
# ---------------------------------------------------------------------------
movie_stats_fv = FeatureView(
    name="movie_stats",
    entities=[movie],
    ttl=None,
    schema=[
        Field(name="movie_id", dtype=Int64),
        Field(name="avg_rating", dtype=Float32),
        Field(name="rating_count", dtype=Int32),
        Field(name="rating_stddev", dtype=Float32),
        Field(name="genres", dtype=String),
    ],
    source=movie_stats_source,
    tags={"group": "movie", "type": "aggregate"},
)

# ---------------------------------------------------------------------------
# Interaction feature view (raw ratings)
# ---------------------------------------------------------------------------
interaction_fv = FeatureView(
    name="interactions",
    entities=[user, movie],
    ttl=None,
    schema=[
        Field(name="user_id", dtype=Int64),
        Field(name="movie_id", dtype=Int64),
        Field(name="rating", dtype=Float32),
        Field(name="timestamp", dtype=Int32),
    ],
    source=interaction_source,
    tags={"group": "interaction", "type": "raw"},
)