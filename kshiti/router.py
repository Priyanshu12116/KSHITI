"""USP-4 fast lane: Cerebras reads the question in well under a second and
returns language, intent, calculator topics and the citizen's numbers.

Cerebras never writes the answer. Its numbers are only accepted if they appear in
the question itself, and a rule-based extractor covers the case where Cerebras is
slow, down or unsure.
"""
from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .calculator import ALL_TOPICS, CalcInputs
from .lang import detect_lang
from .rules import rule_titles

load_dotenv()

CEREBRAS_MODEL = os.environ.get("KSHITI_CEREBRAS_MODEL", "gpt-oss-120b")
TIMEOUT_S = float(os.environ.get("KSHITI_ROUTER_TIMEOUT", "4"))
Intent = Literal["calculation", "rule_question", "out_of_scope", "unclear"]
SQFT_TO_SQM = 0.09290304


class Route(BaseModel):
    lang: str = "en"
    intent: Intent = "rule_question"
    topics: list[str] = Field(default_factory=list)
    inputs: CalcInputs = Field(default_factory=CalcInputs)
    candidate_rules: list[str] = Field(default_factory=list)
    source: Literal["cerebras", "rules"] = "rules"
    seconds: float = 0.0
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- rule-based extractor
DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
NUM = r"(\d+(?:\.\d+)?)"
M = r"(?:m\b|mt\b|mtr|meter|metre|मीटर|मी\.?)"
AREA_SQM = r"(?:sq\.?\s*m(?:t|tr|eter|etre)?s?\b|sqm\b|square\s*met(?:er|re)s?|वर्ग\s*मीटर|वर्गमीटर|वर्ग\s*मी\.?)"
AREA_SQFT = r"(?:sq\.?\s*f(?:ee)?t\b|sqft\b|square\s*f(?:ee|oo)t|वर्ग\s*फ़?फुट|वर्ग\s*फीट)"
ROAD = r"(?:road|street|sadak|sarak|सड़क|सडक|रोड|मार्ग)"
TALL = r"(?:tall|high\b|height|uncha|unchai|ऊँचा|ऊंचा|ऊँचाई|ऊंचाई|ऊँची|ऊंची)"
BUILT = r"(?:built[\s-]*up|covered|construction|निर्मित|निर्माण)"
FRONTAGE = r"(?:frontage|अग्रभाग)"

TOPIC_WORDS = {
    "front_setback": r"\bfront\b|aage|आगे|सामने की (?:जगह|खुली)|front setback|front margin",
    "rear_setback": r"\brear\b|\bback\b|peeche|piche|पीछे",
    "side_setback": r"\bside\b|बगल|पार्श्व|side open",
    "far": (r"(?-i:\bFAR\b)|floor\s+area|how many floors|floors?\s+can|storeys?\s+can|built[\s-]*up\s+area\s+allowed|"
            r"kitni\s+(?:manzil|manjil)|कितनी\s+(?:मंज़िल|मंजिल)|कितने\s+(?:तल|फ्लोर)|एफएआर|फर्शी क्षेत्र"),
    "height": (r"max(?:imum)?\s+height|height\s+limit|how\s+(?:tall|high)|how many floors|floors?\s+can|storeys?\s+can|"
               r"kitni\s+(?:manzil|manjil|unchai)|कितनी\s+(?:मंज़िल|मंजिल|ऊँचाई|ऊंचाई)|(?:ऊँचाई|ऊंचाई)\s+कितनी|"
               r"कितने\s+(?:तल|फ्लोर)"),
    "fee": r"\bfees?\b|shulk|शुल्क|फीस|charges?|kitna paisa|पैसे",
}
OUT_OF_SCOPE = r"property\s*tax|house\s*tax|market\s*(rate|price|value)|land\s*(rate|price)|circle\s*rate|stamp\s*duty|registry|संपत्ति\s*कर|प्रॉपर्टी\s*टैक्स|बाजार\s*(भाव|दर|मूल्य)|बाज़ार\s*(भाव|दर|मूल्य)|ज़मीन\s*का\s*रेट|जमीन\s*का\s*रेट"
# Uses with their own norms elsewhere in the rules: the residential calculator must not answer for them.
SPECIAL_USE = (r"farm\s*house|agricultur|tourist facility|cinema|theat(?:re|er)|marriage\s+garden|mangal\s+karyalaya|"
               r"fuel|petrol|filling\s+station|multiplex|shopping\s+mall|\bmall\b|group\s+housing|industr|factory|"
               r"hostel|hospital|school|college|dharmshala|फार्म\s*हाउस|फ़ार्म\s*हाउस|कृषि|सिनेमा|मैरिज|विवाह\s*उद्यान|"
               r"पेट्रोल|उद्योग|औद्योगिक|कारखाना|अस्पताल|विद्यालय")
