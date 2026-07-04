# gh-pulse

GitHub 오픈소스 레포들의 지표(스타·포크·이슈 수)를 **매일 자동 수집**해서 쌓고,
FastAPI로 조회하는 미니 데이터 파이프라인.

```
GitHub API ──▶ collect.py ──▶ SQLite (data/data.db)
              (수집·정제)      + CSV (data/snapshots.csv)
                                      │
GitHub Actions (매일 06:00 KST) ──────┤  수집 결과를 레포에 자동 커밋
                                      ▼
                               api.py (FastAPI 조회 API)
```

## 특징

- **멱등한 적재** — `(repo, snapshot_date)` 기본키에 upsert. 같은 날 몇 번을 다시 실행해도 중복이 생기지 않는다.
- **정제 단계 분리** — API 원본 JSON에서 필요한 필드만 추리고, 결측 숫자 필드는 0으로 보정 (`collect.normalize`, pandas).
- **서버 없는 스케줄링** — GitHub Actions cron이 매일 수집을 실행하고 결과 DB/CSV를 커밋한다. 커밋 이력이 곧 파이프라인 가동 기록.
- **키 발급 불필요** — Actions가 자동 주입하는 `GITHUB_TOKEN` 사용 (시간당 1,000회).

## 로컬 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python collect.py            # 1회 수집 (토큰 없이 시간당 60회 제한)
uvicorn api:app --reload     # 조회 API → http://localhost:8000/docs
pytest                       # 테스트
```

## API

| 엔드포인트 | 설명 |
|---|---|
| `GET /repos` | 레포별 최신 스냅샷 (스타 내림차순) |
| `GET /repos/{owner}/{name}/history?days=30` | 특정 레포의 일별 시계열 |
| `GET /trending?days=7` | 최근 N일 스타 증가량 순위 |

## 추적 대상 바꾸기

`repos.txt`에 `owner/name` 형식으로 한 줄에 하나씩. push하면 다음 수집부터 반영된다.

## 확장 아이디어

- 소스 추가: 릴리스·PR 수 등 다른 GitHub 엔드포인트, 또는 외부 API 결합
- SQLite → PostgreSQL, GitHub Actions → Airflow DAG로 승격
- 시계열 시각화 페이지 추가
