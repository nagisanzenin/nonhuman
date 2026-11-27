# nonhuman

Agent-first coding mode. One 700-token skill for any coding agent.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img alt="-18% billed cost at Claude Opus 5.5 list prices on 16 held-out SWE-Bench Pro tasks, 16/16 resolved (same as no skill), 13.7 to 11.2 model calls per run" src="assets/hero-light.svg">
</picture>

## Philosophy

Code written by agents is increasingly read only by agents. Comments, padding, narration and extra round-trips serve a human reader who is not there, and every following agent pays for them. Optimise for the next agent: **fewest billed tokens per correct, secure result.** Readability is optional. Validation, authorisation, escaping, bounds checks and error handling are not.

## Math

An agent run is N model calls. Each call re-reads the fixed prefix P and everything appended so far (Δᵢ = tool results + its own output and thinking, which all stay in context), then emits visible output oᵢ and thinking hᵢ. With Claude Opus 5.5 list prices relative to base input (cache write 1.25, cache read 0.05, output 5):

```
C = P·(1.25u + 0.05N)  +  Σᵢ Δᵢ·(1.25 + 0.05(N − i))  +  5·Σᵢ (oᵢ + hᵢ)          E[C_task] = C / p_success
    prefix re-reads       context growth                 output + thinking
```

The decomposition is accounting, not a fit: on 84 runs (830 billed calls) it matches every bill to within 0.02%. Measured on the 48 held-out SWE-Bench Pro runs (Opus 5.5, list prices):

| quantity | value |
|---|---|
| one extra call | ≈ 13.4k units, 6.7% of an average run · corr(N, C) = 0.63 |
| an average call after the first | ≈ 13.3k units: re-read 3.7k · new context 3.7k · visible output 3.7k · thinking 2.2k |
| cost split (no skill) | prefix 32% · context growth 30% · visible output 25% · thinking 13% |
| one output or thinking token | ≈ 6.5 units end to end: 5 to write it, 1.25 to cache it, 0.05 for each later call that re-reads it |
| ceiling of "write terser code" | the code is part of the visible output, a quarter of the bill |

