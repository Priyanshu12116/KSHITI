"""Measure Kshiti on the 17 official sample questions.

  python eval/run_eval.py              full run: router + calculator + Claude + checks (needs API keys)
  python eval/run_eval.py --offline    router + calculator only (no API calls)
  python eval/run_eval.py --only 1,14  a subset

Scores (see eval/answer_key.json):
  rule      the answer cites at least one correct rule (questions the rules answer)
  not found says "not found" for questions the rules do not answer, and never for the others
  figures   every expected number appears in the answer or the calculator output
  language  the answer is in the language of the question
  quotes    share of citations that passed the word-for-word check; invented rule numbers
  amendment the 28-08-2026 amendment is flagged where it applies
Writes eval/results.json (read by the interface) and eval/results.md (for the README).
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from kshiti.calculator import calculate  # noqa: E402
from kshiti.lang import detect_lang  # noqa: E402
from kshiti.router import route  # noqa: E402

KEY = ROOT / "eval" / "answer_key.json"
OUT_JSON = ROOT / "eval" / "results.json"
OUT_MD = ROOT / "eval" / "results.md"
DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def numbers(text: str) -> set[float]:
    return {float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", (text or "").translate(DEV_DIGITS))}


def base(rule: str) -> str:
    m = re.match(r"\d+", rule or "")
    return m.group(0) if m else rule


def score_one(item: dict, res) -> dict:
    a = res.answer
    cited = a.cited_rules
    mentioned = a.mentioned_rules
    calc_text = " ".join(r.display for r in res.calc.results)
    nums = numbers(a.text) | numbers(calc_text)
    expected = {base(r) for r in item["rules"]}
    row = {
        "id": item["id"], "q": item["q"], "lang_expected": item["lang"], "found_expected": item["found"],
        "status": a.status, "cited_rules": cited, "mentioned_rules": mentioned,
        "calc": [f"{r.label_en}: {r.display}" for r in res.calc.results],
        "answer": a.text if a.status != "not_found" else a.not_found_reason,
        "citations": len(a.citations), "verified": sum(c.verified for c in a.citations),
        "warnings": [w.kind for w in a.warnings], "error": a.error,
        "seconds": res.seconds_total, "router": res.route.source, "router_seconds": res.route.seconds,
        "first_figure_s": res.seconds_to_first_figure,
    }
    if item["found"]:
        row["rule_ok"] = bool(expected & ({base(r) for r in cited} | {base(r) for r in mentioned if r in cited or not cited}))
        row["rule_ok"] = bool(expected & {base(r) for r in cited})          # only verified citations count
        row["false_not_found"] = a.status == "not_found"
    else:
        row["not_found_ok"] = a.status == "not_found"
    if item["figures"]:
        row["figures_ok"] = all(any(abs(n - f) < 1e-6 for n in nums) for f in item["figures"])
    shown = a.text or a.not_found_reason
    row["lang_ok"] = (detect_lang(shown) == item["lang"]) if shown else False
    if item.get("amendment"):
        row["amendment_ok"] = "amendment" in row["warnings"]
    row["invented_rules"] = row["warnings"].count("invented_rule")
    return row


def summarise(rows: list[dict], model: str, offline: bool) -> dict:
    found = [r for r in rows if r["found_expected"]]
    nf = [r for r in rows if not r["found_expected"]]
    figs = [r for r in rows if "figures_ok" in r]
    secs = [r["seconds"] for r in rows if r.get("seconds") and r["status"] != "error"]
    s = {
        "rule_hit": sum(r.get("rule_ok", False) for r in found), "rule_total": len(found),
        "not_found_hit": sum(r.get("not_found_ok", False) for r in nf), "not_found_total": len(nf),
        "false_not_found": sum(r.get("false_not_found", False) for r in found),
        "figure_hit": sum(r["figures_ok"] for r in figs), "figure_total": len(figs),
        "lang_hit": sum(r["lang_ok"] for r in rows), "lang_total": len(rows),
        "quotes_verified": sum(r["verified"] for r in rows), "quotes_total": sum(r["citations"] for r in rows),
        "invented_rules": sum(r["invented_rules"] for r in rows),
        "amendment_hit": sum(r.get("amendment_ok", False) for r in rows), "amendment_total": sum("amendment_ok" in r for r in rows),
        "errors": sum(r["status"] == "error" for r in rows),
        "median_seconds": round(statistics.median(secs), 1) if secs else None,
    }
    return {"run_date": datetime.now().strftime("%d-%m-%Y %H:%M"), "model": model, "offline": offline,
            "summary": s, "questions": rows}


def write_md(res: dict) -> None:
    s = res["summary"]
    pct = lambda a, b: f"{a}/{b} ({round(100 * a / b)}%)" if b else "—"  # noqa: E731
    lines = [
        f"# Kshiti accuracy on the 17 official sample questions",
        "",
        f"Run: {res['run_date']} · model: {res['model']} · {'OFFLINE (router + calculator only)' if res['offline'] else 'full pipeline'}",
        "",
        "| Measure | Result |", "|---|---|",
        f"| Correct rule cited (questions the rules answer) | {pct(s['rule_hit'], s['rule_total'])} |",
        f"| \"Not found\" when the rules are silent | {pct(s['not_found_hit'], s['not_found_total'])} |",
        f"| Wrong \"not found\" on answerable questions | {s['false_not_found']} |",
        f"| Correct table figures | {pct(s['figure_hit'], s['figure_total'])} |",
        f"| Answer in the question's language | {pct(s['lang_hit'], s['lang_total'])} |",
        f"| Quotes verified word for word | {pct(s['quotes_verified'], s['quotes_total'])} |",
        f"| Invented rule numbers | {s['invented_rules']} |",
        f"| Later amendment flagged (Q11) | {pct(s['amendment_hit'], s['amendment_total'])} |",
        f"| Median time per answer | {s['median_seconds']} s |" if s["median_seconds"] else "| Median time per answer | — |",
        "",
        "| # | Lang | Status | Rules cited | Rule | Figures | Lang | Quotes | Time |", "|---|---|---|---|---|---|---|---|---|",
    ]
    tick = lambda v: "—" if v is None else ("✅" if v else "❌")  # noqa: E731
    for r in res["questions"]:
        rule_cell = tick(r.get("rule_ok")) if r["found_expected"] else tick(r.get("not_found_ok"))
        lines.append(f"| {r['id']} | {r['lang_expected']} | {r['status']} | {', '.join(r['cited_rules']) or '—'} | {rule_cell} | "
                     f"{tick(r.get('figures_ok'))} | {tick(r['lang_ok'])} | {r['verified']}/{r['citations']} | {r['seconds'] or '—'} s |")
    lines += ["", "Answer key: eval/answer_key.json. Full answers: eval/results.json."]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def offline_row(item: dict) -> dict:
    """Router + calculator only: checks numbers and figures without any API call."""
    rt = route(item["q"])
    calc = calculate(rt.inputs, rt.topics) if rt.topics else None
    text = " ".join(r.display for r in calc.results) if calc else ""
    nums = numbers(text)
    row = {"id": item["id"], "intent": rt.intent, "topics": rt.topics,
           "inputs": {k: v for k, v in rt.inputs.model_dump().items() if v is not None},
           "calc": [f"{r.label_en}: {r.display} (Rule {r.sub_rule}, p.{r.page})" for r in (calc.results if calc else [])]}
    if not item["found"]:
        row["out_of_scope_ok"] = rt.intent == "out_of_scope"
    if item["figures"] and calc and calc.results:
        row["figures_ok"] = all(any(abs(n - f) < 1e-6 for n in nums) for f in item["figures"])
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    items = json.loads(KEY.read_text(encoding="utf-8"))["questions"]
    if args.only:
        want = {int(x) for x in args.only.split(",")}
        items = [i for i in items if i["id"] in want]

    if args.offline:
        for item in items:
            print(json.dumps(offline_row(item), ensure_ascii=False))
        return

    from kshiti.engine import MODEL
    from kshiti.pipeline import run

    rows = []
    for item in items:
        t0 = time.perf_counter()
        res = run(item["q"])
        row = score_one(item, res)
        rows.append(row)
        flag = "OK " if row.get("rule_ok", row.get("not_found_ok")) else "BAD"
        print(f"[{flag}] Q{item['id']:>2} {row['status']:<11} cited={row['cited_rules']} verified={row['verified']}/{row['citations']} "
              f"figs={row.get('figures_ok', '-')} lang={row['lang_ok']} warn={row['warnings']} {time.perf_counter() - t0:.1f}s"
              + (f" ERROR: {row['error']}" if row["error"] else ""))
    res = summarise(rows, MODEL, offline=False)
    if not args.only:
        OUT_JSON.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        write_md(res)
    print(json.dumps(res["summary"], indent=2))


if __name__ == "__main__":
    main()
