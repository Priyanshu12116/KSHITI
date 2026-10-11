# Kshiti · क्षिति — Bhumi Vikas Sahayak

**Ask the Bhopal building rulebook. Get a short answer in your language, with the rule number and the exact text it came from. When the rules are silent, Kshiti says so.**

| | |
|---|---|
| **Track** | Track 1 · Bhumi Vikas Sahayak · Claude Impact Lab × Cerebras, Bhopal, 11 October 2026 |
| **Team** | THETA172 |
| **Members** | Priyanshu Sharma (solo) |
| **The one user** | A building-permission clerk at the Bhopal Municipal Corporation counter |
| **The one workflow** | A citizen asks → the clerk types the question in English or Hindi → a cited answer in under a minute → a printable PDF slip for the citizen |

![Kshiti home screen](docs/screenshots/02_home.png)

## The problem

The MP Bhumi Vikas Rules, 2012 run to 108 pages and 105 rules. The numbers people ask about most (setbacks, floor area, fees) sit in tables in different parts of the book, the rules keep changing, and questions come in English and Hindi. A clerk needs a correct answer within a minute, with the rule number to show the citizen.

## What Kshiti does

1. **Reads the question** (Cerebras, under a second): language, topic and the citizen's numbers, such as road width or plot area.
2. **Calculates figures in code** from tables checked against the official PDF: front, rear and side open space, FAR and maximum built-up area, height band, and fees.
3. **Writes a short cited answer** (Claude): from the 106 rules only, in the question's language, citing the exact paragraph or table.
4. **Checks every quote word for word** against the official text. A quote that does not match is removed. Rule numbers that do not exist are flagged.
5. **Shows the proof:** rule, sub-rule, PDF page, the official text with the matching table row highlighted, and a link that opens the PDF at that page.
6. **Prints a PDF answer slip** for the citizen, with a receipt ID, QR code and the version of the rules used.

## Why it can be trusted (what makes it different)

| Promise | How it is enforced |
|---|---|
| **Every answer shows its rule and source text** | Claude's built-in citations over the rulebook, split into 867 quotable blocks with their PDF page. Each quote is then matched word for word against the data pack (`kshiti/verify.py`). |
| **No invented rules** | Unknown rule numbers in an answer are flagged. An answer with no verified quote is marked "Not verified" and never shown as confident. |
| **Table numbers are right** | Figures come from `data/tables/tables.json`, read from the official PDF (pages 35, 36, 58, 77, 78, 83). Tests check every row and boundary against the rule text (`tests/test_calculator.py`). Claude is given the same figures, and a cross-check warns if its wording differs. |
| **Says "not found"** | A dedicated tool for questions the rules do not cover (property tax, land prices). Kshiti never answers those from general knowledge. |
| **Never assumes the citizen's facts** | If road width, plot area or height is missing, Kshiti asks for it with a short form. Assumptions it does make (for example "residential use") are shown on screen. |
| **Knows which version of the rules it used** | Every answer and slip shows "consolidated to 06-03-2025" and a SHA-256 fingerprint of the rulebook. The 28-08-2026 amendment to Rule 2(5)(c) is flagged where it applies. |
| **Fast enough for a queue** | Figures appear in milliseconds; the cited answer streams in as it is written. |

## Accuracy on the 17 official sample questions

The answer key is in [eval/answer_key.json](eval/answer_key.json), with the expected rule and figures for each question.

**Offline check (router and calculator, no AI), run 11-10-2026:**

| Measure | Result |
|---|---|
| Calculator figures correct (Q1 3.6 m, Q10 1.5 m, Q14 3.0 m) | 3/3 |
| Out-of-scope questions caught (Q16, Q17) | 2/2 |
| Questions where no wrong figure was offered | 17/17 |
| Unit tests (tables, quote checks, router, calculator, server, PDF) | 84 passing |

**Full live run (with Claude):** not yet run. API keys were not available during the build. Running `python eval/run_eval.py` scores correct rule, "not found", figures, language, verified quotes, invented rules and the amendment flag, and writes [eval/results.md](eval/results.md). The interface shows these scores in its "Measured accuracy" panel.

## How to run it (5 steps)

1. `git clone https://github.com/Priyanshu12116/KSHITI.git && cd KSHITI`
2. `python -m venv .venv`, then activate it (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere)
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and add `ANTHROPIC_API_KEY` and `CEREBRAS_API_KEY`
5. `python run.py`, then open http://localhost:8000

Optional: `pytest` runs the tests; `python eval/run_eval.py` measures accuracy.

## What works and what does not

