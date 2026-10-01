"""Discord Components V2 카드. 위키 편집 알림과 같은 구성으로 색 막대, 굵은 첫 줄, 작은 둘째 줄, 링크 버튼."""
from __future__ import annotations

import re

RED = 0xEF4444
DARK_RED = 0xB91C1C
AMBER = 0xF59E0B
GREEN = 0x22C55E
GRAY = 0x64748B

_MD = re.compile(r"([\\*_~`|\[\]])")

NOTICE_STYLE = {
    "fail": ("❌", RED),
    "warn": ("⚠️", AMBER),
    "ok": ("✅", GREEN),
    "info": ("ℹ️", GRAY),
}


def escape(text) -> str:
    return _MD.sub(r"\\\1", str(text))


def clip(text, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def join(*parts) -> str:
    return " | ".join(str(p) for p in parts if p)


def link(url) -> str | None:
    if isinstance(url, str) and url.startswith(("http://", "https://")) and len(url) <= 512:
        return url
    return None


def notice(title: str, status: str = "info", detail: str | None = None,
           url: str | None = None, url_label: str | None = None) -> dict:
    """내부 작업 알림용 범용 카드."""
    emoji, color = NOTICE_STYLE.get(status, NOTICE_STYLE["info"])
    card = {"color": color, "line1": f"{emoji} **{escape(clip(title, 120))}**"}
    if detail:
        card["line2"] = escape(clip(detail, 300))
    if link(url):
        card["button"] = (clip(url_label or "열기", 40), url)
    return card


def build_message(card: dict) -> dict:
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
