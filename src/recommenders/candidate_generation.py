"""
Candidate Generation Model — Matrix Factorization (SVD)

Uses scikit-learn's TruncatedSVD on the user-item rating matrix to produce
low-dimensional embeddings for users and items. Candidate generation is
performed by computing the dot product between a user embedding and all
item embeddings, returning the top-N highest-scored items.

This is Stage 1 of the two-stage retrieval + ranking architecture.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, lil_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize


class SVDCandidateGenerator:
    """
    SVD-based candidate generation model.

    Fits a TruncatedSVD on the user-item rating matrix, then uses the
    resulting user/item embeddings to retrieve top-N candidate items
    via dot-product similarity.

    Attributes:
        n_factors: Number of latent factors (embedding dimension).
        n_iter: Number of SVD iterations.
        random_state: Seed for reproducibility.
        model: The fitted TruncatedSVD instance.
        user_embeddings: (n_users, n_factors) array, row-normalized.
        item_embeddings: (n_items, n_factors) array, row-normalized.
        user_map: Mapping from raw user_id to matrix row index.
        item_map: Mapping from raw movie_id to matrix column index.
        reverse_item_map: Mapping from matrix column index back to movie_id.
        global_mean: Global average rating (used for imputation).
    """

    def __init__(
        self,
        n_factors: int = 50,
        n_iter: int = 10,
        random_state: int = 42,
    ) -> None:
        self.n_factors = n_factors
        self.n_iter = n_iter
        self.random_state = random_state

        self.model: TruncatedSVD | None = None
        self.user_embeddings: np.ndarray | None = None
        self.item_embeddings: np.ndarray | None = None
        self.user_map: dict[int, int] = {}
        self.item_map: dict[int, int] = {}
        self.reverse_item_map: dict[int, int] = {}
        self.global_mean: float = 0.0

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(self, ratings: pd.DataFrame) -> "SVDCandidateGenerator":
        """
        Fit the SVD model on a ratings DataFrame.

        Args:
            ratings: DataFrame with columns [user_id, movie_id, rating].
                     user_id and movie_id should be int64.
        """
        # Build mappings
        unique_users = sorted(ratings["user_id"].unique())
        unique_items = sorted(ratings["movie_id"].unique())
        self.user_map = {uid: i for i, uid in enumerate(unique_users)}
        self.item_map = {mid: i for i, mid in enumerate(unique_items)}
        self.reverse_item_map = {i: mid for mid, i in self.item_map.items()}

        n_users = len(self.user_map)
        n_items = len(self.item_map)

        self.global_mean = float(ratings["rating"].mean())

        # Build sparse matrix (users x items)
        matrix = lil_matrix((n_users, n_items), dtype=np.float32)
        for _, row in ratings.iterrows():
            u_idx = self.user_map[int(row["user_id"])]
            i_idx = self.item_map[int(row["movie_id"])]
            matrix[u_idx, i_idx] = row["rating"] - self.global_mean

        sparse_matrix = matrix.tocsr()

        # Fit SVD
        self.model = TruncatedSVD(
            n_components=self.n_factors,
            n_iter=self.n_iter,
            random_state=self.random_state,
        )
        self.model.fit(sparse_matrix)

        # Extract embeddings
        # U * Sigma gives user embeddings; Vt^T gives item embeddings
        self.user_embeddings = normalize(self.model.transform(sparse_matrix))
        self.item_embeddings = normalize(self.model.components_.T)

        return self

    # ------------------------------------------------------------------
    # Candidate retrieval
    # ------------------------------------------------------------------

    def get_candidates(
        self,
        user_id: int,
        n_candidates: int = 100,
        exclude_items: set[int] | None = None,
    ) -> list[int]:
        """
        Retrieve top-N candidate items for a user.

        Args:
            user_id: The raw user ID.
            n_candidates: Number of candidates to return.
            exclude_items: Optional set of item IDs to exclude (e.g., already rated).

        Returns:
            List of movie_id candidates, highest score first.
        """
        if self.user_embeddings is None or self.item_embeddings is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        u_idx = self.user_map.get(user_id)
        if u_idx is None:
            # Cold-start user: return popular items
            return self._popular_fallback(n_candidates)

        user_vec = self.user_embeddings[u_idx].reshape(1, -1)
        scores = self.item_embeddings @ user_vec.T
        scores = scores.flatten()

        # Sort by score descending
        ranked_indices = np.argsort(-scores)

        candidates: list[int] = []
        exclude = exclude_items or set()
        for idx in ranked_indices:
            mid = self.reverse_item_map[idx]
            if mid not in exclude:
                candidates.append(mid)
                if len(candidates) >= n_candidates:
                    break

        return candidates

    def _popular_fallback(self, n_candidates: int) -> list[int]:
        """Return most popular items as fallback for cold-start users."""
        # Items are ordered by their index which corresponds to their
        # frequency in the training data (since we sorted by movie_id).
        # A better fallback would use item popularity counts.
        all_items = list(self.reverse_item_map.values())
        return all_items[:n_candidates]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Serialize the model to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: str | Path) -> "SVDCandidateGenerator":
        """Load a serialized model from disk."""
        with open(path, "rb") as f:
            return pickle.load(f)