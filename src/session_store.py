import json
import uuid
from dataclasses import asdict, dataclass
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


def make_session(topic: str, directions: list, search_results: list, review: str) -> Session:
    name = topic[:50].strip() + ("..." if len(topic) > 50 else "")
    return Session(
        id=str(uuid.uuid4()),
        name=name,
        topic=topic,
        created_at=datetime.now().isoformat(),
        directions=directions,
        search_results=list(search_results),
        review=review,
    )


def save_session(session: Session) -> None:
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


def delete_session(session_id: str) -> None:
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
