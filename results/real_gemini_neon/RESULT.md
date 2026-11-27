# Gemini 4 Neon XHigh on the 16 held-out SWE-Bench Pro tasks (and controlled fixtures)

Third model (`gemini-4-neon-xhigh`), second harness (Antigravity CLI), same 16 held-out tasks (`h01`–`h16`), same `nonhuman` v1.2.0 skill text, same Ponytail comparator (`sha256 3868c7aa…f379`), same official SWE-Bench Pro evaluator. Not pre-registered; this is a cross-model and cross-harness generalisation check.

**Official Gemini 4 Neon list prices (flat across 1M context, implicit caching only):** `$3.00` / 1M input (`1×`), `$0.15` / 1M cached input (`0.05×`, 95% off, no cache-write fee), `$15.00` / 1M output including thinking (`5×`).

## 1. Real repositories (`h01`–`h16`, SWE-Bench Pro)

| 16 tasks, `gemini-4-neon-xhigh`, n=1 per arm | no skill | Ponytail | nonhuman v1.2 |
|---|---|---|---|
| billed cost at Gemini 4 Neon list prices (95% CI over tasks) | 1.000× | 0.876× (0.830–0.920) | **0.766× (0.722–0.811)** |
| implied API cost across 16 tasks (`$3 / $0.15 / $15` per 1M) | $42.20 ($2.64/task) | $36.96 ($2.31/task) | **$32.32 ($2.02/task)** |
| model calls per run | 28.2 | 24.8 | **20.6** |
| thinking tokens per run | 83.0k | 74.7k | **67.5k** |
| wall time per run | 16.2m | 14.6m | **13.8m** |
| resolved (hidden `FAIL_TO_PASS` + `PASS_TO_PASS`) | 16/16 | 16/16 | **16/16** |
| discordant pairs vs no skill | — | W0 / L0 | **W0 / L0** |
| cheaper than no skill on | — | 14/16 | **16/16** |

- **Head-to-head `nonhuman` vs Ponytail:** **0.874× (0.829–0.922)** (`nonhuman` is cheaper than Ponytail on **14/16** tasks).
- **By repository:** `ansible/ansible` (n=6) Ponytail `0.866×` / **nonhuman `0.729×`**; `internetarchive/openlibrary` (n=6) Ponytail `0.887×` / **nonhuman `0.815×`**; `qutebrowser/qutebrowser` (n=4) Ponytail `0.873×` / **nonhuman `0.734×`**.
- **Gold control:** resolved on **16/16** tasks. All 48 runs ended cleanly (`SUCCESS`, 0 turn-cap/timeout hits).
- **`h10` stress test:** on DeepSeek V4.1 Flash, both `nonhuman` and Ponytail lost `h10` reproducibly (`0/3` vs `2/3` for no skill). On Gemini 4 Neon XHigh, all three arms resolved `h10` cleanly (`7/7` `f2p`, `10/10` `p2p`), with `nonhuman` cutting cost to `0.792×` (`17` vs `23` calls).
- **Where the bill goes on Gemini 4 Neon XHigh (no skill mean: 879.3k base-input units = $2.64/run):** output + thinking is `57.7%` (`47.2%` thinking, `10.6%` visible), fresh input `24.5%`, cache reads `17.8%`. `nonhuman` cuts calls by `-27.0%`, cache reads by `-44.8%` (`3.13M → 1.73M`), fresh input by `-21.6%` (`215.1k → 168.7k`), and thinking+visible output by `-17.5%` (`101.5k → 83.7k`).
- **Verify independently from the published CSV/JSONL:**
  ```bash
  python3 scripts/verify.py --runs results/real_gemini_neon/billed_runs.csv --grades results/real_gemini_neon/grades_neon.jsonl --tasks
  ```

### Per-task breakdown (`h01`–`h16`, Gemini 4 Neon list prices `1 / 0.05 cr / 5 out`)

| task | repo | no skill (k · calls) | Ponytail (k · calls · ratio) | nonhuman (k · calls · ratio) | resolved (`base / pt / nh / gold`) |
|---|---|---:|---:|---:|---|
| h01 | ansible | 1,237.7 · 27 | 1,207.0 · 22 · 0.975× | **997.3 · 21 · 0.806×** | yes / yes / yes / yes |
| h02 | ansible | 1,048.0 · 39 | 889.9 · 40 · 0.849× | **733.9 · 28 · 0.700×** | yes / yes / yes / yes |
| h03 | ansible | 626.6 · 14 | 565.6 · 17 · 0.903× | **504.6 · 13 · 0.805×** | yes / yes / yes / yes |
| h04 | ansible | 1,473.8 · 33 | 1,276.2 · 29 · 0.866× | **1,034.3 · 24 · 0.702×** | yes / yes / yes / yes |
| h05 | ansible | 1,126.2 · 31 | 825.1 · 24 · 0.733× | **744.4 · 23 · 0.661×** | yes / yes / yes / yes |
| h06 | ansible | 310.8 · 15 | 277.4 · 13 · 0.892× | **230.6 · 11 · 0.742×** | yes / yes / yes / yes |
| h07 | openlibrary | 921.3 · 35 | 751.1 · 22 · 0.815× | **660.7 · 18 · 0.717×** | yes / yes / yes / yes |
| h08 | openlibrary | 1,163.7 · 34 | **864.6 · 23 · 0.743×** | 896.0 · 18 · 0.770× | yes / yes / yes / yes |
| h09 | openlibrary | 1,297.9 · 26 | 1,225.7 · 28 · 0.944× | **1,203.2 · 29 · 0.927×** | yes / yes / yes / yes |
| h10 | openlibrary | 447.0 · 23 | 442.4 · 21 · 0.990× | **354.1 · 17 · 0.792×** | yes / yes / yes / yes |
| h11 | openlibrary | 702.8 · 25 | 706.4 · 30 · 1.005× | **569.9 · 20 · 0.811×** | yes / yes / yes / yes |
| h12 | openlibrary | 1,336.6 · 34 | 1,214.2 · 28 · 0.908× | **1,099.7 · 26 · 0.823×** | yes / yes / yes / yes |
| h13 | qutebrowser | 762.4 · 32 | 765.0 · 30 · 1.003× | **546.5 · 23 · 0.717×** | yes / yes / yes / yes |
| h14 | qutebrowser | 500.4 · 24 | 406.6 · 25 · 0.812× | **305.3 · 15 · 0.610×** | yes / yes / yes / yes |
| h15 | qutebrowser | 648.4 · 29 | 516.4 · 22 · 0.796× | **440.5 · 21 · 0.679×** | yes / yes / yes / yes |
| h16 | qutebrowser | 464.5 · 31 | **386.1 · 23 · 0.831×** | 452.2 · 23 · 0.973× | yes / yes / yes / yes |

