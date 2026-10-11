"""Project summary PDF in the Kshiti template -> docs/Kshiti_Summary.pdf

Run: python tools/make_summary.py
"""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from pathlib import Path

import qrcode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kshiti.rules import rulebook_fingerprint  # noqa: E402
from kshiti.slip import G100, IST, O100, O700, KshitiPDF  # noqa: E402

REPO = "https://github.com/Priyanshu12116/KSHITI"


class SummaryPDF(KshitiPDF):
    def _qr(self) -> io.BytesIO:
        buf = io.BytesIO()
        qrcode.make(REPO, box_size=6, border=1).save(buf, format="PNG")
        buf.seek(0)
        return buf


def accuracy_text() -> str:
    live = ROOT / "eval" / "results.json"
    off = ROOT / "eval" / "results_offline.json"
    if live.exists():
        res = json.loads(live.read_text(encoding="utf-8"))
        s = res["summary"]
        return (f"Live run on the 17 official sample questions ({res.get('model', '')}, {res.get('run_date', '')}): "
                f"correct rule {s['rule_hit']}/{s['rule_total']}, \"not found\" {s['not_found_hit']}/{s['not_found_total']} "
                f"(wrong not-found {s['false_not_found']}), table figures {s['figure_hit']}/{s['figure_total']}, "
                f"answer language {s['lang_hit']}/{s['lang_total']}, quotes verified {s['quotes_verified']}/{s['quotes_total']}, "
                f"invented rule numbers {s['invented_rules']}, amendment flagged {s['amendment_hit']}/{s['amendment_total']}. "
                "Q14 was answered by the calculator after the model wrongly said \"not found\". Single answers took 3 to 5 s; "
                "the batch median was higher because of free-tier rate limits.")
    s = json.loads(off.read_text(encoding="utf-8"))["summary"]
    return (f"Offline check on the 17 official sample questions (router and calculator, no AI): calculator figures "
            f"{s['calc_figure_hit']}/{s['calc_figure_total']} correct, out-of-scope questions caught "
            f"{s['out_of_scope_hit']}/{s['out_of_scope_total']}, no wrong figure offered on {s['no_wrong_figure']}/{s['questions']}. "
            "The full live run with Claude was not done during the build because API keys were not available; "
            "python eval/run_eval.py produces it.")


def main() -> None:
    now = datetime.now(IST)
    pdf = SummaryPDF("THETA172 · TRACK 1", now, rulebook_fingerprint(), "Project summary · परियोजना सारांश")
    pdf.add_page()

    pdf.label("In one line", "एक पंक्ति में")
    pdf.box("Kshiti answers building-permission questions on the MP Bhumi Vikas Rules 2012 at the Bhopal Municipal "
            "Corporation counter, in English or Hindi, with the rule number and the exact text it came from. When the "
            "rules are silent, it says so.", font=("sans", "B", 11.5), lh=6)

    pdf.label("The user and the problem", "उपयोगकर्ता और समस्या")
    pdf.box("User: a building-permission clerk at the BMC counter. A citizen asks: \"My plot is 200 sq m on a 9 m road. How much gap "
            "do I leave at the front, how many floors can I build, and what fee do I pay?\" The answers sit in tables across a "
            "108-page rulebook that keeps changing, and questions come in English and Hindi. The clerk needs a correct answer "
            "within a minute, with the rule number to show the citizen.", fill=G100, shadow=False)

    pdf.label("What Kshiti does", "क्षिति क्या करता है")
    pdf.box("1. Reads the question in milliseconds: language, topic, the citizen's numbers.\n"
            "2. Calculates figures in code from tables checked against the official PDF: front, rear and side open space "
            "(Rule 56), FAR and maximum built-up area (Rule 61), height band (Rule 42), fees (Rule 21).\n"
            "3. Writes a short answer in the question's language from the rules only, quoting the exact paragraph: Claude Opus 5.5 "
            "when an Anthropic key is set, gpt-oss-120b on Groq otherwise (the engine used at the event).\n"
            "4. Checks every quote word for word against the official text; removes anything that does not match; flags "
            "rule numbers that do not exist; flags the 28-08-2026 amendment.\n"
            "5. Shows the proof (rule, page, official text, PDF link) and prints a PDF slip with a receipt ID and QR code.",
            font=("sans", "", 10), lh=5.2)

    pdf.label("Example: the counter question", "उदाहरण")
    pdf.figures([
        ("Front open space\nसामने का खुला स्थान", "3.0 m", "Rule 56(1)(a)\nPage 77", "Up to 9.0 meters"),
        ("Max built-up area\nअधिकतम निर्मित क्षेत्र", "250 sq m\n(FAR 1.25)", "Rule 61 (Table 8)\nPage 83", "Resdential  1.25"),
        ("Maximum height\nअधिकतम ऊँचाई", "12.5 m", "Rule 42(1) (Table 4)\nPage 58", "12.0 m. 1000 sq. 18 m.  1:1.50"),
        ("Fees (at 250 sq m)\nशुल्क", "Rs 3,250", "Rule 21(2)(ii) + 21(3)(b)\nPage 36", "201  300  3,000"),
    ])

    pdf.label("Why it can be trusted", "भरोसा क्यों")
    pdf.box("• Numbers from code, not from the language model; every table row tested against the rule text.\n"
            "• Quotes verified word for word; answers with no verified quote are marked \"Not verified\".\n"
            "• \"Not found\" when the rules are silent; never answers from general knowledge.\n"
            "• Never assumes a missing fact (road width, plot area, height); asks the clerk.\n"
            "• Every answer and slip states the rules version (consolidated 06-03-2025) and a SHA-256 fingerprint.\n"
            "• Numbers read from the question are accepted only if written in it; special uses never get residential figures.",
            font=("sans", "", 9.5), lh=5)

    pdf.label("Measured accuracy", "मापी गई सटीकता", color=O700)
    pdf.box(accuracy_text(), font=("sans", "", 9.5), fill=O100, border=O700, lh=5)

    pdf.label("Known limits", "ज्ञात सीमाएँ")
    pdf.box("Rules consolidated to 06-03-2025; only the known 28-08-2026 amendment is flagged, and its Gazette text is not "
            "available. Calculator covers residential setbacks, FAR, height band and fees. The rules give no number of floors. "
            "Source quotes are from the English PDF. A town's Development Plan may differ (Rule 103). Not legal advice.",
            font=("sans", "", 9), shadow=False, dashed=True, lh=4.6)

    pdf.label("Run it · Team", "चलाएँ · टीम")
    pdf.box(f"{REPO}\npip install -r requirements.txt · add keys to .env · python run.py · http://localhost:8000\n"
            "Team THETA172 · Priyanshu Sharma (solo) · Track 1, Claude Impact Lab × Cerebras, Bhopal, 11-10-2026 · MIT License",
            font=("sans", "", 9), fill=G100, shadow=False, lh=4.8)

    out = ROOT / "docs" / "Kshiti_Summary.pdf"
    out.write_bytes(bytes(pdf.output()))
    print(out, pdf.page_no(), "page(s)")


if __name__ == "__main__":
    main()
