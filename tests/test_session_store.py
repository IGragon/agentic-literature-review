import json
import time
import uuid

import pytest

from src.session_store import (
    Session,
    delete_session,
    list_sessions,
    load_session,
    make_session,
    save_session,
)


# ---------------------------------------------------------------------------
# make_session
# ---------------------------------------------------------------------------


def test_make_session_generates_uuid():
    s = make_session("topic", [], [], "review")
    uuid.UUID(s.id)  # raises if not valid UUID


def test_make_session_uses_provided_id():
    sid = str(uuid.uuid4())
    s = make_session("topic", [], [], "review", session_id=sid)
    assert s.id == sid


def test_make_session_truncates_name_at_50():
    long_topic = "A" * 60
    s = make_session(long_topic, [], [], "review")
    assert s.name.endswith("...")
    assert len(s.name) <= 53  # 50 chars + "..."


def test_make_session_short_name_no_ellipsis():
    s = make_session("Short topic", [], [], "review")
    assert "..." not in s.name
    assert s.name == "Short topic"


def test_make_session_quality_warning_stored():
    s = make_session("topic", [], [], "review", quality_warning="Low quality")
    assert s.quality_warning == "Low quality"


def test_make_session_quality_warning_defaults_to_none():
    s = make_session("topic", [], [], "review")
    assert s.quality_warning is None


# ---------------------------------------------------------------------------
# save / load roundtrip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(sessions_dir):
    s = make_session(
        "My research topic",
        ["dir1", "dir2"],
        [{"title": "Paper", "paper_id": "123", "relevance": "REL"}],
        "## Review content",
        session_id="test-id-123",
        quality_warning="some warning",
    )
    save_session(s)
    loaded = load_session("test-id-123")
    assert loaded.id == s.id
    assert loaded.topic == s.topic
    assert loaded.directions == s.directions
    assert loaded.review == s.review
    assert loaded.quality_warning == s.quality_warning
    assert len(loaded.search_results) == 1


def test_save_load_roundtrip_no_quality_warning(sessions_dir):
    s = make_session("topic", [], [], "review", session_id="no-warn-id")
    save_session(s)
    loaded = load_session("no-warn-id")
    assert loaded.quality_warning is None


def test_load_session_legacy_json_without_quality_warning(sessions_dir, tmp_path):
    """Sessions saved before quality_warning was added should still load."""
    sessions_dir.mkdir(parents=True, exist_ok=True)
    legacy = {
        "id": "legacy-id",
        "name": "old session",
        "topic": "something",
        "created_at": "2024-01-01T00:00:00",
        "directions": [],
        "search_results": [],
        "review": "old review",
        # no quality_warning key
    }
    (sessions_dir / "legacy-id.json").write_text(json.dumps(legacy))
    loaded = load_session("legacy-id")
    assert loaded.id == "legacy-id"
    assert loaded.quality_warning is None


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


def test_list_sessions_empty_when_no_dir(sessions_dir):
    # sessions_dir fixture sets the path but doesn't create it
    result = list_sessions()
    assert result == []


def test_list_sessions_returns_sessions(sessions_dir):
    s1 = make_session("topic 1", [], [], "r1", session_id="id-1")
    s2 = make_session("topic 2", [], [], "r2", session_id="id-2")
    sessions_dir.mkdir(parents=True, exist_ok=True)
    save_session(s1)
    time.sleep(0.01)  # ensure mtime differs
    save_session(s2)

    result = list_sessions()
    assert len(result) == 2
    # newest first
    assert result[0].id == "id-2"
    assert result[1].id == "id-1"


def test_list_sessions_skips_malformed_json(sessions_dir):
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "bad.json").write_text("not json {{{")
    s = make_session("good topic", [], [], "review", session_id="good-id")
    save_session(s)

    result = list_sessions()
    assert len(result) == 1
    assert result[0].id == "good-id"


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------


def test_delete_session_removes_file(sessions_dir):
    s = make_session("topic", [], [], "review", session_id="del-id")
    save_session(s)
    assert (sessions_dir / "del-id.json").exists()
    delete_session("del-id")
    assert not (sessions_dir / "del-id.json").exists()


def test_delete_session_nonexistent_does_not_raise(sessions_dir):
    sessions_dir.mkdir(parents=True, exist_ok=True)
    delete_session("nonexistent-id")  # should not raise