**Works**
- English, Hindi and Hindi typed in English letters ("aage kitni jagah chhodni hai"); answers follow the question's language.
- Cited answers for all 106 rules; calculated figures for residential front, rear and side open space (Rule 56), FAR and maximum built-up area (Rule 61), height band (Rule 42, Table 4) and building permission fees (Rule 21).
- Not found, missing-input form, amendment warning, table check warning, unverified answers, error and retry.
- PDF answer slip with receipt ID, QR code and rulebook fingerprint; full Hindi interface; high contrast and text size controls; works on a phone.

**Does not, or not yet**
- **The full live accuracy run has not been done** (see above).
- **Later amendments:** only the 28-08-2026 change to Rule 2(5)(c) is known, from a published summary; its exact Gazette text is not available, so it is flagged but never quoted.
- **Calculator scope:** residential setbacks, FAR, height band and fees only. Other uses (farm house, cinema, fuel station, industry) are answered from the cited text, never with residential figures.
- **Number of floors:** the rules limit height and built-up area but never state a number of floors. Kshiti says so.
- **Fee slabs** are whole square metres in the official table; a built-up area between slabs (for example 75.5 sq m) is put in the next slab.
- **Hindi source text:** quotes are from the English PDF (the source of truth). The official Hindi PDF uses an old font that cannot be machine-read.
- **Development Plan:** a town's Development Plan may set different norms (Rule 103). Kshiti cannot see Development Plans.
- **Not legal advice.** Kshiti points to the rule; the competent authority decides.

## Screenshots

| Opening | Rule drawer | PDF slip (Hindi) |
|---|---|---|
| ![Opening animation](docs/screenshots/01_opening.png) | ![Full rule drawer](docs/screenshots/04_rule_drawer.png) | ![PDF slip](docs/screenshots/05_pdf_slip_hindi.png) |

[Answer screen preview](docs/screenshots/03_answer_preview.png). This preview and the PDF slip use a recorded sample answer, because API keys were not available during the build. The figures, quotes and checks shown in them come from the real calculator and verifier; the answer sentences are a stand-in.

## How it is built

```mermaid
flowchart LR
  Q[Clerk's question<br/>EN / HI] --> R[Router<br/>Cerebras gpt-oss-120b<br/>+ rule-based fallback]
  R --> C[Calculator<br/>tables checked against PDF]
  C --> L[Claude Opus 5.5<br/>106 rules as citable documents<br/>prompt cache]
  L --> V[Checks<br/>quotes word for word<br/>rule numbers, amendments, figures]
  V --> U[Interface + PDF slip]
```

| Part | Where |
|---|---|
| Rulebook loading, quotable blocks with PDF pages | `kshiti/rules.py` |
| Claude answer engine (citations, tools, caching, streaming) | `kshiti/engine.py`, `kshiti/prompts.py` |
| Quote check, invented-rule check, warnings | `kshiti/verify.py` |
| Calculator and checked tables | `kshiti/calculator.py`, `data/tables/tables.json` |
| Cerebras router with rule-based fallback | `kshiti/router.py` |
| Pipeline | `kshiti/pipeline.py` |
| PDF slip template | `kshiti/slip.py` |
| Web server and interface (no build step) | `app/server.py`, `app/static/` |
| Evaluation | `eval/run_eval.py`, `eval/answer_key.json` |

Safety of the AI parts: Cerebras only classifies the question and extracts numbers, and any number it returns that is not written in the question is discarded. Claude only writes the answer text; figures come from code and quotes are checked against the official text before they are shown.

## Data used

| Data | Source |
|---|---|
| MP Bhumi Vikas Rules 2012, consolidated to 06-03-2025: rules JSONL, page text, English and Hindi PDFs, 17 sample questions | Official Track 1 data pack: https://github.com/Vishal4742/bhopal-impact-lab-2026-problem-statements (English PDF: https://mptownplan.gov.in/NewsPDF/bvn06032025E.pdf) |
| Amendment of 28-08-2026 to Rule 2(5)(c), plots up to 500 sq m (summary) | https://teamleaseregtech.com/updates/article/59469/government-of-madhya-pradesh-amendment-to-land-development-rules, linked in the official problem statement |
| Emblem of India; Emblem of Madhya Pradesh | Wikimedia Commons (public domain). Used with permission obtained by the team. No government portal was scraped. |
| Fonts: Tillana, Anek Devanagari, Inter, Noto Sans, Noto Sans Devanagari, Noto Sans Mono | Google Fonts / Noto, SIL Open Font License |

No personal data is used or stored. Issued slips are logged locally (question, rules cited, time) in `logs/`, which is not committed.

## Security

API keys are read from `.env` (not committed; see `.env.example`). No keys or secrets are in the code.

## License

MIT, see [LICENSE](LICENSE). Offered to the Government of Madhya Pradesh through MPSeDC.

Built by **Priyanshu Sharma · THETA172**.
