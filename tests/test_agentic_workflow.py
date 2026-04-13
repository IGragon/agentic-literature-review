"""Tests for pure logic in src/agentic_workflow.py — no real LLM or network calls."""

import os
import pytest
from unittest.mock import MagicMock, patch

# Set dummy env vars so module-level code in agentic_workflow doesn't error
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("OPENROUTER_MODEL", "test-model")

from src.agentic_workflow import (
    NoRelevantPapersFound,
    _compute_completeness,
    _invoke_with_retry,
    _is_transient,
    _route_after_quality,
    _tls,
    evaluate_quality,
    filter_relevance,
    search,
    set_search_progress_callback,
    set_summarize_progress_callback,
)


# ---------------------------------------------------------------------------
# _compute_completeness
# ---------------------------------------------------------------------------


def test_completeness_all_fields_populated():
    paper = {
        "title": "A",
        "authors": "B",
        "abstract": "C",
        "doi": "D",
        "url": "E",
        "citation": "F",
        "published_date": "G",
    }
    assert _compute_completeness(paper) == 7


def test_completeness_none_values_not_counted():
    paper = {
        "title": "A",
        "authors": None,
        "abstract": None,
        "doi": None,
        "url": "E",
        "citation": None,
        "published_date": None,
    }
    assert _compute_completeness(paper) == 2


def test_completeness_empty_strings_not_counted():
    paper = {
        "title": "A",
        "authors": "",
        "abstract": "",
        "doi": "",
        "url": "",
        "citation": "",
        "published_date": "",
    }
    assert _compute_completeness(paper) == 1


def test_completeness_whitespace_not_counted():
    paper = {
        "title": "  ",
        "authors": "\t",
        "abstract": "actual content",
        "doi": "",
        "url": "",
        "citation": "",
        "published_date": "",
    }
    assert _compute_completeness(paper) == 1


def test_completeness_partial():
    paper = {
        "title": "Title",
        "authors": "Author",
        "abstract": "Abstract",
        "doi": "",
        "url": "",
        "citation": "",
        "published_date": "",
    }
    assert _compute_completeness(paper) == 3


def test_completeness_missing_keys_treated_as_empty():
    paper = {"title": "Only title"}
    assert _compute_completeness(paper) == 1


# ---------------------------------------------------------------------------
# _is_transient
# ---------------------------------------------------------------------------


def _exc(name: str) -> Exception:
    """Create an exception whose class name matches *name*."""
    cls = type(name, (Exception,), {})
    return cls("test error")


def test_is_transient_remote_protocol_error():
    assert _is_transient(_exc("RemoteProtocolError")) is True


def test_is_transient_read_timeout():
    assert _is_transient(_exc("ReadTimeout")) is True


def test_is_transient_connect_error():
    assert _is_transient(_exc("ConnectError")) is True


def test_is_transient_incomplete_read():
    assert _is_transient(_exc("IncompleteRead")) is True


def test_is_transient_chunked_encoding_error():
    assert _is_transient(_exc("ChunkedEncodingError")) is True


def test_is_transient_value_error():
    assert _is_transient(ValueError("bad input")) is False


def test_is_transient_key_error():
    assert _is_transient(KeyError("missing")) is False


def test_is_transient_runtime_error():
    assert _is_transient(RuntimeError("oops")) is False


# ---------------------------------------------------------------------------
# _route_after_quality
# ---------------------------------------------------------------------------


def test_route_returns_retry_when_not_ok():
    assert _route_after_quality({"quality_ok": False}) == "retry"


def test_route_returns_proceed_when_ok():
    assert _route_after_quality({"quality_ok": True}) == "proceed"


def test_route_returns_retry_when_none():
    assert _route_after_quality({"quality_ok": None}) == "retry"


def test_route_returns_retry_when_key_missing():
    assert _route_after_quality({}) == "retry"


# ---------------------------------------------------------------------------
# evaluate_quality
# ---------------------------------------------------------------------------


