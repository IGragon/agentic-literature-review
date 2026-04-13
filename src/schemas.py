from typing import TypedDict


class PaperSearchResult(TypedDict):
    title: str
    authors: str
    published_date: str
    abstract: str
    doi: str
    url: str
    citation: str
    summary: str
    paper_id: str
    relevance: str           # "NOT_REL" | "REL-" | "REL" | "REL+" | "" (empty = unscored)
    completeness_score: int  # count of non-empty fields (0-7)


class Directions(TypedDict):
    directions: list[str]


class SearchQueries(TypedDict):
    search_queries: list[str]


class ReviewEvaluation(TypedDict):
    accepted: bool
    feedback: str  # empty string if accepted, specific improvements otherwise


class PaperRelevanceScore(TypedDict):
    paper_id: str
    relevance: str  # one of NOT_REL, REL-, REL, REL+


class RelevanceScores(TypedDict):
    scores: list[PaperRelevanceScore]


class State(TypedDict):
    topic: str
    session_id: str | None
    directions: list[str] | None
    search_queries: list[str] | None
    search_results: list[PaperSearchResult] | None
    review: str | None              # LaTeX source of the review
    review_pdf_path: str | None
    review_iterations_remaining: int | None
    review_feedback: str | None
    review_accepted: bool | None
    search_iteration: int           # starts at 0; incremented each retry
    quality_warning: str | None     # set when max iterations reached with insufficient papers
    quality_ok: bool | None         # set by evaluate_quality node
