"""Regression: --bm25-weight 0 --semantic-weight 0 must be an argparse error,
not a ZeroDivisionError (SIMP-D2-024)."""
import sys

import pytest

from memory import hybrid_search


def test_zero_weight_sum_is_usage_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "hybrid_search.py", "--query", "x",
        "--bm25-weight", "0", "--semantic-weight", "0",
    ])
    with pytest.raises(SystemExit) as exc:
        hybrid_search.main()
    assert exc.value.code == 2  # argparse usage error, not a traceback
    assert "sum to > 0" in capsys.readouterr().err


def test_negative_weight_sum_is_usage_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "hybrid_search.py", "--query", "x",
        "--bm25-weight", "-0.5", "--semantic-weight", "0.5",
    ])
    with pytest.raises(SystemExit) as exc:
        hybrid_search.main()
    assert exc.value.code == 2
