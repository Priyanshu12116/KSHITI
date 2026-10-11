# Kshiti demo script

## Before recording (5 minutes)

1. `.env` has `ANTHROPIC_API_KEY` (Claude Opus 5.5 answers) and `GROQ_API_KEY` (free router in place of Cerebras). Do not ask questions in the browser while `eval/run_eval.py` is running.
2. `python run.py`. Open http://localhost:8000 in a fresh browser window (the opening animation plays once per session; open a new window to see it again).
3. Ask the headline question once before recording, so Claude has the rulebook in its cache; answers then take about 10 to 15 s, and the figures appear at once.
4. Screen at 1366×768 or 1920×1080, browser zoom 100%, notifications off.

> Say which models run: **Claude Opus 5.5** writes the cited answers; **gpt-oss-20b on Groq** (free inference) reads the question in place of Cerebras. The progress bar shows both. If the Anthropic key stops working, Kshiti falls back to gpt-oss-120b on Groq and the labels change with it.

## 2-minute recording (record at 16:00)

| Time | Show | Say |
|---|---|---|
| 0:00–0:10 | Opening animation | "This is Kshiti, for the building-permission clerk at the Bhopal Municipal Corporation." |
| 0:10–0:20 | Home screen, point at the four guarantee cards | "A citizen asks a question. The clerk needs a correct answer in a minute, with the rule to show." |
| 0:20–0:50 | Click the first example (200 sq m, 9 m road). Point at the figure cards as they appear, then the answer | "The figures appear first. They are calculated in code from tables checked against the official PDF: 3 metres in front, 250 square metres of built-up area, 12.5 metres height, Rs 3,250 in fees. Then Claude writes the answer from the 106 rules and cites the exact text." |
| 0:50–1:05 | Scroll to the source cards; click "Open PDF at page 77" | "Every quote is the official text, checked word for word. The matching table row is highlighted, and this opens the PDF at the right page." |
| 1:05–1:20 | Click the Hindi example | "Questions in Hindi get answers in Hindi." |
| 1:20–1:32 | Click "How do I pay my property tax online?" | "When the rules are silent, Kshiti says so. It does not guess." |
| 1:32–1:45 | Ask: "Do I need separate development permission for a 300 sq m plot that matches the Development Plan?" | "This rule changed on 28 August 2026, after the rulebook we were given. Kshiti flags it." |
| 1:45–1:55 | Click "Download answer slip (PDF)" and show the slip | "The clerk prints this for the citizen: rule, source text, version of the rules, receipt number." |
| 1:55–2:00 | Point at "Measured accuracy" | "And we measured it on the 17 official sample questions." |

## 6-minute presentation (if selected)

1. **Problem (45 s).** 108 pages, numbers in tables, rules that keep changing, two languages. A clerk with a queue.
2. **Live demo (3 min).** Follow the recording script.
3. **Why it can be trusted (1 min).** Numbers from code; quotes verified word for word; "not found" instead of guessing; never assumes missing facts; version of the rules on every answer.
4. **Accuracy and honesty (45 s).** The eval results; the known limits from the README.
5. **Day one (30 s).** One command to run. Runs on a counter PC with a browser. Offered to MPSeDC under MIT.

## Likely questions

- **What if the AI makes up a rule?** Every quote must match the official text word for word, or it is removed. Rule numbers that do not exist are flagged. An answer with no verified quote is marked "Not verified".
- **What if the table number is wrong?** Table figures come from code, not from the model. Each row was read from the PDF and is tested against the rule text, including boundaries such as exactly 9 m or 150 sq m.
- **How do you handle new amendments?** Add an entry to `data/amendments.json`; Kshiti warns on every related answer. When a new consolidated rulebook is published, replace the data file; the fingerprint on every slip changes with it.
- **Which AI does it use?** At the event: gpt-oss-120b on Groq, because that was the key available. With an Anthropic key it switches to Claude Opus 5.5 with built-in citations over all 106 rules. Both go through the same checks, so neither can show an unverified quote as verified.
- **What does it cost to run?** On Groq's free tier, nothing. With Claude, the rulebook is cached, so after the first question each answer reads it from the cache.
- **Cerebras?** The Cerebras router is built in (it would read the question and extract numbers in well under a second), but no Cerebras key was used at the event; the local rule-based reader did that job in milliseconds.
- **Number of floors?** The rules limit height and built-up area; they do not state a number of floors. Kshiti says that rather than inventing one.
