"""Autotune regression tests (SIMP-D2-033): the empty-prompt-corpus path must
return the same arity as the normal path — it once returned a 3-tuple against
the caller's 2-tuple unpack, so every fresh-corpus run raised ValueError that
was swallowed into last_run_error (self-blinding: protocol_gate's autotune
check reads the same state file and stayed silent too)."""
import json

import pytest

from subconscious import subconscious_autotune as autotune


@pytest.fixture
def empty_world(tmp_path, monkeypatch):
    """Empty prompt corpus + empty piece index + temp state/journal paths."""
    index_path = tmp_path / "subconscious_index.json"
    index_path.write_text(json.dumps({"pieces": []}), encoding="utf-8")
    monkeypatch.setattr(autotune, "INDEX_PATH", index_path)
    monkeypatch.setattr(autotune, "STATE_PATH", tmp_path / "autotune_state.json")
    monkeypatch.setattr(autotune, "JOURNAL_PATH", tmp_path / "logs" / "autotune.log")
    monkeypatch.setattr(autotune, "load_prompts", lambda *a, **kw: [])
    return tmp_path


def test_mine_candidates_empty_corpus_returns_two_tuple(empty_world):
    result = autotune.mine_candidates({"pending": []})
    assert result == ([], 0)
    queued, n_prompts = result  # the caller's exact unpack must not raise
    assert queued == [] and n_prompts == 0


def test_run_completes_on_empty_corpus(empty_world):
    assert autotune.run(dry_run=False) == 0
    state = json.loads(autotune.STATE_PATH.read_text(encoding="utf-8"))
    assert state["last_run"] is not None
    assert state["pending"] == []
