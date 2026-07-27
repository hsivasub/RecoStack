"""
explore_data.py — Phase 2: Data Exploration

Loads ratings.csv and movies.csv from the MovieLens ml-latest-small dataset
and prints summary statistics: row counts, date range, unique users/items,
rating distribution, and matrix sparsity.
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "ml-latest-small"

SEPARATOR = "=" * 62


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    ratings = pd.read_csv(DATA_DIR / "ratings.csv")
    movies = pd.read_csv(DATA_DIR / "movies.csv")
    return ratings, movies


def explore_ratings(ratings: pd.DataFrame) -> None:
    """Print key statistics for the ratings dataset."""

    n_ratings = len(ratings)
    n_users = ratings["userId"].nunique()
    n_items = ratings["movieId"].nunique()

    # Convert timestamp to datetime
    ratings["datetime"] = pd.to_datetime(ratings["timestamp"], unit="s")
    min_date = ratings["datetime"].min()
    max_date = ratings["datetime"].max()

    # Rating distribution
    dist = ratings["rating"].value_counts().sort_index()

    # Sparsity
    # Total possible entries in the user-item matrix = n_users * n_items
    # Sparsity = 1 - (filled cells / total possible cells)
    possible_entries = n_users * n_items
    sparsity_pct = (1 - n_ratings / possible_entries) * 100

    print(SEPARATOR)
    print("📊  RATINGS DATASET OVERVIEW")
    print(SEPARATOR)
    print(f"  Number of ratings:     {n_ratings:>10,}")
    print(f"  Number of users:       {n_users:>10,}")
    print(f"  Number of movies:      {n_items:>10,}")
    print(f"  Date range:            {min_date.date()}  →  {max_date.date()}")
    print(f"  User-Item matrix size: {n_users} × {n_items} = {possible_entries:,} cells")
    print(f"  Filled cells:          {n_ratings:,}")
    print(f"  Sparsity:              {sparsity_pct:.4f}%  ({100 - sparsity_pct:.4f}% filled)")
    print()

    print(SEPARATOR)
    print("📈  RATING DISTRIBUTION")
    print(SEPARATOR)
    for rating, count in dist.items():
        bar = "█" * int(count / dist.max() * 30)
        print(f"  {rating:5.1f}  {count:>8,}  {bar}")
    print(f"\n  Mean rating:  {ratings['rating'].mean():.3f}")
    print(f"  Median rating: {ratings['rating'].median():.1f}")
    print(f"  Std rating:    {ratings['rating'].std():.3f}")
    print()

    print(SEPARATOR)
    print("👤  ACTIONS PER USER (ratings per user)")
    print(SEPARATOR)
    rpu = ratings.groupby("userId").size()
    print(f"  Min ratings per user:  {rpu.min():>6,}")
    print(f"  Max ratings per user:  {rpu.max():>6,}")
    print(f"  Mean ratings per user: {rpu.mean():>8.1f}")
    print(f"  Median ratings/user:   {rpu.median():>8.1f}")
    print(f"  Users with < 20 ratings: {(rpu < 20).sum():>6,} ({(rpu < 20).mean() * 100:.1f}%)")
    print()

    print(SEPARATOR)
    print("🎬  ACTIONS PER ITEM (ratings per movie)")
    print(SEPARATOR)
    rpi = ratings.groupby("movieId").size()
    print(f"  Min ratings per movie:  {rpi.min():>6,}")
    print(f"  Max ratings per movie:  {rpi.max():>6,}")
    print(f"  Mean ratings per movie: {rpi.mean():>8.1f}")
    print(f"  Median ratings/movie:   {rpi.median():>8.1f}")


def explore_movies(movies: pd.DataFrame) -> None:
    """Print key statistics for the movies dataset."""
    print()
    print(SEPARATOR)
    print("🎞️  MOVIES DATASET OVERVIEW")
    print(SEPARATOR)
    print(f"  Total movies:    {len(movies):>10,}")

    # Parse genres (pipe-separated)
    all_genres = movies["genres"].str.split("|").explode()
    genre_counts = all_genres.value_counts()
    print(f"  Unique genres:   {len(genre_counts):>10,}")
    print()
    print("  Genre breakdown:")
    for genre, count in genre_counts.items():
        bar = "█" * int(count / genre_counts.max() * 30)
        print(f"    {genre:<20} {count:>5,}  {bar}")


def main() -> None:
    ratings, movies = load_data()
    explore_ratings(ratings)
    explore_movies(movies)
    print()
    print(SEPARATOR)
    print("✅  Exploration complete.")


if __name__ == "__main__":
    main()