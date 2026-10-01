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


def _project_name(project) -> str:
    """project는 문자열(event 리소스)일 수도 dict(issue 리소스)일 수도 있다."""
    if isinstance(project, dict):
        return project.get("slug") or project.get("name") or "sentry"
    return str(project) if project else "sentry"


def build_embed(payload: dict) -> dict:
    """Sentry webhook 본문 → Discord embed dict.

    두 payload 형식을 모두 지원한다:
    - issue 구독:  {"data": {"issue": {...}}}         (project가 dict, tags 없음)
    - event_alert: {"data": {"event": {...}, "triggered_rule": ...}}  (tags 배열)
    """
    data = payload.get("data") or {}
    obj = data.get("event") or data.get("issue") or {}
    metadata = obj.get("metadata") or {}

    # 제목: title 우선, 없으면 metadata.type + value
    title = obj.get("title") or metadata.get("type") or "알 수 없는 이슈"
    if not obj.get("title") and metadata.get("value"):
        title = f"{title}: {metadata['value']}"

    level = (obj.get("level") or "error").lower()
    color = LEVEL_TO_COLOR.get(level, DEFAULT_COLOR)

    url = obj.get("web_url") or obj.get("url") or obj.get("permalink") or obj.get("issue_url")
    culprit = obj.get("culprit") or metadata.get("filename")

    project = _project_name(obj.get("project") or data.get("project_slug"))
    rule = data.get("triggered_rule") or data.get("rule")

    # 필드: event 리소스면 태그에서, issue 리소스면 이슈 속성에서.
    fields = []
    tags = _tags_dict(obj)
    if tags:
        for key in TAG_FIELDS:
            if tags.get(key):
                fields.append({"name": key, "value": str(tags[key]), "inline": True})
    else:
        # issue 리소스는 태그가 없다. 대신 유용한 속성으로 채운다.
        fields.append({"name": "level", "value": level, "inline": True})
        if obj.get("shortId"):
            fields.append({"name": "issue", "value": obj["shortId"], "inline": True})
        if obj.get("count") and str(obj["count"]) != "1":
            fields.append({"name": "count", "value": str(obj["count"]), "inline": True})

    footer_parts = [project]
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
    ts = obj.get("timestamp") or obj.get("lastSeen") or obj.get("firstSeen") or obj.get("dateCreated")
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
