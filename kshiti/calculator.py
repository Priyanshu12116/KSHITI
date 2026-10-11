"""USP-2: numbers come from code, not from the language model.

Every figure is looked up in data/tables/tables.json (checked against the official
PDF) and returned with its rule, page, the matched table row and the official
table text, which is then checked word for word against the rulebook.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from .rules import ROOT, get_rule
from .verify import quote_in_rule

TABLES_FILE = ROOT / "data" / "tables" / "tables.json"
Topic = Literal["front_setback", "rear_setback", "side_setback", "far", "height", "fee"]
ALL_TOPICS: tuple[Topic, ...] = ("front_setback", "rear_setback", "side_setback", "far", "height", "fee")


class CalcInputs(BaseModel):
    road_width_m: float | None = None
    building_height_m: float | None = None
    plot_area_sqm: float | None = None
    built_up_area_sqm: float | None = None
    frontage_m: float | None = None
    building_use: Literal["residential", "commercial", "shop_cum_residence", "public_semi_public", "other"] | None = None
    building_type: Literal["detached", "semi_detached", "row"] | None = None


class CalcResult(BaseModel):
    key: Topic
    label_en: str
    label_hi: str
    value: float | None
    unit: str
    display: str                       # "3.6 m", "Rs 3,000", "1.25"
    rule: str
    sub_rule: str
    page: int
    row_text: str = ""                 # the matched table row, verbatim
    quote: str = ""                    # the official table/paragraph text
    basis_en: str = ""
    basis_hi: str = ""
    assumptions_en: list[str] = Field(default_factory=list)
    assumptions_hi: list[str] = Field(default_factory=list)
    verified: bool = False


class MissingFor(BaseModel):
    key: Topic
    fields: list[str]


class CalcOutput(BaseModel):
    results: list[CalcResult] = Field(default_factory=list)
    missing: list[MissingFor] = Field(default_factory=list)
    notes_en: list[str] = Field(default_factory=list)
    notes_hi: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def tables() -> dict:
    return json.loads(TABLES_FILE.read_text(encoding="utf-8"))


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def table_text(rule_no: str, marker: str) -> str:
    """The official block of a rule that contains the table marker."""
    rule = get_rule(rule_no)
    for c in rule.chunks if rule else ():
        if marker in c.text:
            return c.text
    return ""


def _band(rows: list[dict], x: float) -> dict:
    """Pick the row with above < x <= upto (open ends allowed)."""
    for row in rows:
        lo, hi = row["above"], row["upto"]
        if (lo is None or x > lo) and (hi is None or x <= hi):
            return row
    raise ValueError(f"no row for {x}")


def _m(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".") if v % 1 else f"{v:.1f}"


def _a(v: float) -> str:
    """Areas: 250 -> '250', 187.5 -> '187.5'."""
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _rs(v: float) -> str:
    """Indian digit grouping: 125000 -> 1,25,000."""
    n = int(round(v))
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", head)
    return f"{head},{tail}"


def _finish(r: CalcResult) -> CalcResult:
    r.verified = bool(r.quote) and quote_in_rule(r.quote, r.rule) and (
        not r.row_text or _squash(r.row_text) in _squash(r.quote)
    )
    return r


def _is_tall(inp: CalcInputs) -> bool:
    return inp.building_height_m is not None and inp.building_height_m > 12.5


def front_setback(inp: CalcInputs) -> CalcResult:
    t = tables()["front_open_space"]
    row = _band(t["rows"], inp.road_width_m)
    return _finish(CalcResult(
        key="front_setback", label_en="Front open space (minimum)", label_hi="सामने का खुला स्थान (न्यूनतम)",
        value=row["value"], unit="m", display=f"{_m(row['value'])} m",
        rule=t["rule"], sub_rule=t["sub_rule"], page=t["page"], row_text=row["row_text"],
        quote=table_text(t["rule"], t["table_marker"]),
        basis_en=f"Street width {_m(inp.road_width_m)} m falls in the row \"{row['row_text']}\".",
        basis_hi=f"सड़क की चौड़ाई {_m(inp.road_width_m)} मीटर, तालिका की पंक्ति \"{row['row_text']}\" में आती है।",
    ))


def rear_setback(inp: CalcInputs) -> CalcResult:
    t = tables()["rear_open_space"]
    row = _band(t["rows"], inp.plot_area_sqm)
    disp = row.get("display") or f"{_m(row['value'])} m"
    return _finish(CalcResult(
        key="rear_setback", label_en="Rear open space (minimum)", label_hi="पीछे का खुला स्थान (न्यूनतम)",
        value=row["value"], unit="m", display=disp,
        rule=t["rule"], sub_rule=t["sub_rule"], page=t["page"], row_text=row["row_text"],
        quote=table_text(t["rule"], t["table_marker"]),
        basis_en=f"Plot area {_a(inp.plot_area_sqm)} sq m falls in the row \"{row['row_text']}\".",
        basis_hi=f"भूखण्ड क्षेत्रफल {_a(inp.plot_area_sqm)} वर्ग मीटर, तालिका की पंक्ति \"{row['row_text']}\" में आता है।",
    ))


def side_setback(inp: CalcInputs) -> CalcResult:
    t = tables()["side_open_space"]
    kind = t[inp.building_type]
    value = kind["value"]
    basis_en = {"detached": "Detached building: 3 m on both sides.",
                "semi_detached": "Semi-detached building: 3.0 m on one side.",
                "row": "Row-type building: no side open space is required."}[inp.building_type]
    basis_hi = {"detached": "पृथक भवन: दोनों ओर 3 मीटर।",
                "semi_detached": "अर्ध-पृथक भवन: एक ओर 3.0 मीटर।",
                "row": "पंक्तिबद्ध भवन: पार्श्व खुला स्थान आवश्यक नहीं।"}[inp.building_type]
    notes_en, notes_hi = [], []
    h, f = inp.building_height_m, inp.frontage_m
    if inp.building_type == "detached" and h is not None and f is not None and h <= 7 and f < 12:
        notes_en.append("Height up to 7 m and frontage below 12 m: one side may be reduced to 1.5 m.")
        notes_hi.append("ऊँचाई 7 मीटर तक और अग्रभाग 12 मीटर से कम: एक ओर 1.5 मीटर तक कम किया जा सकता है।")
    if inp.building_type == "semi_detached" and h is not None and f is not None and h <= 10 and f <= 10:
        value = 2.5
        notes_en.append("Height up to 10 m and frontage up to 10 m: may be reduced to 2.5 m.")
        notes_hi.append("ऊँचाई 10 मीटर तक और अग्रभाग 10 मीटर तक: 2.5 मीटर तक कम किया जा सकता है।")
    return _finish(CalcResult(
        key="side_setback", label_en="Side open space (minimum)", label_hi="पार्श्व खुला स्थान (न्यूनतम)",
        value=value, unit="m", display="None" if value == 0 else f"{_m(value)} m",
        rule=t["rule"], sub_rule=t["sub_rule"], page=t["page"], quote=kind["quote"],
        basis_en=" ".join([basis_en, *notes_en]), basis_hi=" ".join([basis_hi, *notes_hi]),
    ))


def far_limit(inp: CalcInputs) -> CalcResult:
    t = tables()["far"]
    use = inp.building_use or "residential"
    if use == "shop_cum_residence":
        use = "residential"
    rows = [r for r in t["rows"] if r["use"] == use]
    if not rows or len(rows) > 1:
        raise ValueError("FAR needs a single use group")
    row = rows[0]
    res = CalcResult(
        key="far", label_en="Floor Area Ratio (FAR)", label_hi="फर्शी क्षेत्र अनुपात (FAR)",
        value=row["value"], unit="", display=f"{row['value']:.2f}",
        rule=t["rule"], sub_rule=t["sub_rule"], page=t["page"], row_text=row["row_text"],
        quote=table_text(t["rule"], t["table_marker"]),
        basis_en=f"Table 8 gives FAR {row['value']:.2f} for {use.replace('_', ' ')} use.",
        basis_hi=f"तालिका 8 में {'आवासीय' if use == 'residential' else use} उपयोग के लिए FAR {row['value']:.2f} है।",
        assumptions_en=["The Development Plan of the town may set a different FAR (footnote to Table 8)."],
        assumptions_hi=["नगर की विकास योजना में भिन्न FAR हो सकता है (तालिका 8 की टिप्पणी)।"],
    )
    if inp.plot_area_sqm:
        max_bua = round(row["value"] * inp.plot_area_sqm, 2)
        res.basis_en += f" Maximum built-up area = {row['value']:.2f} × {_a(inp.plot_area_sqm)} sq m = {_a(max_bua)} sq m."
        res.basis_hi += f" अधिकतम निर्मित क्षेत्र = {row['value']:.2f} × {_a(inp.plot_area_sqm)} = {_a(max_bua)} वर्ग मीटर।"
        res.display = f"{row['value']:.2f} → {_a(max_bua)} sq m"
    return _finish(res)


def height_norms(inp: CalcInputs) -> CalcResult:
    """Which height band applies: up to 12.5 m (Rule 56) or Table 4 of Rule 42."""
    t = tables()["height_above_12_5"]
    ok = [
        r for r in t["rows"]
        if inp.road_width_m >= r["min_road_m"] and inp.plot_area_sqm >= r["min_plot_sqm"]
        and (inp.frontage_m is None or inp.frontage_m >= r["min_frontage_m"])
    ]
    quote = table_text(t["rule"], t["table_marker"])
    if not ok:
        first = t["rows"][0]
        return _finish(CalcResult(
            key="height", label_en="Maximum building height", label_hi="भवन की अधिकतम ऊँचाई",
            value=12.5, unit="m", display="12.5 m",
            rule=t["rule"], sub_rule=t["sub_rule"], page=t["page"], row_text=first["row_text"], quote=quote,
            basis_en=(f"Buildings above 12.5 m need at least a {_m(first['min_road_m'])} m road, a "
                      f"{first['min_plot_sqm']} sq m plot and {first['min_frontage_m']} m frontage (Rule 42, Table 4). "
                      "This plot does not meet that, so the norms for buildings up to 12.5 m apply."),
            basis_hi=(f"12.5 मीटर से ऊँचे भवन के लिए कम से कम {_m(first['min_road_m'])} मीटर सड़क, "
                      f"{first['min_plot_sqm']} वर्ग मीटर भूखण्ड और {first['min_frontage_m']} मीटर अग्रभाग चाहिए "
                      "(नियम 42, तालिका 4)। यह भूखण्ड इसे पूरा नहीं करता, इसलिए 12.5 मीटर तक के भवन के मानदंड लागू होंगे।"),
            assumptions_en=["The rules limit height and built-up area; they do not state a number of floors."],
            assumptions_hi=["नियम ऊँचाई और निर्मित क्षेत्र सीमित करते हैं; मंज़िलों की संख्या सीधे नहीं बताते।"],
        ))
    best = ok[-1]
    return _finish(CalcResult(
        key="height", label_en="Maximum building height", label_hi="भवन की अधिकतम ऊँचाई",
        value=float(best["max_height_m"]), unit="m", display=f"{best['max_height_m']} m",
        rule=t["rule"], sub_rule=t["sub_rule"], page=t["page"], row_text=best["row_text"], quote=quote,
        basis_en=(f"Road {_m(inp.road_width_m)} m and plot {_a(inp.plot_area_sqm)} sq m meet the row \"{best['row_text']}\": "
                  f"height up to {best['max_height_m']} m, FAR 1:{best['far']:.2f}, front M.O.S. {best['front_mos_m']} m, "
                  f"sides/rear {best['side_rear_mos_m']} m."),
        basis_hi=(f"सड़क {_m(inp.road_width_m)} मीटर और भूखण्ड {_a(inp.plot_area_sqm)} वर्ग मीटर पंक्ति \"{best['row_text']}\" "
                  f"में आते हैं: ऊँचाई {best['max_height_m']} मीटर तक, FAR 1:{best['far']:.2f}, सामने {best['front_mos_m']} मीटर, "
                  f"पार्श्व/पीछे {best['side_rear_mos_m']} मीटर।"),
        assumptions_en=["Frontage was not given; check it meets the row." if inp.frontage_m is None else "",
                        "The rules limit height and built-up area; they do not state a number of floors."],
        assumptions_hi=["अग्रभाग नहीं बताया गया; पंक्ति की शर्त जाँचें।" if inp.frontage_m is None else "",
                        "नियम ऊँचाई और निर्मित क्षेत्र सीमित करते हैं; मंज़िलों की संख्या सीधे नहीं बताते।"],
    ))


def fee(inp: CalcInputs) -> CalcResult:
    """Application fee (Rs 1/sq m) + residential permission fee slab (+50% where the table says so)."""
    t = tables()["permission_fee_residential"]
    app = tables()["application_fee"]
    area = inp.built_up_area_sqm
    assumed = False
    if area is None and inp.plot_area_sqm:
        area = round(tables()["far"]["rows"][0]["value"] * inp.plot_area_sqm, 2)
        assumed = True
    row = next(r for r in t["rows"] if r["to"] is None or area <= r["to"])
    permission = float(row["fee"])
    surcharge = (inp.building_use or "residential") in t["surcharge_50_percent_for"]
    if surcharge:
        permission *= 1.5
    application = round(app["rate_per_sqm"] * area, 2)
    total = permission + application
    res = CalcResult(
        key="fee", label_en="Building permission fees", label_hi="भवन अनुज्ञा शुल्क",
        value=total, unit="Rs", display=f"Rs {_rs(total)}",
        rule=t["rule"], sub_rule=f"{app['sub_rule']} + {t['sub_rule']}", page=t["page"], row_text=row["row_text"],
        quote=table_text(t["rule"], t["table_marker"]),
        basis_en=(f"Permission fee Rs {_rs(permission)} (built-up area {_a(area)} sq m, row \"{_squash(row['row_text'])}\""
                  f"{', plus 50% for this use' if surcharge else ''}) + application fee Rs {_rs(application)} "
                  f"(Rs 1.00 × {_a(area)} sq m, Rule 21(2)(ii), page {app['page']}) = Rs {_rs(total)}."),
        basis_hi=(f"अनुज्ञा शुल्क ₹{_rs(permission)} (निर्मित क्षेत्र {_a(area)} वर्ग मीटर, पंक्ति \"{_squash(row['row_text'])}\""
                  f"{', इस उपयोग हेतु 50% अतिरिक्त' if surcharge else ''}) + आवेदन शुल्क ₹{_rs(application)} "
                  f"(₹1.00 × {_a(area)} वर्ग मीटर, नियम 21(2)(ii), पृष्ठ {app['page']}) = ₹{_rs(total)}।"),
    )
    if assumed:
        res.assumptions_en.append(f"Built-up area not given: calculated for the maximum allowed by FAR ({_a(area)} sq m).")
        res.assumptions_hi.append(f"निर्मित क्षेत्र नहीं बताया गया: FAR के अनुसार अधिकतम ({_a(area)} वर्ग मीटर) पर गणना।")
    res.assumptions_en.append("Fees for high-rise buildings follow Rule 21(3)(c) and are not calculated here.")
    res.assumptions_hi.append("बहुमंज़िला (हाई-राइज़) भवनों का शुल्क नियम 21(3)(c) से है, यहाँ गणना नहीं की गई।")
    return _finish(res)


NEEDS: dict[Topic, tuple[str, ...]] = {
    "front_setback": ("road_width_m",),
    "rear_setback": ("plot_area_sqm",),
    "side_setback": ("building_type",),
    "far": (),
    "height": ("road_width_m", "plot_area_sqm"),
    "fee": ("plot_area_sqm|built_up_area_sqm",),
}
FUNCS = {"front_setback": front_setback, "rear_setback": rear_setback, "side_setback": side_setback,
         "far": far_limit, "height": height_norms, "fee": fee}


def _has(inp: CalcInputs, need: str) -> bool:
    return any(getattr(inp, f) is not None for f in need.split("|"))


def calculate(inp: CalcInputs, topics: list[str]) -> CalcOutput:
    out = CalcOutput()
    non_res = inp.building_use not in (None, "residential", "shop_cum_residence")
    if inp.building_use == "other":
        # Farm houses, cinemas, fuel stations, industry etc. have their own norms in their own rules.
        out.notes_en.append("This use has its own norms in the rules; the residential tables are not used. See the cited rule.")
        out.notes_hi.append("इस उपयोग के अपने मानदंड नियमों में हैं; आवासीय तालिकाएँ लागू नहीं की गईं। उद्धृत नियम देखें।")
        return out
    for topic in [t for t in ALL_TOPICS if t in topics]:
        if topic in ("front_setback", "rear_setback", "side_setback") and non_res:
            out.notes_en.append("Open spaces for non-residential buildings follow Rule 57; not calculated here.")
            out.notes_hi.append("गैर-आवासीय भवनों के खुले स्थान नियम 57 के अनुसार हैं; यहाँ गणना नहीं की गई।")
            continue
        if topic in ("front_setback", "rear_setback") and _is_tall(inp):
            out.notes_en.append("Above 12.5 m height the open spaces come from Rule 42, Table 4 (see height).")
            out.notes_hi.append("12.5 मीटर से अधिक ऊँचाई पर खुले स्थान नियम 42, तालिका 4 से तय होते हैं।")
            if "height" not in topics:
                topics = [*topics, "height"]
            continue
        if topic == "fee" and inp.building_use in ("public_semi_public", "other"):
            out.notes_en.append("Fees for this use are not calculated; see Rule 21(3)(b).")
            out.notes_hi.append("इस उपयोग का शुल्क यहाँ नहीं निकाला गया; नियम 21(3)(b) देखें।")
            continue
        missing = [n.split("|")[0] for n in NEEDS[topic] if not _has(inp, n)]
        if missing:
            out.missing.append(MissingFor(key=topic, fields=missing))
            continue
        try:
            out.results.append(FUNCS[topic](inp))
        except ValueError:
            continue
    if "height" in topics and not any(r.key == "height" for r in out.results) and not any(m.key == "height" for m in out.missing):
        missing = [n for n in NEEDS["height"] if not _has(inp, n)]
        if missing:
            out.missing.append(MissingFor(key="height", fields=missing))
        else:
            out.results.append(height_norms(inp))
    for r in out.results:
        r.assumptions_en = [a for a in r.assumptions_en if a]
        r.assumptions_hi = [a for a in r.assumptions_hi if a]
    if inp.building_use is None and any(r.key != "height" for r in out.results):
        out.notes_en.append("Use of the building was not stated: calculated for a residential building.")
        out.notes_hi.append("भवन का उपयोग नहीं बताया गया: आवासीय भवन मानकर गणना की गई।")
    return out