def _make_paper(relevance: str) -> dict:
    return {
        "title": "T",
        "authors": "A",
        "abstract": "",
        "doi": "",
        "url": "",
        "citation": "",
        "summary": "",
        "paper_id": "p1",
        "published_date": "",
        "relevance": relevance,
        "completeness_score": 5,
    }


def test_quality_passes_when_enough_rel_papers(monkeypatch):
    monkeypatch.setattr("src.agentic_workflow.MIN_REL_PAPERS", 3)
    papers = [_make_paper("REL"), _make_paper("REL"), _make_paper("REL")]
    state = {"search_results": papers, "search_iteration": 0}
    result = evaluate_quality(state)
    assert result["quality_ok"] is True
    assert result.get("quality_warning") is None


def test_quality_passes_counting_rel_plus(monkeypatch):
    monkeypatch.setattr("src.agentic_workflow.MIN_REL_PAPERS", 2)
    papers = [_make_paper("REL+"), _make_paper("REL+")]
    state = {"search_results": papers, "search_iteration": 0}
    result = evaluate_quality(state)
    assert result["quality_ok"] is True


def test_quality_fails_first_iteration(monkeypatch):
    monkeypatch.setattr("src.agentic_workflow.MIN_REL_PAPERS", 3)
    monkeypatch.setattr("src.agentic_workflow.MAX_SEARCH_ITERATIONS", 3)
    papers = [_make_paper("REL")]
    state = {"search_results": papers, "search_iteration": 0}
    result = evaluate_quality(state)
    assert result["quality_ok"] is False
    assert result["search_iteration"] == 1


def test_quality_increments_iteration(monkeypatch):
    monkeypatch.setattr("src.agentic_workflow.MIN_REL_PAPERS", 5)
    monkeypatch.setattr("src.agentic_workflow.MAX_SEARCH_ITERATIONS", 3)
    papers = [_make_paper("REL")]
    state = {"search_results": papers, "search_iteration": 1}
    result = evaluate_quality(state)
    assert result["quality_ok"] is False
    assert result["search_iteration"] == 2


def test_quality_accepts_with_warning_at_max_iter(monkeypatch):
    monkeypatch.setattr("src.agentic_workflow.MIN_REL_PAPERS", 5)
    monkeypatch.setattr("src.agentic_workflow.MAX_SEARCH_ITERATIONS", 3)
    papers = [_make_paper("REL")]
    state = {"search_results": papers, "search_iteration": 3}
    result = evaluate_quality(state)
    assert result["quality_ok"] is True
    assert result["quality_warning"] is not None
    assert "1" in result["quality_warning"]  # mentions count


def test_quality_raises_no_papers_at_max_iter(monkeypatch):
    monkeypatch.setattr("src.agentic_workflow.MIN_REL_PAPERS", 3)
    monkeypatch.setattr("src.agentic_workflow.MAX_SEARCH_ITERATIONS", 3)
    state = {"search_results": [], "search_iteration": 3}
    with pytest.raises(NoRelevantPapersFound):
        evaluate_quality(state)


def test_quality_does_not_raise_no_papers_below_max(monkeypatch):
    monkeypatch.setattr("src.agentic_workflow.MIN_REL_PAPERS", 3)
    monkeypatch.setattr("src.agentic_workflow.MAX_SEARCH_ITERATIONS", 3)
    state = {"search_results": [], "search_iteration": 1}
    result = evaluate_quality(state)
    assert result["quality_ok"] is False


def test_quality_rel_minus_not_counted(monkeypatch):
    monkeypatch.setattr("src.agentic_workflow.MIN_REL_PAPERS", 2)
    monkeypatch.setattr("src.agentic_workflow.MAX_SEARCH_ITERATIONS", 3)
    # Only REL- papers — should not pass quality check
    papers = [_make_paper("REL-"), _make_paper("REL-"), _make_paper("REL-")]
    state = {"search_results": papers, "search_iteration": 0}
    result = evaluate_quality(state)
    assert result["quality_ok"] is False