USE_WORDS = {
    "shop_cum_residence": r"shop[\s-]*cum[\s-]*residen|दुकान\s*सह\s*आवास",
    "commercial": r"commercial|\bshop|showroom|office|दुकान|वाणिज्यिक|कमर्शियल",
    "residential": r"\bhouse|\bhome|residen|\bghar\b|makaa?n|मकान|घर|आवास|आवासीय|bungalow|बंगला",
}
TYPE_WORDS = {
    "semi_detached": r"semi[\s-]*detached|अर्ध[\s-]*पृथक",
    "detached": r"\bdetached|पृथक|independent house",
    "row": r"row[\s-]*(type|house)|पंक्ति",
}


def _first(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.I)
    return float(m.group(1)) if m else None


def rule_based_route(question: str) -> Route:
    q = question.translate(DEV_DIGITS)
    ql = q.lower()
    inp = CalcInputs()
    notes: list[str] = []

    inp.road_width_m = (_first(rf"{NUM}\s*{M}\s*(?:wide|चौड़ी|चौड़ा|चौड़ाई|चौडी|ki|की|का)?\s*{ROAD}", q)
                        or _first(rf"{ROAD}\D{{0,25}}?{NUM}\s*{M}", q))
    inp.building_height_m = (_first(rf"{NUM}\s*{M}\s*(?:\w+\s*){{0,2}}{TALL}", q)
                             or _first(rf"{TALL}\D{{0,20}}?{NUM}\s*{M}", q))
    inp.frontage_m = _first(rf"{FRONTAGE}\D{{0,20}}?{NUM}\s*{M}", q) or _first(rf"{NUM}\s*{M}\s*{FRONTAGE}", q)
    built = _first(rf"{BUILT}\D{{0,25}}?{NUM}\s*{AREA_SQM}", q) or _first(rf"{NUM}\s*{AREA_SQM}\s*{BUILT}", q)
    plot = _first(rf"{NUM}\s*{AREA_SQM}", q)
    plot_ft = _first(rf"{NUM}\s*{AREA_SQFT}", q)
    if built is not None:
        inp.built_up_area_sqm = built
        plot = _first(rf"(?:plot|bhukhand|भूखण्ड|भूखंड|प्लॉट|प्लाट)\D{{0,25}}?{NUM}\s*{AREA_SQM}", q)
    if plot is None and plot_ft is not None:
        plot = round(plot_ft * SQFT_TO_SQM, 2)
        notes.append(f"{plot_ft:g} sq ft converted to {plot:g} sq m.")
    inp.plot_area_sqm = plot

    if re.search(SPECIAL_USE, ql, re.I):
        inp.building_use = "other"            # norms for this use are not in the residential tables
    else:
        for use, pat in USE_WORDS.items():
            if re.search(pat, ql, re.I):
                inp.building_use = use
                break
    for kind, pat in TYPE_WORDS.items():
        if re.search(pat, ql, re.I):
            inp.building_type = kind
            break

    topics = [t for t, pat in TOPIC_WORDS.items() if re.search(pat, q, re.I)]
    has_numbers = any(v is not None for v in (inp.road_width_m, inp.building_height_m, inp.plot_area_sqm, inp.built_up_area_sqm))
    if re.search(OUT_OF_SCOPE, ql, re.I):
        intent: Intent = "out_of_scope"
    elif topics and has_numbers:
        intent = "calculation"
    else:
        intent = "rule_question"
    return Route(lang=detect_lang(question), intent=intent, topics=topics, inputs=inp, source="rules", notes=notes)


# ---------------------------------------------------------------- Cerebras
ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "language": {"type": "string", "enum": ["en", "hi"]},
        "intent": {"type": "string", "enum": ["calculation", "rule_question", "out_of_scope", "unclear"]},
        "topics": {"type": "array", "items": {"type": "string", "enum": list(ALL_TOPICS)}},
        "road_width_m": {"type": "number"},
        "building_height_m": {"type": "number"},
        "plot_area_sqm": {"type": "number"},
        "built_up_area_sqm": {"type": "number"},
        "frontage_m": {"type": "number"},
        "building_use": {"type": "string", "enum": ["residential", "commercial", "shop_cum_residence", "public_semi_public", "other", "unknown"]},
        "building_type": {"type": "string", "enum": ["detached", "semi_detached", "row", "unknown"]},
        "candidate_rules": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["language", "intent", "topics", "road_width_m", "building_height_m", "plot_area_sqm",
                 "built_up_area_sqm", "frontage_m", "building_use", "building_type", "candidate_rules"],
    "additionalProperties": False,
}


