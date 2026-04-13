import pytest
import requests

from src.utils import get_bibtex_from_doi, reconstruct_abstract


# ---------------------------------------------------------------------------
# reconstruct_abstract
# ---------------------------------------------------------------------------


def test_reconstruct_abstract_basic():
    index = {"hello": [0], "world": [1]}
    assert reconstruct_abstract(index) == "hello world"


def test_reconstruct_abstract_reorders_positions():
    # positions are out of order in the dict
    index = {"world": [1], "hello": [0], "there": [2]}
    assert reconstruct_abstract(index) == "hello world there"


def test_reconstruct_abstract_duplicate_positions():
    # one word at multiple positions
    index = {"the": [0, 3], "cat": [1], "sat": [2]}
    result = reconstruct_abstract(index)
    words = result.split()
    assert words[0] == "the"
    assert words[1] == "cat"
    assert words[2] == "sat"
    assert words[3] == "the"


def test_reconstruct_abstract_empty_dict():
    assert reconstruct_abstract({}) == ""


def test_reconstruct_abstract_none():
    assert reconstruct_abstract(None) == ""


# ---------------------------------------------------------------------------
# get_bibtex_from_doi
# ---------------------------------------------------------------------------


def test_get_bibtex_from_doi_success(mocker):
    mock_resp = mocker.MagicMock()
    mock_resp.text = "@article{test2024, title={Test}}"
    mock_resp.raise_for_status = mocker.MagicMock()
    mocker.patch("src.utils.requests.get", return_value=mock_resp)
    mocker.patch("src.utils.sleep")  # skip the 0.1s delay

    result = get_bibtex_from_doi("10.1234/test")
    assert result == "@article{test2024, title={Test}}"


def test_get_bibtex_from_doi_constructs_correct_url(mocker):
    mock_resp = mocker.MagicMock()
    mock_resp.text = "@article{}"
    mock_resp.raise_for_status = mocker.MagicMock()
    mock_get = mocker.patch("src.utils.requests.get", return_value=mock_resp)
    mocker.patch("src.utils.sleep")

    get_bibtex_from_doi("10.9999/xyz")

    called_url = mock_get.call_args[0][0]
    assert "10.9999/xyz" in called_url
    assert "bibtex" in called_url


def test_get_bibtex_from_doi_http_error(mocker):
    mocker.patch("src.utils.requests.get", side_effect=requests.RequestException("timeout"))
    mocker.patch("src.utils.sleep")

    result = get_bibtex_from_doi("10.1234/bad")
    assert result is None


def test_get_bibtex_from_doi_bad_status(mocker):
    mock_resp = mocker.MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
    mocker.patch("src.utils.requests.get", return_value=mock_resp)
    mocker.patch("src.utils.sleep")

    result = get_bibtex_from_doi("10.1234/missing")
    assert result is None
