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

import os

from . import engine as claude_engine
from . import groq_engine
from .calculator import CalcOutput, calculate
from .models import Answer, Citation, Warning_
from .lang import detect_lang
from .rules import get_rule
from .router import Route, route

Event = Callable[[str, object], None]


def _claude_configured() -> bool:
    k = os.environ.get("ANTHROPIC_API_KEY", "")
    return bool(k) and not k.startswith("dummy")


def provider() -> str:
    """Claude when an Anthropic key is set; otherwise Groq (gpt-oss) when a Groq key is set."""
    if _claude_configured():
        return "claude"
    return "groq" if groq_engine.available() else "claude"


def ask(question: str, on_text=None, context: str = "", forced_rules: list[str] | None = None) -> Answer:
    if provider() == "groq":
        return groq_engine.ask(question, on_text=on_text, context=context, forced_rules=forced_rules)
    return claude_engine.ask(question, on_text=on_text, context=context)


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


def answer_from_calculator(answer: Answer, calc: CalcOutput, question: str) -> None:
    """If the model says "not found" or fails but code found verified figures, the figures win."""
    if not calc.results or answer.status not in ("not_found", "error", "unverified"):
        return
    if answer.status == "unverified" and answer.text:
        return
    hi = detect_lang(question) == "hi"
    lines = [f"{(r.label_hi if hi else r.label_en)}: {r.display} (नियम {r.sub_rule}, पृष्ठ {r.page})। {r.basis_hi}" if hi
             else f"{r.label_en}: {r.display} (Rule {r.sub_rule}, page {r.page}). {r.basis_en}" for r in calc.results]
    answer.text = " ".join(lines)
    answer.lang = "hi" if hi else "en"
    answer.status = "answered"
    answer.error = ""
    answer.not_found_reason = ""
    answer.warnings.append(Warning_(
        kind="info",
        text_en="This answer was written from the calculator, using the official table checked against the PDF.",
        text_hi="यह उत्तर गणना से लिखा गया है, PDF से जाँची गई आधिकारिक तालिका के आधार पर।",
    ))


def attach_calc_citations(answer: Answer, calc: CalcOutput) -> None:
    """A calculated figure always shows the official table it came from (already checked word for word)."""
    if answer.status not in ("answered", "unverified"):
        return
    have = {(c.rule, " ".join(c.quote.split())[:80]) for c in answer.citations}
    for r in calc.results:
        if not (r.verified and r.quote):
            continue
        key = (r.rule, " ".join(r.quote.split())[:80])
        if key in have or any(c.rule == r.rule and c.is_table and c.page == r.page for c in answer.citations):
            continue
        rule = get_rule(r.rule)
        answer.citations.insert(0, Citation(rule=r.rule, title=rule.title, part=rule.part, page=r.page, quote=r.quote,
                                            supports=f"{r.label_en}: {r.display}", verified=True, is_table=True))
        have.add(key)
    if answer.status == "unverified" and answer.citations:
        answer.status = "answered"


def run(question: str, on_event: Event | None = None) -> Result:
    emit = on_event or (lambda kind, data: None)
    t0 = time.perf_counter()

    rt = route(question)
    emit("route", rt)

    calc = calculate(rt.inputs, rt.topics) if rt.topics else CalcOutput()
    first_fig = round(time.perf_counter() - t0, 2) if calc.results else None
    emit("calc", calc)

    forced = list(dict.fromkeys(r.rule for r in calc.results))
    answer = ask(question, on_text=lambda t: emit("text", t), context=calc_context(calc), forced_rules=forced)
    answer.timing.router_s = rt.seconds
    answer_from_calculator(answer, calc, question)
    attach_calc_citations(answer, calc)
    cross_check(answer, calc)
    result = Result(question=question, route=rt, calc=calc, answer=answer,
                    seconds_to_first_figure=first_fig, seconds_total=round(time.perf_counter() - t0, 2))
    emit("done", result)
    return result
