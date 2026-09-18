# `summarize_ingest` 관리 명령 추가 인수인계

## 요청 목적과 완료 결과

15일차 5교시의 `python manage.py summarize_ingest`가 `Unknown command`로 실패한 원인을 확인했다. 기존 사용자 작성 Spark 작업 `spark_jobs/summarize_ingest.py`는 보존하고, 이를 기존 Spark 클러스터에 제출하는 Django 관리 명령을 `analytics` 앱에 추가했다.

실제 UUID `e12980a0-0161-41ae-8478-f255cb666f6a`로 배치를 실행했다. 결과는 수집 행 876개, 고유 사건 876개, 선택 사건 일치 행 1개이며 Spark 애플리케이션 `app-20260918152833-0006`은 `FINISHED`로 종료됐다. 실행 후 활성 Spark 애플리케이션은 없다.

## 작업 시작 전 Git 상태

- 저장소: `C:/MLO01-01/Chapter3/Game-server`, Git 저장소 확인.
- 직전 커밋: `273fbd2 data commit`.
- staged·unstaged tracked 변경: 없음.
- 작업 시작 전에 존재한 untracked 항목:
  - `.vscode/`
  - `docs/`
  - `server/analytics/ingest_views.py`
  - `server/analytics/management/commands/capture_ingest_environment.py`
  - `server/game/management/commands/run_game_ingest.py`
  - `spark_jobs/game_ingest.py`
  - `spark_jobs/summarize_ingest.py`
  - `tools/check_action_handoff.py`
- 위 기존 항목 중 `spark_jobs/summarize_ingest.py`는 사용자 작업으로 읽고 수정하지 않았다. 기존 `.vscode`, 기존 인수인계 문서와 다른 untracked 파일도 변경하지 않았다.

## 이번 작업 파일

추가:

- `server/analytics/management/commands/summarize_ingest.py`
- `docs/server-routing/README.md`
- `docs/server-routing/files/spark_jobs/summarize_ingest.py.md`
- `docs/server-routing/files/server/analytics/management/commands/summarize_ingest.py.md`
- `docs/handoffs/2026-09-18-summarize-ingest-command.md`

이동·삭제: 없음.

실행 산출물:

- `data/marts/stream-summary.json` 갱신
- `data/evidence/day15/event-e12980a0-0161-41ae-8478-f255cb666f6a.json` 생성 또는 갱신

데이터 경로는 현재 Git 상태에 나타나지 않으며, 코드 변경으로 주장하지 않는다.

## 설계와 책임 경계

- Django 관리 명령은 옵션 검증과 `spark-submit` 인자 조립만 담당한다.
- 집계 계산과 JSON 생성은 기존 `spark_jobs/summarize_ingest.py`가 담당한다.
- `--event-id`는 제출 전에 `uuid.UUID`로 검증하고 정규화한다.
- 작업 파일 존재와 `spark://` Master 주소를 제출 전에 확인한다.
- Spark 비정상 종료 코드는 Django `CommandError`로 변환한다.
- 배치는 Kafka에 접속하지 않고 기존 Parquet만 읽는다. 게임 상태와 기존 `game-summary.json`을 변경하지 않는다.

## 라우팅 문서

- `docs/server-routing/README.md`에 Spark 집계와 Django 관리 명령의 1:1 짝을 등록했다.
- `spark_jobs/summarize_ingest.py` 문서는 작업 시작 시점의 사용자 구현을 먼저 반영했다.
- 관리 명령 문서는 최종 시그니처, 옵션, 의사코드, 직접 호출 외부 코드와 변수 출처를 반영했다.

## 검사 결과

- `python -m py_compile analytics/management/commands/summarize_ingest.py ../spark_jobs/summarize_ingest.py`: 통과.
- `python manage.py check`: 통과.
- `python manage.py help summarize_ingest`: 명령과 옵션 표시 확인.
- `python manage.py summarize_ingest --event-id not-a-uuid`: 예상한 `CommandError` 확인.
- 실제 Spark 배치: 종료 코드 0, `records=876 events=876`, `selected_event_matches=1`.
- 생성 JSON 검산: 상태별 합, 행동별 합, 방별 합, 중복 수 공식, `event_count <= valid_record_count` 모두 통과.
- `python manage.py test analytics`: 1개 테스트 통과.
- Spark Master: 최신 애플리케이션 `app-20260918152833-0006` 상태 `FINISHED`, 활성 앱 0개.

Spark 종료 시 executor 연결에서 `Connection reset` 경고가 출력됐지만 SparkContext가 `exitCode 0`으로 정상 종료됐고 결과 파일 검산도 통과했다.

## 후속 확인 순서

`server` 폴더와 프로젝트 가상환경에서 다음 명령으로 다시 실행할 수 있다.

```powershell
cd C:\MLO01-01\Chapter3\Game-server\server
.\.venv\Scripts\Activate.ps1
python manage.py summarize_ingest --cores 2 --event-id "e12980a0-0161-41ae-8478-f255cb666f6a"
```

작은 결과는 `data/marts/stream-summary.json`, 선택 사건 증거는 `data/evidence/day15/event-e12980a0-0161-41ae-8478-f255cb666f6a.json`에서 확인한다.

