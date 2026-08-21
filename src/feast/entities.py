"""
Feast Entity Definitions — RecoStack

Defines the entities that appear in our feature views:
  - user: identified by user_id (int64)
  - movie: identified by movie_id (int64)

Entities are the "join keys" that link feature values to training examples
and online inference requests.
"""

from feast import Entity, ValueType

# ---------------------------------------------------------------------------
# User entity
# ---------------------------------------------------------------------------
user = Entity(
    name="user",
    join_keys=["user_id"],
    value_type=ValueType.INT64,
    description="A user who rates movies",
    tags={"source": "movielens"},
)

# ---------------------------------------------------------------------------
# Movie entity
# ---------------------------------------------------------------------------
movie = Entity(
    name="movie",
    join_keys=["movie_id"],
    value_type=ValueType.INT64,
    description="A movie that can be recommended",
    tags={"source": "movielens"},
)