# ---------------------------------------------------------------------------
# filter_relevance (mock get_llm)
# ---------------------------------------------------------------------------


def _full_paper(paper_id: str, **overrides) -> dict:
    base = {
        "title": "Title",
        "authors": "Author",
        "abstract": "Abstract text",
        "doi": "10.1234/x",
        "url": "https://example.com",
        "citation": "@article{}",
        "summary": "",
        "paper_id": paper_id,
        "published_date": "2024-01-01",
        "relevance": "",
        "completeness_score": 0,
    }
    base.update(overrides)
    return base


def _sparse_paper(paper_id: str) -> dict:
    """Paper with only title — completeness_score will be 1 after filtering."""
    return {
        "title": "Sparse Paper",
        "authors": "",
        "abstract": "",
        "doi": "",
        "url": "",
        "citation": "",
        "summary": "",
        "paper_id": paper_id,
        "published_date": "",
        "relevance": "",
        "completeness_score": 0,
    }


def _mock_llm(mocker, scores: list[dict]):
    """Patch get_llm() to return a mock that yields the given scores."""
    mock_llm_instance = MagicMock()
    mock_llm_instance.with_structured_output.return_value.invoke.return_value = {
        "scores": scores
    }
    mocker.patch("src.agentic_workflow.get_llm", return_value=mock_llm_instance)
    return mock_llm_instance


def test_filter_empty_input_returns_empty_without_llm_call(mocker):
    mock_get_llm = mocker.patch("src.agentic_workflow.get_llm")
    state = {"topic": "t", "directions": [], "search_results": []}
    result = filter_relevance(state)
    assert result["search_results"] == []
    mock_get_llm.assert_not_called()


def test_filter_removes_not_rel(mocker):
    papers = [
        _full_paper("p1"),
        _full_paper("p2"),
    ]
    _mock_llm(mocker, [
        {"paper_id": "p1", "relevance": "REL"},
        {"paper_id": "p2", "relevance": "NOT_REL"},
    ])
    state = {"topic": "t", "directions": [], "search_results": papers}
    result = filter_relevance(state)
    ids = [p["paper_id"] for p in result["search_results"]]
    assert "p1" in ids
    assert "p2" not in ids


def test_filter_keeps_good_rel_minus(mocker):
    """REL- paper with completeness >= 3 should be kept."""
    papers = [_full_paper("p1"), _full_paper("p2")]
    _mock_llm(mocker, [
        {"paper_id": "p1", "relevance": "REL+"},
        {"paper_id": "p2", "relevance": "REL-"},
    ])
    state = {"topic": "t", "directions": [], "search_results": papers}
    result = filter_relevance(state)
    ids = [p["paper_id"] for p in result["search_results"]]
    # p2 is REL- but has completeness 7 (all fields populated) → kept
    assert "p2" in ids


def test_filter_removes_bad_completeness_rel_minus(mocker):
    """REL- paper with completeness < 3 is removed when other papers remain."""
    papers = [
        _full_paper("p1"),           # REL, completeness 7 → kept
        _sparse_paper("p2"),         # REL-, completeness 1 → removed
    ]
    _mock_llm(mocker, [
        {"paper_id": "p1", "relevance": "REL"},
        {"paper_id": "p2", "relevance": "REL-"},
    ])
    state = {"topic": "t", "directions": [], "search_results": papers}
    result = filter_relevance(state)
    ids = [p["paper_id"] for p in result["search_results"]]
    assert "p1" in ids
    assert "p2" not in ids


def test_filter_keeps_bad_rel_minus_if_only_paper(mocker):
    """If the only paper is REL- with low completeness, keep it anyway."""
    papers = [_sparse_paper("p1")]
    _mock_llm(mocker, [{"paper_id": "p1", "relevance": "REL-"}])
    state = {"topic": "t", "directions": [], "search_results": papers}
    result = filter_relevance(state)
    assert len(result["search_results"]) == 1


