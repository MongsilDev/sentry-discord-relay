"""Discord Incoming Webhook 전송. 표준 라이브러리만 사용."""
from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.request

log = logging.getLogger("sentry-discord-relay.discord")
_SSL = ssl.create_default_context()

# Discord API는 명시적 User-Agent를 요구한다. urllib 기본값(Python-urllib/x)은
# 403으로 차단되므로 반드시 지정한다.
USER_AGENT = "sentry-discord-relay (https://mongsil.dev, 1.0)"


def send_embed(webhook_url: str, embed: dict, timeout: int = 15) -> str | None:
    """embed 하나를 Discord 채널로 전송. 성공하면 메시지 ID."""
    return send_json(webhook_url, {"embeds": [embed]}, timeout=timeout)


def with_query(url: str, **params) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return url + ("&" if "?" in url else "?") + query


def send_json(webhook_url: str, payload: dict, components: bool = False, timeout: int = 15) -> str | None:
    """웹훅 본문을 전송. 성공하면 메시지 ID(모르면 빈 문자열), 실패하면 None.

    wait=true로 보내 메시지 ID를 받는다. 429(rate limit)면 Retry-After만큼 1회 대기 후
    재시도하고, 그래도 실패면 버린다(알림 유실이 프로세스 중단보다 낫다).
    """
    params = {"wait": "true"}
    if components:
        params["with_components"] = "true"
    url = with_query(webhook_url, **params)
    body = json.dumps(payload).encode("utf-8")
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
                method="POST")
            with urllib.request.urlopen(req, context=_SSL, timeout=timeout) as resp:
                if resp.status in (200, 204):
                    try:
                        return str(json.loads(resp.read().decode("utf-8")).get("id") or "")
                    except ValueError:
                        return ""
                log.warning("Discord 응답 %s", resp.status)
                return None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 1:
                retry = _retry_after(e)
                log.warning("Discord rate limit, %.1fs 후 재시도", retry)
                time.sleep(retry)
                continue
            detail = ""
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            log.error("Discord 전송 실패 HTTP %s %s", e.code, detail)
            return None
        except Exception as e:
            log.error("Discord 전송 오류: %s", e)
            return None
    return None


def _retry_after(err: urllib.error.HTTPError) -> float:
    """429 응답에서 대기 시간(초). 헤더 우선, 없으면 본문 JSON, 없으면 1초."""
    hdr = err.headers.get("Retry-After")
    if hdr:
        try:
            return min(float(hdr), 10.0)
        except ValueError:
            pass
    try:
        data = json.loads(err.read().decode("utf-8"))
        return min(float(data.get("retry_after", 1)), 10.0)
    except Exception:
        return 1.0
