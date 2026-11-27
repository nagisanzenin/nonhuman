# Gemini 4 Neon XHigh on the 16 held-out SWE-Bench Pro tasks (and controlled fixtures)

Third model (`gemini-4-neon-xhigh`), second harness (Antigravity CLI), same 16 held-out tasks (`h01`–`h16`), same `nonhuman` v1.2.0 skill text, same Ponytail comparator (`sha256 3868c7aa…f379`), same official SWE-Bench Pro evaluator. Not pre-registered; this is a cross-model and cross-harness generalisation check.

## 1. Real repositories (`h01`–`h16`, SWE-Bench Pro)

| 16 tasks, `gemini-4-neon-xhigh`, n=1 per arm | no skill | Ponytail | nonhuman v1.2 |
|---|---|---|---|
| cost, Gemini weights `1 / 0.10 cr / 6 out` (95% CI over tasks) | 1.000× | 0.865× (0.815–0.914) | **0.742× (0.696–0.790)** |
| cost, Anthropic Opus 5.5 weights `1 / 0.05 cr / 5 out` (95% CI) | 1.000× | 0.876× (0.830–0.920) | **0.766× (0.722–0.811)** |
| model calls per run | 28.2 | 24.8 | **20.6** |
| thinking tokens per run | 83.0k | 74.7k | **67.5k** |
| wall time per run | 16.2m | 14.6m | **13.8m** |
| resolved (hidden `FAIL_TO_PASS` + `PASS_TO_PASS`) | 16/16 | 16/16 | **16/16** |
| discordant pairs vs no skill | — | W0 / L0 | **W0 / L0** |
| cheaper than no skill on (Gemini / Anthropic weights) | — | 15/16 · 14/16 | **16/16 · 16/16** |

- **Head-to-head `nonhuman` vs Ponytail:** **0.857× (0.810–0.905)** at Gemini weights and **0.874× (0.829–0.922)** at Anthropic weights (`nonhuman` is cheaper than Ponytail on **14/16** tasks).
- **By repository (Gemini weights):** `ansible/ansible` (n=6) Ponytail `0.858×` / **nonhuman `0.711×`**; `internetarchive/openlibrary` (n=6) Ponytail `0.873×` / **nonhuman `0.785×`**; `qutebrowser/qutebrowser` (n=4) Ponytail `0.863×` / **nonhuman `0.707×`**.
- **Gold control:** resolved on **16/16** tasks. All 48 runs ended cleanly (`SUCCESS`, 0 turn-cap/timeout hits).
- **`h10` stress test:** on DeepSeek V4.1 Flash, both `nonhuman` and Ponytail lost `h10` reproducibly (`0/3` vs `2/3` for no skill). On Gemini 4 Neon XHigh, all three arms resolved `h10` cleanly (`7/7` `f2p`, `10/10` `p2p`), with `nonhuman` cutting cost to `0.759×` (`17` vs `23` calls).
- **Where the bill goes on Gemini 4 Neon XHigh (no skill mean: 1,137.3k Gemini units):** output + thinking is `53.6%` (`43.8%` thinking, `9.8%` visible), cache reads `27.5%`, fresh input `18.9%`. `nonhuman` cuts calls by `-27.0%`, cache reads by `-44.8%` (`3.13M → 1.73M`), fresh input by `-21.6%` (`215.1k → 168.7k`), and thinking+visible output by `-17.5%` (`101.5k → 83.7k`).
- **Verify independently from the published CSV/JSONL:**
  ```bash
  python3 scripts/verify.py --runs results/real_gemini_neon/billed_runs.csv --grades results/real_gemini_neon/grades_neon.jsonl --cache-read 0.10 --output-weight 6.0 --tasks
  python3 scripts/verify.py --runs results/real_gemini_neon/billed_runs.csv --grades results/real_gemini_neon/grades_neon.jsonl --cache-read 0.05 --output-weight 5.0
  ```

### Per-task breakdown (`h01`–`h16`, Gemini weights `1 / 0.10 cr / 6 out`)

| task | repo | no skill (k · calls) | Ponytail (k · calls · ratio) | nonhuman (k · calls · ratio) | resolved (`base / pt / nh / gold`) |
|---|---|---:|---:|---:|---|
| h01 | ansible | 1,554.5 · 27 | 1,495.8 · 22 · 0.962× | **1,229.9 · 21 · 0.791×** | yes / yes / yes / yes |
| h02 | ansible | 1,415.5 · 39 | 1,189.6 · 40 · 0.840× | **955.4 · 28 · 0.675×** | yes / yes / yes / yes |
| h03 | ansible | 751.3 · 14 | 694.7 · 17 · 0.925× | **610.7 · 13 · 0.813×** | yes / yes / yes / yes |
| h04 | ansible | 1,895.3 · 33 | 1,639.2 · 29 · 0.865× | **1,301.1 · 24 · 0.686×** | yes / yes / yes / yes |
| h05 | ansible | 1,481.1 · 31 | 1,056.0 · 24 · 0.713× | **946.8 · 23 · 0.639×** | yes / yes / yes / yes |
| h06 | ansible | 384.6 · 15 | 344.1 · 13 · 0.895× | **278.3 · 11 · 0.724×** | yes / yes / yes / yes |
| h07 | openlibrary | 1,228.9 · 35 | 953.0 · 22 · 0.776× | **813.7 · 18 · 0.662×** | yes / yes / yes / yes |
| h08 | openlibrary | 1,526.6 · 34 | **1,088.2 · 23 · 0.713×** | 1,097.6 · 18 · 0.719× | yes / yes / yes / yes |
| h09 | openlibrary | 1,630.9 · 26 | 1,539.3 · 28 · 0.944× | **1,513.7 · 29 · 0.928×** | yes / yes / yes / yes |
| h10 | openlibrary | 572.8 · 23 | 563.3 · 21 · 0.983× | **434.9 · 17 · 0.759×** | yes / yes / yes / yes |
| h11 | openlibrary | 901.9 · 25 | 933.0 · 30 · 1.034× | **714.0 · 20 · 0.792×** | yes / yes / yes / yes |
| h12 | openlibrary | 1,737.7 · 34 | 1,555.0 · 28 · 0.895× | **1,394.7 · 26 · 0.803×** | yes / yes / yes / yes |
| h13 | qutebrowser | 1,010.1 · 32 | 1,005.8 · 30 · 0.996× | **706.1 · 23 · 0.699×** | yes / yes / yes / yes |
| h14 | qutebrowser | 645.3 · 24 | 529.5 · 25 · 0.820× | **376.4 · 15 · 0.583×** | yes / yes / yes / yes |
| h15 | qutebrowser | 836.0 · 29 | 650.1 · 22 · 0.778× | **556.4 · 21 · 0.666×** | yes / yes / yes / yes |
| h16 | qutebrowser | 623.8 · 31 | **502.1 · 23 · 0.805×** | 563.4 · 23 · 0.903× | yes / yes / yes / yes |

