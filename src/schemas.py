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


class Directions(TypedDict):
    directions: list[str]


class SearchQueries(TypedDict):
    search_queries: list[str]


class State(TypedDict):
    topic: str
    directions: list[str] | None
    search_queries: list[str] | None
    search_results: list[PaperSearchResult] | None
    review: str | None
