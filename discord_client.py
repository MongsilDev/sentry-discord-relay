"""Discord Incoming Webhook으로 embed 전송. 표준 라이브러리만 사용."""
from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.request

log = logging.getLogger("relay.discord")
_SSL = ssl.create_default_context()


def send_embed(webhook_url: str, embed: dict, timeout: int = 15) -> bool:
    """embed 하나를 Discord 채널로 전송. 성공하면 True.

    429(rate limit)면 Retry-After만큼 1회 대기 후 재시도. 그래도 실패면 버린다
    (알림 유실이 프로세스 중단보다 낫다).
    """
    body = json.dumps({"embeds": [embed]}).encode("utf-8")
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(
                webhook_url, data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, context=_SSL, timeout=timeout) as resp:
                if resp.status in (200, 204):
                    return True
                log.warning("Discord 응답 %s", resp.status)
                return False
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 1:
                retry = _retry_after(e)
                log.warning("Discord rate limit, %.1fs 후 재시도", retry)
                time.sleep(retry)
                continue
            log.error("Discord 전송 실패 HTTP %s", e.code)
            return False
        except Exception as e:
            log.error("Discord 전송 오류: %s", e)
            return False
    return False


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
