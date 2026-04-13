import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path("sessions")


@dataclass
class Session:
    id: str
    name: str
    topic: str
    created_at: str
    directions: list
    search_results: list
    review: str
    quality_warning: str | None = field(default=None)


def make_session(
    topic: str,
    directions: list,
    search_results: list,
    review: str,
    session_id: str | None = None,
    quality_warning: str | None = None,
) -> Session:
    name = topic[:50].strip() + ("..." if len(topic) > 50 else "")
    return Session(
        id=session_id or str(uuid.uuid4()),
        name=name,
        topic=topic,
        created_at=datetime.now().isoformat(),
        directions=directions,
        search_results=list(search_results),
        review=review,
        quality_warning=quality_warning,
    )


def save_session(session: Session, pdf_path: str | None = None) -> None:
    # pdf_path param kept for signature compatibility but unused — PDF lives at sessions/{id}/review.pdf
    SESSIONS_DIR.mkdir(exist_ok=True)
    path = SESSIONS_DIR / f"{session.id}.json"
    path.write_text(json.dumps(asdict(session), indent=2, ensure_ascii=False))


def load_session(session_id: str) -> Session:
    path = SESSIONS_DIR / f"{session_id}.json"
    data = json.loads(path.read_text())
    return Session(**data)


def list_sessions() -> list:
    if not SESSIONS_DIR.exists():
        return []
    paths = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    sessions = []
    for path in paths:
        try:
            data = json.loads(path.read_text())
            sessions.append(Session(**data))
        except Exception:
            pass
    return sessions


def get_session_pdf_path(session_id: str) -> str | None:
    # Primary location: sessions/{id}/review.pdf (Code-Act working dir)
    new_path = SESSIONS_DIR / session_id / "review.pdf"
    if new_path.exists():
        return str(new_path)
    # Legacy fallback: sessions/{id}.pdf
    legacy_path = SESSIONS_DIR / f"{session_id}.pdf"
    return str(legacy_path) if legacy_path.exists() else None


def delete_session(session_id: str) -> None:
    # Remove JSON metadata
    json_path = SESSIONS_DIR / f"{session_id}.json"
    if json_path.exists():
        json_path.unlink()
    # Remove session working directory (LaTeX files, PDF, latexmk artifacts)
    session_dir = SESSIONS_DIR / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir)
    # Remove legacy PDF if present
    legacy_pdf = SESSIONS_DIR / f"{session_id}.pdf"
    if legacy_pdf.exists():
        legacy_pdf.unlink()
