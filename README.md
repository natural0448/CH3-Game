# 10일차 전체 · 11일차 4교시까지

2026-09-15 첨부 교안과 현재 파일을 비교해 보완했습니다. 경로는 사용자의 구조를 유지합니다.

```text
Chapter3/
  Game-client/           # Python 3.12 + pygame-ce + aiohttp, 자체 .venv
    main.py, network.py, state.py, render.py, config.json
    requirements.txt
    assets/              # Kenney PNG 5개, 원본 ZIP, 공개 한글 폰트, 라이선스
  Game-server/
    config/              # 프로젝트 설정 (server 밖에 유지)
    server/              # manage.py, .venv, .env, game, analytics
    infra/kafka/         # 3개 노드 설정
    infra/runtime/       # Kafka 4.1.2 배포판과 검증한 원본 압축파일, Git 제외
    tools/kafka.ps1      # 초기화/노드 실행/상태/Topic/그룹 조회
    data/kafka/          # 영속 Kafka 데이터, Git 제외
    data/samples/        # 실제 GameEvent 샘플
    data/notes/          # 비교/전달 관찰/화면 확인 결과
```

## 실행

MySQL은 기존 환경을 사용합니다. Kafka 저장소 초기화와 Topic 생성은 이미 완료했습니다.
매번 format하거나 데이터 폴더를 지우지 않습니다. Java 17.0.20.1은 현재 설치되어 있습니다.

먼저 **서로 다른 터미널 세 개**에서 아래 명령을 각각 실행합니다. 각 터미널 위치는 `C:\MLO01-01\Chapter3\Game-server`입니다.

```powershell
.\tools\kafka.ps1 -Action start -Node 1
```

```powershell
.\tools\kafka.ps1 -Action start -Node 2
```

```powershell
.\tools\kafka.ps1 -Action start -Node 3
```

네 번째 터미널에서 같은 Game-server 위치를 사용합니다.

```powershell
.\tools\kafka.ps1 -Action status
.\tools\kafka.ps1 -Action describe-topic
.\server\.venv\Scripts\python.exe .\server\manage.py runserver --noreload 127.0.0.1:8000
```

접속기는 별도 터미널에서 실행합니다.

```powershell
cd C:\MLO01-01\Chapter3\Game-client
.\.venv\Scripts\python.exe main.py
```

JSON 인증 API가 추가되어 이제 기존 학습 계정으로 서버에 로그인할 수 있습니다. 계정 비밀번호는 이 문서나 로그에 기록하지 않습니다. 기존 로컬 계정 안내 파일은 `server/.env.classroom`이며 Git에서 제외됩니다.

publisher는 **한 프로세스만** 별도 터미널에서 실행합니다. Game-server 위치 기준:

```powershell
.\server\.venv\Scripts\python.exe .\server\manage.py publish_game_events
```

관찰 터미널에서 같은 위치를 사용합니다.

```powershell
.\server\.venv\Scripts\python.exe .\server\manage.py watch_game_events --limit 10
.\tools\kafka.ps1 -Action group
```

첫 poll에서 그룹 할당을 기다려 `observed=0`이면 같은 명령을 다시 실행합니다. 같은 그룹은 commit된 다음 위치부터 읽습니다. 기존 기록을 별도 관찰하려면 `--group village-inspect-v1`을 사용합니다. 그룹 offset을 reset하지 않습니다.

한 묶음만 발행하려면 `publish_game_events --once --batch-size 50`을 사용합니다. 전체 미발행 건수가 50보다 많으면 여러 번 필요합니다. Kafka가 꺼져 있어도 게임의 이동/채집 DB 처리는 독립적이며 이벤트는 미발행으로 남습니다.

종료는 접속기에서 로그아웃 후 창 닫기, publisher와 Django 터미널에서 Ctrl+C, Kafka 각 터미널에서 Ctrl+C 순서로 합니다. 데이터와 Topic은 유지됩니다.

## 반영한 누락 사항

| 교안 범위 | 확인 당시 | 보완/검증 |
| --- | --- | --- |
| 10일차 1~2교시 | Python/DB/모델/계정 준비됨 | Django check와 migration 상태 확인 |
| 10일차 3교시 | HTML 로그인만 존재 | JSON CSRF·로그인·로그아웃 API 추가, 세션/CSRF 보호 유지 |
| 10일차 4~6교시 | 서비스·WS·Pygame 접속기 존재 | 로그인 응답 authenticated 값 검사, 서버 확정/중복 방지/WS 계약 검증 |
| 10일차 7교시 | 단색 그림만 존재 | CC0 잔디·길·나무·건물·캐릭터, Noto CJK 한글 폰트, 출처·라이선스 추가 |
| 10일차 8교시 | 직렬화/내보내기 없음 | serialize_event, export_event_sample 추가; 기존 이벤트 샘플 저장 |
| 11일차 1교시 | Kafka 미설치 | 공식 4.1.2 설치, SHA-512 검증, KRaft 3 voter 초기화 |
| 11일차 2교시 | Topic/연결 설정 없음 | game.events.v1: P3/RF3/min ISR2, 환경 설정과 .env.example 추가 |
| 11일차 3교시 | publisher 없음 | ack 후 published_at 표시, --once, 기본 batch-size 50 구현 |
| 11일차 4교시 | consumer 없음 | limit만큼 poll 후 출력/commit, room_id 포함, 두 관찰 그룹 확인 |

11일차 5교시 이후의 공동 마을 presence/snapshot 기능은 이번 범위에 포함하지 않았습니다. 접속기의 player_id 표시 사전은 유지합니다.

## 확인 결과

- `manage.py test game --noinput`: 20개 통과. 테스트 DB는 실행 후 삭제되었습니다.
- 실제 MySQL alice/bob 계정으로 JSON 인증·CSRF 회전·서로 다른 WS 초기 state·로그아웃을 인프로세스 HTTP/ASGI로 확인했습니다. 그 확인 동안 좌표·coins·version·이벤트 수는 유지했습니다.
- Pygame은 디스플레이 없이 실제 ASGI state를 렌더해 로컬 아트/한글/누락 에셋 fallback을 검증했습니다. 수동 창 조작 테스트와는 구분합니다.
- Kafka 3개 voter 정상, 모든 Topic 파티션의 ISR 3개, 기존 미발행 이벤트 1건 전달 성공. 같은 그룹 재실행은 observed=0, 별도 inspect 그룹은 observed=1, watch LAG는 0입니다.
- 재발행 명령은 published=0, 모델 변경/미적용 migration은 없습니다.

실제 관찰 값은 `data/notes/day11-delivery.md`, 화면은 `data/notes/day10-client.png`에 있습니다.

## 공식 출처

- [Apache Kafka 4.1.2 배포판](https://archive.apache.org/dist/kafka/4.1.2/), [KRaft 문서](https://kafka.apache.org/41/operations/kraft/)
- [Kenney Tiny Town](https://kenney.nl/assets/tiny-town), [Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon)
- [Noto CJK](https://github.com/notofonts/noto-cjk)

에셋별 원본 파일/치수/라이선스는 `../Game-client/assets/README.md`에 기록했습니다.
