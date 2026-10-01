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
import re

import sentry_sdk
from flask import Flask, request

from discord_client import send_embed, send_json
from discord_embed import build_embed
import uptime_card


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

_SECRET_PATH = re.compile(r"/uptimerobot/[^/\s\"?]+")


def _redact_path(text):
    return _SECRET_PATH.sub("/uptimerobot/***", text) if isinstance(text, str) else text


def _scrub_event(event, hint):
    req = event.get("request") or {}
    if req.get("url"):
        req["url"] = _redact_path(req["url"])
    for crumb in (event.get("breadcrumbs") or {}).get("values") or []:
        crumb["message"] = _redact_path(crumb.get("message"))
    return event


sentry_sdk.init(dsn=os.getenv("SENTRY_DSN", ""), traces_sample_rate=0.1,
                before_send=_scrub_event, before_send_transaction=_scrub_event)

SENTRY_CLIENT_SECRET = os.environ.get("SENTRY_CLIENT_SECRET", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
UPTIMEROBOT_RELAY_TOKEN = os.environ.get("UPTIMEROBOT_RELAY_TOKEN", "")
PORT = int(os.environ.get("PORT", "8092"))
# 127.0.0.1만 바인드 — Cloudflare Tunnel만 도달, LAN 직접 접근 차단
HOST = os.environ.get("HOST", "127.0.0.1")


class _PlainFormatter(logging.Formatter):
    # werkzeug 요청 로그의 ANSI 색 코드 제거
    _ansi = re.compile(r"\x1b\[[0-9;]*m")

    def format(self, record):
        return self._ansi.sub("", super().format(record))


class _SecretPathFilter(logging.Filter):
    # werkzeug 접근 로그의 요청 줄에 경로 토큰이 그대로 실림
    def filter(self, record):
        if record.args:
            record.args = tuple(_redact_path(a) for a in record.args)
        record.msg = _redact_path(record.msg)
        return True


logging.getLogger("werkzeug").addFilter(_SecretPathFilter())
_handler = logging.StreamHandler()
_handler.setFormatter(_PlainFormatter(
    "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger("sentry-discord-relay")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    """Sentry-Hook-Signature = HMAC-SHA256(client_secret, raw_body). 상수시간 비교."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def should_relay(resource: str, payload: dict) -> bool:
    """issue 구독은 새 이슈만 보낸다. 재발은 알림 규칙이 event_alert로 따로 보낸다."""
    return resource != "issue" or payload.get("action") == "created"


@app.post("/sentry-hook")
def sentry_hook():
    raw = request.get_data()
    signature = request.headers.get("Sentry-Hook-Signature")
    if not verify_signature(SENTRY_CLIENT_SECRET, raw, signature):
        client_ip = request.headers.get("CF-Connecting-IP") or request.remote_addr
        log.warning("서명 검증 실패 — 거부 (from %s)", client_ip)
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

    if not should_relay(resource, payload):
        issue = (payload.get("data") or {}).get("issue") or {}
        log.info("건너뜀: %s.%s substatus=%s %s", resource, payload.get("action"),
                 issue.get("substatus"), issue.get("shortId"))
        return {"status": "skipped"}, 200

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


@app.post("/uptimerobot/<token>")
def uptimerobot_hook(token: str):
    if not UPTIMEROBOT_RELAY_TOKEN or not hmac.compare_digest(token, UPTIMEROBOT_RELAY_TOKEN):
        return {"error": "not found"}, 404
    payload = request.get_json(force=True, silent=True)
    if not isinstance(payload, dict):
        log.warning("UptimeRobot 본문 파싱 실패")
        return {"error": "bad payload"}, 400

    card = uptime_card.parse(payload)
    if card is None:
        log.warning("UptimeRobot 형식을 몰라 원문 전달: 키 %s", sorted(payload))
        ok = send_json(DISCORD_WEBHOOK_URL, payload)
    else:
        ok = send_json(_with_components(DISCORD_WEBHOOK_URL), uptime_card.build_message(card))
        log.info("UptimeRobot 카드 전송 %s: %s (원문 %s)", "완료" if ok else "실패", card["line1"][:80],
                 uptime_card.source_text(payload)[:200])
    return ({"status": "sent"}, 200) if ok else ({"status": "discord failed"}, 502)


def _with_components(url: str) -> str:
    return url + ("&" if "?" in url else "?") + "with_components=true"


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
