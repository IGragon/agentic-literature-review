import pytest


@pytest.fixture
def sample_paper():
    """A fully-populated PaperSearchResult dict."""
    return {
        "title": "Test Paper on Transformers",
        "authors": "Alice Smith, Bob Jones",
        "published_date": "2024-01-15",
        "abstract": "We study attention mechanisms in large language models.",
        "doi": "10.1234/test.2024",
        "url": "https://arxiv.org/abs/2401.00001",
        "citation": "@article{Smith2024, title={Test Paper}, year={2024}}",
        "summary": "",
        "paper_id": "2401.00001",
        "relevance": "",
        "completeness_score": 0,
    }


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    """Redirect session_store.SESSIONS_DIR to a temporary directory."""
    import src.session_store as ss

    target = tmp_path / "sessions"
    monkeypatch.setattr(ss, "SESSIONS_DIR", target)
    return target
