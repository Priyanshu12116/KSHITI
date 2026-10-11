# KSHITI (क्षिति) — Build Phases

**Track 1 · Bhumi Vikas Sahayak** · Claude Impact Lab × Cerebras, Bhopal · 11-Oct-2026
**Solo:** Priyanshu Sharma · THETA1728 · **Repo:** github.com/Priyanshu12116/KSHITI · **Local:** `D:\KSHITI`
**Hard deadline:** form submitted before **5:00 PM**. Times below assume "go" at **1:20 PM**.

**User:** a building-permission clerk at the Bhopal Municipal Corporation counter.
**Job:** a correct answer in under a minute, in the question's language, with the rule number and source text. When the rules are silent, say so.

---

## USPs

| # | USP | What makes it true |
|---|---|---|
| **U1** | **Checked quotes, no invented rules** | Claude's built-in citations (quote taken from the source data) + a word-for-word check against the rule text. Fails → "Could not verify" |
| **U2** | **Numbers from code** | Setback/FAR come from tables **checked by hand against the PDF**, with pytest tests per row |
| **U3** | **Asks before guessing** | Missing road width / height / plot area → the tool asks for it instead of assuming |
| **U4** | **Speed + accuracy** | Cerebras `gpt-oss-120b` router (<1 s, fast lane) + Claude Opus 5.5 (cited deep answer) |
| **U5** | **Knows when it might be out of date** | Warning for Rule 2(5)(c), amended 28-Aug-2026 |
| **U6** | **Printable proof** | PDFs with receipt ID, QR, rulebook fingerprint, all in the Kshiti template |
| **U7** | **Plot diagram** | Top-down drawing of the plot, roughly to scale, with front/side/rear open space in metres |
| **U8** | **Measured accuracy** | Eval on the 17 sample questions, shown in the app (About) and the README |
| **U9** | **Government-standard design** | GIGW top bar, English default + Hindi toggle, emblem/MP/BMC logos, calligraphic opening animation |
| Stretch | **Case Check** | Whole application checked rule by rule, with proposed-vs-required bars and a PDF report |

---

## Design system (fixed)

**Colours (only orange, white, black and greys):**
| Token | Hex | Use |
|---|---|---|
| `ink` | `#111111` | Text, 2px borders, hard shadows, verified chip |
| `grey-700` | `#3D3D3D` | Secondary text |
| `grey-500` | `#6B6B6B` | Not-found text, captions |
| `grey-300` | `#CFCFCF` | Dividers, bar tracks |
| `grey-100` | `#F3F3F3` | Page background, not-found card |
| `white` | `#FFFFFF` | Cards |
| `orange-600` | `#EA580C` | Primary button and number card (black text on it) |
| `orange-700` | `#C2410C` | Orange text/links on white (AA contrast) |
| `orange-100` | `#FFEDD5` | Warning / amendment background |

**What each colour signals (icon + word always, never colour alone):**
- Verified → black chip `✓ VERIFIED` (custom seal icon)
- Warning or amendment → orange-100 block, orange-700 border
- Not found → grey-100 block, grey-500 text
- Case Check fail → solid orange block "FAILS"
- Case Check pass → black outline "PASSES"

**Style: calm neo-brutalism**
- 2px `ink` borders and a hard `4px 4px 0` shadow, no blur
- Flat colour, no gradients, 0–4px corners, strict grid
- Buttons "press" on click (the shadow shrinks)
- No neon colours, no tilted elements, no animation except the opening and loading states

**Fonts:**
- **Tillana:** the name only (क्षिति / KSHITI), in the opening animation, header, PDF header and favicon
- **Anek Devanagari:** Hindi interface text
- **Inter:** English interface text and numbers
- **Noto Sans Devanagari + Inter:** PDF body text
- All font files are served from the repo (no CDN)

**Icons:** a custom SVG set (no emojis), 24px grid, 2px stroke, colour taken from the surrounding text, `aria-label` on each.

**Language:**
- The interface is English by default; the `English | हिंदी` toggle switches the whole interface
- The name "Kshiti / क्षिति" never changes
- **Answers always follow the question's language** (a problem-statement requirement)

**Charts:**
- Plot diagram (U7), proposed-vs-required bars (Case Check), accuracy bars (U8)
- Drawn as simple inline SVGs, no chart library, no pie charts

---

## PDF template (every PDF uses it, every word inside it)

`app/pdf/template.py` → `KshitiPDF(FPDF)` (fpdf2 with **text shaping turned on**, so Hindi conjuncts and matras render correctly). Every PDF type builds on this template; nothing prints outside it.

