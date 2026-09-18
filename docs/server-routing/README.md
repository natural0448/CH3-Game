# 서버 라우팅 문서

이 색인은 현재 문서화된 서버·Spark 개발 파일과 1:1 짝 문서를 연결한다. 아직 문서화하지 않은 기존 파일을 현재 구조처럼 설명하지 않는다.

## Spark 집계

| 개발 파일 | 짝 문서 | 책임 |
| --- | --- | --- |
| `spark_jobs/summarize_ingest.py` | `files/spark_jobs/summarize_ingest.py.md` | 수집된 Parquet의 레코드·고유 사건 집계와 선택 UUID 증거 생성 |

## Django 관리 명령

| 개발 파일 | 짝 문서 | 책임 |
| --- | --- | --- |
| `server/analytics/management/commands/summarize_ingest.py` | `files/server/analytics/management/commands/summarize_ingest.py.md` | Spark 집계 제출 인자 조립과 프로세스 실행 |

