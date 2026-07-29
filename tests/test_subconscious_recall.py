"""subconscious_recall guards (SIMP-D2-034): cosine must refuse
mismatched-dimension vectors — zip() silently truncates, so an index built
with a different embedding model scored meaningless dot products with no
error, forever. semantic_search.py already guarded this; the hook didn't."""
import pytest

from subconscious.subconscious_recall import cosine


def test_cosine_mismatched_lengths_returns_zero():
    assert cosine([1.0, 0.0, 0.0], [1.0, 0.0]) == 0.0
    assert cosine([], [1.0]) == 0.0


def test_cosine_matched_lengths_normal_math():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine([0.0, 0.0], [0.0, 0.0]) == 0.0  # zero-norm guard unchanged