(Pricing note: these numbers use Opus 5.5's 5% cache read. Versions of this README before 2026-11-25 used the older 10% weight, which gave −20% instead of −18%.)

**N is the lever.** Terse code helps; fewer calls helps more.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/cost-anatomy-dark.svg">
  <img alt="Per-run cost split for no skill, Ponytail and nonhuman" src="assets/cost-anatomy-light.svg">
</picture>

## Rules (the whole skill)

1. **Fewer calls.** Batch independent tool calls; read targeted ranges once; one edit per file; verify once; check every requirement against the diff before replying.
2. **Cut ephemeral output, never the contract.** No narration, recap or re-printed code; minimal diffs; reuse before writing. Keep the spec's exact names and cover every case each requirement names: the smallest diff never means the smallest behaviour.
3. **Keep what the next agent needs.** Typed signatures (codebase convention); a one-line comment only for a non-obvious invariant or security reason; at most one compact test.
4. **Small tool output.** `-q`, `| tail`, grep for failures; never cut off the failing line.
5. **Never cut** validation, auth, escaping, path-traversal guards, bounds/overflow checks, data-loss error handling.

Full text: [`skills/nonhuman/SKILL.md`](skills/nonhuman/SKILL.md). Each rule's possible failure and its guard: [`FAILURE_MODES.md`](FAILURE_MODES.md).

## Benchmark

### Real repositories (primary, pre-registered)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/cost-per-task-dark.svg">
  <img alt="Billed cost per held-out task relative to no skill" src="assets/cost-per-task-light.svg">
</picture>

| 16 held-out tasks, Opus, n=1 per arm | no skill | Ponytail | nonhuman v1.2 |
|---|---|---|---|
| billed cost at Opus 5.5 list prices (95% CI over tasks) | 1.00× | 0.96× (0.89–1.05) | **0.82× (0.76–0.88)** |
| model calls per run | 13.7 | 14.8 | **11.2** |
| resolved (hidden FAIL_TO_PASS + PASS_TO_PASS) | 16/16 | 16/16 | **16/16** |

#### Cross-model generalisation (same 16 held-out SWE-Bench Pro tasks, n=1 per arm)

| model (harness) | no skill | Ponytail (95% CI) | nonhuman v1.2 (95% CI) | calls (base → nh) | resolved (base → nh) | data |
|---|---|---|---|---|---|---|
| **Claude Opus 5.5** (Claude Code, pre-registered) | 1.00× | 0.96× (0.89–1.05) | **0.82× (0.76–0.88)** | 13.7 → **11.2** | 16/16 → **16/16** | [`results/real/`](results/real/README.md) |
| **Gemini 4 Neon XHigh** (Antigravity CLI) | 1.00× | 0.88× (0.83–0.92) | **0.77× (0.72–0.81)** | 28.2 → **20.6** | 16/16 → **16/16** | [`results/real_gemini_neon/`](results/real_gemini_neon/RESULT.md) |
| **DeepSeek V4.1 Flash** (Claude Code `--bare`) | 1.00× | 1.00× (0.89–1.11) | **0.84× (0.70–0.97)** | 52.7 → **39.2** | 14/16 → 12/16 *(h10 0/3 vs 2/3)* | [`results/real_deepseek/`](results/real_deepseek/RESULT.md) |

- **Tasks:** every Python instance of the [SWE-Bench Pro](https://arxiv.org/abs/2509.16941) public `hard` split not used during development (ansible ×6, openlibrary ×6, qutebrowser ×4), each a real multi-file issue.
- **Protocol:** criteria, task list and skill hash were [pre-registered](results/real/PREREG.md) before the first run: cost ≤ 0.95×, at most 2 more lost than won discordant pairs. Both passed on Opus 5.5 and Gemini 4 Neon XHigh (0 discordant pairs on both; on Gemini 4 Neon XHigh, `nonhuman` also beat Ponytail at 0.87×, 95% CI 0.83–0.92, cheaper on 14/16 tasks).
- **Harness:** one task per session, each run in its own no-network container built from the official instance image, with hidden tests removed. Grading uses the official evaluator, the gold patch as a control on every task, and [three documented fixes](bench/real/EVALUATOR_PATCH.md) (including a race in its local-Docker mode). Raw data: [`results/real/`](results/real/README.md) (Opus 5.5), [`results/real_gemini_neon/`](results/real_gemini_neon/RESULT.md) (Gemini 4 Neon XHigh), [`results/real_deepseek/`](results/real_deepseek/RESULT.md) (DeepSeek V4.1 Flash). **Check the tables:** `python3 scripts/verify.py` recomputes Opus 5.5 from published files (standard library only); pass `--runs results/real_gemini_neon/billed_runs.csv --grades results/real_gemini_neon/grades_neon.jsonl` for Gemini 4 Neon XHigh (official list prices `$3 / $0.15 / $15` per 1M tokens give the same `1 / 0.05 / 5` weights). Re-run the benchmark: [`bench/real/README.md`](bench/real/README.md).
- **How v1.2 came about:** a 4-task pilot of v1.1 cost 0.84× but lost 2 runs that no skill won. Both losses traced to terseness leaking into the contract: a renamed identifier and an incomplete cleanup. v1.2 adds one principle against that whole class, not a patch per task, and was then tested only on tasks it had never seen.

### Controlled fixtures (secondary)

Four purpose-built services (Python, TypeScript, Rust, C) with hidden functional and **security** tests (SQL injection, path traversal, authz, overflow, XSS, ASan leaks). Specs never mention security. 3 runs per cell, several tasks per prompt. Costs in this table use the older 10% cache-read weight.

| | no skill | Ponytail | nonhuman v1.0 | nonhuman v1.2 | Gemini 4 Neon XHigh (v1.2, Antigravity) |
|---|---|---|---|---|---|
| billed cost | 1.00× | 1.00× | 0.71× | 0.86× (≈0.78× cache-normalised) | **0.77×** (12/12 cheaper) |
| security tests | 513/516 | 513/516 | 513/516 | 513/516 | **513/516** (vs 513/516 no skill) |
| functional tests | 499/510 | 498/510 | 498/510 | 498/510 | **501/510** (vs 501/510 no skill) |

v1.2 trades part of v1.0's fixture saving for the requirement check that closed the real-repo losses. All Opus v1.2 runs started with a cold prompt cache (≈+20k units each), which is a harness artifact. Gemini 4 Neon XHigh fixture data (at official `$3 / $0.15 / $15` list prices): [`results/fixture_gemini_neon/`](results/fixture_gemini_neon/README.md).

## Install

| Platform | |
|---|---|
| Claude Code | `claude plugin marketplace add nagisanzenin/nonhuman` → `claude plugin install nonhuman@nonhuman` |
| Codex | `codex plugin marketplace add nagisanzenin/nonhuman` → `codex plugin add nonhuman@nonhuman` |
| Gemini CLI | `gemini extensions install https://github.com/nagisanzenin/nonhuman` |
| Antigravity | `agy plugin install https://github.com/nagisanzenin/nonhuman` |
| Cursor · Windsurf · Cline · Copilot · Kiro | copy the file from [`rules/`](rules/) into the platform's rules folder |
| AGENTS.md agents (OpenCode, Amp, Goose, Jules) | append [`rules/AGENTS.md`](rules/AGENTS.md) |

Claude Code and Antigravity install routes are verified live; other platform routes follow each platform's documented format.

## Limits

- Tested across three models and two harnesses on the same 16 held-out tasks: **Claude Opus 5.5** (Claude Code, pre-registered: 0.82×, 16/16), **Gemini 4 Neon XHigh** (Antigravity CLI: 0.77× at `$3 / $0.15 / $15` list prices, 16/16, [`results/real_gemini_neon/RESULT.md`](results/real_gemini_neon/RESULT.md)), and **DeepSeek V4.1 Flash** (Claude Code `--bare`: 0.84×, 12/16 vs 14/16, [`results/real_deepseek/RESULT.md`](results/real_deepseek/RESULT.md)). DeepSeek lost one task reproducibly (`h10`: 0/3 vs 2/3 for no skill; Ponytail also 0/3), showing that weaker models can drop defensive shape checks under minimal-diff rules.
- Real-repo tasks are Python only: Go and JS repos hung or ran out of memory under x86 emulation on the test machine, so they are not measured.
- n=1 per arm per task. Equal resolve rates show no large regression, not parity at the level of a few points.
- Thinking budget was left at the harness default.

MIT.
