# Kshiti demo script

## Before recording (5 minutes)

1. Real API keys in `.env`, then `python tools/check_keys.py` shows two "OK" lines.
2. `python run.py`. Open http://localhost:8000 in a fresh browser window (the opening animation plays once per session; open a new window to see it again).
3. Ask the headline question once before recording, so the rulebook is in Claude's cache and answers come back fast.
4. Screen at 1366×768 or 1920×1080, browser zoom 100%, notifications off.

> If the keys are not working by recording time, do **not** present recorded sample answers as live answers. Either record only what works live (opening, interface, calculator figures, "not found" check from the router) or say on screen: "sample answer recorded for layout; live answers need the API key".

## 2-minute recording (record at 16:00)

| Time | Show | Say |
|---|---|---|
| 0:00–0:10 | Opening animation | "This is Kshiti, for the building-permission clerk at the Bhopal Municipal Corporation." |
| 0:10–0:20 | Home screen, point at the four guarantee cards | "A citizen asks a question. The clerk needs a correct answer in a minute, with the rule to show." |
| 0:20–0:50 | Click the first example (200 sq m, 9 m road). Point at the figure cards as they appear, then the answer | "The figures appear first. They are calculated in code from tables checked against the official PDF: 3 metres in front, 250 square metres of built-up area, 12.5 metres height, Rs 3,250 in fees. Then Claude writes the answer, citing the rules." |
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
- **What does it cost to run?** The whole rulebook is cached by Claude, so after the first question each answer reads it from the cache.
- **Why Cerebras?** It reads the question and extracts the citizen's numbers in well under a second, so figures appear immediately. It never writes the answer, and any number it returns that is not in the question is discarded.
- **Number of floors?** The rules limit height and built-up area; they do not state a number of floors. Kshiti says that rather than inventing one.
