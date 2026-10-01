"""Sentry 웹훅(issue 생성, event_alert)을 Components V2 카드로 바꾼다."""
from __future__ import annotations

import re

from cards import AMBER, DARK_RED, GRAY, RED, clip, escape, join, link

LEVEL_COLOR = {"fatal": DARK_RED, "error": RED, "warning": AMBER}
PRIORITY = {"high": "우선순위 높음", "medium": "우선순위 보통", "low": "우선순위 낮음"}

_PROJECT_IN_URL = re.compile(r"/projects/[^/]+/(?P<slug>[^/]+)/events/")
_EVENTS_SUFFIX = re.compile(r"events/[^/]+/?$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _tags(event: dict) -> dict:
    tags = event.get("tags")
    if isinstance(tags, dict):
        return tags
    return {t[0]: t[1] for t in tags or [] if isinstance(t, (list, tuple)) and len(t) == 2}


def _release(value) -> str | None:
    if not value:
        return None
    value = str(value)
    return value[:7] if _SHA.match(value) else clip(value, 30)


def _card(emoji: str, project: str, title: str, level: str, detail: list, url) -> dict:
    card = {
        "color": LEVEL_COLOR.get(level, GRAY),
        "line1": f"{emoji} **{escape(project)}** {escape(clip(title, 150))}",
    }
    line2 = join(*(escape(clip(d, 120)) for d in detail if d))
    if line2:
        card["line2"] = line2
    if link(url):
        card["button"] = ("이슈", url)
    return card


def _issue_card(issue: dict) -> dict | None:
    title = issue.get("title")
    project = issue.get("project") or {}
    slug = project.get("slug") if isinstance(project, dict) else project
    if not title or not slug:
        return None
    level = str(issue.get("level") or "error").lower()
    detail = [
        level,
        issue.get("culprit"),
        issue.get("shortId"),
        PRIORITY.get(str(issue.get("priority") or "").lower()),
        "미처리 예외" if issue.get("isUnhandled") else None,
    ]
    return _card("🆕", slug, title, level, detail, issue.get("web_url") or issue.get("permalink"))


def _event_card(event: dict, rule) -> dict | None:
    title = event.get("title")
    m = _PROJECT_IN_URL.search(str(event.get("url") or ""))
    if not title or not m:
        return None
    tags = _tags(event)
    level = str(event.get("level") or tags.get("level") or "error").lower()
    rule = str(rule or "")
    regression = "재발" in rule or "regress" in rule.lower()
    detail = [
        level,
        event.get("culprit") or event.get("location"),
        tags.get("environment"),
        _release(event.get("release") or tags.get("release")),
        "미처리 예외" if tags.get("handled") == "no" else None,
        None if regression else rule,
    ]
    url = _EVENTS_SUFFIX.sub("", str(event.get("web_url") or ""))
    if regression:
        return _card("🔁", m["slug"], f"재발: {title}", level, detail, url)
    return _card("🔔", m["slug"], title, level, detail, url)


def build(resource: str, payload: dict) -> dict | None:
    """알아본 형식이면 카드 dict, 아니면 None."""
    data = payload.get("data") or {}
    if resource == "issue" and isinstance(data.get("issue"), dict):
        return _issue_card(data["issue"])
    if resource == "event_alert" and isinstance(data.get("event"), dict):
        return _event_card(data["event"], data.get("triggered_rule"))
    return None