def test_filter_defaults_missing_score_to_rel_minus(mocker):
    """If LLM omits a paper from scores, default to REL-."""
    papers = [_full_paper("p1"), _full_paper("p2")]
    _mock_llm(mocker, [
        {"paper_id": "p1", "relevance": "REL"},
        # p2 missing from scores
    ])
    state = {"topic": "t", "directions": [], "search_results": papers}
    result = filter_relevance(state)
    p2 = next((p for p in result["search_results"] if p["paper_id"] == "p2"), None)
    assert p2 is not None
    assert p2["relevance"] == "REL-"


# ---------------------------------------------------------------------------
# _invoke_with_retry
# ---------------------------------------------------------------------------


def test_invoke_succeeds_on_first_try():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="response")
    result = _invoke_with_retry(mock_llm, "prompt", max_retries=3)
    assert mock_llm.invoke.call_count == 1


def test_invoke_retries_on_transient_error(mocker):
    transient_cls = type("RemoteProtocolError", (Exception,), {})
    mock_llm = MagicMock()
    good_response = MagicMock(content="ok")
    mock_llm.invoke.side_effect = [transient_cls("drop"), good_response]
    mocker.patch("src.agentic_workflow.time.sleep")  # skip backoff

    result = _invoke_with_retry(mock_llm, "prompt", max_retries=3)

    assert mock_llm.invoke.call_count == 2
    assert result.content == "ok"


def test_invoke_raises_after_max_retries(mocker):
    transient_cls = type("RemoteProtocolError", (Exception,), {})
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = transient_cls("always fails")
    mocker.patch("src.agentic_workflow.time.sleep")

    with pytest.raises(Exception, match="always fails"):
        _invoke_with_retry(mock_llm, "prompt", max_retries=3)

    assert mock_llm.invoke.call_count == 3


def test_invoke_does_not_retry_non_transient():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = ValueError("bad prompt")

    with pytest.raises(ValueError, match="bad prompt"):
        _invoke_with_retry(mock_llm, "prompt", max_retries=3)

    assert mock_llm.invoke.call_count == 1  # no retry


# ---------------------------------------------------------------------------
# Progress callbacks
# ---------------------------------------------------------------------------


def test_set_search_progress_callback_stores_and_clears():
    calls = []
    set_search_progress_callback(lambda c, t, q: calls.append((c, t, q)))
    cb = getattr(_tls, "on_search_progress", None)
    assert cb is not None
    cb(1, 5, "test query")
    assert calls == [(1, 5, "test query")]
    set_search_progress_callback(None)
    assert getattr(_tls, "on_search_progress", None) is None


def test_set_summarize_progress_callback_stores_and_clears():
    calls = []
    set_summarize_progress_callback(lambda c, t, ti: calls.append((c, t, ti)))
    cb = getattr(_tls, "on_summarize_progress", None)
    assert cb is not None
    cb(3, 7, "Some Paper Title")
    assert calls == [(3, 7, "Some Paper Title")]
    set_summarize_progress_callback(None)
    assert getattr(_tls, "on_summarize_progress", None) is None


def test_search_node_calls_progress_callback(mocker):
    """search() should call the progress callback once per query."""
    calls = []
    set_search_progress_callback(lambda c, t, q: calls.append((c, t, q)))

    mock_engine = mocker.patch("src.agentic_workflow.SEARCH_ENGINE")
    mock_engine.search.return_value = []  # no results to avoid schema issues

    try:
        state = {
            "search_queries": ["query one", "query two"],
            "search_results": None,
        }
        search(state)
    finally:
        set_search_progress_callback(None)

    assert len(calls) == 2
    assert calls[0] == (1, 2, "query one")
    assert calls[1] == (2, 2, "query two")


def test_search_node_works_without_callback(mocker):
    """search() must not raise when no progress callback is registered."""
    set_search_progress_callback(None)
    mock_engine = mocker.patch("src.agentic_workflow.SEARCH_ENGINE")
    mock_engine.search.return_value = []
    state = {"search_queries": ["q"], "search_results": None}
    search(state)  # should not raise
