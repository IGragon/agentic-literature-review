"""Tests that all Jinja2 prompt templates render without error and contain expected content."""

import pytest

from src.prompts import (
    PROMPT_ADDITIONAL_QUERIES,
    PROMPT_COMPOSE_REVIEW,
    PROMPT_CONSTRUCT_SEARCH_QUERIES,
    PROMPT_EXPAND_TOPIC,
    PROMPT_RELEVANCE_FILTER,
    PROMPT_SUMMARIZE_PAPER,
)


@pytest.fixture
def papers():
    return [
        {
            "paper_id": "2401.00001",
            "title": "Attention Is All You Need",
            "abstract": "We propose the Transformer architecture.",
            "relevance": "REL+",
            "summary": "Problem: seq2seq. Method: attention. Results: SOTA.",
            "authors": "Vaswani et al.",
            "published_date": "2017-06-12",
            "doi": "10.48550/arXiv.1706.03762",
            "url": "https://arxiv.org/abs/1706.03762",
            "citation": "@article{vaswani2017}",
            "completeness_score": 7,
        },
        {
            "paper_id": "openalex:W9876",
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "abstract": "We introduce BERT.",
            "relevance": "REL",
            "summary": "Problem: NLP pre-training. Method: masked LM. Results: GLUE SOTA.",
            "authors": "Devlin et al.",
            "published_date": "2019-05-24",
            "doi": "",
            "url": "https://arxiv.org/abs/1810.04805",
            "citation": "",
            "completeness_score": 5,
        },
    ]


@pytest.fixture
def directions():
    return ["Self-attention mechanisms", "Pre-training strategies"]


# ---------------------------------------------------------------------------
# PROMPT_EXPAND_TOPIC
# ---------------------------------------------------------------------------


def test_expand_topic_renders(directions):
    rendered = PROMPT_EXPAND_TOPIC.render(topic="Large language models")
    assert "Large language models" in rendered
    assert len(rendered) > 10


# ---------------------------------------------------------------------------
# PROMPT_CONSTRUCT_SEARCH_QUERIES
# ---------------------------------------------------------------------------


def test_construct_search_queries_renders(directions):
    rendered = PROMPT_CONSTRUCT_SEARCH_QUERIES.render(
        topic="Transformer architectures",
        directions=directions,
    )
    assert "Transformer architectures" in rendered
    assert "Self-attention" in rendered
    assert "Pre-training" in rendered


# ---------------------------------------------------------------------------
# PROMPT_RELEVANCE_FILTER
# ---------------------------------------------------------------------------


def test_relevance_filter_renders_topic_and_directions(papers, directions):
    rendered = PROMPT_RELEVANCE_FILTER.render(
        topic="Deep learning for NLP",
        directions=directions,
        papers=papers,
    )
    assert "Deep learning for NLP" in rendered
    assert "Self-attention" in rendered


def test_relevance_filter_renders_all_paper_ids(papers, directions):
    rendered = PROMPT_RELEVANCE_FILTER.render(
        topic="NLP",
        directions=directions,
        papers=papers,
    )
    assert "2401.00001" in rendered
    assert "openalex:W9876" in rendered


def test_relevance_filter_renders_relevance_labels_explanation(papers, directions):
    rendered = PROMPT_RELEVANCE_FILTER.render(
        topic="NLP",
        directions=directions,
        papers=papers,
    )
    assert "NOT_REL" in rendered
    assert "REL+" in rendered


# ---------------------------------------------------------------------------
# PROMPT_SUMMARIZE_PAPER
# ---------------------------------------------------------------------------


def test_summarize_with_full_text_uses_full_text_block():
    rendered = PROMPT_SUMMARIZE_PAPER.render(
        title="My Paper",
        full_text="Introduction: We study X. Method: We use Y. Results: Z.",
        abstract="Short abstract.",
    )
    assert "My Paper" in rendered
    assert "Introduction" in rendered


def test_summarize_without_full_text_uses_abstract():
    rendered = PROMPT_SUMMARIZE_PAPER.render(
        title="My Paper",
        full_text=None,
        abstract="Short abstract about transformers.",
    )
    assert "My Paper" in rendered
    assert "Short abstract about transformers" in rendered


def test_summarize_requests_structured_sections():
    rendered = PROMPT_SUMMARIZE_PAPER.render(
        title="Paper",
        full_text=None,
        abstract="abstract",
    )
    assert "Problem" in rendered
    assert "Method" in rendered
    assert "Results" in rendered
    assert "Limitations" in rendered


# ---------------------------------------------------------------------------
# PROMPT_ADDITIONAL_QUERIES
# ---------------------------------------------------------------------------


def test_additional_queries_renders_previous_queries(papers, directions):
    rendered = PROMPT_ADDITIONAL_QUERIES.render(
        topic="NLP",
        directions=directions,
        papers=papers,
        previous_queries=["transformers attention", "BERT pre-training"],
    )
    assert "transformers attention" in rendered
    assert "BERT pre-training" in rendered


def test_additional_queries_renders_paper_relevance(papers, directions):
    rendered = PROMPT_ADDITIONAL_QUERIES.render(
        topic="NLP",
        directions=directions,
        papers=papers,
        previous_queries=[],
    )
    assert "REL+" in rendered
    assert "Attention Is All You Need" in rendered


# ---------------------------------------------------------------------------
# PROMPT_COMPOSE_REVIEW
# ---------------------------------------------------------------------------


def test_compose_review_renders_papers(papers, directions):
    rendered = PROMPT_COMPOSE_REVIEW.render(
        topic="Transformer models",
        directions=directions,
        search_results=papers,
    )
    assert "Transformer models" in rendered
    assert "Attention Is All You Need" in rendered
    assert "BERT" in rendered


def test_compose_review_renders_summaries(papers, directions):
    rendered = PROMPT_COMPOSE_REVIEW.render(
        topic="NLP",
        directions=directions,
        search_results=papers,
    )
    assert "Problem: seq2seq" in rendered


def test_compose_review_renders_review_tags(papers, directions):
    rendered = PROMPT_COMPOSE_REVIEW.render(
        topic="NLP",
        directions=directions,
        search_results=papers,
    )
    assert "<review>" in rendered
    assert "</review>" in rendered