## 2. Controlled fixtures (24 runs: `py, ts, rs, c` × 3 replicates, `baseline` vs `nonhuman`)

Raw files: [`../fixture_gemini_neon/`](../fixture_gemini_neon/README.md). Same 4-language fixture suite (23 tasks, 170 hidden functional + 172 hidden security tests per replicate), 900s timeout per run.

| metric (12 runs per arm) | no skill | nonhuman v1.2 | ratio / delta |
|---|---:|---:|---:|
| cost, Gemini weights `1 / 0.10 cr / 6 out` (95% CI) | 485.6k/run | **366.1k/run** | **0.754× (0.714–0.799)** · 12/12 cheaper |
| cost, Anthropic weights `1 / 0.05 cr / 5 out` (95% CI) | 406.0k/run | **311.0k/run** | **0.766× (0.729–0.808)** · 12/12 cheaper |
| cost, legacy 10% weights `1 / 0.10 cr / 5 out` (95% CI) | 428.1k/run | **322.0k/run** | **0.752× (0.711–0.799)** · 12/12 cheaper |
| model calls per run | 8.9 | **6.1** | **-31.8%** |
| added code tokens (`o200k_base`) per run | 8,948 | **5,671** | **-36.6%** |
| wall time per run | 504.7s | **384.0s** | **-23.9%** |
| hidden security tests | 513/516 | **513/516** | exact tie (`py` 126/126, `ts` 96/99, `rs` 90/90, `c` 201/201) |
| hidden functional tests | 501/510 | **501/510** | exact tie (`py` 150/150, `ts` 78/87, `rs` 93/93, `c` 180/180) |

Per-language Gemini cost ratios: `py` `0.830×`, `ts` `0.794×`, `rs` `0.731×`, `c` `0.684×`.

## 3. Harness & Independent Audit

- **Harness:** Antigravity CLI (`agy -p ... --model gemini-4-neon-xhigh --output-format stream-json --dangerously-skip-permissions --print-timeout 2700s`). Each SWE-Bench Pro run executed in its own `--network none` `linux/amd64` Docker container via a shell wrapper `x`. All subagent invocations were disabled in the prompt (`0` subagent calls verified across all 72 streams).
- **Git history purge:** before every SWE-Bench Pro run, `/tests` and `/workspace` were removed, all git refs were deleted (`git for-each-ref | wc -l == 0`), and unreachable objects were pruned (`git gc --prune=now`).
- **Arm activation & prefix accounting:**
  - `nonhuman` was installed as a real Antigravity plugin (`agy plugin install`) and toggled live via `agy plugin enable/disable nonhuman` (no concurrent cross-arm execution).
  - Because this repository ships both `rules/AGENTS.md` and `rules/GEMINI.md` (the latter for `gemini-extension.json`), Antigravity loaded **both** copies on the `nonhuman` arm, adding **+1,467 tokens** to turn-1 `ctx0` (mean `+1,442` across 16 SWE-Pro tasks; `+1,462.5` across 12 fixture pairs) instead of `+700`. `ponytail` was injected once without frontmatter (`+715` tokens on `h03`–`h16`). `nonhuman` therefore beat both `baseline` and `ponytail` while carrying ~2× the rule prefix overhead.
  - On `h01`/`h02`, the Antigravity hub restarted between an initial 900s-timeout batch (discarded for `h01`, kept for `h02 nonhuman` which had already finished cleanly in 724.7s) and the 2700s re-run, shifting baseline `ctx0` by ~+410 tokens (`<0.15%` of run cost; `0.02%` of total 16-task cost).
- **Discarded attempts:** three initial SWE-Bench Pro runs (`h01 baseline`, `h02 baseline`, `h01 nonhuman`) hit a 900s timeout before the timeout was raised to 2700s (matching the DeepSeek harness); two `h15`/`h16 nonhuman` runs hit a 5h rolling quota limit and were re-run cleanly after reset; two `h08`/`h09 ponytail` runs hit a 3s 0-call backend handshake error and were re-run cleanly. All 48 published SWE-Pro runs and 24 fixture runs completed with `status == SUCCESS`.
- **Independent raw-stream audit:** all 72 raw `.stream.jsonl` logs and 48 SWE-Bench Pro `.diff` patches were re-parsed from scratch: `0` token mismatches against CSVs, `0` subagent calls, `0` leak flags, `0` edits to hidden `test_patch` files, `0` binary diffs, and `16/16` passing `gold_r0` controls.
