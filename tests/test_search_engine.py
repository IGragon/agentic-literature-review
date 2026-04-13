import pytest

from src.search_engine import _build_minimal_bibtex, _dedup_accept, _normalize_arxiv_id
from src.schemas import PaperSearchResult


# ---------------------------------------------------------------------------
# _normalize_arxiv_id
# ---------------------------------------------------------------------------


def test_normalize_strips_version():
    assert _normalize_arxiv_id("2301.12345v2") == "2301.12345"


def test_normalize_strips_version_v1():
    assert _normalize_arxiv_id("2301.12345v1") == "2301.12345"


def test_normalize_no_version_unchanged():
    assert _normalize_arxiv_id("2301.12345") == "2301.12345"


def test_normalize_old_hep_format():
    assert _normalize_arxiv_id("hep-th/9901001v1") == "hep-th/9901001"


def test_normalize_old_format_no_version():
    assert _normalize_arxiv_id("hep-th/9901001") == "hep-th/9901001"


# ---------------------------------------------------------------------------
# _dedup_accept helpers
# ---------------------------------------------------------------------------


def _make_paper(paper_id: str, doi: str = "") -> PaperSearchResult:
    return PaperSearchResult(
        title="T",
        authors="A",
        published_date="2024-01-01",
        abstract="",
        doi=doi,
        url="",
        citation="",
        summary="",
        paper_id=paper_id,
        relevance="",
        completeness_score=0,
    )


# ---------------------------------------------------------------------------
# _dedup_accept
# ---------------------------------------------------------------------------


def test_dedup_accept_new_doi():
    seen_dois: set = set()
    seen_arxiv: set = set()
    paper = _make_paper("openalex:W1", doi="10.1234/abc")
    assert _dedup_accept(paper, seen_dois, seen_arxiv) is True
    assert "10.1234/abc" in seen_dois


def test_dedup_accept_duplicate_doi():
    seen_dois = {"10.1234/abc"}
    seen_arxiv: set = set()
    paper = _make_paper("openalex:W2", doi="10.1234/abc")
    assert _dedup_accept(paper, seen_dois, seen_arxiv) is False


def test_dedup_accept_doi_case_insensitive():
    seen_dois = {"10.1234/abc"}
    seen_arxiv: set = set()
    paper = _make_paper("openalex:W3", doi="10.1234/ABC")
    assert _dedup_accept(paper, seen_dois, seen_arxiv) is False


def test_dedup_accept_new_arxiv_id():
    seen_dois: set = set()
    seen_arxiv: set = set()
    paper = _make_paper("2301.12345v1")
    assert _dedup_accept(paper, seen_dois, seen_arxiv) is True
    assert "2301.12345" in seen_arxiv


def test_dedup_accept_duplicate_arxiv_different_version():
    seen_dois: set = set()
    seen_arxiv = {"2301.12345"}
    paper = _make_paper("2301.12345v2")
    assert _dedup_accept(paper, seen_dois, seen_arxiv) is False


def test_dedup_accept_openalex_prefix_not_treated_as_arxiv():
    seen_dois: set = set()
    seen_arxiv: set = set()
    paper1 = _make_paper("openalex:W111")
    paper2 = _make_paper("openalex:W222")
    assert _dedup_accept(paper1, seen_dois, seen_arxiv) is True
    # second openalex paper with different id is also accepted (no arxiv overlap)
    assert _dedup_accept(paper2, seen_dois, seen_arxiv) is True
    assert len(seen_arxiv) == 0  # nothing added to arxiv set


def test_dedup_accept_no_doi_no_arxiv_accepted():
    seen_dois: set = set()
    seen_arxiv: set = set()
    paper = _make_paper("openalex:W999", doi="")
    assert _dedup_accept(paper, seen_dois, seen_arxiv) is True


# ---------------------------------------------------------------------------
# _build_minimal_bibtex
# ---------------------------------------------------------------------------


def _make_openalex_item(display_name="Test Paper", year=2024, authors=None, doi="10.99/test"):
    item = {
        "display_name": display_name,
        "publication_year": year,
        "authorships": authors or [],
    }
    return item


def test_build_minimal_bibtex_with_author_and_year():
    item = _make_openalex_item(
        authors=[{"author": {"display_name": "Jane Doe"}}],
        year=2023,
    )
    result = _build_minimal_bibtex(item, "10.1234/x")
    assert "Doe2023" in result
    assert "2023" in result


def test_build_minimal_bibtex_no_authors_uses_openalex_key():
    item = _make_openalex_item(authors=[], year=2021)
    result = _build_minimal_bibtex(item, "10.1234/x")
    assert "openalex2021" in result


def test_build_minimal_bibtex_contains_doi():
    item = _make_openalex_item(doi="10.9999/mypaper")
    result = _build_minimal_bibtex(item, "10.9999/mypaper")
    assert "10.9999/mypaper" in result


def test_build_minimal_bibtex_contains_title():
    item = _make_openalex_item(display_name="My Great Paper")
    result = _build_minimal_bibtex(item, "10.1234/x")
    assert "My Great Paper" in result
