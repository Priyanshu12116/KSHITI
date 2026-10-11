from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


def test_interface_and_assets_are_served():
    r = client.get("/")
    assert r.status_code == 200 and "Kshiti" in r.text and 'lang="en"' in r.text
    for path in ["/static/css/kshiti.css", "/static/js/app.js", "/static/js/i18n.js", "/static/brand/wordmark-hi.svg",
                 "/static/brand/favicon.svg", "/static/fonts/web/Inter.woff2", "/static/logos/emblem-of-india.svg"]:
        assert client.get(path).status_code == 200, path


def test_meta_reports_rulebook_version_and_amendment():
    m = client.get("/api/meta").json()
    assert m["rules_count"] == 106 and len(m["fingerprint"]) == 64
    assert "06-03-2025" in m["rules_version"] and m["amendments"][0]["sub_rule"] == "2(5)(c)"


def test_rule_endpoint_returns_blocks_with_pages():
    r = client.get("/api/rule/56").json()
    assert r["title"] == "Residential Buildings" and r["blocks"][0]["page"] == 77
    assert client.get("/api/rule/26-B").status_code == 200
    assert client.get("/api/rule/999").status_code == 404


def test_official_pdf_is_served_inline():
    r = client.get("/rules.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"


def test_fixtures_are_not_available_outside_developer_mode():
    r = client.post("/api/ask", json={"question": "front open space?", "fixture": "headline"})
    assert r.status_code == 404


def test_ask_validates_input():
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
