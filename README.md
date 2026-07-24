# sentry-discord-relay

Sentry 에러 알림을 Discord 채널로 중계하는 webhook 서버. Sentry 공식 Discord 통합은 Team 플랜 이상에서만 제공되므로, 무료 플랜에서 쓸 수 있는 Internal Integration webhook을 받아 Discord로 넘긴다.

## 기능

- Sentry 이슈, 에러 알림을 Discord 채널에 실시간 전달
- issue 구독과 event_alert 규칙 두 가지 webhook payload 형식 지원
- 레벨별 색상, 이슈 링크, 태그 필드를 담은 embed 변환. 색상 값은 Sentry 공식 Discord 통합에서 그대로 이식
- Discord rate limit 응답을 받으면 `Retry-After`만큼, 최대 10초 대기 후 한 번 재시도
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
