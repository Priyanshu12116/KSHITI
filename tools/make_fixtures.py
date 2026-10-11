"""Developer-only fixtures for visual tests of the interface (served only with KSHITI_DEV=1).

They run the REAL router, calculator and quote check. Only Claude's reply is
replaced by a recorded stand-in whose citations point at real rule blocks, so the
interface can be tested without an API key. Never used to answer real questions.

Run: python tools/make_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kshiti import pipeline  # noqa: E402
from kshiti.engine import parse_message  # noqa: E402
from kshiti.rules import get_rule, rule_order  # noqa: E402
from kshiti.verify import verify  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def cite(rule: str, marker: str):
    r = get_rule(rule)
    c = next(c for c in r.chunks if marker in c.text)
    return NS(type="content_block_location", document_index=rule_order().index(rule),
              start_block_index=c.index, end_block_index=c.index + 1, cited_text=c.text)


def fake_ask(blocks, status_tool=None):
    def _ask(question, on_text=None, context="", **kw):
        content = [NS(type="text", text=t, citations=cs) for t, cs in blocks]
        if status_tool:
            content.append(NS(type="tool_use", name=status_tool[0], input=status_tool[1]))
        for t, _ in blocks:
            if on_text:
                on_text(t)
        usage = NS(input_tokens=1200, output_tokens=180, cache_read_input_tokens=84000, cache_creation_input_tokens=0)
        msg = NS(content=content, stop_reason="tool_use" if status_tool else "end_turn", model="claude-opus-5-5", usage=usage)
        a = verify(parse_message(question, msg))
        a.timing.total_s, a.timing.first_token_s = 5.8, 2.1
        return a
    return _ask


CASES = {
    "headline": (
        "My plot is 200 sq m on a 9 m road. How much gap do I leave at the front, how many floors can I build, and what fee do I pay?",
        [("Front open space: at least 3.0 m, because the road is up to 9.0 m wide (Rule 56(1)(a)). ", [cite("56", "Width of street facing the plot")]),
         ("Floors: the rules do not fix a number of floors. They limit the built-up area through FAR 1.25 for residential use, so up to 250 sq m on a 200 sq m plot (Rule 61, Table 8), ", [cite("61", "FLOOR AREA RATIO")]),
         ("and height to 12.5 m, because buildings above 12.5 m need at least a 12 m road and a 1000 sq m plot (Rule 42, Table 4). ", [cite("42", "TABLE No. 4")]),
         ("Fee: for a 250 sq m house the permission fee is Rs 3,000 (Rule 21(3)(b), Item 1) ", [cite("21", "exclusively as residence")]),
         ("plus the application fee of Rs 1.00 per sq m, Rs 250, so Rs 3,250 in total (Rule 21(2)(ii)).", [cite("21", "for the Building Permission Rs 1.00")])],
        None,
    ),
    "hindi": (
        "मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?",
        [("सामने कम से कम 3.0 मीटर खुली जगह छोड़नी होगी, क्योंकि सड़क 9.0 मीटर तक चौड़ी है (नियम 56(1)(a))।", [cite("56", "Width of street facing the plot")])],
        None,
    ),
    "amendment": (
        "Do I need separate development permission for a 300 sq m plot that matches the Development Plan?",
        [("Under Rule 2(5)(c) of the consolidated rules, in the already developed central area of the Development Plan the local body issues building permission as per the land use of the Development Plan. ", [cite("2", "The land is already developed in the Central area")]),
         ("This provision was amended on 28-08-2026: plots up to 500 sq m that conform to the Development Plan land use no longer need separate development permission under Rule 2(5)(a).", [])],
        None,
    ),
    "notfound": (
        "How do I pay my property tax online?",
        [],
        ("report_not_found", {"reason": "The MP Bhumi Vikas Rules 2012 cover building and development permission, not property tax payment.",
                              "suggestion": "Ask the revenue (property tax) section of the Municipal Corporation."}),
    ),
}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (q, blocks, tool) in CASES.items():
        pipeline.ask = fake_ask(blocks, tool)
        res = pipeline.run(q)
        (OUT / f"{name}.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")
        a = res.answer
        print(f"{name}: status={a.status} citations={len(a.citations)} verified={sum(c.verified for c in a.citations)} warnings={[w.kind for w in a.warnings]}")
