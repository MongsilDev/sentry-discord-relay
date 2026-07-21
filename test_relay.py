"""중계기 회귀 테스트 — 네트워크 없이 embed 변환과 서명 검증을 확인."""
import hashlib
import hmac
import json
import sys

from discord_embed import build_embed, LEVEL_TO_COLOR
from app import verify_signature


def run(name, fn):
    try:
        fn()
    except AssertionError as e:
        print("FAIL %s: %s" % (name, e))
        return False
    print("PASS %s" % name)
    return True


# ── embed 변환 ──────────────────────────────────────────────────────────

SAMPLE = {
    "action": "triggered",
    "data": {
        "event": {
            "title": "위젯 갱신 실패 (HTTP 500)",
            "level": "error",
            "web_url": "https://mongsildev.sentry.io/issues/123/",
            "culprit": "main.py in push_widget",
            "timestamp": 1_784_500_000.0,
            "project": "widgetbot",
            "tags": [["environment", "production"], ["level", "error"],
                     ["server_name", "nas"]],
            "metadata": {"type": "HTTPError", "value": "500"},
        },
        "triggered_rule": "high priority issues",
    },
}


def test_embed_core_fields():
    e = build_embed(SAMPLE)
    assert e["title"] == "위젯 갱신 실패 (HTTP 500)", e["title"]
    assert e["color"] == LEVEL_TO_COLOR["error"], e["color"]
    assert e["url"] == "https://mongsildev.sentry.io/issues/123/", e.get("url")
    assert e["description"] == "main.py in push_widget", e.get("description")
    assert "timestamp" in e and e["timestamp"].startswith("2026"), e.get("timestamp")


def test_embed_footer_has_project_and_rule():
    e = build_embed(SAMPLE)
    assert "widgetbot" in e["footer"]["text"], e["footer"]
    assert "high priority issues" in e["footer"]["text"], e["footer"]


def test_embed_tag_fields():
    e = build_embed(SAMPLE)
    names = {f["name"] for f in e.get("fields", [])}
    assert "environment" in names, names
    assert "server_name" in names, names


def test_embed_level_color_mapping():
    for level, color in (("warning", LEVEL_TO_COLOR["warning"]),
                         ("info", LEVEL_TO_COLOR["info"]),
                         ("fatal", LEVEL_TO_COLOR["fatal"])):
        p = json.loads(json.dumps(SAMPLE))
        p["data"]["event"]["level"] = level
        assert build_embed(p)["color"] == color, level


def test_embed_missing_title_falls_back_to_metadata():
    p = json.loads(json.dumps(SAMPLE))
    del p["data"]["event"]["title"]
    e = build_embed(p)
    assert "HTTPError" in e["title"], e["title"]
    assert "500" in e["title"], e["title"]


def test_embed_issue_resource_shape():
    """issue 구독 리소스는 event 대신 issue 키를 쓴다."""
    p = {"data": {"issue": {"title": "테스트 이슈", "level": "warning",
                            "web_url": "https://x/", "tags": {}}}}
    e = build_embed(p)
    assert e["title"] == "테스트 이슈", e["title"]
    assert e["color"] == LEVEL_TO_COLOR["warning"], e["color"]


def test_embed_dict_tags():
    """태그가 dict 형태로 와도 처리."""
    p = json.loads(json.dumps(SAMPLE))
    p["data"]["event"]["tags"] = {"environment": "staging"}
    e = build_embed(p)
    names = {f["name"] for f in e.get("fields", [])}
    assert "environment" in names, names


# ── 서명 검증 ───────────────────────────────────────────────────────────

def test_signature_valid():
    secret = "topsecret"
    body = b'{"hello":"world"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(secret, body, sig) is True


def test_signature_wrong_rejected():
    assert verify_signature("topsecret", b"body", "deadbeef") is False


def test_signature_missing_rejected():
    assert verify_signature("topsecret", b"body", None) is False


def test_signature_empty_secret_rejected():
    body = b"body"
    sig = hmac.new(b"", body, hashlib.sha256).hexdigest()
    # 시크릿 미설정이면 서명이 맞아도 거부(설정 누락 방어)
    assert verify_signature("", body, sig) is False


if __name__ == "__main__":
    ok = True
    for name, fn in [
        ("embed 핵심 필드", test_embed_core_fields),
        ("footer에 프로젝트+규칙", test_embed_footer_has_project_and_rule),
        ("태그 필드", test_embed_tag_fields),
        ("레벨별 색상 매핑", test_embed_level_color_mapping),
        ("제목 없으면 metadata 폴백", test_embed_missing_title_falls_back_to_metadata),
        ("issue 리소스 형태", test_embed_issue_resource_shape),
        ("dict 태그 처리", test_embed_dict_tags),
        ("올바른 서명 통과", test_signature_valid),
        ("틀린 서명 거부", test_signature_wrong_rejected),
        ("서명 없음 거부", test_signature_missing_rejected),
        ("시크릿 미설정 거부", test_signature_empty_secret_rejected),
    ]:
        ok = run(name, fn) and ok
    sys.exit(0 if ok else 1)
