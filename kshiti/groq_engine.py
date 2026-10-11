"""Answer engine on Groq (gpt-oss), used when no Anthropic key is configured.

Groq's free tier allows about 8,000 tokens per minute per model, so the whole
rulebook cannot be sent with every question. Instead:

  1. gpt-oss-20b reads the 106 rule titles and picks the likely rules, and turns the
     question into English search terms (works for Hindi and Hinglish too);
  2. a BM25 search over the 867 rule blocks picks the best paragraphs from those
     rules (plus the rules behind any calculated figure), within a fixed budget;
  3. gpt-oss-120b answers in strict JSON, quoting the numbered sources;
  4. every quote is then checked word for word against the official text by
     verify.py, exactly as for the Claude engine. A quote that does not match is removed.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from collections import Counter
from collections.abc import Callable
from functools import lru_cache

import httpx
from dotenv import load_dotenv

from .lang import detect_lang
from .models import Answer, Citation, MissingInput, Timing, Usage
from .rules import RULES_VERSION, Chunk, get_rule, load_rules, rule_titles
from .verify import load_amendments, verify

load_dotenv()

URL = "https://api.groq.com/openai/v1/chat/completions"
ANSWER_MODEL = os.environ.get("KSHITI_GROQ_MODEL", "openai/gpt-oss-120b")
ROUTER_MODEL = os.environ.get("KSHITI_GROQ_ROUTER_MODEL", "openai/gpt-oss-20b")
SOURCE_BUDGET = int(os.environ.get("KSHITI_GROQ_SOURCE_CHARS", "9500"))
TOPIC_RULES = {"front_setback": ["56"], "rear_setback": ["56"], "side_setback": ["56"], "far": ["61"],
               "height": ["42", "65"], "fee": ["21"]}


def available() -> bool:
    k = os.environ.get("GROQ_API_KEY", "")
    return bool(k) and not k.startswith("dummy")


def model_label() -> str:
    return f"groq:{ANSWER_MODEL}"


# ------------------------------------------------------------------ BM25 over rule blocks
WORD = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
STOP = set("the of and to in a or be shall for by any as on with is which such that this from at an under it are "
           "not may have has its these those than other into per all no each".split())


def _tokens(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOP and len(w) > 1]


@lru_cache(maxsize=1)
def _index():
    chunks: list[Chunk] = [c for r in load_rules().values() for c in r.chunks]
    docs = [Counter(_tokens(c.text + " " + get_rule(c.rule).title)) for c in chunks]
    df = Counter(w for d in docs for w in d)
    avg = sum(sum(d.values()) for d in docs) / len(docs)
    return chunks, docs, df, avg


def bm25(query: str, k1: float = 1.4, b: float = 0.7) -> list[tuple[float, Chunk]]:
    chunks, docs, df, avg = _index()
    n = len(chunks)
    q = _tokens(query)
    out = []
    for c, d in zip(chunks, docs):
        dl = sum(d.values())
        s = 0.0
        for w in q:
            if w in d:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * d[w] * (k1 + 1) / (d[w] + k1 * (1 - b + b * dl / avg))
        if s > 0:
            out.append((s, c))
    return sorted(out, key=lambda x: -x[0])


# ------------------------------------------------------------------ Groq calls
class RateLimited(Exception):
    pass


def _post(body: dict, timeout: float = 60.0) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}", "Content-Type": "application/json"}
    for attempt in range(3):
        r = httpx.post(URL, json=body, headers=headers, timeout=timeout)
        if r.status_code == 429 and attempt < 2:
            wait = float(r.headers.get("retry-after", "8"))
            time.sleep(min(max(wait, 2.0), 30.0))
            continue
        if r.status_code == 429:
            raise RateLimited(r.text[:200])
        r.raise_for_status()
        return r.json()
    raise RateLimited("rate limited")


def _json_call(model: str, system: str, user: str, schema: dict, name: str, max_tokens: int, effort: str = "low") -> tuple[dict, dict]:
    data = _post({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}},
        "max_completion_tokens": max_tokens,
        "reasoning_effort": effort,
        "temperature": 0.1,
    })
    content = data["choices"][0]["message"].get("content") or "{}"
    return json.loads(content), data.get("usage", {})


PICK_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {"type": "array", "items": {"type": "string"}},
        "search_terms": {"type": "string"},
        "in_scope": {"type": "boolean"},
    },
    "required": ["rules", "search_terms", "in_scope"],
    "additionalProperties": False,
}


@lru_cache(maxsize=1)
def _pick_system() -> str:
    titles = "\n".join(f"{no}: {t}" for no, t in rule_titles())
    return ("You help find rules in the MP Bhumi Vikas Rules 2012 for a building-permission counter in Bhopal. "
            "Given a question (English, Hindi, or Hindi in English letters), return JSON with: rules = up to 4 rule "
            "numbers from the list below most likely to answer it (best first); search_terms = 6 to 15 English keywords "
            "a rulebook would use for this question (translate Hindi); in_scope = false only if the rulebook clearly "
            "cannot answer it (property tax, land prices, other departments).\nRules:\n" + titles)


def pick_rules(question: str) -> tuple[list[str], str, bool, dict]:
    data, usage = _json_call(ROUTER_MODEL, _pick_system(), question, PICK_SCHEMA, "pick", 700)
    known = set(load_rules())
    rules = [r.strip() for r in data.get("rules", []) if r.strip() in known][:4]
    return rules, data.get("search_terms", ""), bool(data.get("in_scope", True)), usage


def select_sources(question: str, picked: list[str], terms: str, forced: list[str]) -> list[Chunk]:
    """Best blocks from picked + forced rules first, then the best of the rest, within the budget."""
    query = f"{terms} {question if detect_lang(question) == 'en' else ''}"
    ranked = bm25(query)
    priority = list(dict.fromkeys(forced + picked))
    chosen: list[Chunk] = []
    used = 0

    def add(c: Chunk) -> bool:
        nonlocal used
        if c in chosen or used + len(c.text) > SOURCE_BUDGET:
            return False
        chosen.append(c)
        used += len(c.text)
        return True

    for rule in priority:                                  # best 2 blocks of each priority rule
        in_rule = [c for _, c in ranked if c.rule == rule][:2] or list(get_rule(rule).chunks[:1])
        for c in in_rule:
            add(c)
    for _, c in ranked[:30]:                               # then the strongest blocks anywhere
        if used > SOURCE_BUDGET * 0.92:
            break
        add(c)
    return chosen


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["answered", "not_found", "need_inputs"]},
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {
            "type": "object",
            "properties": {"source": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["source", "quote"], "additionalProperties": False}},
        "not_found_reason": {"type": "string"},
        "suggestion": {"type": "string"},
        "missing": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": ["road_width_m", "building_height_m", "plot_area_sqm", "built_up_area_sqm",
                                                     "building_use", "number_of_floors", "other"]},
                "label": {"type": "string"}, "unit": {"type": "string"}},
            "required": ["field", "label", "unit"], "additionalProperties": False}},
    },
    "required": ["status", "answer", "citations", "not_found_reason", "suggestion", "missing"],
    "additionalProperties": False,
}


def _answer_system() -> str:
    amend = "\n".join(f"- {a['date']}: Rule {a['sub_rule']} amended. {a['summary_en']} (Summary only; not in the sources; never quote it.)"
                      for a in load_amendments())
    return f"""You are Kshiti, the rulebook assistant at the building-permission counter of the Bhopal Municipal Corporation. A clerk types the citizen's question. You point to the rule; the clerk decides.

