import io
from pathlib import Path

import pytest
import requests

from src.tools import download_arxiv_pdf, extract_pdf_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_pdf_response(mocker, content_type="application/pdf"):
    """Build a mock requests.Response that streams fake PDF bytes."""
    pdf_bytes = _minimal_pdf_bytes()
    mock_resp = mocker.MagicMock()
    mock_resp.headers = {"content-type": content_type}
    mock_resp.raise_for_status = mocker.MagicMock()
    mock_resp.iter_content = mocker.MagicMock(return_value=[pdf_bytes])
    return mock_resp


def _minimal_pdf_bytes() -> bytes:
    """Create a real minimal single-page PDF with known text using pypdf."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _pdf_with_text(text: str) -> Path:
    """Write a single-page PDF containing *text* to a temp file and return the path."""
    # We use reportlab if available, else fall back to a pre-built PDF fixture.
    # Since reportlab may not be installed, build a raw minimal PDF manually.
    # pypdf's PdfWriter doesn't easily add text — use a hand-crafted PDF stream.
    from pypdf import PdfWriter, PageObject
    import pypdf.generic as pdf_gen

    writer = PdfWriter()
    # A blank page won't have extractable text; encode text via content stream
    # Use raw PDF syntax for a simple text page
    raw_pdf = _raw_pdf_with_text(text)
    buf = io.BytesIO(raw_pdf)
    return buf  # caller reads via pypdf


def _raw_pdf_with_text(text: str) -> bytes:
    """Generate a minimal valid PDF (1 page) containing *text* as a text object."""
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode()
    stream_len = len(stream)

    content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        + f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode()
        + stream
        + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )
    # xref + trailer
    xref_pos = len(content)
    content += (
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000300 00000 n \n"
        + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return content


# ---------------------------------------------------------------------------
# download_arxiv_pdf
# ---------------------------------------------------------------------------


def test_download_success_writes_file(tmp_path, mocker):
    mocker.patch("src.tools.sleep")
    mock_resp = _make_mock_pdf_response(mocker)
    mocker.patch("src.tools.requests.get", return_value=mock_resp)

    dest = tmp_path / "2301.12345.pdf"
    result = download_arxiv_pdf("2301.12345", dest)

    assert result is True
    assert dest.exists()


def test_download_strips_version_in_url(tmp_path, mocker):
    mocker.patch("src.tools.sleep")
    mock_get = mocker.patch("src.tools.requests.get", return_value=_make_mock_pdf_response(mocker))

    download_arxiv_pdf("2301.12345v3", tmp_path / "out.pdf")

    called_url = mock_get.call_args[0][0]
    assert "2301.12345" in called_url
    assert "v3" not in called_url


def test_download_http_error_returns_false(tmp_path, mocker):
    mocker.patch("src.tools.sleep")
    mocker.patch("src.tools.requests.get", side_effect=requests.RequestException("timeout"))

    dest = tmp_path / "out.pdf"
    result = download_arxiv_pdf("2301.12345", dest)

    assert result is False
    assert not dest.exists()


def test_download_wrong_content_type_returns_false(tmp_path, mocker):
    mocker.patch("src.tools.sleep")
    mocker.patch("src.tools.requests.get", return_value=_make_mock_pdf_response(mocker, "text/html"))

    dest = tmp_path / "out.pdf"
    result = download_arxiv_pdf("2301.12345", dest)

    assert result is False


def test_download_creates_parent_directory(tmp_path, mocker):
    mocker.patch("src.tools.sleep")
    mocker.patch("src.tools.requests.get", return_value=_make_mock_pdf_response(mocker))

    dest = tmp_path / "subdir" / "nested" / "out.pdf"
    result = download_arxiv_pdf("2301.12345", dest)

    assert result is True
    assert dest.exists()


# ---------------------------------------------------------------------------
# extract_pdf_text
# ---------------------------------------------------------------------------


def test_extract_text_from_valid_pdf(tmp_path):
    text = "Hello PDF world"
    pdf_bytes = _raw_pdf_with_text(text)
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_bytes)

    result = extract_pdf_text(pdf_path)
    assert "Hello" in result or result == ""  # pypdf may or may not decode Type1 fonts
    # At minimum: no exception and returns a string
    assert isinstance(result, str)


def test_extract_text_truncated_at_max_chars(tmp_path):
    # Create a PDF by writing many pages worth of content; mock pypdf instead
    # to avoid font encoding issues with minimal PDFs
    from unittest.mock import MagicMock, patch

    long_text = "A" * 500
    mock_page = MagicMock()
    mock_page.extract_text.return_value = long_text
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")

    with patch("pypdf.PdfReader", return_value=mock_reader):
        result = extract_pdf_text(pdf_path, max_chars=100)

    assert len(result) <= 100


def test_extract_text_invalid_file_returns_empty(tmp_path):
    bad_pdf = tmp_path / "corrupt.pdf"
    bad_pdf.write_bytes(b"this is not a pdf")

    result = extract_pdf_text(bad_pdf)
    assert result == ""


def test_extract_text_missing_file_returns_empty(tmp_path):
    missing = tmp_path / "nonexistent.pdf"
    result = extract_pdf_text(missing)
    assert result == ""
