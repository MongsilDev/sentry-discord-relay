"""UptimeRobot Discord 연동이 보내는 웹훅 본문을 Components V2 카드로 바꾼다."""
from __future__ import annotations

import re

COLOR_DOWN = 0xEF4444
COLOR_UP = 0x22C55E

_HEAD = re.compile(r"Monitor is (?P<state>DOWN|UP)\s*:\s*(?P<name>.+?)\s*\(\s*(?P<url>\S+)\s*\)", re.I)
_REASON = re.compile(r"Reason\s*:\s*(?P<reason>[^\n]+?)\s*(?:/\s*Location\s*:[^\n]*)?$", re.I | re.M)
_DURATION = re.compile(r"(?:was down|down) for\s+(?P<dur>.+?)\s*\.?\s*$", re.I | re.S)
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


def _escape(text: str) -> str:
    return re.sub(r"([\\*_~`|>#\[\]])", r"\\\1", text)


def parse(payload: dict) -> dict | None:
    """알아본 형식이면 카드 dict(color, line1, line2, button), 아니면 None."""
    text = source_text(payload)
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
        "line1": f"**{_escape(head['name'])}** {'중단' if down else '복구'}",
    }
    if detail:
        card["line2"] = " ".join(detail.split())[:300]
    url = head["url"]
    if url.startswith(("http://", "https://")) and len(url) <= 512:
        card["button"] = ("열기", url)
    return card


def build_message(card: dict) -> dict:
    """위키 편집 알림과 같은 구성: 색 막대 컨테이너 안에 두 줄 텍스트와 링크 버튼."""
    text = card["line1"] + (f"\n-# {card['line2']}" if card.get("line2") else "")
    inner = {"type": 10, "content": text[:3900]}
    if card.get("button"):
        label, url = card["button"]
        inner = {
            "type": 9,
            "components": [inner],
            "accessory": {"type": 2, "style": 5, "label": label, "url": url},
        }
    return {
        "flags": 1 << 15,
        "allowed_mentions": {"parse": []},
        "components": [{"type": 17, "accent_color": card["color"], "components": [inner]}],
    }
