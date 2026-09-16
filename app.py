#!/usr/bin/env python3
"""Sentry → Discord 실시간 알림 중계기.

Sentry Internal Integration이 이벤트 발생 시 POST하는 webhook을 받아,
서명을 검증하고 Discord embed로 변환해 Discord Incoming Webhook으로 보낸다.

노출된 엔드포인트이므로 HMAC 서명 검증이 유일하자 핵심 방어다. 시크릿을 모르면
유효한 요청을 위조할 수 없다.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os

from flask import Flask, request

from discord_client import send_embed
from discord_embed import build_embed


def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

SENTRY_CLIENT_SECRET = os.environ.get("SENTRY_CLIENT_SECRET", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", "8092"))
# 127.0.0.1만 바인드 — Cloudflare Tunnel만 도달, LAN 직접 접근 차단
HOST = os.environ.get("HOST", "127.0.0.1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("relay")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    """Sentry-Hook-Signature = HMAC-SHA256(client_secret, raw_body). 상수시간 비교."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/sentry-hook")
def sentry_hook():
    raw = request.get_data()
    signature = request.headers.get("Sentry-Hook-Signature")
    if not verify_signature(SENTRY_CLIENT_SECRET, raw, signature):
        log.warning("서명 검증 실패 — 거부 (from %s)", request.remote_addr)
        return {"error": "invalid signature"}, 401

    resource = request.headers.get("Sentry-Hook-Resource", "")
    # 알림 대상만 처리. 설치/삭제 등 다른 리소스는 200으로 무시.
    if resource not in ("event_alert", "issue", "error"):
        log.info("무시 리소스: %s", resource)
        return {"status": "ignored"}, 200

    try:
        payload = request.get_json(force=True, silent=False)
    except Exception as e:
        log.error("본문 파싱 실패: %s", e)
        return {"error": "bad payload"}, 400

    if not isinstance(payload, dict):
        return {"error": "bad payload"}, 400

    try:
        embed = build_embed(payload)
    except Exception as e:
        log.exception("embed 변환 실패: %s", e)
        return {"error": "build failed"}, 400

    ok = send_embed(DISCORD_WEBHOOK_URL, embed)
    if ok:
        log.info("Discord 전송 완료: %s", embed.get("title", "")[:60])
        return {"status": "sent"}, 200
    log.error("Discord 전송 실패: %s", embed.get("title", "")[:60])
    return {"status": "discord failed"}, 502


@app.get("/health")
def health():
    return {"status": "ok", "configured": bool(SENTRY_CLIENT_SECRET and DISCORD_WEBHOOK_URL)}, 200


if __name__ == "__main__":
    missing = [k for k, v in (("SENTRY_CLIENT_SECRET", SENTRY_CLIENT_SECRET),
                              ("DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK_URL)) if not v]
    if missing:
        log.warning("미설정 환경변수: %s (검증/전송이 동작하지 않음)", ", ".join(missing))
    log.info("중계기 시작 — %s:%d", HOST, PORT)
    app.run(host=HOST, port=PORT)