```
┌──────────────────────────────────────────────────────────────┐ 2px ink border
│ [Emblem] KSHITI · क्षिति (Tillana)                     [BMC]  │ header (every page)
│ Bhumi Vikas Sahayak · Govt of MP · Bhopal Municipal Corp     │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀ orange-600 rule ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀ │
│ Receipt KSH-YYYYMMDD-XXXX · DD-MM-YYYY HH:MM IST        [QR]  │
├──────────────────────────────────────────────────────────────┤
│ [SECTION BLOCKS: same card style as the app]                 │
│  QUESTION · ANSWER · RESULT (number card + plot diagram)     │
│  RULE CITED (rule, title, page) · SOURCE TEXT ✓ VERIFIED      │
│  WARNINGS (orange-100) / NOT FOUND (grey-100)                 │
├──────────────────────────────────────────────────────────────┤
│ Rules: MP Bhumi Vikas Rules 2012, consolidated 06-Mar-2025 · │ footer (every page)
│ fingerprint a1b2c3 · For information only; the competent     │
│ authority decides. · Kshiti by THETA1728 · Page 1/1           │
└──────────────────────────────────────────────────────────────┘
```

**PDF types:**
1. **Answer slip** (core): one page, in the language of the question, with English section labels
2. **Case Check report** (stretch): checklist + proposed-vs-required bars
3. **Project summary** (Phase 6): problem, user, solution, USPs, architecture, accuracy, known limits, credits, generated with the same template

**Tested before done:** क्षेत्र, निर्माण, स्वीकृति, र्‍, numbers, a long quote across a page break.

---

## Accuracy safeguards (apply in every phase)

| Risk | Safeguard | Phase |
|---|---|---|
| Invented rule or quote | Built-in citations + word-for-word check, plus a check that the rule number exists | 1 |
| Wrong table number | Hand-checked tables + pytest per row + "check against PDF p.N" link | 2 |
| Guessing missing inputs | `ask_missing_inputs` tool + validated calculator inputs | 1–2 |
| Router mistake | Cerebras only sorts the question and extracts inputs, never writes the answer; unsure → Claude; >2 s → Claude | 2 |
| Answering when the rules are silent | `report_not_found` tool; quick "not found" only when the router also suggests no likely rules | 1–2 |
| Out-of-date rule | Amendment warning | 3 |
| Inserted rules (26-B, sub-rules inside their parent) | Rule IDs kept as strings; sub-rule text searched inside the parent rule | 1 |
| Unproven claims | Eval on the 17 questions, published | 4 |

---

## Phase 0 — Setup · 1:20–1:35 · Claude
- [ ] `git init` in `D:\KSHITI`, remote `Priyanshu12116/KSHITI`, branch `main`
- [ ] Folders: `app/ app/pdf/ app/ui/ data/ data/tables/ static/fonts/ static/logos/ static/icons/ i18n/ eval/ tests/ docs/`
- [ ] Organiser data copied in (rules JSONL, page text, English PDF, sample questions)
- [ ] Fonts: Tillana, Anek Devanagari, Inter, Noto Sans Devanagari (all OFL)
- [ ] Logos: emblem (Wikimedia SVG), MP Govt, BMC → SVG where an official one exists, otherwise a high-resolution PNG (cleaned, **not redrawn**) → **you approve them**
- [ ] `.venv` + `requirements.txt` (anthropic, cerebras-cloud-sdk, streamlit, pydantic, rapidfuzz, fpdf2, uharfbuzz, qrcode, python-dotenv, pytest), `.env.example`, `.gitignore`, MIT `LICENSE` (Priyanshu Sharma · THETA1728)
- [ ] **You:** put `ANTHROPIC_API_KEY` and `CEREBRAS_API_KEY` into `D:\KSHITI\.env`

**Done when:** both APIs answer a test call, and the first commit is pushed.

## Phase 1 — Claude answer engine (U1, U3) · 1:35–2:20 · Claude
- [ ] `rules.py`: load the rules, look up by number (string IDs), list rule titles
- [ ] `engine.py`:
  - Claude Opus 5.5, with each rule as a separate block with citations on
  - prompt caching on the rulebook, streaming, the `fallbacks: "default"` setting
- [ ] Tools (`strict: true`): `report_not_found`, `ask_missing_inputs`, `calculate`
- [ ] System prompt:
  - answer in the question's language
  - only from the rules
  - the clerk decides
  - never fill in missing inputs
- [ ] `verify.py`: map each citation to its rule number, check the quote word for word, mark ✓ Verified or remove the citation, check the rule number exists
- [ ] Answer object (pydantic): `answer, lang, citations[], result?, warnings[], found, receipt`

