"""SQLite 연결과 스키마 관리."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS repo_snapshots (
    repo          TEXT NOT NULL,            -- owner/name
    snapshot_date TEXT NOT NULL,            -- YYYY-MM-DD (UTC)
    stars         INTEGER NOT NULL,
    forks         INTEGER NOT NULL,
    open_issues   INTEGER NOT NULL,
    subscribers   INTEGER NOT NULL,
    pushed_at     TEXT,
    collected_at  TEXT NOT NULL,
    PRIMARY KEY (repo, snapshot_date)
);
"""


def db_path() -> Path:
    """DB 경로. 테스트나 배포 환경에서는 DB_PATH 환경변수로 바꿀 수 있다."""
    return Path(os.environ.get("DB_PATH", DEFAULT_DB_PATH))


def get_conn(path: Path | None = None) -> sqlite3.Connection:
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
