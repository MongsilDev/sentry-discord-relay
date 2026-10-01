# sentry-discord-relay

Sentry 에러 알림을 Discord 채널로 중계하는 webhook 서버. Sentry 공식 Discord 통합은 Team 플랜 이상에서만 제공되므로, 무료 플랜에서 쓸 수 있는 Internal Integration webhook을 받아 Discord로 넘긴다.

## 기능

- Sentry 이슈, 에러 알림을 Discord 채널에 실시간 전달
- issue 구독과 event_alert 규칙 두 가지 webhook payload 형식 지원
- 새 이슈와 재발 알림을 Components V2 카드로 전달. 레벨별 색 막대, 프로젝트와 제목, 위치와 환경, release, 이슈 링크 버튼. 모르는 형식은 embed로 전달
- Discord rate limit 응답을 받으면 `Retry-After`만큼, 최대 10초 대기 후 한 번 재시도
- UptimeRobot Discord 연동 알림을 받아 중단과 복구를 색 막대 카드(Components V2)로 바꿔 전달. 모르는 형식은 원문 그대로 전달
- `POST /notify/<토큰>`으로 내부 작업 알림(title, status, detail, url)을 같은 카드 형식으로 전달
- `GET /health`로 상태 확인

## 동작 방식

Sentry Internal Integration이 `POST /sentry-hook`으로 보내는 이벤트를 받아, 요청 원문을 client secret으로 HMAC-SHA256 계산해 `Sentry-Hook-Signature` 헤더와 상수시간 비교하고 불일치하면 401로 거부한다. 알림성 리소스인 `event_alert`, `issue`, `error`만 처리하고 나머지는 무시한다. 통과한 이벤트는 Discord embed로 변환해 채널의 Incoming Webhook으로 전송한다.

## 실행

```bash
pip install -r requirements.txt

cp .env.example .env   # SENTRY_CLIENT_SECRET, DISCORD_WEBHOOK_URL 채우기

python3 app.py
```

기본으로 `127.0.0.1:8092`에 바인드한다. 네트워크 없이 embed 변환과 서명 검증을 확인하는 회귀 테스트는 `python3 test_relay.py`로 돌린다.

## 설정

환경변수는 프로세스 환경 또는 프로젝트 루트의 `.env` 파일에서 읽는다.

| 키 | 설명 | 기본값 |
|---|---|---|
| `SENTRY_CLIENT_SECRET` | Sentry Internal Integration의 client secret. 서명 검증에 사용 | 없음 |
| `DISCORD_WEBHOOK_URL` | 알림을 보낼 Discord 채널의 Incoming Webhook URL | 없음 |
| `PORT` | 수신 포트 | `8092` |
| `HOST` | 바인드 주소 | `127.0.0.1` |
| `SENTRY_DSN` | 설정하면 중계기 자체 오류를 Sentry로 전송 | 없음 |
| `UPTIMEROBOT_RELAY_TOKEN` | `POST /uptimerobot/<토큰>` 경로 토큰. 비어 있으면 이 경로는 404 | 없음 |
| `RELAY_NOTIFY_TOKEN` | `POST /notify/<토큰>` 경로 토큰. 비어 있으면 이 경로는 404 | 없음 |
