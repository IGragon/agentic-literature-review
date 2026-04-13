import os
import re
import threading
import time
from collections.abc import Callable
from logging import getLogger
from pathlib import Path

from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from src.prompts import (
    PROMPT_ADDITIONAL_QUERIES,
    PROMPT_COMPOSE_REVIEW,
    PROMPT_CONSTRUCT_SEARCH_QUERIES,
    PROMPT_EXPAND_TOPIC,
    PROMPT_RELEVANCE_FILTER,
    PROMPT_SUMMARIZE_PAPER,
)
from src.schemas import RelevanceScores, SearchQueries, State, Directions
from src.search_engine import SearchEngine
from src.tools import download_arxiv_pdf, extract_pdf_text

load_dotenv()
logger = getLogger(__name__)

_ARXIV_VERSION_RE = re.compile(r"v\d+$")

MIN_REL_PAPERS = int(os.getenv("MIN_REL_PAPERS", "3"))
MAX_SEARCH_ITERATIONS = int(os.getenv("MAX_SEARCH_ITERATIONS", "3"))

SEARCH_ENGINE = SearchEngine()


class NoRelevantPapersFound(Exception):
    pass


# ---------------------------------------------------------------------------
# Progress callbacks
# Each Streamlit session runs in its own thread, so threading.local() keeps
# callbacks isolated between concurrent sessions.
# ---------------------------------------------------------------------------

_tls = threading.local()


def set_search_progress_callback(cb: "Callable[[int, int, str], None] | None") -> None:
    """Register a callback invoked before each search query.

    Signature: ``cb(current: int, total: int, query: str)``
    Pass ``None`` to unregister.
    """
    _tls.on_search_progress = cb


def set_summarize_progress_callback(cb: "Callable[[int, int, str], None] | None") -> None:
    """Register a callback invoked before each paper is summarized.

    Signature: ``cb(current: int, total: int, title: str)``
    Pass ``None`` to unregister.
    """
    _tls.on_summarize_progress = cb


def wrap_logger(func):
    def wrapper(*args, **kwargs):
        logger.info(f"Running {func.__name__}")
        return func(*args, **kwargs)

    return wrapper


