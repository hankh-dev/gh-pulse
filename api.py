"""수집된 레포 스냅샷 조회 API.

실행: uvicorn api:app --reload
문서: http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from db import get_conn

app = FastAPI(
    title="gh-pulse",
    description="GitHub 레포 지표를 매일 수집하는 파이프라인의 조회 API",
)


@app.get("/repos")
def list_repos() -> list[dict]:
    """레포별 가장 최근 스냅샷 (스타 수 내림차순)."""
    sql = """
    SELECT s.*
    FROM repo_snapshots s
    JOIN (
        SELECT repo, MAX(snapshot_date) AS latest
        FROM repo_snapshots GROUP BY repo
    ) m ON s.repo = m.repo AND s.snapshot_date = m.latest
    ORDER BY s.stars DESC
    """
    conn = get_conn()
    try:
        return [dict(row) for row in conn.execute(sql)]
    finally:
        conn.close()


@app.get("/repos/{owner}/{name}/history")
def repo_history(
    owner: str,
    name: str,
    days: int = Query(30, ge=1, le=365, description="최근 N일"),
) -> list[dict]:
    """특정 레포의 일별 지표 시계열 (오래된 날짜부터)."""
    sql = """
    SELECT snapshot_date, stars, forks, open_issues, subscribers
    FROM repo_snapshots
    WHERE repo = ?
    ORDER BY snapshot_date DESC
    LIMIT ?
    """
    conn = get_conn()
    try:
        rows = [dict(row) for row in conn.execute(sql, (f"{owner}/{name}", days))]
    finally:
        conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"{owner}/{name}의 스냅샷이 없습니다")
    return list(reversed(rows))


@app.get("/trending")
def trending(days: int = Query(7, ge=1, le=90, description="최근 N일")) -> list[dict]:
    """최근 N일 동안 스타가 많이 늘어난 순위."""
    sql = """
    WITH bounds AS (
        SELECT repo,
               MIN(snapshot_date) AS first_date,
               MAX(snapshot_date) AS last_date
        FROM repo_snapshots
        WHERE snapshot_date >= date('now', ?)
        GROUP BY repo
    )
    SELECT b.repo,
           b.first_date,
           b.last_date,
           last.stars                AS stars,
           last.stars - first.stars  AS star_growth
    FROM bounds b
    JOIN repo_snapshots first
        ON first.repo = b.repo AND first.snapshot_date = b.first_date
    JOIN repo_snapshots last
        ON last.repo = b.repo AND last.snapshot_date = b.last_date
    ORDER BY star_growth DESC
    """
    conn = get_conn()
    try:
        return [dict(row) for row in conn.execute(sql, (f"-{days} day",))]
    finally:
        conn.close()
