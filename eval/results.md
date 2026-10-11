# Kshiti accuracy on the 17 official sample questions

Run: 11-10-2026 15:54 · model: claude-opus-5-5 · full pipeline

| Measure | Result |
|---|---|
| Correct rule cited (questions the rules answer) | 15/15 (100%) |
| "Not found" when the rules are silent | 2/2 (100%) |
| Wrong "not found" on answerable questions | 0 |
| Correct table figures | 5/5 (100%) |
| Answer in the question's language | 17/17 (100%) |
| Quotes verified word for word | 107/107 (100%) |
| Invented rule numbers | 0 |
| Later amendment flagged (Q11) | 1/1 (100%) |
| Median time per answer | 12.8 s |

| # | Lang | Status | Rules cited | Rule | Figures | Lang | Quotes | Time |
|---|---|---|---|---|---|---|---|---|
| 1 | en | answered | 56, 103 | ✅ | ✅ | ✅ | 4/4 | 8.28 s |
| 2 | en | answered | 17 | ✅ | ✅ | ✅ | 5/5 | 12.2 s |
| 3 | en | answered | 23 | ✅ | — | ✅ | 3/3 | 12.75 s |
| 4 | en | answered | 28, 35, 26-B | ✅ | — | ✅ | 4/4 | 9.76 s |
| 5 | en | answered | 52 | ✅ | ✅ | ✅ | 2/2 | 6.39 s |
| 6 | en | answered | 18, 26, 14 | ✅ | — | ✅ | 11/11 | 14.33 s |
| 7 | en | answered | 14, 16, 21, 15, 83, 19, 12 | ✅ | — | ✅ | 18/18 | 20.9 s |
| 8 | en | answered | 21, 2 | ✅ | — | ✅ | 7/7 | 15.59 s |
| 9 | en | answered | 21, 24, 10, 14 | ✅ | — | ✅ | 10/10 | 13.65 s |
| 10 | en | answered | 56 | ✅ | ✅ | ✅ | 4/4 | 7.67 s |
| 11 | en | answered | 12, 2 | ✅ | — | ✅ | 7/7 | 14.31 s |
| 12 | en | answered | 103, 61, 37 | ✅ | — | ✅ | 4/4 | 6.78 s |
| 13 | en | answered | 83, 26, 2, 42, 16 | ✅ | — | ✅ | 16/16 | 13.99 s |
| 14 | hi | answered | 56, 57 | ✅ | ✅ | ✅ | 4/4 | 17.41 s |
| 15 | hi | answered | 21 | ✅ | — | ✅ | 8/8 | 17.28 s |
| 16 | en | not_found | — | ✅ | — | ✅ | 0/0 | 3.41 s |
| 17 | en | not_found | — | ✅ | — | ✅ | 0/0 | 3.97 s |

Answer key: eval/answer_key.json. Full answers: eval/results.json.