@lru_cache(maxsize=1)
def _router_system() -> str:
    titles = "\n".join(f"{no}: {title}" for no, title in rule_titles())
    return (
        "You classify questions asked at the building-permission counter of the Bhopal Municipal Corporation "
        "about the MP Bhumi Vikas Rules 2012. Return JSON only.\n"
        "language: 'hi' for Hindi in Devanagari or Hindi written in English letters, else 'en'.\n"
        "intent: 'calculation' if the citizen gives numbers and asks for open space, FAR, floors, height or fees; "
        "'rule_question' for any other question the rulebook could answer; 'out_of_scope' only if the rulebook "
        "clearly cannot answer it (property tax, land prices, stamp duty, other departments); 'unclear' otherwise.\n"
        "topics: which of front_setback, rear_setback, side_setback, far, height, fee the citizen asks about "
        "(a question about floors means far and height).\n"
        "Numbers: copy only numbers written in the question, converted to metres or square metres. Use -1 when "
        "a number is not given. Never guess a number.\n"
        "building_use and building_type: only if the question says so, else 'unknown'.\n"
        "candidate_rules: up to 4 rule numbers from this list that most likely answer the question:\n" + titles
    )


def _numbers_in(text: str) -> set[float]:
    return {float(x) for x in re.findall(r"\d+(?:\.\d+)?", text.translate(DEV_DIGITS))}


def cerebras_route(question: str) -> Route | None:
    key = os.environ.get("CEREBRAS_API_KEY", "")
    if not key or key.startswith("dummy"):
        return None
    try:
        from cerebras.cloud.sdk import Cerebras

        t0 = time.perf_counter()
        out = Cerebras(api_key=key, timeout=TIMEOUT_S, max_retries=0).chat.completions.create(
            model=CEREBRAS_MODEL,
            messages=[{"role": "system", "content": _router_system()}, {"role": "user", "content": question}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": "route", "strict": True, "schema": ROUTER_SCHEMA}},
        )
        data = json.loads(out.choices[0].message.content)
        seconds = round(time.perf_counter() - t0, 2)
    except Exception:  # noqa: BLE001 - any failure falls back to the rule-based route
        return None

    present = _numbers_in(question)
    sqft = re.search(AREA_SQFT, question, re.I) is not None

    def num(field: str) -> float | None:
        v = data.get(field)
        if not isinstance(v, (int, float)) or v < 0:
            return None
        # Accept only numbers the citizen actually wrote (allowing sq ft -> sq m conversion).
        if float(v) in present or (sqft and any(abs(p * SQFT_TO_SQM - v) < 0.6 for p in present)):
            return float(v)
        return None

    use = data.get("building_use")
    kind = data.get("building_type")
    inputs = CalcInputs(
        road_width_m=num("road_width_m"), building_height_m=num("building_height_m"),
        plot_area_sqm=num("plot_area_sqm"), built_up_area_sqm=num("built_up_area_sqm"), frontage_m=num("frontage_m"),
        building_use=None if use in (None, "unknown") else use,
        building_type=None if kind in (None, "unknown") else kind,
    )
    known = {no for no, _ in rule_titles()}
    return Route(
        lang=data.get("language", detect_lang(question)), intent=data.get("intent", "unclear"),
        topics=[t for t in data.get("topics", []) if t in ALL_TOPICS], inputs=inputs,
        candidate_rules=[r for r in data.get("candidate_rules", []) if r in known][:4],
        source="cerebras", seconds=seconds,
    )


def route(question: str) -> Route:
    """Cerebras first; the rule-based extractor fills gaps and is the fallback."""
    t0 = time.perf_counter()
    base = rule_based_route(question)
    fast = cerebras_route(question)
    if fast is None:
        base.seconds = round(time.perf_counter() - t0, 3)
        return base
    for field in CalcInputs.model_fields:
        if getattr(fast.inputs, field) is None and getattr(base.inputs, field) is not None:
            setattr(fast.inputs, field, getattr(base.inputs, field))
    fast.topics = [t for t in ALL_TOPICS if t in set(fast.topics) | set(base.topics)]
    if base.inputs.building_use == "other":
        fast.inputs.building_use = "other"     # special uses never get residential figures
    if base.intent == "out_of_scope":
        fast.intent = "out_of_scope"
    elif fast.intent == "out_of_scope" and base.topics:
        fast.intent = "rule_question"          # never drop a question that names a rule topic
    fast.notes = base.notes
    return fast
