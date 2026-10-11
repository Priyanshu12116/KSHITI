"""The Claude answer engine (deep lane).

One request per question: the whole rulebook (one citable document per rule,
cached), the clerk's question, and two tools for "not found" and "missing facts".
The reply's citations are mapped back to rule, page and exact source text, then
checked by verify.py before anything is shown.
"""
from __future__ import annotations

import os
import time
from collections.abc import Callable
from functools import lru_cache

import anthropic
from dotenv import load_dotenv

from .lang import detect_lang
from .models import Answer, Citation, MissingInput, Timing, Usage
from .prompts import SYSTEM_PROMPT, TOOLS
from .rules import RULES_VERSION, load_rules, rule_order
from .verify import verify

load_dotenv()

MODEL = os.environ.get("KSHITI_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("KSHITI_EFFORT", "medium")       # low | medium | high
MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"           # fallbacks="default" form


@lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=2, timeout=120.0)


@lru_cache(maxsize=1)
def rule_documents() -> tuple[dict, ...]:
    """One custom-content document per rule, in book order; the last one carries
    the cache breakpoint so tools + system + all rules are cached together."""
    docs = []
    for no in rule_order():
        r = load_rules()[no]
        docs.append(
            {
                "type": "document",
                "source": {"type": "content", "content": [{"type": "text", "text": c.text} for c in r.chunks]},
                "title": f"Rule {r.rule}: {r.title}",
                "context": f"{RULES_VERSION}. {r.part}. PDF pages {r.page_start} to {r.page_end}.",
                "citations": {"enabled": True},
            }
        )
    docs[-1] = {**docs[-1], "cache_control": {"type": "ephemeral"}}
    return tuple(docs)


def build_request(question: str, context: str = "") -> dict:
    """The full request body (without streaming/beta options). Pure: no network.

    `context` (calculator results) goes after the cached rulebook, so caching still works."""
    text = f"Question at the counter:\n{question.strip()}"
    if context:
        text += f"\n\n{context}"
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "tools": TOOLS,
        "output_config": {"effort": EFFORT},
        "messages": [
            {
                "role": "user",
                "content": [
                    *rule_documents(),
                    {"type": "text", "text": text},
                ],
            }
        ],
    }


def _citation_from(raw, supports: str) -> Citation | None:
    """Map a content_block_location citation to rule, page and exact text."""
    if getattr(raw, "type", "") != "content_block_location":
        return None
    order = rule_order()
    doc_i = getattr(raw, "document_index", -1)
    if not 0 <= doc_i < len(order):
        return None
    rule = load_rules()[order[doc_i]]
    start = getattr(raw, "start_block_index", 0)
    end = max(getattr(raw, "end_block_index", start + 1), start + 1)
    chunks = rule.chunks[start:end]
    if not chunks:
        return None
    return Citation(
        rule=rule.rule,
        title=rule.title,
        part=rule.part,
        page=chunks[0].page,
        quote=getattr(raw, "cited_text", "") or "\n".join(c.text for c in chunks),
        supports=supports.strip(),
        is_table=any(c.is_table for c in chunks),
    )


def parse_message(question: str, message) -> Answer:
    """Turn the final API message into an Answer (before verification)."""
    ans = Answer(question=question, lang=detect_lang(question), model=getattr(message, "model", MODEL))
    parts: list[str] = []
    for block in message.content:
        btype = getattr(block, "type", "")
        if btype == "text":
            parts.append(block.text)
            for raw in getattr(block, "citations", None) or []:
                c = _citation_from(raw, block.text)
                if c:
                    ans.citations.append(c)
        elif btype == "tool_use" and block.name == "report_not_found":
            ans.status = "not_found"
            ans.not_found_reason = block.input.get("reason", "")
            ans.suggestion = block.input.get("suggestion", "")
        elif btype == "tool_use" and block.name == "ask_missing_inputs":
            ans.status = "need_inputs"
            ans.not_found_reason = block.input.get("prompt", "")
            ans.missing_inputs = [MissingInput(**m) for m in block.input.get("missing", [])]
    ans.text = "".join(parts).strip()
    if ans.text:
        ans.lang = detect_lang(ans.text)

    if message.stop_reason == "refusal":
        ans.status, ans.error = "error", "The model declined this request. Please rephrase the question."
    elif message.stop_reason == "max_tokens":
        ans.error = "The answer was cut short. Please ask a narrower question."

    u = getattr(message, "usage", None)
    if u:
        ans.usage = Usage(
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )
    return ans


def _stream(req: dict, on_text: Callable[[str], None] | None, t0: float, timing: Timing):
    """Stream with server-side refusal fallback; retry without it if the beta is rejected."""
    def run(stream_ctx):
        with stream_ctx as stream:
            for event in stream:
                if event.type == "content_block_delta" and getattr(event.delta, "type", "") == "text_delta":
                    if timing.first_token_s is None:
                        timing.first_token_s = round(time.perf_counter() - t0, 2)
                    if on_text:
                        on_text(event.delta.text)
            return stream.get_final_message()

    try:
        return run(_client().beta.messages.stream(**req, betas=[FALLBACK_BETA], fallbacks="default"))
    except anthropic.BadRequestError as e:
        if "fallback" not in str(e).lower():
            raise
        return run(_client().messages.stream(**req))


def ask(question: str, on_text: Callable[[str], None] | None = None, context: str = "") -> Answer:
    """Answer one counter question. Never raises: errors come back as status='error'."""
    t0 = time.perf_counter()
    timing = Timing()
    question = (question or "").strip()
    if not question:
        return Answer(question="", status="error", error="Please type a question.")
    try:
        message = _stream(build_request(question, context), on_text, t0, timing)
        ans = verify(parse_message(question, message))
    except anthropic.AuthenticationError:
        ans = Answer(question=question, lang=detect_lang(question), status="error",
                     error="The Claude API key is missing or invalid. Add ANTHROPIC_API_KEY to the .env file.")
    except anthropic.RateLimitError:
        ans = Answer(question=question, lang=detect_lang(question), status="error",
                     error="Too many requests right now. Please try again in a minute.")
    except anthropic.APIConnectionError:
        ans = Answer(question=question, lang=detect_lang(question), status="error",
                     error="No connection to the Claude service. Check the internet connection.")
    except anthropic.APIStatusError as e:
        ans = Answer(question=question, lang=detect_lang(question), status="error",
                     error=f"The Claude service returned an error ({e.status_code}). Please try again.")
    timing.total_s = round(time.perf_counter() - t0, 2)
    ans.timing = timing
    return ans
