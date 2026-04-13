import os
import re
import threading
import time
from collections.abc import Callable
from logging import getLogger
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from src.prompts import (
    AGENT_SYSTEM_PROMPT,
    PROMPT_ADDITIONAL_QUERIES,
    PROMPT_COMPOSE_AGENT_TASK,
    PROMPT_CONSTRUCT_SEARCH_QUERIES,
    PROMPT_EVALUATE_REVIEW,
    PROMPT_EXPAND_TOPIC,
    PROMPT_RELEVANCE_FILTER,
    PROMPT_SUMMARIZE_PAPER,
)
from src.schemas import Directions, RelevanceScores, ReviewEvaluation, SearchQueries, State
from src.search_engine import SearchEngine
from src.tools import download_arxiv_pdf, extract_pdf_text, make_latex_tools
from src.utils import extract_bibtex_key, sanitize_bibtex_entry

load_dotenv()
logger = getLogger(__name__)

_ARXIV_VERSION_RE = re.compile(r"v\d+$")

MAX_REVIEW_ITERATIONS = int(os.getenv("MAX_REVIEW_ITERATIONS", "3"))
MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "10"))
MIN_REL_PAPERS = int(os.getenv("MIN_REL_PAPERS", "3"))
MAX_SEARCH_ITERATIONS = int(os.getenv("MAX_SEARCH_ITERATIONS", "3"))

SEARCH_ENGINE = SearchEngine()


class NoRelevantPapersFound(Exception):
    pass


# ---------------------------------------------------------------------------
# Progress callbacks (thread-local so concurrent Streamlit sessions stay isolated)
# ---------------------------------------------------------------------------

_tls = threading.local()


def set_search_progress_callback(cb: "Callable[[int, int, str], None] | None") -> None:
    _tls.on_search_progress = cb


def set_summarize_progress_callback(cb: "Callable[[int, int, str], None] | None") -> None:
    _tls.on_summarize_progress = cb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_llm() -> ChatOpenRouter:
    return ChatOpenRouter(
        model=os.getenv("OPENROUTER_MODEL"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL"),
    )


def wrap_logger(func):
    def wrapper(*args, **kwargs):
        logger.info(f"Running {func.__name__}")
        return func(*args, **kwargs)
    return wrapper


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


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

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
    existing = state.get("search_results") or []
    paper_ids = {r["paper_id"] for r in existing}
    search_results = list(existing)

    total_queries = len(queries)
    logger.info("search: running %d queries (existing papers: %d)", total_queries, len(existing))
    for i, query in enumerate(queries, 1):
        cb = getattr(_tls, "on_search_progress", None)
        if cb:
            cb(i, total_queries, query)
        logger.info("search: query %d/%d - %r", i, total_queries, query)
        for result in SEARCH_ENGINE.search(query):
            if result["paper_id"] not in paper_ids:
                result["relevance"] = ""
                result["completeness_score"] = 0
                search_results.append(result)
                paper_ids.add(result["paper_id"])
        logger.info("search: after query %d/%d total papers: %d", i, len(queries), len(search_results))

    return {"search_results": search_results}


def _compute_completeness(paper: dict) -> int:
    fields = ["title", "authors", "abstract", "doi", "url", "citation", "published_date"]
    return sum(1 for f in fields if (paper.get(f) or "").strip())


@wrap_logger
def filter_relevance(state: State) -> dict:
    papers = state.get("search_results") or []
    if not papers:
        logger.info("filter_relevance: no papers to filter")
        return {"search_results": []}

    for paper in papers:
        paper["completeness_score"] = _compute_completeness(paper)

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

    for paper in papers:
        paper["relevance"] = score_map.get(paper["paper_id"], "REL-")

    not_rel_removed = [p for p in papers if p["relevance"] != "NOT_REL"]
    logger.info(
        "filter_relevance: removed %d NOT_REL papers (%d remain)",
        len(papers) - len(not_rel_removed),
        len(not_rel_removed),
    )

    high_quality = [p for p in not_rel_removed if not (p["relevance"] == "REL-" and p["completeness_score"] < 3)]
    filtered = high_quality if high_quality else not_rel_removed
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
            "evaluate_quality: insufficient papers - will retry (iteration %d -> %d)",
            iteration, iteration + 1,
        )
        return {"quality_ok": False, "search_iteration": iteration + 1}

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
def compose_review_latex(state: State) -> dict:
    iterations_remaining = (state.get("review_iterations_remaining") or MAX_REVIEW_ITERATIONS) - 1
    feedback = state.get("review_feedback")
    session_id = state["session_id"]

    # Sanitize BibTeX keys: spaces in keys (common from doi.org) break bibtex parsing.
    papers_with_keys = []
    bibliography_entries = []
    for p in state["search_results"]:
        citation = p.get("citation") or ""
        if citation:
            clean_key, clean_citation = sanitize_bibtex_entry(citation)
            clean_key = clean_key or extract_bibtex_key(citation) or p["paper_id"]
        else:
            clean_key, clean_citation = p["paper_id"], ""
        papers_with_keys.append({**p, "bibtex_key": clean_key})
        if clean_citation:
            bibliography_entries.append(clean_citation)
    bibliography = "\n\n".join(bibliography_entries)

    # Session-scoped working directory: all LaTeX files live here.
    session_dir = Path("sessions") / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    tools = make_latex_tools(str(session_dir))
    tool_map = {t.name: t for t in tools}
    llm_with_tools = get_llm().bind_tools(tools)

    messages = [
        SystemMessage(AGENT_SYSTEM_PROMPT),
        HumanMessage(PROMPT_COMPOSE_AGENT_TASK.render(
            topic=state["topic"],
            directions=state["directions"],
            papers=papers_with_keys,
            bibliography=bibliography,
            feedback=feedback,
        )),
    ]

    # Code-Act loop: LLM calls tools, observes results, iterates until done or limit hit.
    for step in range(MAX_AGENT_STEPS):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            logger.info("compose_review_latex: agent finished at step %d (no tool calls)", step + 1)
            break

        for tc in response.tool_calls:
            logger.info("compose_review_latex: step %d tool=%s", step + 1, tc["name"])
            result = tool_map[tc["name"]].invoke(tc["args"])
            logger.info("compose_review_latex: result preview: %s", str(result)[:200])
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    else:
        logger.warning("compose_review_latex: reached MAX_AGENT_STEPS=%d without finish signal", MAX_AGENT_STEPS)

    pdf_path = session_dir / "review.pdf"
    if not pdf_path.exists():
        raise RuntimeError(
            f"Agent did not produce review.pdf after {MAX_AGENT_STEPS} steps."
        )

    review = (session_dir / "review.tex").read_text(encoding="utf-8")
    return {
        "review": review,
        "review_pdf_path": str(pdf_path),
        "review_iterations_remaining": iterations_remaining,
        "review_feedback": None,
    }


