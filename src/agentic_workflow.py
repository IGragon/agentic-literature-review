from logging import getLogger

from dotenv import load_dotenv
import os
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from src.prompts import (
    PROMPT_COMPOSE_REVIEW,
    PROMPT_CONSTRUCT_SEARCH_QUERIES,
    PROMPT_EXPAND_TOPIC,
)
from src.schemas import SearchQueries, State, Directions
from src.search_engine import SearchEngine

load_dotenv()
logger = getLogger(__name__)


def wrap_logger(func):
    def wrapper(*args, **kwargs):
        logger.info(f"Running {func.__name__}")
        return func(*args, **kwargs)

    return wrapper


SEARCH_ENGINE = SearchEngine()


def get_llm() -> ChatOpenRouter:
    return ChatOpenRouter(
        model=os.getenv("OPENROUTER_MODEL"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL"),
    )


@wrap_logger
def expand_topic(state: State) -> dict:
    llm_with_structure = get_llm().with_structured_output(Directions)

    result = llm_with_structure.invoke(
        PROMPT_EXPAND_TOPIC.render(topic=state["topic"]),
    )

    # print(result)

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
    # print(result)

    return {"search_queries": result["search_queries"]}


@wrap_logger
def search(state: State) -> dict:
    queries = state["search_queries"]
    logger.info("search: running %d queries", len(queries))
    search_results = []
    paper_ids = set()
    for i, query in enumerate(queries, 1):
        logger.info("search: query %d/%d — %r", i, len(queries), query)
        for result in SEARCH_ENGINE.search(query):
            if result["paper_id"] not in paper_ids:
                search_results.append(result)
                paper_ids.add(result["paper_id"])
        logger.info("search: after query %d/%d total papers so far: %d", i, len(queries), len(search_results))

    return {"search_results": search_results}


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

    # print(review)

    return {"review": review}


class AgenticLiteratureReview:
    def __init__(self, topic):
        self.initial_state = State(topic=topic)
        self.config = {"configurable": {"thread_id": "mock_thread_id"}}
        self.flow: CompiledStateGraph = self._make_workflow()

    def _make_workflow(self) -> CompiledStateGraph:
        workflow = StateGraph(State)

        # add nodes
        workflow.add_node("expand_topic", expand_topic)
        workflow.add_node("form_search_queries", form_search_queries)
        workflow.add_node("search", search)
        workflow.add_node("compose_review", compose_review)

        # add edges
        workflow.add_edge(START, "expand_topic")
        workflow.add_edge("expand_topic", "form_search_queries")
        workflow.add_edge("form_search_queries", "search")
        workflow.add_edge("search", "compose_review")
        workflow.add_edge("compose_review", END)

        return workflow.compile()

    def run(self):
        for chunk in self._stream():
            if chunk["type"] == "updates":
                for node_name, state in chunk["data"].items():
                    # print(f"Node {node_name} updated {state}")
                    yield node_name, state

    def _stream(self):
        return self.flow.stream(
            self.initial_state,
            self.config,
            stream_mode="updates",
            version="v2",
        )