**Done when:** sample questions 1, 6, 12, 14, 16 are correct and verified, and question 16 says "not found".

## Phase 2 — Calculator + Cerebras router (U2, U3, U4) · 2:00–2:50
- [ ] **You (most important task, ~40 min):** check every value I extract into `data/tables/*.json` (front/side/rear open space, FAR) against the PDF, then confirm my draft answer key for the 17 questions
- [ ] **Claude:**
  - `calculator.py` (`front_setback`, `side_rear_setback`, `far_limit`) → `{value, unit, rule, table, page, row}` + pytest tests per row
  - `router.py`: Cerebras with strict JSON output → `{lang, intent, inputs, candidate_rules}`
  - routing between the fast lane and the deep lane, falling back to Claude on timeout

**Done when:** questions 1, 10 and 14 show the correct number in under 1 s with the table row, and all pytest tests pass.

## Phase 3 — Interface (U5, U7, U9) · 2:40–3:35 · Claude, you review
- [ ] Theme: calm neo-brutalist CSS with the orange/black/white/grey colours, fonts, the SVG icon set
- [ ] **Opening animation:** "क्षिति" in Tillana converted to SVG with proper text shaping, ink-reveal ~1.8 s → "KSHITI" → logo moves into the header (≤3 s, once per session, reduced-motion fallback)
- [ ] **GIGW shell:**
  - top bar: skip link, A- A A+, high contrast, English | हिंदी
  - header: emblem · Govt of MP · BMC
  - footer: credits, data sources, disclaimer
- [ ] i18n: `en.json` / `hi.json` (Hindi terms from the official Hindi rulebook)
- [ ] **Ask screen:** question box + example questions → timers (fast/deep) → number card + **plot diagram (U7)** → answer → rule cards (✓ VERIFIED, highlighted quote, PDF page) → warnings → Download PDF
- [ ] **States:** loading, asking for inputs, not found, amendment warning (U5), check failed, API down
- [ ] **About panel:** accuracy bars (U8), data sources, known limits

**Done when:** you play the clerk for 6 questions in English and Hindi, and nothing breaks at 1366×768.

## Phase 3b — PDF template + answer slip (U6) · 3:15–3:45 · Claude
- [ ] `KshitiPDF` template (header/footer/section blocks, brutalist borders, colours, fonts, text shaping)
- [ ] Answer slip: receipt ID, QR code, rulebook fingerprint (SHA-256), plot diagram, verified quote, warnings / not found
- [ ] Test the Hindi words listed above, a long quote, a not-found slip

**Done when:** an English slip and a Hindi slip both look correct when opened and printed.

## Phase 4 — Eval + fixes (U8) · 3:45–4:10 · Claude runs, you judge
- [ ] `eval/run_eval.py` on the 17 questions: correct rule, correct number, correct "not found", quotes verified, language, speed (fast/deep)
- [ ] Fix → run again → freeze `eval/results.md` → feed the About accuracy bars
- [ ] **4:10 code freeze**

**Target:** ≥15/17 correct rule, 2/2 "not found", **0 invented quotes**, 100% language match.

## Phase 5 — Demo · 4:10–4:30 · You record
1. Opening animation
2. Question 1 → number in under 1 s + plot diagram + cited answer
3. Question 14 in Hindi
4. Question 16 → not found
5. Question 11 → amendment warning
6. Download the PDF
7. About → accuracy bars

(2 minutes or less)

## Phase 6 — README + project summary PDF + submit · 4:30–4:55
- [ ] README:
  - Kshiti, problem, USP table, screenshots
  - 3-command run steps, architecture diagram
  - accuracy table, known limits
  - data sources, logo permission note
  - credits (Priyanshu Sharma · THETA1728)
- [ ] Project summary PDF generated with the same template → `docs/Kshiti_Summary.pdf`
- [ ] Search for leaked keys, check `.env` isn't committed, make the repo **public**, test the run steps on a fresh clone
- [ ] **Submit the Google Form before 5:00 PM**

## Stretch (only if Phase 4 finishes early)
Case Check tab + proposed-vs-required bars + Case Check PDF → rules "as on" a date → fee table

---

## Cut order if late (cut from the top)
1. Case Check (stretch)
2. About panel (keep the accuracy table in the README)
3. Project summary PDF
4. Plot diagram in the PDF (keep it in the app)
5. Shrinking-logo step of the opening animation (keep the ink reveal)

**Never cut:** checked citations, hand-checked tables, not found, the eval, the answer slip PDF.