@wrap_logger
def evaluate_review(state: State) -> dict:
    llm_with_structure = get_llm().with_structured_output(ReviewEvaluation)

    result = llm_with_structure.invoke(
        PROMPT_EVALUATE_REVIEW.render(
            topic=state["topic"],
            directions=state["directions"],
            review=state["review"],
        )
    )

    remaining = state["review_iterations_remaining"]
    logger.info(
        "evaluate_review: accepted=%s, iterations_remaining=%d, feedback=%r",
        result["accepted"], remaining, result.get("feedback", "")[:120],
    )

    if result["accepted"] or remaining <= 0:
        return {"review_accepted": True, "review_feedback": None}

    return {
        "review_accepted": False,
        "review_feedback": result["feedback"],
    }


def should_iterate_review(state: State) -> str:
    if state.get("review_accepted"):
        return END
    return "compose_review_latex"


# ---------------------------------------------------------------------------
# Workflow assembly
# ---------------------------------------------------------------------------

class AgenticLiteratureReview:
    def __init__(self, topic: str, session_id: str):
        self.initial_state: State = {
            "topic": topic,
            "session_id": session_id,
            "directions": None,
            "search_queries": None,
            "search_results": None,
            "review": None,
            "review_pdf_path": None,
            "review_iterations_remaining": None,
            "review_feedback": None,
            "review_accepted": None,
            "search_iteration": 0,
            "quality_warning": None,
            "quality_ok": None,
        }
        self.config = {"configurable": {"thread_id": session_id}}
        self.flow: CompiledStateGraph = self._make_workflow()

    def _make_workflow(self) -> CompiledStateGraph:
        workflow = StateGraph(State)

        workflow.add_node("expand_topic", expand_topic)
        workflow.add_node("form_search_queries", form_search_queries)
        workflow.add_node("search", search)
        workflow.add_node("filter_relevance", filter_relevance)
        workflow.add_node("evaluate_quality", evaluate_quality)
        workflow.add_node("form_additional_queries", form_additional_queries)
        workflow.add_node("download_and_summarize", download_and_summarize)
        workflow.add_node("compose_review_latex", compose_review_latex)
        workflow.add_node("evaluate_review", evaluate_review)

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
        workflow.add_edge("download_and_summarize", "compose_review_latex")
        workflow.add_edge("compose_review_latex", "evaluate_review")
        workflow.add_conditional_edges("evaluate_review", should_iterate_review)

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
