import re
import requests
from time import sleep


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters for use in LaTeX text (e.g. title)."""
    # Backslash must come first to avoid double-escaping
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\^{}"),
        ("_", r"\_"),
    ]
    for char, replacement in replacements:
        text = text.replace(char, replacement)
    return text


def extract_bibtex_key(bibtex: str) -> str | None:
    """Extract the citation key from a BibTeX entry string."""
    match = re.search(r"@\w+\{([^,\s]+)", bibtex.strip())
    return match.group(1) if match else None


def sanitize_bibtex_entry(bibtex: str) -> tuple[str, str]:
    """Sanitize a BibTeX entry by replacing spaces in the citation key with underscores.

    BibTeX does not allow spaces in citation keys. The doi.org API sometimes returns
    keys like 'Smith_van der Meer_2017', which breaks bibtex parsing.

    Returns (sanitized_key, sanitized_entry). If no key is found, returns ("", bibtex).
    """
    m = re.search(r"@\w+\{([^,\n]+),", bibtex)
    if not m:
        return "", bibtex
    raw_key = m.group(1)
    clean_key = re.sub(r"\s+", "_", raw_key.strip())
    if clean_key == raw_key:
        return clean_key, bibtex
    # Replace only the key at the matched position to avoid clobbering body text
    clean_entry = bibtex[: m.start(1)] + clean_key + bibtex[m.end(1) :]
    return clean_key, clean_entry


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
