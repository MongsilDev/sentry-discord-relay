# sentry-discord-relay

Sentry 에러 알림을 Discord 채널로 전달하는 웹훅 서버입니다.\
Sentry 공식 Discord 통합은 Team 플랜 이상에서만 제공되므로, 무료 플랜에서도 쓸 수 있는 Internal Integration 웹훅을 받아 Discord로 보냅니다.

## 기능

- Sentry 이슈, 에러 알림을 Discord 채널에 실시간 전달
- issue 구독과 event_alert 규칙 두 가지 웹훅 형식 지원
- 새 이슈와 재발 알림을 Components V2 카드로 전달.\
  모든 카드에 레벨별 색 막대, 프로젝트와 제목, 레벨, 위치, 이슈 링크 버튼이 들어감.\
  issue 구독으로 받은 새 이슈 카드에는 이슈 번호와 우선순위가, event_alert 규칙 카드에는 환경과 release가 더 들어감.\
  모르는 형식은 embed로 전달
- Discord rate limit 응답을 받으면 `Retry-After`만큼, 최대 10초 기다린 뒤 한 번 재시도
- UptimeRobot의 Discord 연동 알림을 받아 중단과 복구를 Components V2 색 막대 카드로 바꿔 전달.\
  모르는 형식은 원문 그대로 전달
- `POST /notify/<토큰>`으로 받은 내부 작업 알림을 같은 카드 형식으로 전달.\
  본문 필드는 title, status, detail, url, key, route
- Sentry, UptimeRobot, 내부 알림을 채널별 웹훅으로 나눠 전달
- 바로 봐야 하는 알림만 푸시로 보냄.\
  warning 이하나 우선순위 낮음인 Sentry 이슈, 복구, 내부 알림 중 fail이 아닌 것은 푸시 없는 무음 메시지로 올림
- 해결되거나 복구되면 새 카드를 올리지 않고 처음 올린 카드를 고침.\
  Sentry 이슈가 해결되면 카드 둘째 줄 끝에 해결됨을 표시하고, UptimeRobot 복구는 중단 카드를 복구 카드로 바꿈.\
  내부 알림은 같은 key로 status ok가 오면 fail 카드를 고침
- `GET /health`로 상태 확인

## 동작 방식

Sentry Internal Integration이 `POST /sentry-hook`으로 보내는 이벤트를 받으면, 요청 원문을 client secret으로 HMAC-SHA256 계산해 `Sentry-Hook-Signature` 헤더와 상수 시간으로 비교하고, 다르면 401로 거부합니다.\
알림 대상인 `event_alert`, `issue`, `error`만 처리하고 나머지는 무시합니다.\
통과한 이벤트는 Components V2 카드로 만들어 채널의 Incoming Webhook으로 보내고, 카드로 만들 수 없는 형식만 embed로 보냅니다.

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env   # SENTRY_CLIENT_SECRET, DISCORD_WEBHOOK_URL 채우기
python3 app.py
```

기본으로 `127.0.0.1:8092`에 바인드합니다.\
네트워크 없이 카드와 embed 변환, 서명 검증을 확인하는 회귀 테스트는 `python3 test_relay.py`로 돌립니다.

## 설정

환경변수는 프로세스 환경이나 프로젝트 루트의 `.env` 파일에서 읽습니다.

| 키 | 설명 | 기본값 |
|---|---|---|
| `SENTRY_CLIENT_SECRET` | Sentry Internal Integration의 client secret.<br>서명 검증에 사용 | 없음 |
| `DISCORD_WEBHOOK_URL` | 알림을 보낼 Discord 채널의 Incoming Webhook URL.<br>아래 채널별 웹훅이 비어 있으면 이 주소로 보냄 | 없음 |
| `SENTRY_WEBHOOK_URL` | Sentry 알림을 보낼 웹훅 | `DISCORD_WEBHOOK_URL` |
| `UPTIME_WEBHOOK_URL` | UptimeRobot 알림을 보낼 웹훅 | `DISCORD_WEBHOOK_URL` |
| `OPS_WEBHOOK_URL` | 내부 작업 알림을 보낼 웹훅.<br>`/notify`에 route를 주지 않으면 여기로 보냄 | `DISCORD_WEBHOOK_URL` |
| `DATA_DIR` | 카드를 고치려고 보낸 메시지 ID를 저장하는 폴더 | `data` |
| `PORT` | 수신 포트 | `8092` |
| `HOST` | 바인드 주소 | `127.0.0.1` |
| `SENTRY_DSN` | 설정하면 중계기 자체 오류를 Sentry로 전송 | 없음 |
| `UPTIMEROBOT_RELAY_TOKEN` | `POST /uptimerobot/<토큰>` 경로 토큰.<br>비어 있으면 이 경로는 404 | 없음 |
| `RELAY_NOTIFY_TOKEN` | `POST /notify/<토큰>` 경로 토큰.<br>비어 있으면 이 경로는 404 | 없음 |
