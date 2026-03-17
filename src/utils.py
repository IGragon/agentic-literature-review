import requests
from time import sleep


def get_bibtex_from_doi(doi: str) -> str | None:
    sleep(0.1)
    url = f"https://citation.doi.org/format?doi={doi}&style=bibtex&lang=en-US"
    try:
        response = requests.get(url)
        response.raise_for_status()

        return response.text
    except requests.HTTPError:
        return None
