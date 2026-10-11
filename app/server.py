"""Kshiti web server: the clerk's interface plus a small JSON/stream API.

Run:  python run.py        (or: uvicorn app.server:app --port 8000)

Routes
  GET  /                    the interface
  GET  /api/meta            rulebook version, fingerprint, amendments, service status, accuracy
  POST /api/ask             one question -> Server-Sent Events: route, calc, text..., done
  GET  /api/rule/{rule}     full rule text in blocks with page numbers (for the rule drawer)
  GET  /rules.pdf           the official English rulebook (open at #page=N)
"""
from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from kshiti.rules import RULES_FILE, RULES_VERSION, get_rule, load_rules, rulebook_fingerprint
from kshiti.verify import load_amendments

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
PDF_EN = ROOT / "data" / "source" / "rules_EN.pdf"
EVAL_RESULTS = ROOT / "eval" / "results.json"
EVAL_OFFLINE = ROOT / "eval" / "results_offline.json"
FIXTURES = ROOT / "tests" / "fixtures"
DEV = os.environ.get("KSHITI_DEV") == "1"

app = FastAPI(title="Kshiti · Bhumi Vikas Sahayak", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    if request.url.path.startswith("/static/fonts") or request.url.path.startswith("/static/brand"):
        resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp


def _configured(var: str) -> bool:
    v = os.environ.get(var, "")
    return bool(v) and not v.startswith("dummy")


def _router() -> str:
    from kshiti.router import router_provider

    return router_provider()


def _engine() -> str:
    from kshiti.pipeline import provider

    return provider()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))


@app.get("/rules.pdf")
def rules_pdf() -> FileResponse:
    return FileResponse(PDF_EN, media_type="application/pdf", filename="MP_Bhumi_Vikas_Rules_2012_EN.pdf",
                        content_disposition_type="inline")


@app.get("/api/meta")
def meta() -> JSONResponse:
    from dotenv import load_dotenv

    load_dotenv()
    rules = load_rules()
    accuracy = None
    for path in (EVAL_RESULTS, EVAL_OFFLINE):          # live results win; offline check until then
        if path.exists():
            accuracy = json.loads(path.read_text(encoding="utf-8"))
            accuracy.pop("questions", None)
            break
    return JSONResponse({
        "rules_version": RULES_VERSION,
        "rules_count": len(rules),
        "blocks_count": sum(len(r.chunks) for r in rules.values()),
        "fingerprint": rulebook_fingerprint(),
        "rules_file": RULES_FILE.name,
        "amendments": load_amendments(),
        "services": {
            "engine": _engine(),
            "router": _router(),
            "groq": _configured("GROQ_API_KEY"),
            "groq_model": os.environ.get("KSHITI_GROQ_MODEL", "openai/gpt-oss-120b"),
            "claude": _configured("ANTHROPIC_API_KEY"),
            "cerebras": _configured("CEREBRAS_API_KEY"),
            "claude_model": os.environ.get("KSHITI_MODEL", "claude-opus-5-5"),
            "cerebras_model": os.environ.get("KSHITI_CEREBRAS_MODEL", "gpt-oss-120b"),
        },
        "accuracy": accuracy,
        "dev": DEV,
    })


@app.get("/api/rule/{rule_no}")
def rule(rule_no: str) -> JSONResponse:
    r = get_rule(rule_no)
    if r is None:
        raise HTTPException(404, "No such rule")
    return JSONResponse({
        "rule": r.rule, "title": r.title, "part": r.part, "page_start": r.page_start, "page_end": r.page_end,
        "blocks": [{"index": c.index, "page": c.page, "text": c.text, "is_table": c.is_table} for c in r.chunks],
    })


class AskBody(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    fixture: str | None = None


def _sse(event: str, data) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    lines = "\n".join(f"data: {line}" for line in payload.split("\n"))
    return f"event: {event}\n{lines}\n\n"


def _dump(obj):
    return obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj


RATE_LIMIT = int(os.environ.get("KSHITI_RATE_LIMIT", "30"))      # questions per visitor per window
RATE_WINDOW = 600                                                  # seconds
_hits: dict[str, list[float]] = {}


def _over_limit(request: Request) -> bool:
    """Simple per-visitor limit so a public deployment cannot run up the API bill."""
    import time

    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    now = time.time()
    recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
    if len(recent) >= RATE_LIMIT:
        _hits[ip] = recent
        return True
    recent.append(now)
    _hits[ip] = recent
    if len(_hits) > 5000:
        _hits.clear()
    return False


@app.post("/api/ask")
def ask(body: AskBody, request: Request) -> StreamingResponse:
    if body.fixture:
        return _fixture_stream(body)
    if _over_limit(request):
        return JSONResponse({"message": "Too many questions from this computer in the last 10 minutes. Please wait a few minutes."},
                            status_code=429)

    from kshiti.pipeline import run

    q: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            run(body.question, on_event=lambda kind, data: q.put((kind, data)))
        except Exception as e:  # noqa: BLE001 - surface any failure to the interface
            q.put(("error", {"message": f"{type(e).__name__}: {e}"}))
        finally:
            q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        yield ": open\n\n"
        while True:
            item = q.get()
            if item is None:
                break
            kind, data = item
            yield _sse(kind, data if kind == "text" else _dump(data))

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/slip")
def slip(result: dict) -> Response:
    from kshiti.pipeline import Result
    from kshiti.slip import build_slip

    data, rid = build_slip(Result.model_validate(result))
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Kshiti_{rid}.pdf"'})


def _fixture_stream(body: AskBody) -> StreamingResponse:
    """Developer-only replay of a recorded result (KSHITI_DEV=1), used for visual tests."""
    path = FIXTURES / f"{Path(body.fixture).name}.json"
    if not DEV or not path.exists():
        raise HTTPException(404, "Fixtures are only available in developer mode")
    import time

    result = json.loads(path.read_text(encoding="utf-8"))

    def stream():
        yield _sse("route", result["route"])
        time.sleep(0.25)
        yield _sse("calc", result["calc"])
        time.sleep(0.4)
        text = result["answer"]["text"]
        for i in range(0, len(text), 12):
            yield _sse("text", text[i:i + 12])
            time.sleep(0.02)
        yield _sse("done", result)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
