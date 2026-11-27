# Controlled fixture results — Gemini 4 Neon XHigh (Antigravity CLI)

24 clean runs (`py, ts, rs, c` × 3 replicates × `{baseline, nonhuman}`) using `agy` with `gemini-4-neon-xhigh` and `nonhuman` v1.2.0 installed as an Antigravity plugin (`agy plugin enable/disable nonhuman`).

| file | content |
|---|---|
| `billed_runs.csv` | one row per run (24 rows; `cost` column uses official Gemini 4 Neon list prices `$3 / $0.15 / $15` per 1M = `in + 0.05·cr + 5·out`) |
| `billed_calls.csv` | one row per model call parsed from raw `agy --output-format stream-json` logs |
| `quality.json` | per-run and per-task hidden functional/security test results and `o200k_base` `added_tok` |

Summary and methodology: see [`../real_gemini_neon/RESULT.md`](../real_gemini_neon/RESULT.md#2-controlled-fixtures-24-runs-py-ts-rs-c--3-replicates-baseline-vs-nonhuman).
