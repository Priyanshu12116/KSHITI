"""One counter question, end to end.

  1. Cerebras router (fast)       -> language, intent, topics, the citizen's numbers
  2. Calculator (code, instant)   -> verified figures from checked tables
  3. Claude (deep, cited)         -> short answer with exact quotes, told the figures
  4. Checks                       -> quotes verified, figures cross-checked, warnings

`on_event(kind, data)` lets the interface show each stage as soon as it is ready:
"route", "calc", "text" (streamed answer), "done".
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable

from pydantic import BaseModel, Field

from .calculator import CalcOutput, calculate
from .engine import ask
from .models import Answer, Warning_
from .router import Route, route

Event = Callable[[str, object], None]


class Result(BaseModel):
    question: str
    route: Route
    calc: CalcOutput = Field(default_factory=CalcOutput)
    answer: Answer
    seconds_to_first_figure: float | None = None
    seconds_total: float = 0.0


def calc_context(calc: CalcOutput) -> str:
    """Calculator figures handed to Claude so the written answer uses the same numbers."""
    if not calc.results:
        return ""
    lines = ["Verified calculator results for this question (computed in code from tables checked against the "
             "official PDF). Use exactly these figures, and cite the same rule tables:"]
    for r in calc.results:
        lines.append(f"- {r.label_en}: {r.display} (Rule {r.sub_rule}, page {r.page}). {r.basis_en}")
        lines.extend(f"  Note: {a}" for a in r.assumptions_en)
    lines.extend(f"- Note: {n}" for n in calc.notes_en)
    return "\n".join(lines)


def _figure_tokens(display: str) -> list[str]:
    return re.findall(r"\d[\d,]*(?:\.\d+)?", display)


def cross_check(answer: Answer, calc: CalcOutput) -> None:
    """Warn if Claude's text does not contain a calculated figure (never silently disagree)."""
    if answer.status != "answered" or not answer.text:
        return
    digits = answer.text.translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    for r in calc.results:
        tokens = _figure_tokens(r.display)
        if not tokens:
            continue
        main = tokens[-1] if r.key == "far" else tokens[0]
        variants = {main, main.replace(",", ""), main.rstrip("0").rstrip(".") if "." in main else main}
        if not any(v and v in digits for v in variants):
            answer.warnings.append(Warning_(
                kind="info",
                text_en=f"{r.label_en}: the calculator gives {r.display} (Rule {r.sub_rule}, page {r.page}). Use this figure.",
                text_hi=f"{r.label_hi}: गणना के अनुसार {r.display} (नियम {r.sub_rule}, पृष्ठ {r.page})। यही मान लें।",
            ))


def run(question: str, on_event: Event | None = None) -> Result:
    emit = on_event or (lambda kind, data: None)
    t0 = time.perf_counter()

    rt = route(question)
    emit("route", rt)

    calc = calculate(rt.inputs, rt.topics) if rt.topics else CalcOutput()
    first_fig = round(time.perf_counter() - t0, 2) if calc.results else None
    emit("calc", calc)

    answer = ask(question, on_text=lambda t: emit("text", t), context=calc_context(calc))
    answer.timing.router_s = rt.seconds
    cross_check(answer, calc)
    result = Result(question=question, route=rt, calc=calc, answer=answer,
                    seconds_to_first_figure=first_fig, seconds_total=round(time.perf_counter() - t0, 2))
    emit("done", result)
    return result
