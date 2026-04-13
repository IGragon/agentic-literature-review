import re
from logging import getLogger
from pathlib import Path
from time import sleep

import requests

logger = getLogger(__name__)

_ARXIV_VERSION_RE = re.compile(r"v\d+$")


def download_arxiv_pdf(arxiv_id: str, dest_path: Path) -> bool:
    """Download a PDF from arxiv.org for the given arXiv ID.

    Strips any version suffix (e.g. '2301.12345v2' → '2301.12345') so the
    latest version is always fetched.  Returns True on success.
    """
    base_id = _ARXIV_VERSION_RE.sub("", arxiv_id)
    url = f"https://arxiv.org/pdf/{base_id}"
    try:
        sleep(0.5)  # polite delay
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type and "octet-stream" not in content_type:
            logger.warning("Unexpected content-type for %s PDF: %s", arxiv_id, content_type)
            return False
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with dest_path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        logger.info("Downloaded PDF for %s → %s", arxiv_id, dest_path)
        return True
    except requests.RequestException as e:
        logger.warning("PDF download failed for %s: %s", arxiv_id, e)
        return False


def extract_pdf_text(pdf_path: Path, max_chars: int = 64000) -> str:
    """Extract plain text from a PDF file using pypdf.

    Returns up to *max_chars* characters concatenated from all pages.
    Returns an empty string if the file cannot be read.
    """
    try:
        from pypdf import PdfReader  # local import to keep startup fast if pypdf is missing

        reader = PdfReader(str(pdf_path))
        parts: list[str] = []
        total = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            remaining = max_chars - total
            if remaining <= 0:
                break
            parts.append(text[:remaining])
            total += len(text)
            if total >= max_chars:
                break
        return "".join(parts)
    except Exception as e:
        logger.warning("PDF text extraction failed for %s: %s", pdf_path, e)
        return ""
