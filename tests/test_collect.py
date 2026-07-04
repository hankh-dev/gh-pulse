"""정제(normalize)와 적재(upsert) 로직 테스트."""

from datetime import datetime, timezone

from collect import normalize, upsert
from db import get_conn, init_schema

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)

SAMPLE = [
    {
        "full_name": "a/x",
        "stargazers_count": 10,
        "forks_count": 2,
        "open_issues_count": 1,
        "subscribers_count": 5,
        "pushed_at": "2026-07-01T00:00:00Z",
    },
    {
        # 숫자 필드 일부가 결측인 경우
        "full_name": "b/y",
        "stargazers_count": None,
        "forks_count": 3,
        "open_issues_count": 0,
        "subscribers_count": None,
        "pushed_at": None,
    },
    {
        # full_name이 없으면 식별 불가 → 버려져야 한다
        "stargazers_count": 99,
    },
]


def make_conn(tmp_path):
    conn = get_conn(tmp_path / "test.db")
    init_schema(conn)
    return conn


def test_normalize_drops_rows_without_repo():
    df = normalize(SAMPLE, NOW)
    assert list(df["repo"]) == ["a/x", "b/y"]


def test_normalize_fills_missing_counts_with_zero():
    df = normalize(SAMPLE, NOW)
    row = df[df["repo"] == "b/y"].iloc[0]
    assert row["stars"] == 0
    assert row["subscribers"] == 0


def test_normalize_sets_snapshot_date_from_collected_at():
    df = normalize(SAMPLE, NOW)
    assert set(df["snapshot_date"]) == {"2026-07-04"}


def test_upsert_is_idempotent(tmp_path):
    conn = make_conn(tmp_path)
    df = normalize(SAMPLE, NOW)
    upsert(df, conn)
    upsert(df, conn)  # 같은 날짜로 두 번 실행
    count = conn.execute("SELECT COUNT(*) FROM repo_snapshots").fetchone()[0]
    assert count == 2


def test_upsert_updates_same_day_snapshot(tmp_path):
    conn = make_conn(tmp_path)
    upsert(normalize(SAMPLE, NOW), conn)
    changed = [dict(SAMPLE[0], stargazers_count=42)]
    upsert(normalize(changed, NOW), conn)
    stars = conn.execute(
        "SELECT stars FROM repo_snapshots WHERE repo = 'a/x'"
    ).fetchone()[0]
    assert stars == 42