def get_llm() -> ChatOpenRouter:
    return ChatOpenRouter(
        model=os.getenv("OPENROUTER_MODEL"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL"),
    )


_TRANSIENT_ERROR_NAMES = {
    "RemoteProtocolError",
    "RemoteDisconnected",
    "ConnectError",
    "ConnectTimeout",
    "ReadTimeout",
    "IncompleteRead",
    "ChunkedEncodingError",
}


def _is_transient(exc: Exception) -> bool:
    return type(exc).__name__ in _TRANSIENT_ERROR_NAMES


def _invoke_with_retry(llm: ChatOpenRouter, prompt: str, max_retries: int = 3) -> object:
    """Invoke the LLM and retry on transient network errors with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return llm.invoke(prompt)
        except Exception as exc:
            if attempt < max_retries - 1 and _is_transient(exc):
                wait = 5 * (2 ** attempt)
                logger.warning(
                    "LLM call transient error (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1, max_retries, wait, exc,
                )
                time.sleep(wait)
            else:
                raise


@wrap_logger
def expand_topic(state: State) -> dict:
    llm_with_structure = get_llm().with_structured_output(Directions)

    result = llm_with_structure.invoke(
        PROMPT_EXPAND_TOPIC.render(topic=state["topic"]),
    )

    return {"directions": result["directions"]}


@wrap_logger
def form_search_queries(state: State) -> dict:
    llm_with_structure = get_llm().with_structured_output(SearchQueries)

    result = llm_with_structure.invoke(
        PROMPT_CONSTRUCT_SEARCH_QUERIES.render(
            topic=state["topic"],
            directions=state["directions"],
        ),
    )

    return {"search_queries": result["search_queries"]}


@wrap_logger
def search(state: State) -> dict:
    queries = state["search_queries"]
    # Accumulate results across iterations: seed from existing papers
    existing = state.get("search_results") or []
    paper_ids = {r["paper_id"] for r in existing}
    search_results = list(existing)

    total_queries = len(queries)
    logger.info("search: running %d queries (existing papers: %d)", total_queries, len(existing))
    for i, query in enumerate(queries, 1):
        cb = getattr(_tls, "on_search_progress", None)
        if cb:
            cb(i, total_queries, query)
        logger.info("search: query %d/%d — %r", i, total_queries, query)
        for result in SEARCH_ENGINE.search(query):
            if result["paper_id"] not in paper_ids:
                # Initialise new schema fields for freshly retrieved papers
                result["relevance"] = ""
                result["completeness_score"] = 0
                search_results.append(result)
                paper_ids.add(result["paper_id"])
        logger.info("search: after query %d/%d total papers: %d", i, len(queries), len(search_results))

    return {"search_results": search_results}


def _compute_completeness(paper: dict) -> int:
    """Count non-empty fields relevant to completeness (max 7)."""
    fields = ["title", "authors", "abstract", "doi", "url", "citation", "published_date"]
    return sum(1 for f in fields if (paper.get(f) or "").strip())


@wrap_logger
def filter_relevance(state: State) -> dict:
    papers = state.get("search_results") or []
    if not papers:
        logger.info("filter_relevance: no papers to filter")
        return {"search_results": []}

    # 1. Compute completeness scores
    for paper in papers:
        paper["completeness_score"] = _compute_completeness(paper)

    # 2. Batch LLM call to score relevance
    llm_with_structure = get_llm().with_structured_output(RelevanceScores)
    scores_result = llm_with_structure.invoke(
        PROMPT_RELEVANCE_FILTER.render(
            topic=state["topic"],
            directions=state["directions"],
            papers=papers,
        )
    )

    score_map: dict[str, str] = {
        s["paper_id"]: s["relevance"]
        for s in scores_result.get("scores", [])
    }
    logger.info("filter_relevance: received scores for %d/%d papers", len(score_map), len(papers))

    # 3. Attach relevance labels
    for paper in papers:
        paper["relevance"] = score_map.get(paper["paper_id"], "REL-")  # default to REL- if missing

    # 4. Filter
    not_rel_removed = [p for p in papers if p["relevance"] != "NOT_REL"]
    logger.info(
        "filter_relevance: removed %d NOT_REL papers (%d remain)",
        len(papers) - len(not_rel_removed),
        len(not_rel_removed),
    )

    # Remove REL- papers with low completeness, but only if it doesn't empty the list
    high_quality = [p for p in not_rel_removed if not (p["relevance"] == "REL-" and p["completeness_score"] < 3)]
    if high_quality:
        filtered = high_quality
    else:
        filtered = not_rel_removed  # keep them all rather than return empty
    logger.info(
        "filter_relevance: removed %d low-completeness REL- papers (%d remain)",
        len(not_rel_removed) - len(filtered),
        len(filtered),
    )

    return {"search_results": filtered}


@wrap_logger
def evaluate_quality(state: State) -> dict:
    papers = state.get("search_results") or []
    iteration = state.get("search_iteration", 0)

    rel_count = sum(1 for p in papers if p.get("relevance") in {"REL", "REL+"})
    logger.info(
        "evaluate_quality: %d REL/REL+ papers out of %d total (iteration %d)",
        rel_count, len(papers), iteration,
    )

    # Fail hard if no papers at all after exhausting retries
    if not papers and iteration >= MAX_SEARCH_ITERATIONS:
        raise NoRelevantPapersFound(
            "No relevant papers found after maximum search iterations. "
            "Try a broader or differently-phrased topic."
        )

    if rel_count >= MIN_REL_PAPERS:
        logger.info("evaluate_quality: quality OK (%d >= %d)", rel_count, MIN_REL_PAPERS)
        return {"quality_ok": True, "quality_warning": None}

    if iteration < MAX_SEARCH_ITERATIONS:
        logger.info(
            "evaluate_quality: insufficient papers — will retry (iteration %d → %d)",
            iteration, iteration + 1,
        )
        return {"quality_ok": False, "search_iteration": iteration + 1}

    # Max iterations exhausted — accept with warning
    warning = (
        f"Only {rel_count} highly relevant paper(s) found after {iteration} search iteration(s). "
        "The review may be of limited quality."
    )
    logger.warning("evaluate_quality: %s", warning)
    return {"quality_ok": True, "quality_warning": warning}


def _route_after_quality(state: State) -> str:
    return "retry" if not state.get("quality_ok") else "proceed"


@wrap_logger
def form_additional_queries(state: State) -> dict:
    llm_with_structure = get_llm().with_structured_output(SearchQueries)

    result = llm_with_structure.invoke(
        PROMPT_ADDITIONAL_QUERIES.render(
            topic=state["topic"],
            directions=state["directions"],
            papers=state.get("search_results") or [],
            previous_queries=state.get("search_queries") or [],
        )
    )

    new_queries = result["search_queries"]
    logger.info("form_additional_queries: generated %d new queries", len(new_queries))
    return {"search_queries": new_queries}


@wrap_logger
def download_and_summarize(state: State) -> dict:
    papers = state.get("search_results") or []
    session_id = state.get("session_id") or "unknown"
    pdf_dir = Path("sessions") / session_id / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    llm = get_llm()
    updated_papers = []
    total_papers = len(papers)

    for idx, paper in enumerate(papers, 1):
        cb = getattr(_tls, "on_summarize_progress", None)
        if cb:
            cb(idx, total_papers, paper["title"])
        pid = paper["paper_id"]
        arxiv_id = None if pid.startswith("openalex:") else pid

        full_text = None
        if arxiv_id:
            base_id = _ARXIV_VERSION_RE.sub("", arxiv_id)
            safe_name = base_id.replace("/", "_")
            pdf_path = pdf_dir / f"{safe_name}.pdf"
            if not pdf_path.exists():
                download_arxiv_pdf(base_id, pdf_path)
            if pdf_path.exists():
                full_text = extract_pdf_text(pdf_path)

        if full_text:
            logger.info("summarize: using full text for %s (%d chars)", pid, len(full_text))
        else:
            logger.info("summarize: using abstract fallback for %s", pid)

        summary = _invoke_with_retry(
            llm,
            PROMPT_SUMMARIZE_PAPER.render(
                title=paper["title"],
                full_text=full_text,
                abstract=paper["abstract"],
            ),
        ).content.strip()

        updated_papers.append({**paper, "summary": summary})

    return {"search_results": updated_papers}


@wrap_logger
def compose_review(state: State) -> dict:
    llm = get_llm()
    review = llm.invoke(
        PROMPT_COMPOSE_REVIEW.render(
            topic=state["topic"],
            directions=state["directions"],
            search_results=state["search_results"],
        )
    ).content

    review = review[
        review.find("<review>") + len("<review>") : review.find("</review>")
    ]

    return {"review": review}


class AgenticLiteratureReview:
    def __init__(self, topic: str, session_id: str):
        self.session_id = session_id
        self.initial_state: State = {
            "topic": topic,
            "session_id": session_id,
            "directions": None,
            "search_queries": None,
            "search_results": None,
            "review": None,
            "search_iteration": 0,
            "quality_warning": None,
            "quality_ok": None,
        }
        self.config = {"configurable": {"thread_id": session_id}}
        self.flow: CompiledStateGraph = self._make_workflow()

    def _make_workflow(self) -> CompiledStateGraph:
        workflow = StateGraph(State)

        # nodes
        workflow.add_node("expand_topic", expand_topic)
        workflow.add_node("form_search_queries", form_search_queries)
        workflow.add_node("search", search)
        workflow.add_node("filter_relevance", filter_relevance)
        workflow.add_node("evaluate_quality", evaluate_quality)
        workflow.add_node("form_additional_queries", form_additional_queries)
        workflow.add_node("download_and_summarize", download_and_summarize)
        workflow.add_node("compose_review", compose_review)

        # edges
        workflow.add_edge(START, "expand_topic")
        workflow.add_edge("expand_topic", "form_search_queries")
        workflow.add_edge("form_search_queries", "search")
        workflow.add_edge("search", "filter_relevance")
        workflow.add_edge("filter_relevance", "evaluate_quality")
        workflow.add_conditional_edges(
            "evaluate_quality",
            _route_after_quality,
            {"retry": "form_additional_queries", "proceed": "download_and_summarize"},
        )
        workflow.add_edge("form_additional_queries", "search")
        workflow.add_edge("download_and_summarize", "compose_review")
        workflow.add_edge("compose_review", END)

        return workflow.compile()

    def run(self):
        for chunk in self._stream():
            if chunk["type"] == "updates":
                for node_name, state in chunk["data"].items():
                    yield node_name, state

    def _stream(self):
        return self.flow.stream(
            self.initial_state,
            self.config,
            stream_mode="updates",
            version="v2",
        )