## 2. Controlled fixtures (24 runs: `py, ts, rs, c` × 3 replicates, `baseline` vs `nonhuman`)

Raw files: [`../fixture_gemini_neon/`](../fixture_gemini_neon/README.md). Same 4-language fixture suite (23 tasks, 170 hidden functional + 172 hidden security tests per replicate), 900s timeout per run.

| metric (12 runs per arm) | no skill | nonhuman v1.2 | ratio / delta |
|---|---:|---:|---:|
| billed cost at Gemini 4 Neon list prices (95% CI) | 406.0k/run ($14.62 tot) | **311.0k/run ($11.20 tot)** | **0.766× (0.729–0.808)** · 12/12 cheaper |
| model calls per run | 8.9 | **6.1** | **-31.8%** |
| added code tokens (`o200k_base`) per run | 8,948 | **5,671** | **-36.6%** |
| wall time per run | 504.7s | **384.0s** | **-23.9%** |
| hidden security tests | 513/516 | **513/516** | exact tie (`py` 126/126, `ts` 96/99, `rs` 90/90, `c` 201/201) |
| hidden functional tests | 501/510 | **501/510** | exact tie (`py` 150/150, `ts` 78/87, `rs` 93/93, `c` 180/180) |

Per-language cost ratios: `py` `0.839×`, `ts` `0.803×`, `rs` `0.744×`, `c` `0.698×`.

## 3. Harness & Independent Audit

- **Harness:** Antigravity CLI (`agy -p ... --model gemini-4-neon-xhigh --output-format stream-json --dangerously-skip-permissions --print-timeout 2700s`). Each SWE-Bench Pro run executed in its own `--network none` `linux/amd64` Docker container via a shell wrapper `x`. All subagent invocations were disabled in the prompt (`0` subagent calls verified across all 72 streams).
- **Git history purge:** before every SWE-Bench Pro run, `/tests` and `/workspace` were removed, all git refs were deleted (`git for-each-ref | wc -l == 0`), and unreachable objects were pruned (`git gc --prune=now`).
- **Arm activation & prefix accounting:**
  - `nonhuman` was installed as a real Antigravity plugin (`agy plugin install`) and toggled live via `agy plugin enable/disable nonhuman` (no concurrent cross-arm execution).
  - Because this repository ships both `rules/AGENTS.md` and `rules/GEMINI.md` (the latter for `gemini-extension.json`), Antigravity loaded **both** copies on the `nonhuman` arm, adding **+1,467 tokens** to turn-1 `ctx0` (mean `+1,442` across 16 SWE-Pro tasks; `+1,462.5` across 12 fixture pairs) instead of `+700`. `ponytail` was injected once without frontmatter (`+715` tokens on `h03`–`h16`). `nonhuman` therefore beat both `baseline` and `ponytail` while carrying ~2× the rule prefix overhead.
  - On `h01`/`h02`, the Antigravity hub restarted between an initial 900s-timeout batch (discarded for `h01`, kept for `h02 nonhuman` which had already finished cleanly in 724.7s) and the 2700s re-run, shifting baseline `ctx0` by ~+410 tokens (`<0.15%` of run cost; `0.02%` of total 16-task cost).
- **Discarded attempts:** three initial SWE-Bench Pro runs (`h01 baseline`, `h02 baseline`, `h01 nonhuman`) hit a 900s timeout before the timeout was raised to 2700s (matching the DeepSeek harness); two `h15`/`h16 nonhuman` runs hit a 5h rolling quota limit and were re-run cleanly after reset; two `h08`/`h09 ponytail` runs hit a 3s 0-call backend handshake error and were re-run cleanly. All 48 published SWE-Pro runs and 24 fixture runs completed with `status == SUCCESS`.
- **Independent raw-stream audit:** all 72 raw `.stream.jsonl` logs and 48 SWE-Bench Pro `.diff` patches were re-parsed from scratch: `0` token mismatches against CSVs, `0` subagent calls, `0` leak flags, `0` edits to hidden `test_patch` files, `0` binary diffs, and `16/16` passing `gold_r0` controls.
