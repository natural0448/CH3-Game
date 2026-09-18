# `server/analytics/management/commands/summarize_ingest.py`

## 책임과 호출 위치

Django CLI에서 수집 요약 옵션을 받고 기존 Spark 클러스터에 `spark_jobs/summarize_ingest.py`를 제출한다. 이 계층은 집계 계산이나 JSON 생성을 수행하지 않는다.

사용자는 `server` 폴더에서 `python manage.py summarize_ingest ...`로 호출한다.

## 클래스와 메서드

### `Command.add_arguments(parser)` → `None`

- `parser`: Django가 전달하는 명령행 parser.

등록 옵션:

- `--data-dir`: 기본값 `settings.DATA_DIR`.
- `--cores`: 정수 `1` 또는 `2`, 기본값 `2`.
- `--event-id`: 선택 UUID 문자열.

```text
data-dir, cores, event-id 옵션을 Django parser에 등록
```

직접 호출하는 외부 코드는 Django argument parser다.

### `Command.handle(*args, **options)` → `None`

- `args`: Django 관리 명령의 위치 인자. 현재 사용하지 않는다.
- `options`: `add_arguments`가 등록한 값과 Django 공통 옵션.

```text
SPARK_MASTER가 standalone spark 주소인지 확인
PROJECT_DIR/spark_jobs/summarize_ingest.py 존재 확인
spark-submit 실행 파일, 클러스터 옵션, Python 실행 경로, 작업 인자를 list로 조립
event-id가 있으면 UUID로 검증하고 정규화
현재 Python을 driver와 worker Python 환경으로 지정
BASE_DIR에서 subprocess.run(check=True) 실행
Spark 실패 코드를 Django CommandError로 변환
```

직접 호출하는 외부 코드는 `settings`, `uuid.UUID`, `pathlib.Path`, `subprocess.run`이다. Spark 작업이 성공하면 `spark_jobs/summarize_ingest.py`가 요약과 선택 사건 증거 파일을 생성한다.

## 주요 변수와 값 출처

- `script`: `settings.PROJECT_DIR / "spark_jobs" / "summarize_ingest.py"`.
- `command`: `settings.SPARK_SUBMIT`, `settings.SPARK_MASTER`, 선택한 core 수와 데이터 경로에서 조립한 인자 목록.
- `selected_id`: `UUID(options["event_id"])`로 검증·정규화한 문자열.
- `env`: 현재 프로세스 환경의 복사본에 `PYSPARK_PYTHON`과 `PYSPARK_DRIVER_PYTHON`을 `sys.executable`로 설정한 값.

