# sentry-discord-relay

Sentry 이벤트를 **실시간으로 Discord 채널에 알림**으로 중계한다.

무료 플랜에서는 Sentry 공식 Discord 통합(Team plan 필요)을 못 쓴다. 대신 Sentry
**Internal Integration webhook**을 받아 Discord Incoming Webhook으로 변환해 보낸다.

```
봇 에러 → Sentry → Alert(Internal Integration webhook) → [이 중계기] → Discord 채널
```

## 동작
- `POST /sentry-hook` — Sentry webhook 수신. `Sentry-Hook-Signature`(HMAC-SHA256)를
  client secret으로 검증하고, 통과하면 Discord embed로 변환해 전송한다. 서명이 없거나
  틀리면 401.
- `GET /health` — 헬스체크.

embed 모양은 Sentry 공식 Discord 통합
(`src/sentry/integrations/discord/message_builder/issues.py`)을 본떴다. 색상 값도
공식 그대로. 버튼(Resolve/Archive)만 제외했다(Discord Bot API가 필요해 Incoming
Webhook으로는 불가). 대신 embed 제목이 Sentry 이슈로 링크된다.

## 보안
- `127.0.0.1`만 바인드 → Cloudflare Tunnel만 도달
- HMAC 서명 검증이 핵심 방어 — 시크릿 모르면 위조 불가
- 받아서 Discord로 전달만. 파일시스템·DB·타 서비스 접근 없음

## 설정
`.env.example` 참고. 필수: `SENTRY_CLIENT_SECRET`, `DISCORD_WEBHOOK_URL`.

## 실행 / 테스트
- 실행: `python3 app.py`
- 테스트: `python3 test_relay.py` (네트워크 불필요)

## 배포
NAS python 컨테이너 PMC 프로세스. `sentry-relay.mongsil.dev`(Cloudflare Tunnel) →
`127.0.0.1:8092`. 설계 상세는 `docs/superpowers/specs/`.