Your only source is the numbered SOURCES: paragraphs and tables from the Madhya Pradesh Bhumi Vikas Rules, 2012 ({RULES_VERSION}). Never use general knowledge.

Return JSON:
- status "answered": answer in 2 to 5 short sentences. Give the number first with its unit, then the condition that makes it apply, and ALWAYS name the rule and sub-rule in the sentence (for example "3.6 m, because the street is more than 9 m and up to 12 m wide (Rule 56(1)(a))"). citations: for every fact, the source id (S1, S2...) and a quote copied EXACTLY, character for character, from that source (one sentence or one table row is enough; never paraphrase inside a quote).
- status "not_found": the sources do not answer the question (for example property tax, land prices). Give not_found_reason (one sentence) and a short suggestion of the kind of office to ask, or "".
- status "need_inputs": only when the question asks for one specific figure for the citizen's own case and a fact that changes it is missing. List missing fields. If a general answer is useful, prefer "answered" and say which fact decides the exact figure.
Language: answer in the language of the question. Devanagari Hindi, or Hindi written in English letters, gets an answer in Hindi (Devanagari). Keep rule numbers, units and figures in digits. Quotes stay exactly as in the sources (English).
Inserted rules (12-A, 17-a, 25(A), 26-A, 42-A, 93(a)) sit inside the text of the rule before them but are separate provisions: for example Rule 17 is the farm house and 17-a is the agricultural tourist facility. Never mix their figures; use only the clauses of the provision the question is about.
Tables: match the citizen's values to row boundaries exactly ("up to", "more than", "above"). If calculator results are given, use exactly those figures, name exactly the rule given for each figure (for example FAR for a house is Rule 61, Table 8; never cite another rule that happens to show the same number, such as cinema norms), and cite the source that contains that table.
Plain text in "answer": no markdown, no headings, no disclaimers.
Known amendments after the rulebook (not in the sources):
{amend}
If a question touches one of these, answer from the sources first, then add one sentence that the provision was amended on that date, with the summary."""


def _sources_text(chunks: list[Chunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        r = get_rule(c.rule)
        parts.append(f"[S{i}] Rule {r.rule}: {r.title} (page {c.page})\n{c.text}")
    return "\n\n".join(parts)


def ask(question: str, on_text: Callable[[str], None] | None = None, context: str = "",
        forced_rules: list[str] | None = None) -> Answer:
    t0 = time.perf_counter()
    timing = Timing()
    q = (question or "").strip()
    ans = Answer(question=q, lang=detect_lang(q), model=model_label())
    try:
        picked, terms, in_scope, u1 = pick_rules(q)
        chunks = select_sources(q, picked, terms, forced_rules or [])
        want = "Hindi (Devanagari script)" if ans.lang == "hi" else "English only (no Hindi words)"
        user = (f"QUESTION:\n{q}\n\nANSWER LANGUAGE: {want}. Write the answer as plain sentences, not a numbered list.\n\n"
                + (f"{context}\n\n" if context else "") + f"SOURCES:\n{_sources_text(chunks)}")
        if not in_scope and not forced_rules:
            user += "\n\nNote: a first reading suggests this may be outside the rules. Say not_found unless the sources clearly answer it."
        data, u2 = _json_call(ANSWER_MODEL, _answer_system(), user, ANSWER_SCHEMA, "answer", 3000, effort="medium")
        timing.first_token_s = round(time.perf_counter() - t0, 2)
    except RateLimited:
        ans.status, ans.error = "error", "The free Groq quota is busy for a moment (8,000 tokens per minute). Please try again in about a minute."
        timing.total_s = round(time.perf_counter() - t0, 2)
        ans.timing = timing
        return ans
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        ans.status = "error"
        ans.error = ("The Groq API key is missing or invalid. Check GROQ_API_KEY in the .env file." if code in (401, 403)
                     else f"The Groq service returned an error ({code}). Please try again.")
        ans.timing = timing
        return ans
    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
        ans.status, ans.error = "error", f"Could not reach the answer service ({type(e).__name__}). Check the internet connection."
        ans.timing = timing
        return ans

    status = data.get("status", "answered")
    if status == "not_found":
        ans.status = "not_found"
        ans.not_found_reason = data.get("not_found_reason", "")
        ans.suggestion = data.get("suggestion", "")
    elif status == "need_inputs" and data.get("missing"):
        ans.status = "need_inputs"
        ans.not_found_reason = data.get("answer") or data.get("not_found_reason", "")
        ans.missing_inputs = [MissingInput(**m) for m in data["missing"]]
    else:
        ans.text = (data.get("answer") or "").strip()
        for cit in data.get("citations", []):
            m = re.match(r"\s*S?(\d+)", cit.get("source", ""))
            if not m or not 1 <= int(m.group(1)) <= len(chunks):
                ans.citations.append(Citation(rule="?", title="", part="", page=0, quote=cit.get("quote", "")))
                continue
            c = chunks[int(m.group(1)) - 1]
            r = get_rule(c.rule)
            quote = (cit.get("quote") or "").strip()
            if len(quote) < 12:
                quote = c.text                                     # the whole cited block
            ans.citations.append(Citation(rule=r.rule, title=r.title, part=r.part, page=c.page, quote=quote,
                                          supports=ans.text[:240], is_table=c.is_table))
        if ans.text:
            ans.lang = detect_lang(ans.text)
            if on_text:
                on_text(ans.text)
    ans.usage = Usage(input_tokens=u1.get("prompt_tokens", 0) + u2.get("prompt_tokens", 0),
                      output_tokens=u1.get("completion_tokens", 0) + u2.get("completion_tokens", 0))
    verify(ans)
    timing.total_s = round(time.perf_counter() - t0, 2)
    ans.timing = timing
    return ans
