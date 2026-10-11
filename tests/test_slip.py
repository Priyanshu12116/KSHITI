import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server import app
from kshiti.pipeline import Result
from kshiti.slip import _pdf_value, build_slip

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("name", ["headline", "hindi", "amendment", "notfound"])
def test_slip_builds_for_every_answer_type(name):
    r = Result.model_validate(json.loads((FIX / f"{name}.json").read_text(encoding="utf-8")))
    data, rid = build_slip(r)
    assert data[:5] == b"%PDF-" and len(data) > 10_000
    assert rid.startswith("KSH-") and len(rid) == 17


def test_slip_endpoint_returns_pdf_download():
    body = json.loads((FIX / "headline.json").read_text(encoding="utf-8"))
    resp = TestClient(app).post("/api/slip", json=body)
    assert resp.status_code == 200 and resp.headers["content-type"] == "application/pdf"
    assert "Kshiti_KSH-" in resp.headers["content-disposition"]


def test_far_value_has_no_arrow_glyph_in_pdf():
    assert _pdf_value("1.25 → 250 sq m") == "250 sq m\n(FAR 1.25)"
    assert _pdf_value("3.0 m") == "3.0 m"
