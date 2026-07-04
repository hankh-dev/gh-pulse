"""GitHub 레포 스냅샷 수집기.

repos.txt에 나열된 레포들의 지표(스타, 포크, 이슈 수 등)를 GitHub API에서
가져와 정제한 뒤, SQLite에 레포당 하루 1행으로 적재한다.
같은 날 다시 실행해도 중복 없이 그날 행이 갱신된다(멱등).
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from db import DATA_DIR, get_conn, init_schema

API_BASE = "https://api.github.com/repos/"
REPOS_FILE = Path(__file__).parent / "repos.txt"
CSV_PATH = DATA_DIR / "snapshots.csv"

UPSERT_SQL = """
INSERT INTO repo_snapshots
    (repo, snapshot_date, stars, forks, open_issues, subscribers, pushed_at, collected_at)
VALUES
    (:repo, :snapshot_date, :stars, :forks, :open_issues, :subscribers, :pushed_at, :collected_at)
ON CONFLICT(repo, snapshot_date) DO UPDATE SET
    stars        = excluded.stars,
    forks        = excluded.forks,
    open_issues  = excluded.open_issues,
    subscribers  = excluded.subscribers,
    pushed_at    = excluded.pushed_at,
    collected_at = excluded.collected_at
"""


def load_repo_list(path: Path = REPOS_FILE) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    # 로컬에서는 토큰 없이 시간당 60회, GitHub Actions에서는 GITHUB_TOKEN이
    # 자동 주입되어 시간당 1,000회까지 허용된다.
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    return session


def fetch_repo(session: requests.Session, repo: str) -> dict | None:
    resp = session.get(API_BASE + repo, timeout=10)
    if resp.status_code == 404:
        print(f"[warn] {repo}: 존재하지 않는 레포, 건너뜀", file=sys.stderr)
        return None
    resp.raise_for_status()
    return resp.json()


def normalize(raw_rows: list[dict], collected_at: datetime) -> pd.DataFrame:
    """API 원본 JSON 목록에서 필요한 필드만 추려 적재용 DataFrame으로 만든다.

    - full_name이 없는 행은 식별 불가이므로 버린다.
    - 숫자 필드의 결측/비정상 값은 0으로 채운다.
    """
    df = pd.DataFrame(
        {
            "repo": [r.get("full_name") for r in raw_rows],
            "stars": [r.get("stargazers_count") for r in raw_rows],
            "forks": [r.get("forks_count") for r in raw_rows],
            "open_issues": [r.get("open_issues_count") for r in raw_rows],
            "subscribers": [r.get("subscribers_count") for r in raw_rows],
            "pushed_at": [r.get("pushed_at") for r in raw_rows],
        }
    )
    df = df.dropna(subset=["repo"])
    for col in ("stars", "forks", "open_issues", "subscribers"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["pushed_at"] = df["pushed_at"].astype("string").where(df["pushed_at"].notna(), None)
    df["snapshot_date"] = collected_at.date().isoformat()
    df["collected_at"] = collected_at.isoformat(timespec="seconds")
    return df


def upsert(df: pd.DataFrame, conn: sqlite3.Connection) -> int:
    conn.executemany(UPSERT_SQL, df.to_dict("records"))
    conn.commit()
    return len(df)


def export_csv(conn: sqlite3.Connection, path: Path = CSV_PATH) -> None:
    """git에서 diff로 변화를 볼 수 있도록 전체 스냅샷을 CSV로도 남긴다."""
    df = pd.read_sql_query(
        "SELECT * FROM repo_snapshots ORDER BY snapshot_date, repo", conn
    )
    df.to_csv(path, index=False)


def main() -> int:
    repos = load_repo_list()
    session = make_session()

    raw = [data for repo in repos if (data := fetch_repo(session, repo)) is not None]
    if not raw:
        print("수집된 데이터가 없습니다", file=sys.stderr)
        return 1

    df = normalize(raw, datetime.now(timezone.utc))
    conn = get_conn()
    try:
        init_schema(conn)
        count = upsert(df, conn)
        export_csv(conn)
    finally:
        conn.close()

    print(f"{count}개 레포 스냅샷 적재 완료 (snapshot_date={df['snapshot_date'].iloc[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
