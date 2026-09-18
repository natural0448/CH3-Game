# Pylance PySpark 경로 설정 인수인계

작성일: 2026-09-18

## 원인

`spark_jobs/game_ingest.py`는 `spark-submit`이 실행할 때 Spark 배포본의 Python 경로를 받는다. VS Code Pylance는 선택된 `server/.venv`에서만 모듈을 검색했고 이 환경에는 별도 `pyspark` wheel이 없어서 `reportMissingImports`를 표시했다.

## 변경

`.vscode/settings.json`에 다음 경로를 지정했다.

- 기본 interpreter: `server/.venv/Scripts/python.exe`
- PySpark source: `../Oder-insight/Spark-exam/spark-4.1.3-bin-hadoop3-1/python`
- Py4J source archive: 같은 Spark 배포본의 `python/lib/py4j-0.10.9.9-src.zip`

PySpark를 중복 설치하지 않았고 `game_ingest.py`, Spark 설정과 실행 중인 서비스는 변경하지 않았다.

## Git 확인

작업 전 HEAD는 `273fbd2 data commit`이다. 기존 untracked 파일 `server/analytics/management/commands/capture_ingest_environment.py`, `spark_jobs/game_ingest.py`, `tools/check_action_handoff.py`는 사용자 작업으로 보존했다. 이번 작업은 `.vscode/settings.json`과 이 문서만 추가했다.
