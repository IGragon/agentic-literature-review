import os
from logging import getLogger
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from src.prompts import (
    AGENT_SYSTEM_PROMPT,
    PROMPT_COMPOSE_AGENT_TASK,
    PROMPT_CONSTRUCT_SEARCH_QUERIES,
    PROMPT_EVALUATE_REVIEW,
    PROMPT_EXPAND_TOPIC,
)
from src.schemas import Directions, ReviewEvaluation, SearchQueries, State
from src.search_engine import SearchEngine
from src.tools import make_latex_tools
from src.utils import extract_bibtex_key, sanitize_bibtex_entry

load_dotenv()
logger = getLogger(__name__)

MAX_REVIEW_ITERATIONS = int(os.getenv("MAX_REVIEW_ITERATIONS", "3"))
MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "10"))

SEARCH_ENGINE = SearchEngine()


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
    logger.info("search: running %d queries", len(queries))
    search_results = []
    paper_ids = set()
    for i, query in enumerate(queries, 1):
        logger.info("search: query %d/%d - %r", i, len(queries), query)
        for result in SEARCH_ENGINE.search(query):
            if result["paper_id"] not in paper_ids:
                search_results.append(result)
                paper_ids.add(result["paper_id"])
        logger.info("search: after query %d/%d total papers: %d", i, len(queries), len(search_results))
    return {"search_results": search_results}


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
        self.initial_state = State(topic=topic, session_id=session_id)
        self.config = {"configurable": {"thread_id": session_id}}
        self.flow: CompiledStateGraph = self._make_workflow()

    def _make_workflow(self) -> CompiledStateGraph:
        workflow = StateGraph(State)

        workflow.add_node("expand_topic", expand_topic)
        workflow.add_node("form_search_queries", form_search_queries)
        workflow.add_node("search", search)
        workflow.add_node("compose_review_latex", compose_review_latex)
        workflow.add_node("evaluate_review", evaluate_review)

        workflow.add_edge(START, "expand_topic")
        workflow.add_edge("expand_topic", "form_search_queries")
        workflow.add_edge("form_search_queries", "search")
        workflow.add_edge("search", "compose_review_latex")
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
