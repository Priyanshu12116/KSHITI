# Kshiti · क्षिति — Bhumi Vikas Sahayak

> Ask the Bhopal building rulebook. Get a short answer in your language, with the rule number and the exact text it came from. When the rules are silent, Kshiti says so.

| | |
|---|---|
| **Track** | Track 1 · Bhumi Vikas Sahayak · Claude Impact Lab × Cerebras, Bhopal, 11 Oct 2026 |
| **Team** | THETA172 |
| **Members** | Priyanshu Sharma (solo) |
| **The one user** | A building-permission clerk at the Bhopal Municipal Corporation counter |
| **The one workflow** | Citizen asks → clerk types the question (English or Hindi) → cited answer in under a minute → printable PDF slip |

🚧 **Build in progress.** This README will be completed before submission.

## How to run (5 steps)

1. `git clone https://github.com/Priyanshu12116/KSHITI.git && cd KSHITI`
2. `python -m venv .venv` and activate it (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere)
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and add `ANTHROPIC_API_KEY` and `CEREBRAS_API_KEY`
5. `python run.py` and open http://localhost:8000 (the browser opens on its own)

## Data

| Data | Source |
|---|---|
| MP Bhumi Vikas Rules 2012, consolidated to 6 Mar 2025 (rules JSONL, page text, English and Hindi PDFs, sample questions) | Official Track 1 data pack: https://github.com/Vishal4742/bhopal-impact-lab-2026-problem-statements |
| Amendment of 28 Aug 2026 to Rule 2(5)(c) | https://teamleaseregtech.com/updates/article/59469/government-of-madhya-pradesh-amendment-to-land-development-rules (summary only; full gazette text not available) |
| Emblem of India, Emblem of Madhya Pradesh | Wikimedia Commons, public domain |
| Fonts: Tillana, Anek Devanagari, Inter, Noto Sans | Google Fonts / Noto, SIL Open Font License |

## License

MIT, see [LICENSE](LICENSE).
