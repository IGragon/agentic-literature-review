import arxiv
from src.schemas import PaperSearchResult
from src.utils import get_bibtex_from_doi

from logging import getLogger

logger = getLogger(__name__)


class SearchEngine:
    def __init__(self):
        self.client = arxiv.Client(
            delay_seconds=4,
            num_retries=3,
        )
        self.max_results = 3

    def search(self, query: str) -> list[PaperSearchResult]:
        logger.info(f"Search query: {query}")
        search = arxiv.Search(
            query=query,
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending,
        )
        parsed_results = [
            PaperSearchResult(
                title=result.title,
                authors=", ".join(list(map(str, result.authors))),
                published_date=result.published.strftime("%Y-%m-%d"),
                abstract=result.summary,
                doi=result.doi,
                summary=result.summary,
                url=result.entry_id,
                paper_id=result.get_short_id(),
                citation=get_bibtex_from_doi(result.doi)
                if result.doi != ""
                else result.journal_ref,
            )
            for result in search.results()
        ]
        logger.info(f"Retrieved: {len(parsed_results)} results")
        return parsed_results
