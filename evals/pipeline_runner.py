"""Pipeline runner: executes the full literature review pipeline and
extracts outputs for DeepEval LLMTestCase construction."""

import hashlib
import logging
from dataclasses import dataclass

from src.agentic_workflow import AgenticLiteratureReview
from src.utils import extract_bibtex_key

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    topic: str
    review: str
    paper_summaries: list[str]
    paper_citations: list[str]
    directions: list[str]


def _session_id_for_topic(topic: str) -> str:
    digest = hashlib.sha256(topic.encode()).hexdigest()[:12]
    return f"eval-{digest}"


def run_pipeline(topic: str) -> PipelineResult:
    """Run the full literature review pipeline for a given topic.

    Returns a PipelineResult with all fields needed to construct
    DeepEval LLMTestCase instances.
    """
    session_id = _session_id_for_topic(topic)
    alr = AgenticLiteratureReview(topic=topic, session_id=session_id)

    review = None
    search_results = None
    directions = None

    for node_name, state_update in alr.run():
        logger.info("Pipeline node completed: %s", node_name)
        if "review" in state_update and state_update["review"] is not None:
            review = state_update["review"]
        if "search_results" in state_update and state_update["search_results"] is not None:
            search_results = state_update["search_results"]
        if "directions" in state_update and state_update["directions"] is not None:
            directions = state_update["directions"]

    if review is None:
        raise RuntimeError(f"Pipeline completed without producing a review for topic: {topic}")

    papers = search_results or []
    paper_summaries = []
    paper_citations = []
    for p in papers:
        summary_parts = [
            f"Title: {p.get('title', '')}",
            f"Authors: {p.get('authors', '')}",
        ]
        if p.get("summary") and p["summary"] != p.get("abstract", ""):
            summary_parts.append(f"Summary: {p['summary']}")
        elif p.get("abstract"):
            summary_parts.append(f"Abstract: {p['abstract']}")
        paper_summaries.append("\n".join(summary_parts))

        citation = p.get("citation", "")
        if citation:
            key = extract_bibtex_key(citation)
            if key:
                paper_citations.append(key)

    return PipelineResult(
        topic=topic,
        review=review,
        paper_summaries=paper_summaries,
        paper_citations=paper_citations,
        directions=directions or [],
    )
