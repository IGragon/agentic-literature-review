import requests
from time import sleep


def get_bibtex_from_doi(doi: str) -> str | None:
    sleep(0.1)
    url = f"https://citation.doi.org/format?doi={doi}&style=bibtex&lang=en-US"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        return response.text
    except requests.RequestException:
        return None


def reconstruct_abstract(inverted_index: dict[str, list[int]]) -> str:
    """Convert OpenAlex abstract_inverted_index back to plaintext."""
    if not inverted_index:
        return ""
    positions = [
        (pos, word)
        for word, pos_list in inverted_index.items()
        for pos in pos_list
    ]
    return " ".join(word for _, word in sorted(positions))
