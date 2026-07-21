"""Sentry webhook JSON → Discord embed 변환.

Sentry 공식 Discord 통합의 embed 구조를 본떴다:
  src/sentry/integrations/discord/message_builder/issues.py
색상 값(LEVEL_TO_COLOR)은 공식 값을 그대로 이식했다.
"""
from __future__ import annotations

# Sentry 공식 message_builder/__init__.py LEVEL_TO_COLOR 이식 (Discord는 색을 10진 정수로 받음)
LEVEL_TO_COLOR = {
    "debug": 0xFBE14F,
    "info": 0x2788CE,
    "warning": 0xFFC227,
    "error": 0xE03E2F,
    "fatal": 0xFA4747,
}
DEFAULT_COLOR = LEVEL_TO_COLOR["error"]

# footer/필드에 노출할 태그 (있는 것만)
TAG_FIELDS = ("environment", "level", "server_name", "release", "transaction")


def _tags_dict(event: dict) -> dict:
    """event.tags를 dict로. Sentry는 [[k,v],...] 또는 {k:v} 둘 다 보낼 수 있다."""
    tags = event.get("tags")
    if isinstance(tags, dict):
        return tags
    out = {}
    for item in tags or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            out[item[0]] = item[1]
    return out


def build_embed(payload: dict) -> dict:
    """Sentry webhook 본문(event_alert/issue 리소스) → Discord embed dict.

    payload 구조: {"action":..., "data": {"event": {...}, "triggered_rule": ...}}
    이슈 구독 리소스는 {"data": {"issue": {...}}} 형태라 event가 없을 수 있어 둘 다 본다.
    """
    data = payload.get("data") or {}
    event = data.get("event") or data.get("issue") or {}
    metadata = event.get("metadata") or {}

    # 제목: event.title 우선, 없으면 metadata.type + value
    title = event.get("title") or metadata.get("type") or "알 수 없는 이슈"
    if not event.get("title") and metadata.get("value"):
        title = f"{title}: {metadata['value']}"

    level = (event.get("level") or "error").lower()
    color = LEVEL_TO_COLOR.get(level, DEFAULT_COLOR)

    url = event.get("web_url") or event.get("url") or event.get("issue_url")
    culprit = event.get("culprit") or metadata.get("filename")

    tags = _tags_dict(event)
    project = event.get("project") or tags.get("project") or data.get("project_slug") or "sentry"
    rule = data.get("triggered_rule") or data.get("rule")

    fields = []
    for key in TAG_FIELDS:
        if tags.get(key):
            fields.append({"name": key, "value": str(tags[key]), "inline": True})

    footer_parts = [str(project)]
    if rule:
        footer_parts.append(str(rule))

    embed = {
        "title": title[:256],  # Discord embed title 한도
        "color": color,
        "footer": {"text": " · ".join(footer_parts)[:2048]},
    }
    if url:
        embed["url"] = url
    if culprit:
        embed["description"] = str(culprit)[:4096]
    if fields:
        embed["fields"] = fields[:25]  # Discord 한도
    ts = event.get("timestamp") or event.get("dateCreated") or event.get("lastSeen")
    if ts:
        embed["timestamp"] = _iso(ts)

    return embed


def _iso(ts) -> str:
    """Discord는 ISO8601 문자열을 기대. Sentry는 epoch(float) 또는 ISO 문자열을 보낸다."""
    if isinstance(ts, (int, float)):
        # epoch → ISO. datetime 사용(표준 라이브러리)
        from datetime import datetime, timezone
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return str(ts)
