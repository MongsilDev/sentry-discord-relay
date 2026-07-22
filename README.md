# sentry-discord-relay

Sentry 에러를 실시간으로 Discord 채널에 알리는 webhook 중계기. Sentry Internal Integration 이벤트를 받아 서명을 검증하고 Discord embed로 변환해 전달한다.

## 배경

Sentry 공식 Discord 통합은 Team 플랜 이상에서만 열린다. 무료 플랜에서 실시간 알림을 얻는 유일한 경로가 Internal Integration webhook이고, 이 중계기가 그 webhook을 Discord로 넘긴다.

## 동작 방식

1. `POST /sentry-hook`으로 이벤트 수신
2. 원문을 client secret으로 HMAC-SHA256 계산해 `Sentry-Hook-Signature`와 상수시간 비교, 불일치 시 401
3. 알림성 리소스(event_alert/issue/error)만 통과
4. Sentry JSON을 Discord embed로 변환(공식 통합의 색상·구조 이식)
5. Discord Incoming Webhook으로 전달, 429 시 1회 재시도

## 기술 스택

Python 3.12, Flask(수신만). 서명 검증·전송은 표준 라이브러리. `127.0.0.1` 바인딩 + Cloudflare Tunnel(sentry-relay.mongsil.dev)로만 접근, 오리진 IP 비노출.

## 보안·제약

HMAC 서명 검증이 핵심 방어. 시크릿(`SENTRY_CLIENT_SECRET`, `DISCORD_WEBHOOK_URL`)은 `.env`로 주입한다. Incoming Webhook만 쓰므로 Resolve/Archive 같은 상호작용 버튼은 미지원(이슈 링크로 대체).
