# `spark_jobs/summarize_ingest.py`

## 책임과 호출 위치

수집기가 저장한 `data/stream/game-actions-parquet` 전체를 배치로 읽어 작은 요약 JSON을 만든다. 선택한 사건 UUID가 있으면 그 사건의 수집 행만 제한해서 별도 증거 JSON으로 저장한다. 게임 상태, Kafka offset 또는 기존 `game-summary.json`은 변경하지 않는다.

호출 계층은 `server/analytics/management/commands/summarize_ingest.py`이며 `spark-submit`으로 이 파일의 `main()`을 실행한다.

## 상수와 입력 출처

- 입력 폴더: `--data-dir` 아래 `stream/game-actions-parquet`.
- 요약 출력: `--data-dir` 아래 `marts/stream-summary.json`.
- 선택 사건 출력: `--data-dir` 아래 `evidence/day15/event-<UUID>.json`.
- Spark 세션 이름: `village-ingest-summary`.
- Spark SQL 시간대: `UTC`.
- shuffle partition 수: `2`.
- JSON 파일 쓰기: 같은 폴더의 `game_ingest.write_json_atomic`에서 제공한다.

## 함수

### `small_groups(frame, column)` → `list[dict]`

- `frame`: 집계할 Spark DataFrame.
- `column`: groupBy에 사용할 열 이름.
- 허용 범위: 정렬 후 최대 1,000개 그룹. 1,001개가 수집되면 `ValueError`를 발생시킨다.

```text
frame을 column으로 groupBy하고 count
column 순서로 정렬하고 최대 1,001행 collect
1,000행 초과이면 오류
각 행을 {column: 값, count: 정수}로 변환해 반환
```

직접 호출하는 외부 코드는 Spark DataFrame의 `groupBy`, `count`, `orderBy`, `limit`, `collect`다.

### `main()` → `None`

파라미터는 없고 명령줄에서 다음 값을 읽는다.

- `--data-dir`: 필수 데이터 루트 경로.
- `--event-id`: 선택 UUID 문자열. 전달되면 `uuid.UUID`로 정규화하며 잘못된 값은 실패한다.

```text
인자를 파싱하고 Parquet 입력 폴더 존재 확인
SparkSession 생성
Parquet 전체를 cache
parse_status가 valid인 행에서 event_id 중복 제거
상태별 행 수, 고유 사건 수, 행동별·방별 수, 시간 범위 계산
stream-summary.json을 원자적으로 저장
event-id가 있으면 일치 행 수를 세고 최대 20행을 증거 JSON으로 저장
cache 해제 후 SparkSession 종료
```

직접 호출하는 외부 코드는 `SparkSession`, `pyspark.sql.functions`, `game_ingest.write_json_atomic`, `uuid.UUID`다.

## 주요 지역 변수

- `rows`: Parquet에서 읽은 모든 수집 행의 캐시된 DataFrame.
- `valid`: `parse_status == "valid"`인 행.
- `unique`: `valid`에서 `event_id`로 중복 제거한 DataFrame.
- `statuses`: `parse_status`별 수집 행 수 사전.
- `record_count`: 모든 상태 행 수의 합.
- `valid_count`: 정상 운반 행 수.
- `event_count`: 정상 행의 고유 `event_id` 수.
- `selected_id`: 정규화된 선택 UUID 또는 `None`.

