"""USP-6: the answer slip. Every PDF Kshiti makes uses one template (KshitiPDF):
same header, same section blocks, same footer, all text inside the frame.

The slip carries what the problem statement asks for: the question, a short
answer in the question's language, the rule number and the exact source text,
"not found" when the rules are silent, and which version of the rules was used.
It also carries a receipt ID, a QR code and the rulebook fingerprint so the
answer can be traced later.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import datetime, timedelta, timezone
import qrcode
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from .pipeline import Result
from .rules import ROOT, RULES_VERSION, rulebook_fingerprint

FONTS = ROOT / "app" / "static" / "fonts"
LOGOS = ROOT / "app" / "static" / "logos"
LOG = ROOT / "logs" / "receipts.jsonl"
IST = timezone(timedelta(hours=5, minutes=30))

INK = (17, 17, 17)
G700 = (61, 61, 61)
G500 = (107, 107, 107)
G300 = (207, 207, 207)
G100 = (243, 243, 243)
WHITE = (255, 255, 255)
O600 = (234, 88, 12)
O700 = (194, 65, 12)
O100 = (255, 237, 213)

DEV_RE = re.compile(r"[ऀ-ॿ]")


def receipt_id(result: Result, when: datetime) -> str:
    h = hashlib.sha256(f"{result.question}|{result.answer.text}|{when.isoformat()}".encode()).hexdigest()
    return f"KSH-{when:%Y%m%d}-{h[:4].upper()}"


class KshitiPDF(FPDF):
    """The single Kshiti document template."""

    def __init__(self, receipt: str, when: datetime, fingerprint: str, title: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.receipt, self.when, self.fp, self.doc_title = receipt, when, fingerprint, title
        self.set_margins(14, 14, 14)
        self.set_auto_page_break(True, margin=26)
        self.add_font("sans", "", str(FONTS / "NotoSans-Regular.ttf"))
        self.add_font("sans", "B", str(FONTS / "NotoSans-Bold.ttf"))
        self.add_font("deva", "", str(FONTS / "NotoSansDevanagari-Regular.ttf"))
        self.add_font("deva", "B", str(FONTS / "NotoSansDevanagari-Bold.ttf"))
        self.add_font("mono", "", str(FONTS / "NotoSansMono-Regular.ttf"))
        self.add_font("mono", "B", str(FONTS / "NotoSansMono-Bold.ttf"))
        self.add_font("brand", "", str(FONTS / "Tillana-Bold.ttf"))
        self.set_text_shaping(True)
        self.set_fallback_fonts(["deva"], exact_match=False)
        self.set_title(f"Kshiti {title} {receipt}")
        self.set_author("Kshiti · THETA172")
        self.set_creator("Kshiti · Bhumi Vikas Sahayak")
        self.alias_nb_pages()

    # -------------------------------------------------------------- frame
    def header(self) -> None:
        self.set_draw_color(*INK)
        self.set_line_width(0.6)
        self.rect(8, 8, 194, 281)                                 # page frame
        y = 12
        self.image(str(LOGOS / "emblem-of-india.png"), x=14, y=y, h=17)
        self.image(str(LOGOS / "emblem-of-madhya-pradesh.png"), x=26, y=y + 0.5, h=16)
        self.set_xy(46, y - 1)
        self.set_font("brand", size=21)
        self.set_text_color(*INK)
        self.cell(0, 10, "क्षिति  Kshiti", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_xy(46, y + 9)
        self.set_font("sans", "B", 8.5)
        self.set_text_color(*G700)
        self.cell(0, 4.5, "BHUMI VIKAS SAHAYAK  ·  भूमि विकास सहायक", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(46)
        self.set_font("sans", "", 8)
        self.cell(0, 4, "Building Permission Counter · Bhopal Municipal Corporation · Government of Madhya Pradesh")
        # receipt block (right)
        self.set_xy(132, y)
        self.set_font("sans", "B", 7)
        self.set_text_color(*G500)
        self.cell(44, 4, self.doc_title.upper(), align="R", new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_x(132)
        self.set_font("mono", "B", 9)
        self.set_text_color(*INK)
        self.cell(44, 5, self.receipt, align="R", new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_x(132)
        self.set_font("sans", "", 7.5)
        self.cell(44, 4, f"{self.when:%d-%m-%Y %H:%M} IST", align="R")
        self.image(self._qr(), x=179, y=y - 1, w=19, h=19)
        # orange rule
        self.set_fill_color(*O600)
        self.rect(8, 33, 194, 2.2, style="F")
        self.set_draw_color(*INK)
        self.set_line_width(0.4)
        self.line(8, 33, 202, 33)
        self.set_y(40)

    def footer(self) -> None:
        self.set_y(-24)
        self.set_draw_color(*INK)
        self.set_line_width(0.4)
        self.line(14, self.get_y(), 196, self.get_y())
        self.ln(1.5)
        self.set_font("sans", "", 7)
        self.set_text_color(*G700)
        self.multi_cell(0, 3.4, f"Rules used: {RULES_VERSION} (MP Town and Country Planning). Rulebook fingerprint SHA-256 {self.fp[:24]}…",
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("sans", "B", 7)
        self.set_text_color(*INK)
        self.multi_cell(0, 3.6, "For information only. Kshiti points to the rule; the competent authority decides. Not legal advice. "
                        "केवल जानकारी हेतु; अंतिम निर्णय सक्षम प्राधिकारी का।", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("sans", "", 7)
        self.set_text_color(*G500)
        self.cell(0, 3.6, "Kshiti · THETA172 · open source (MIT)")
        self.cell(0, 3.6, f"Page {self.page_no()}/{{nb}}", align="R")

    def _qr(self) -> io.BytesIO:
        payload = f"KSHITI|{self.receipt}|{self.when:%Y-%m-%dT%H:%M}+05:30|rules:{self.fp[:16]}"
        img = qrcode.make(payload, box_size=6, border=1)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    # -------------------------------------------------------------- blocks
    def label(self, en: str, hi: str, color=INK) -> None:
        if self.get_y() + 28 > self.page_break_trigger:
            self.add_page()                       # never leave a section title alone at a page bottom
        self.ln(2.5)
        y = self.get_y()
        self.set_fill_color(*O600)
        self.set_draw_color(*INK)
        self.set_line_width(0.4)
        self.rect(14, y + 1, 3, 3, style="DF")
        self.set_xy(19.5, y)
        self.set_font("sans", "B", 8.5)
        self.set_text_color(*color)
        self.cell(0, 5, f"{en.upper()}  ·  {hi}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(0.8)
        self._last_label = (self.page_no(), y - 2.5, self.get_y(), en, hi, color)

    def _move_to_new_page(self) -> None:
        """Start a new page; if a section title was just drawn, carry it over instead of leaving it alone."""
        last = getattr(self, "_last_label", None)
        if last and last[0] == self.page_no() and abs(last[2] - self.get_y()) < 0.01:
            _, y0, y1, en, hi, color = last
            self.set_fill_color(*WHITE)
            self.rect(12, y0, 186, y1 - y0, style="F")          # remove the stranded title
            self.add_page()
            self.label(en, hi, color)
        else:
            self.add_page()

    def box(self, text: str, *, font=("sans", "", 10.5), fill=WHITE, border=INK, shadow=True, lh=5.4, pad=3.2, dashed=False) -> None:
        """A bordered block with a hard offset shadow, like the cards in the interface."""
        w = 182 - (1.6 if shadow else 0)
        self.set_font(*font)
        h = self.multi_cell(w - 2 * pad, lh, text, dry_run=True, output="HEIGHT") + 2 * pad
        if self.get_y() + h > self.page_break_trigger and h < 200:
            self._move_to_new_page()
            self.set_font(*font)
        x, y = 14, self.get_y()
        if h < 200:
            if shadow:
                self.set_fill_color(*border)
                self.rect(x + 1.6, y + 1.6, w, h, style="F")
            self.set_fill_color(*fill)
            self.set_draw_color(*border)
            self.set_line_width(0.5)
            if dashed:
                self.set_dash_pattern(dash=1.2, gap=1)
            self.rect(x, y, w, h, style="DF")
            self.set_dash_pattern()
        self.set_xy(x + pad, y + pad)
        self.set_text_color(*INK)
        self.multi_cell(w - 2 * pad, lh, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(max(self.get_y(), y + h) + (2.6 if shadow else 1.6))

    def figures(self, rows: list[tuple[str, str, str, str]]) -> None:
        """Calculated figures as a 4-column table: item, value, rule/page, table row."""
        widths = (54, 30, 46, 52)
        self.set_draw_color(*INK)
        self.set_line_width(0.4)
        self.set_fill_color(*INK)
        self.set_text_color(*WHITE)
        self.set_font("sans", "B", 8)
        for w, head in zip(widths, ("Item · मद", "Value · मान", "Rule · Page", "Table row (official)")):
            self.cell(w, 6, f" {head}", border=1, fill=True)
        self.ln()
        for i, (item, value, rule, row) in enumerate(rows):
            fill = O100 if i == 0 else WHITE
            self.set_fill_color(*fill)
            self.set_text_color(*INK)
            y = self.get_y()
            heights = []
            for w, txt, f in zip(widths, (item, value, rule, row), (("sans", "", 8.5), ("sans", "B", 11), ("sans", "", 8), ("mono", "", 7))):
                self.set_font(*f)
                heights.append(self.multi_cell(w - 2, 4.4, txt, dry_run=True, output="HEIGHT"))
            h = max(heights) + 2.4
            if y + h > self.page_break_trigger:
                self.add_page()
                y = self.get_y()
            x = 14
            for w, txt, f in zip(widths, (item, value, rule, row), (("sans", "", 8.5), ("sans", "B", 11), ("sans", "", 8), ("mono", "", 7))):
                self.rect(x, y, w, h, style="DF")
                self.set_xy(x + 1, y + 1.2)
                self.set_font(*f)
                self.multi_cell(w - 2, 4.4, txt)
                x += w
            self.set_y(y + h)
        self.ln(3)


def _pdf_value(display: str) -> str:
    """'1.25 → 250 sq m' -> '250 sq m (FAR 1.25)'; the PDF fonts have no arrow glyph."""
    if " → " in display:
        far, area = display.split(" → ", 1)
        return f"{area}\n(FAR {far})"
    return display


def _clean_quote(q: str) -> str:
    lines = [ln.rstrip() for ln in q.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    indent = min((len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()), default=0)
    return "\n".join(ln[indent:] for ln in lines)


def build_slip(result: Result, when: datetime | None = None) -> tuple[bytes, str]:
    when = when or datetime.now(IST)
    rid = receipt_id(result, when)
    fp = rulebook_fingerprint()
    a = result.answer
    hi = a.lang == "hi" or bool(DEV_RE.search(result.question))
    pdf = KshitiPDF(rid, when, fp, "Answer slip · उत्तर पर्ची")
    pdf.add_page()

    pdf.label("Question at the counter", "काउंटर पर प्रश्न")
    pdf.box(result.question, font=("sans", "", 10.5), fill=G100, shadow=False)
    pdf.set_font("sans", "B", 8)
    pdf.set_text_color(*G700)
    pdf.multi_cell(0, 4, f"Answered from: {RULES_VERSION} · प्रयुक्त नियम: 06-03-2025 तक समेकित · SHA-256 {fp[:16]}…",
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if a.status == "not_found":
        pdf.label("Result", "परिणाम")
        text = ("नियमों में नहीं मिला। " if hi else "Not found in the rules. ") + (a.not_found_reason or "")
        if a.suggestion:
            text += ("\nकहाँ पूछें: " if hi else "\nWhere to ask: ") + a.suggestion
        text += ("\nम.प्र. भूमि विकास नियम 2012 में इसका उत्तर नहीं है। क्षिति अनुमान नहीं लगाता।" if hi
                 else "\nThe MP Bhumi Vikas Rules 2012 do not answer this. Kshiti does not guess.")
        pdf.box(text, font=("sans", "B", 11), fill=G100)
    else:
        amendments = [w for w in a.warnings if w.kind == "amendment"]
        for w in amendments:
            pdf.label("Amended after this rulebook", "इस पुस्तिका के बाद संशोधन", color=O700)
            pdf.box((w.text_hi if hi else w.text_en) + (f"\nSource: {w.source_url}" if w.source_url else ""),
                    font=("sans", "", 9), fill=O100, border=O700)

        pdf.label("Answer" + (" (not verified)" if a.status == "unverified" else ""), "उत्तर")
        pdf.box(a.text or "—", font=("sans", "", 11), lh=5.8, dashed=a.status == "unverified")

        if result.calc.results:
            pdf.label("Figures calculated in code from verified tables", "सत्यापित तालिकाओं से गणना")
            rows = [(f"{r.label_en}\n{r.label_hi}", _pdf_value(r.display), f"Rule {r.sub_rule}\nPage {r.page}",
                     re.sub(r"\s{2,}", "  ", r.row_text).strip() or "—") for r in result.calc.results]
            pdf.figures(rows)
            notes = []
            for r in result.calc.results:
                notes += r.assumptions_hi if hi else r.assumptions_en
            notes += result.calc.notes_hi if hi else result.calc.notes_en
            if notes:
                pdf.set_font("sans", "", 8)
                pdf.set_text_color(*G700)
                pdf.multi_cell(0, 4, "\n".join(f"• {n}" for n in dict.fromkeys(notes)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(2)

        if a.citations:
            pdf.label("Rule cited and the exact source text", "उद्धृत नियम और मूल पाठ")
            for c in a.citations[:6]:
                quote = _clean_quote(c.quote)
                pdf.set_font("mono", "", 7.2)
                need = 6 + pdf.multi_cell(182 - 4.8, 3.6, quote, dry_run=True, output="HEIGHT") + 5
                if pdf.get_y() + (need if need < 200 else 60) > pdf.page_break_trigger:
                    pdf.add_page()                      # keep each rule heading with its quote
                pdf.set_font("sans", "B", 9.5)
                pdf.set_text_color(*INK)
                tick = "VERIFIED word for word · सत्यापित" if c.verified else "NOT verified"
                pdf.multi_cell(0, 5, f"Rule {c.rule} · {c.title} · Page {c.page}   [{tick}]", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(0.6)
                pdf.box(quote, font=("mono", "", 7.2), lh=3.6, shadow=False, pad=2.4)

        other = [w for w in a.warnings if w.kind != "amendment"]
        if other:
            pdf.label("Checks", "जाँच")
            pdf.box("\n".join(f"• {w.text_hi if hi else w.text_en}" for w in other), font=("sans", "", 8.5),
                    fill=WHITE, shadow=False, dashed=True, lh=4.4)

    if pdf.get_y() + 10 < pdf.page_break_trigger:
        pdf.ln(2)
        pdf.set_font("sans", "", 7.5)
        pdf.set_text_color(*G500)
        pdf.multi_cell(0, 3.8, f"Official PDF: https://mptownplan.gov.in/NewsPDF/bvn06032025E.pdf · {a.model or '—'} · {rid}",
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    data = bytes(pdf.output())
    _log(rid, when, result, fp)
    return data, rid


def _log(rid: str, when: datetime, result: Result, fp: str) -> None:
    """Audit trail of issued slips (no personal data: the question text and rules cited only)."""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"receipt": rid, "at": when.isoformat(), "question": result.question,
                                 "status": result.answer.status, "rules": result.answer.cited_rules,
                                 "rulebook_sha256": fp}, ensure_ascii=False) + "\n")
    except OSError:
        pass
