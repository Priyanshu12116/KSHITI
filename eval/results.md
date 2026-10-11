# Kshiti accuracy on the 17 official sample questions

Run: 11-10-2026 15:35 · model: openai/gpt-oss-120b on Groq · full pipeline

| Measure | Result |
|---|---|
| Correct rule cited (questions the rules answer) | 15/15 (100%) |
| "Not found" when the rules are silent | 2/2 (100%) |
| Wrong "not found" on answerable questions | 0 |
| Correct table figures | 5/5 (100%) |
| Answer in the question's language | 17/17 (100%) |
| Quotes verified word for word | 37/37 (100%) |
| Invented rule numbers | 0 |
| Later amendment flagged (Q11) | 1/1 (100%) |
| Median time per answer | 29.6 s |

| # | Lang | Status | Rules cited | Rule | Figures | Lang | Quotes | Time |
|---|---|---|---|---|---|---|---|---|
| 1 | en | answered | 56 | ✅ | ✅ | ✅ | 2/2 | 2.93 s |
| 2 | en | answered | 17 | ✅ | ✅ | ✅ | 2/2 | 10.23 s |
| 3 | en | answered | 23 | ✅ | — | ✅ | 2/2 | 18.62 s |
| 4 | en | answered | 28 | ✅ | — | ✅ | 1/1 | 31.81 s |
| 5 | en | answered | 52 | ✅ | ✅ | ✅ | 2/2 | 26.79 s |
| 6 | en | answered | 18, 26, 26-B | ✅ | — | ✅ | 4/4 | 30.7 s |
| 7 | en | answered | 16, 14 | ✅ | — | ✅ | 2/2 | 31.11 s |
| 8 | en | answered | 21 | ✅ | — | ✅ | 2/2 | 28.54 s |
| 9 | en | answered | 24, 27 | ✅ | — | ✅ | 3/3 | 29.58 s |
| 10 | en | answered | 56 | ✅ | ✅ | ✅ | 2/2 | 26.84 s |
| 11 | en | answered | 12 | ✅ | — | ✅ | 1/1 | 31.54 s |
| 12 | en | answered | 103 | ✅ | — | ✅ | 3/3 | 33.64 s |
| 13 | en | answered | 83 | ✅ | — | ✅ | 9/9 | 39.41 s |
| 14 | hi | answered | 56 | ✅ | ✅ | ✅ | 1/1 | 36.03 s |
| 15 | hi | answered | 21 | ✅ | — | ✅ | 1/1 | 4.7 s |
| 16 | en | not_found | — | ✅ | — | ✅ | 0/0 | 30.89 s |
| 17 | en | not_found | — | ✅ | — | ✅ | 0/0 | 16.81 s |

Answer key: eval/answer_key.json. Full answers: eval/results.json.
