# Real-repository results

`python3 scripts/verify.py` reads this folder and prints the README table, its bootstrap interval and the
pre-registered checks. `--tasks` adds one row per task; `--cache-read 0.1` reproduces the older price weight.

| file | content |
|---|---|
| `PREREG.md` | criteria, task list and skill hash, written before the first v1.2 run |
| `skill_under_test.md` | the skill text that was tested (sha256 in `PREREG.md`) |
| `task_ids.json` | short id to SWE-Bench Pro instance id. `h01`..`h16` are the held-out tasks; the rest are pilot tasks |
| `usage.csv` | run manifest: agent id, task, arm, run |
| `billed_calls.csv` | one row per model call |
| `billed_runs.csv` | one row per run |
| `grades_heldout.jsonl` | official-evaluator grade per held-out run, plus the gold patch (`arm: gold`) as a control |
| `grades_pilot_regraded.jsonl` | the pilot runs, re-graded after the evaluator fix |

Both CSVs hold 96 Opus runs: 48 held-out (16 tasks × 3 arms, run 1) and 48 pilot.

## Columns

| column | meaning |
|---|---|
| `agent` | first 6 characters of the Claude Code subagent id |
| `task`, `arm`, `run` | short task id; `baseline`, `ponytail` or `nonhuman`; run number |
| `call` / `calls` | index of the model call in the run / number of calls |
| `in` | uncached input tokens |
| `cw` | tokens written to the prompt cache |
| `cr` | tokens read from the prompt cache |
| `out` | output tokens, **thinking included** |
| `think` | thinking tokens (a part of `out`) |
| `ctx` | `in + cw + cr`, the context the call read. `ctx0` and `ctx_last` are the first and last call's |
| `cost` | `in + 1.25·cw + 0.05·cr + 5·out`, in units of one fresh input token at Claude Opus 5.5 list prices |
| `tool_result_tok`, `tool_use_tok`, `text_tok` | tiktoken `o200k_base` counts of tool results, tool-call inputs and prose. These are not Claude tokens |

Until 2026-11-26 the `cost` column used a cache-read weight of 0.1, which gives 0.802× for nonhuman instead of 0.816×.
`scripts/verify.py` never reads `cost`; it recomputes from the token columns. The fixture CSVs one level up
(`results/billed_*.csv`) still use 0.1, as the README says for that table.
