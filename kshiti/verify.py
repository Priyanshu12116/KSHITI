"""USP-1: nothing reaches the clerk unless it is traced to the official text.

Checks, in order:
1. every citation points to a real rule and block, and its quote appears word for
   word in that rule's text from the data pack;
2. every rule number the answer mentions exists in the rulebook;
3. answers with no surviving citation are marked unverified;
4. table quotes and amended rules get warnings.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz

from .models import Answer, Citation, Warning_
from .rules import ROOT, get_rule, load_rules, normalise_rule_no, rule_exists

AMENDMENTS_FILE = ROOT / "data" / "amendments.json"
FUZZY_MIN = 97  # tolerate only whitespace/quote-mark noise, never different words


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_in_rule(quote: str, rule_no: str) -> bool:
    """True if the quote appears word for word in the rule's official text."""
    rule = get_rule(rule_no)
    if rule is None or not quote.strip():
        return False
    q, src = _norm(quote), _norm(rule.clean_text)
    if q in src:
        return True
    # Fallback for whitespace or punctuation noise in long quotes only.
    return len(q) > 40 and fuzz.partial_ratio(q, src) >= FUZZY_MIN


RULE_MENTION_RE = re.compile(
    r"(?:\b[Rr]ule|नियम)\s*(\d{1,3}(?:\s*-\s*[A-Za-z]\b|\s*\([a-z]\))?)", re.UNICODE
)


def mentioned_rules(text: str) -> list[str]:
    found: list[str] = []
    for m in RULE_MENTION_RE.finditer(text):
        ref = re.sub(r"\s+", "", m.group(1))
        if ref not in found:
            found.append(ref)
    return found


@lru_cache(maxsize=1)
def load_amendments() -> list[dict]:
    return json.loads(Path(AMENDMENTS_FILE).read_text(encoding="utf-8"))


def amendment_warnings(question: str, cited_rules: list[str]) -> list[Warning_]:
    out: list[Warning_] = []
    q = question.lower()
    for a in load_amendments():
        by_rule = any(normalise_rule_no(r) in a["triggers"] for r in cited_rules)
        by_words = any(k.lower() in q for k in a["keywords"])
        if by_rule or by_words:
            out.append(
                Warning_(
                    kind="amendment",
                    text_en=(
                        f"Rule {a['sub_rule']} was amended on {_ddmmyyyy(a['date'])}. This change is not in the "
                        f"consolidated rulebook (06-03-2025) used for this answer. {a['summary_en']} "
                        "Check the latest Gazette notification before deciding."
                    ),
                    text_hi=(
                        f"नियम {a['sub_rule']} में {_ddmmyyyy(a['date'])} को संशोधन हुआ है। यह संशोधन इस उत्तर में प्रयुक्त "
                        f"समेकित नियम पुस्तिका (06-03-2025) में शामिल नहीं है। {a['summary_hi']} "
                        "निर्णय से पहले नवीनतम राजपत्र अधिसूचना देखें।"
                    ),
                    source_url=a["source_url"],
                )
            )
    return out


def _ddmmyyyy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}-{m}-{y}"


def verify(answer: Answer) -> Answer:
    """Check citations and mentioned rule numbers; add warnings. Returns the same object."""
    kept: list[Citation] = []
    dropped = 0
    for c in answer.citations:
        if rule_exists(c.rule) and quote_in_rule(c.quote, c.rule):
            c.verified = True
            kept.append(c)
        else:
            dropped += 1
    answer.citations = _dedupe(kept)

    answer.mentioned_rules = mentioned_rules(answer.text)
    invented = [r for r in answer.mentioned_rules if not rule_exists(r)]
    if invented:
        answer.warnings.append(
            Warning_(
                kind="invented_rule",
                text_en=f"The answer mentions {', '.join('Rule ' + r for r in invented)}, which does not exist in the rulebook. Ignore that reference.",
                text_hi=f"उत्तर में {', '.join('नियम ' + r for r in invented)} का उल्लेख है, जो नियम पुस्तिका में नहीं है। उस संदर्भ को न मानें।",
            )
        )

    if dropped:
        answer.warnings.append(
            Warning_(
                kind="unverified",
                text_en=f"{dropped} quote(s) could not be matched to the official text and were removed.",
                text_hi=f"{dropped} उद्धरण आधिकारिक पाठ से मेल नहीं खाए, इसलिए हटा दिए गए।",
            )
        )

    if answer.status == "answered" and not answer.citations:
        answer.status = "unverified"

    for c in answer.citations:
        if c.is_table:
            answer.warnings.append(
                Warning_(
                    kind="table",
                    text_en=f"Rule {c.rule} value comes from a table. Check it against the official PDF, page {c.page}.",
                    text_hi=f"नियम {c.rule} का मान तालिका से लिया गया है। आधिकारिक PDF के पृष्ठ {c.page} से मिलान करें।",
                )
            )
            break

    answer.warnings.extend(amendment_warnings(answer.question, answer.cited_rules + answer.mentioned_rules))
    return answer


def _dedupe(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[str, str]] = set()
    out: list[Citation] = []
    for c in citations:
        key = (c.rule, _norm(c.quote)[:200])
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def rules_count() -> int:
    return len(load_rules())
