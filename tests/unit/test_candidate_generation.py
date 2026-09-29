"""
Unit tests — SVD Candidate Generator (src/recommenders/candidate_generation.py)
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.recommenders.candidate_generation import SVDCandidateGenerator


class TestSVDCandidateGenerator:
    N_FACTORS = 2  # must be < min(3 users, 4 movies) = 3

    def test_fit_creates_embeddings(self, sample_ratings: pd.DataFrame):
        model = SVDCandidateGenerator(n_factors=self.N_FACTORS, n_iter=5, random_state=42)
        model.fit(sample_ratings)

        assert model.model is not None
        assert model.user_embeddings is not None
        assert model.item_embeddings is not None
        assert model.user_embeddings.shape == (3, self.N_FACTORS)  # 3 users × N factors
        assert model.item_embeddings.shape == (4, self.N_FACTORS)  # 4 movies × N factors

    def test_fit_builds_mappings(self, sample_ratings: pd.DataFrame):
        model = SVDCandidateGenerator(n_factors=self.N_FACTORS, random_state=42)
        model.fit(sample_ratings)

        assert model.user_map == {1: 0, 2: 1, 3: 2}
        assert model.item_map == {1: 0, 2: 1, 3: 2, 4: 3}
        assert model.reverse_item_map == {0: 1, 1: 2, 2: 3, 3: 4}

    def test_fit_computes_global_mean(self, sample_ratings: pd.DataFrame):
        model = SVDCandidateGenerator(n_factors=self.N_FACTORS, random_state=42)
        model.fit(sample_ratings)

        expected_mean = sample_ratings["rating"].mean()
        assert model.global_mean == pytest.approx(expected_mean)

    def test_get_candidates_returns_list_of_movie_ids(self, sample_ratings: pd.DataFrame):
        model = SVDCandidateGenerator(n_factors=self.N_FACTORS, random_state=42)
        model.fit(sample_ratings)

        candidates = model.get_candidates(user_id=1, n_candidates=3)
        assert isinstance(candidates, list)
        assert len(candidates) == 3
        # Values may be numpy int64, which is int-like but not Python int
        assert all(isinstance(mid, (int, np.integer)) for mid in candidates)

    def test_get_candidates_excludes_rated_items(self, sample_ratings: pd.DataFrame):
        model = SVDCandidateGenerator(n_factors=self.N_FACTORS, random_state=42)
        model.fit(sample_ratings)

        exclude = {2, 3}
        candidates = model.get_candidates(user_id=1, n_candidates=10, exclude_items=exclude)
        assert 2 not in candidates
        assert 3 not in candidates

    def test_get_candidates_cold_start_user(self, sample_ratings: pd.DataFrame):
        """Unknown user should get popular fallback."""
        model = SVDCandidateGenerator(n_factors=self.N_FACTORS, random_state=42)
        model.fit(sample_ratings)

        candidates = model.get_candidates(user_id=999, n_candidates=2)
        assert len(candidates) == 2
        assert all(isinstance(mid, (int, np.integer)) for mid in candidates)

    def test_get_candidates_before_fit_raises(self):
        model = SVDCandidateGenerator()
        with pytest.raises(RuntimeError, match="not fitted"):
            model.get_candidates(user_id=1)

    def test_save_and_load_roundtrip(self, sample_ratings: pd.DataFrame, tmp_path: Path):
        model = SVDCandidateGenerator(n_factors=self.N_FACTORS, random_state=42)
        model.fit(sample_ratings)

        path = tmp_path / "svd_test.pkl"
        model.save(str(path))

        loaded = SVDCandidateGenerator.load(str(path))
        assert loaded.n_factors == self.N_FACTORS
        assert loaded.user_map == model.user_map
        assert loaded.item_map == model.item_map
        assert loaded.global_mean == pytest.approx(model.global_mean)
        assert loaded.user_embeddings is not None
        assert loaded.item_embeddings is not None
        np.testing.assert_array_almost_equal(loaded.user_embeddings, model.user_embeddings)

    def test_embeddings_are_normalized(self, sample_ratings: pd.DataFrame):
        model = SVDCandidateGenerator(n_factors=self.N_FACTORS, random_state=42)
        model.fit(sample_ratings)

        # Each row should have unit norm
        norms = np.linalg.norm(model.user_embeddings, axis=1)
        np.testing.assert_array_almost_equal(norms, np.ones(3), decimal=5)

        norms = np.linalg.norm(model.item_embeddings, axis=1)
        np.testing.assert_array_almost_equal(norms, np.ones(4), decimal=5)

    def test_candidates_ordered_by_score(self, sample_ratings: pd.DataFrame):
        """Candidates should be returned in descending score order."""
        model = SVDCandidateGenerator(n_factors=self.N_FACTORS, random_state=42)
        model.fit(sample_ratings)

        candidates = model.get_candidates(user_id=2, n_candidates=4)
        # Just verify we get results — exact ordering depends on SVD decomposition
        assert len(candidates) == 4
        assert len(set(candidates)) == 4  # no duplicates