import os
import re
import time
import arxiv
import requests
from time import sleep
from logging import getLogger

from src.schemas import PaperSearchResult
from src.utils import get_bibtex_from_doi, reconstruct_abstract

logger = getLogger(__name__)

MAX_RESULTS = int(os.getenv("MAX_RESULTS_PER_SOURCE", "3"))

_ARXIV_VERSION_RE = re.compile(r"v\d+$")

# ---------------------------------------------------------------------------
# arXiv backend
# ---------------------------------------------------------------------------

_arxiv_client = arxiv.Client(
    delay_seconds=3,
    num_retries=3,
    page_size=MAX_RESULTS,
)


def _fetch_arxiv_bibtex(arxiv_id: str) -> str | None:
    try:
        sleep(0.1)
        resp = requests.get(f"https://arxiv.org/bibtex/{arxiv_id}", timeout=10)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.warning("arxiv bibtex fetch failed for %s: %s", arxiv_id, e)
        return None


def _search_arxiv(query: str) -> list[PaperSearchResult]:
    logger.info("arXiv search starting (sleeping 3s): %r", query)
    sleep(3.1)
    results = []
    t0 = time.time()
    try:
        search = arxiv.Search(
            query=query,
            max_results=MAX_RESULTS,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending,
        )
        for r in _arxiv_client.results(search):
            arxiv_id = r.get_short_id()
            logger.info("arXiv fetching BibTeX for %s", arxiv_id)
            if r.doi:
                citation = get_bibtex_from_doi(r.doi)
            else:
                citation = _fetch_arxiv_bibtex(arxiv_id)
            results.append(
                PaperSearchResult(
                    title=r.title,
                    authors=", ".join(str(a) for a in r.authors),
                    published_date=r.published.strftime("%Y-%m-%d"),
                    abstract=r.summary,
                    doi=r.doi or "",
                    summary=r.summary,
                    url=r.entry_id,
                    paper_id=arxiv_id,
                    citation=citation,
                )
            )
    except Exception as e:
        logger.warning("arXiv search failed for %r: %s", query, e)
    logger.info("arXiv retrieved %d results in %.1fs", len(results), time.time() - t0)
    return results


# ---------------------------------------------------------------------------
# OpenAlex backend
# ---------------------------------------------------------------------------

_OPENALEX_BASE = "https://api.openalex.org/works"
_OPENALEX_SELECT = (
    "id,doi,display_name,authorships,publication_date,abstract_inverted_index,ids"
)


def _build_minimal_bibtex(item: dict, doi: str) -> str:
    title = item.get("display_name", "Unknown")
    year = str(item.get("publication_year", ""))
    first_author = ""
    authorships = item.get("authorships") or []
    if authorships and authorships[0].get("author"):
        name = authorships[0]["author"].get("display_name", "")
        first_author = name.split()[-1] if name else ""
    key = f"{first_author}{year}" if first_author else f"openalex{year}"
    return (
        f"@article{{{key},\n"
        f"  title = {{{title}}},\n"
        f"  year = {{{year}}},\n"
        f"  doi = {{{doi}}},\n"
        f"}}"
    )


def _search_openalex(query: str) -> list[PaperSearchResult]:
    logger.info("OpenAlex search starting: %r", query)
    t0 = time.time()
    params: dict = {
        "search": query,
        "per_page": MAX_RESULTS,
        "select": _OPENALEX_SELECT,
    }
    mailto = os.getenv("OPENALEX_MAILTO", "")
    if mailto:
        params["mailto"] = mailto

    results = []
    try:
        resp = requests.get(_OPENALEX_BASE, params=params, timeout=15)
        resp.raise_for_status()
        logger.info("OpenAlex API responded in %.1fs", time.time() - t0)
        for item in resp.json().get("results", []):
            raw_doi = item.get("doi") or ""
            doi = raw_doi.removeprefix("https://doi.org/")

            ids = item.get("ids") or {}
            arxiv_uri = ids.get("arxiv", "")
            arxiv_id = (
                arxiv_uri.removeprefix("https://arxiv.org/abs/") if arxiv_uri else ""
            )

            inverted = item.get("abstract_inverted_index")
            abstract = reconstruct_abstract(inverted) if inverted else ""

            authors = ", ".join(
                a["author"]["display_name"]
                for a in (item.get("authorships") or [])
                if a.get("author") and a["author"].get("display_name")
            )

            url = arxiv_uri or (f"https://doi.org/{doi}" if doi else item.get("id", ""))

            bibtex_source = "DOI" if doi else "arXiv ID" if arxiv_id else "minimal"
            logger.info("OpenAlex fetching BibTeX via %s for %s", bibtex_source, item.get("id", ""))
            if doi:
                citation = get_bibtex_from_doi(doi)
            elif arxiv_id:
                citation = _fetch_arxiv_bibtex(arxiv_id)
            else:
                citation = _build_minimal_bibtex(item, doi)

            paper_id = arxiv_id or f"openalex:{item['id'].split('/')[-1]}"

            results.append(
                PaperSearchResult(
                    title=item.get("display_name") or "",
                    authors=authors,
                    published_date=item.get("publication_date") or "",
                    abstract=abstract,
                    doi=doi,
                    summary=abstract,
                    url=url,
                    paper_id=paper_id,
                    citation=citation,
                )
            )
    except Exception as e:
        logger.warning("OpenAlex search failed for %r after %.1fs: %s", query, time.time() - t0, e)
    logger.info("OpenAlex retrieved %d results in %.1fs", len(results), time.time() - t0)
    return results


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _normalize_arxiv_id(pid: str) -> str:
    return _ARXIV_VERSION_RE.sub("", pid)


def _dedup_accept(
    r: PaperSearchResult,
    seen_dois: set[str],
    seen_arxiv_ids: set[str],
) -> bool:
    doi = r["doi"].strip().lower()
    pid = r["paper_id"].strip()
    arxiv_id = (
        _normalize_arxiv_id(pid)
        if not pid.startswith(("s2:", "openalex:"))
        else ""
    )

    if doi and doi in seen_dois:
        return False
    if arxiv_id and arxiv_id in seen_arxiv_ids:
        return False

    if doi:
        seen_dois.add(doi)
    if arxiv_id:
        seen_arxiv_ids.add(arxiv_id)
    return True


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class SearchEngine:
    def __init__(self):
        active = ["arXiv", "OpenAlex"]
        logger.info("SearchEngine initialized, active backends: %s", active)

    def search(self, query: str) -> list[PaperSearchResult]:
        logger.info("SearchEngine query: %r", query)
        t0 = time.time()
        seen_dois: set[str] = set()
        seen_arxiv_ids: set[str] = set()
        merged: list[PaperSearchResult] = []

        for result in (
            _search_arxiv(query)
            + _search_openalex(query)
        ):
            if _dedup_accept(result, seen_dois, seen_arxiv_ids):
                merged.append(result)

        logger.info("SearchEngine query done in %.1fs — %d results after dedup", time.time() - t0, len(merged))
        return merged
