# nonhuman

**Agent-first coding mode. −30% billed tokens on Claude Opus across Python, TypeScript, Rust and C, with the same hidden-test and security results as no skill.**

One 500-token skill. Works with any agent that reads `SKILL.md`, `AGENTS.md` or rule files.

## Philosophy

Code written by agents is increasingly read only by agents. Comments, docstrings, padding, narration and extra round-trips serve human readers and cost every agent that follows. `nonhuman` optimises for the next agent instead: fewest billed tokens per correct, secure result. Readability is optional. Validation, authorisation, escaping, bounds checks and error handling are never optional.

## Install

| Platform | Install |
|---|---|
| Claude Code | `claude plugin marketplace add nagisanzenin/nonhuman` → `claude plugin install nonhuman@nonhuman` |
| OpenAI Codex | `codex plugin marketplace add nagisanzenin/nonhuman` → `codex plugin add nonhuman@nonhuman` |
| Gemini CLI | `gemini extensions install https://github.com/nagisanzenin/nonhuman` |
| Antigravity | `agy plugin install https://github.com/nagisanzenin/nonhuman` |
| Cursor | copy `rules/cursor/nonhuman.mdc` → `.cursor/rules/` |
| Windsurf | copy `rules/windsurf/nonhuman.md` → `.windsurf/rules/` |
| Cline | copy `rules/cline/nonhuman.md` → `.clinerules/` |
| GitHub Copilot | copy `rules/copilot/copilot-instructions.md` → `.github/` |
| Kiro | copy `rules/kiro/nonhuman.md` → `.kiro/steering/` |
| OpenCode, Amp, Goose, Jules, anything reading `AGENTS.md` | append `rules/AGENTS.md` to your `AGENTS.md` |
| Any `SKILL.md` platform | point it at `skills/` |

One source of truth: `skills/nonhuman/SKILL.md`. `python3 scripts/build_rules.py` regenerates `rules/`.

Status: the skill text is what the benchmark measured. The install routes follow each platform's documented format and are **not yet verified live**; please open an issue with what you see.

## Results (Claude Opus, 36 runs, 207 task attempts)

Billed cost per run, in base-input-token units:

| | baseline | Ponytail | **nonhuman** |
|---|---|---|---|
| Python | 353k | 346k (0.98×) | **201k (0.57×)** |
| TypeScript | 183k | 194k (1.06×) | **177k (0.97×)** |
| Rust | 267k | 243k (0.91×) | **185k (0.69×)** |
| C | 237k | 257k (1.08×) | **169k (0.71×)** |
| **All** | 260k | 260k (1.00×) | **183k (0.70×)** |

| per run | baseline | Ponytail | nonhuman |
|---|---|---|---|
| model calls | 12.2 | 13.2 | **7.4** |
| output tokens | 17,461 | 16,421 | **12,356** |
| thinking tokens | 2,701 | 2,459 | 3,202 |
| functional tests passed | 499/510 | 498/510 | 498/510 |
| security tests passed | 513/516 | 513/516 | 513/516 |

The one functional difference is a TypeScript check that is ambiguous in the spec (empty discount code: 400 or 404). One baseline run passed it; every other run of every arm failed it.

## The math

Every call re-reads the whole context. For a run of N calls with fixed prefix P, appended context Δᵢ (tool results + own output), visible output oᵢ and thinking hᵢ:

```
C = P·(1.25u + 0.1N) + Σᵢ Δᵢ·(1.25 + 0.1(N−i)) + 5·Σᵢ(oᵢ + hᵢ)        E[C_task] = C / p_success
```

(u = uncached share of P; weights = Anthropic prices relative to base input.) Fitted on 437 calls, it reproduces every run's bill to within 28 units of ~170k.

| what it means | measured |
|---|---|
| one extra model call | ≈ 12.5k units, ~7% of a run (corr(N, cost) = 0.81) |
| one output token | ≈ 6.6 units (billed 5×, then re-read as context) |
| cost split | prefix 34% · context growth 31% · visible output 27% · thinking 8% |
| code terseness alone | capped below 10% of total |

So the skill's first rule is **fewer calls**: batch independent tool calls, read targeted ranges once, edit each file once, verify once. Then less output. Details: [`results/MODEL.md`](results/MODEL.md).

## Method

- 4 fixtures (Python service, TypeScript service, Rust crate, C library), 23 feature tasks. Each task has hidden **functional** and **security** tests; specs never mention security; the codebases contain the guard helpers a careful engineer should reuse. Reference solutions pass 100%; mutation checks confirm the security tests catch real flaws.
- Arms: no skill, [Ponytail](https://github.com/DietrichGebert/ponytail) (MIT, strongest public alternative), nonhuman. Same prompt otherwise.
- Cost: per-call `usage` (input, cache write, cache read, output, thinking) from agent transcripts, not estimates.
- Reproduce: `python3 bench/prep.py <py|ts|rs|c> <arm> <run>` → run your agent on the generated `PROMPT.md` → `python3 bench/score.py <lang>` → `python3 bench/billed.py <transcripts_dir>` → `python3 scripts/summarize.py`. Needs `tiktoken`, `pytest`, Node ≥ 22, Rust, clang.

## Limits

- One harness (Claude Code subagents), Opus for v1.0 (an earlier Sonnet run of v0.1 is in `results/quality_*_sonnet_v1.json`), 3 runs per cell, small purpose-built fixtures.
- Prompts held several tasks; batching across tasks helps. Single-task sessions will save less (TypeScript, already lean at 7 calls, saved 3%).
- Thinking budget was left at the harness default.

## License

MIT. Benchmark includes Ponytail's `SKILL.md` under its MIT license (`bench/arms/`).
