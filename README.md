# nonhuman

Agent-first coding mode. One 700-token skill for any coding agent.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img alt="-20% billed cost on 16 held-out SWE-Bench Pro tasks, 16/16 resolved (same as no skill), 13.7 to 11.2 model calls per run" src="assets/hero-light.svg">
</picture>

## Philosophy

Code written by agents is increasingly read only by agents. Comments, padding, narration and extra round-trips serve a human reader who is not there, and every following agent pays for them. Optimise for the next agent: **fewest billed tokens per correct, secure result.** Readability is optional. Validation, authorisation, escaping, bounds checks and error handling are not.

## Math

An agent run is N model calls. Each call re-reads the fixed prefix P and everything appended so far (Δᵢ = tool results + own output), then emits visible output oᵢ and thinking hᵢ. With prices relative to base input (cache write 1.25, cache read 0.1, output 5):

```
C = P·(1.25u + 0.1N)  +  Σᵢ Δᵢ·(1.25 + 0.1(N − i))  +  5·Σᵢ (oᵢ + hᵢ)          E[C_task] = C / p_success
    prefix re-reads       context growth                 output + thinking
```

The decomposition is accounting, not a fit: on 84 runs (830 billed calls) it matches every bill to within 0.02%. Measured on the 36-run Opus fixture study:

| quantity | value (Opus) |
|---|---|
| one extra call | ≈ 13.8k units, 5.9% of a run · corr(N, C) = 0.88 |
| one output token | ≈ 6.6 units: billed ×5, then re-read every later call |
| cost split | prefix 39% · context growth 28% · output 27% · thinking 6% |
| ceiling of "write terser code" | < 10% of the bill |

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
| billed cost (95% CI over tasks) | 1.00× | 0.98× (0.90–1.07) | **0.80× (0.74–0.87)** |
| model calls per run | 13.7 | 14.8 | **11.2** |
| resolved (hidden FAIL_TO_PASS + PASS_TO_PASS) | 16/16 | 16/16 | **16/16** |

- **Tasks:** every Python instance of the [SWE-Bench Pro](https://arxiv.org/abs/2509.16941) public `hard` split not used during development (ansible ×6, openlibrary ×6, qutebrowser ×4), each a real multi-file issue.
- **Protocol:** criteria, task list and skill hash were [pre-registered](results/real/PREREG.md) before the first run: cost ≤ 0.95×, at most 2 more lost than won discordant pairs. Both passed (0 discordant pairs).
- **Harness:** one task per session, each run in its own no-network container built from the official instance image, with hidden tests removed. Grading uses the official evaluator, the gold patch as a control on every task, and [three documented fixes](bench/real/EVALUATOR_PATCH.md) (including a race in its local-Docker mode). Code and raw data: [`bench/real/`](bench/real/), [`results/real/`](results/real/). Reproduce: clone `scaleapi/SWE-bench_Pro-os` into `data/pro-os`, apply the evaluator changes, then `bench/real/prep.py TASK ARM RUN` → run your agent on `PROMPT.md` → `bench/real/grade.py TASK` → `bench/real/billed.py`.
- **How v1.2 came about:** a 4-task pilot of v1.1 cost 0.84× but lost 2 runs that no skill won. Both losses traced to terseness leaking into the contract: a renamed identifier and an incomplete cleanup. v1.2 adds one principle against that whole class, not a patch per task, and was then tested only on tasks it had never seen.

### Controlled fixtures (secondary)

Four purpose-built services (Python, TypeScript, Rust, C) with hidden functional and **security** tests (SQL injection, path traversal, authz, overflow, XSS, ASan leaks). Specs never mention security. 3 runs per cell, several tasks per prompt.

| | no skill | Ponytail | nonhuman v1.0 | nonhuman v1.2 |
|---|---|---|---|---|
| billed cost | 1.00× | 1.00× | 0.71× | 0.86× (≈0.78× with call 1 cache-normalised) |
| security tests | 513/516 | 513/516 | 513/516 | 513/516 |
| functional tests | 499/510 | 498/510 | 498/510 | 498/510 |

v1.2 trades part of v1.0's fixture saving for the requirement check that closed the real-repo losses. All v1.2 runs started with a cold prompt cache (≈+20k units each), which is a harness artifact.

## Install

| Platform | |
|---|---|
| Claude Code | `claude plugin marketplace add nagisanzenin/nonhuman` → `claude plugin install nonhuman@nonhuman` |
| Codex | `codex plugin marketplace add nagisanzenin/nonhuman` → `codex plugin add nonhuman@nonhuman` |
| Gemini CLI | `gemini extensions install https://github.com/nagisanzenin/nonhuman` |
| Antigravity | `agy plugin install https://github.com/nagisanzenin/nonhuman` |
| Cursor · Windsurf · Cline · Copilot · Kiro | copy the file from [`rules/`](rules/) into the platform's rules folder |
| AGENTS.md agents (OpenCode, Amp, Goose, Jules) | append [`rules/AGENTS.md`](rules/AGENTS.md) |

Install routes follow each platform's documented format; not all are verified live yet.

## Limits

- The primary result is one model (Opus) and one harness (Claude Code subagents). A second-model check on DeepSeek V4.1 Flash, run on the same 16 tasks, cut cost to 0.84× (0.70–0.97) and calls from 52.7 to 39.2. It also lost one task reproducibly, 0/3 against 2/3 for no skill: [`results/real_deepseek/RESULT.md`](results/real_deepseek/RESULT.md).
- Real-repo tasks are Python only: Go and JS repos hung or ran out of memory under x86 emulation on the test machine, so they are not measured.
- n=1 per arm per task. Equal resolve rates show no large regression, not parity at the level of a few points.
- Thinking budget was left at the harness default.

MIT.
