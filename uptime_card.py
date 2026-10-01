"""UptimeRobot Discord 연동이 보내는 웹훅 본문을 Components V2 카드로 바꾼다."""
from __future__ import annotations

import re

from cards import GRAY, GREEN, RED, escape, link

COLOR_DOWN = RED
COLOR_UP = GREEN

_HEAD = re.compile(r"Monitor is (?P<state>DOWN|UP)\s*:\s*(?P<name>.+?)\s*\(\s*(?P<url>\S+)\s*\)", re.I)
_REASON = re.compile(r"Reason\s*:\s*(?P<reason>[^\n]+?)\s*(?:/\s*Location\s*:[^\n]*)?$", re.I | re.M)
_CONTACT_ADDED = re.compile(r"alert contact is now successfully added", re.I)
_DURATION = re.compile(r"down for\s+(?P<dur>[^.\n]+)", re.I)
_UNITS = (
    (r"(\d+)\s+days?", r"\1일"),
    (r"(\d+)\s+hours?", r"\1시간"),
    (r"(\d+)\s+minutes?", r"\1분"),
    (r"(\d+)\s+seconds?", r"\1초"),
)


def source_text(payload: dict) -> str:
    parts = [payload.get("content") or ""]
    for embed in payload.get("embeds") or []:
        if isinstance(embed, dict):
            parts += [embed.get("title") or "", embed.get("description") or ""]
            for f in embed.get("fields") or []:
                if isinstance(f, dict):
                    parts.append(f"{f.get('name', '')}: {f.get('value', '')}")
    return "\n".join(p for p in parts if p).strip()


def _korean_duration(text: str) -> str:
    out = text.replace(" and ", " ").replace(",", "")
    for pattern, repl in _UNITS:
        out = re.sub(pattern, repl, out, flags=re.I)
    return re.sub(r"\s+", " ", out).strip()


def parse(payload: dict) -> dict | None:
    """알아본 형식이면 카드 dict(color, line1, line2, button), 아니면 None."""
    text = source_text(payload)
    if _CONTACT_ADDED.search(text):
        return {"color": GRAY, "line1": "ℹ️ **UptimeRobot 알림 연결됨**", "line2": "이 채널로 모니터 중단과 복구 알림이 옵니다"}
    head = _HEAD.search(text)
    if not head:
        return None
    down = head["state"].upper() == "DOWN"
    rest = text[head.end():].strip(" -\n")
    detail = None
    if down:
        m = _REASON.search(rest)
        detail = m["reason"].strip() if m else None
    else:
        m = _DURATION.search(rest)
        detail = f"중단 시간 {_korean_duration(m['dur'])}" if m else None
    card = {
        "color": COLOR_DOWN if down else COLOR_UP,
        "line1": f"{'🔴' if down else '🟢'} **{escape(head['name'])}** {'중단' if down else '복구'}",
    }
    if detail:
        card["line2"] = escape(" ".join(detail.split())[:300])
    if link(head["url"]):
        card["button"] = ("열기", head["url"])
    return card
