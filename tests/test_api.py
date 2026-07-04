"""조회 API 테스트. 임시 DB를 만들어 DB_PATH 환경변수로 주입한다."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import api
from collect import normalize, upsert
from db import get_conn, init_schema


def snapshot(full_name: str, stars: int):
    return {
        "full_name": full_name,
        "stargazers_count": stars,
        "forks_count": 1,
        "open_issues_count": 1,
        "subscribers_count": 1,
        "pushed_at": None,
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    monkeypatch.setenv("DB_PATH", str(db))
    conn = get_conn(db)
    init_schema(conn)
    # 이틀치 스냅샷 적재: a/x는 100 → 150, b/y는 10 → 10
    day1 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    day2 = datetime(2026, 7, 2, tzinfo=timezone.utc)
    upsert(normalize([snapshot("a/x", 100), snapshot("b/y", 10)], day1), conn)
    upsert(normalize([snapshot("a/x", 150), snapshot("b/y", 10)], day2), conn)
    conn.close()
    return TestClient(api.app)


def test_list_repos_returns_latest_snapshot_per_repo(client):
    body = client.get("/repos").json()
    assert len(body) == 2
    assert body[0]["repo"] == "a/x"          # 스타 내림차순
    assert body[0]["stars"] == 150            # 최신 날짜 값
    assert body[0]["snapshot_date"] == "2026-07-02"


def test_history_returns_rows_oldest_first(client):
    body = client.get("/repos/a/x/history?days=30").json()
    assert [r["snapshot_date"] for r in body] == ["2026-07-01", "2026-07-02"]
    assert [r["stars"] for r in body] == [100, 150]


def test_history_unknown_repo_returns_404(client):
    resp = client.get("/repos/no/such/history")
    assert resp.status_code == 404
