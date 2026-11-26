# Token-cost model of an agentic coder (fitted on 48 runs, 437 API calls)

> Correction, 2026-11-26: thinking tokens stay in context in this harness. In the per-call data, the cache write of
> the next call is never smaller than the previous call's output including thinking. Section 1 is fixed below. The
> measured shares in section 2 are unaffected, because the carried thinking was already counted under growth. The
> lever estimates further down price thinking at 5 per token and so understate it by about a quarter. This document
> uses the older cache-read weight of 0.1; Claude Opus 5.5 charges 0.05.

Source data: per-call `usage` from the subagent transcripts of the north-star A/B (`billed.py` →
`billed_calls.csv`, `billed_runs.csv`, `billed_decomposition.md`). Prices relative to base input = 1:
cache write (5-min) 1.25, cache read 0.1, output 5, thinking billed as output (Anthropic pricing).

## 1. The equation

An agent run is a loop of N model calls. Call i sees the whole context so far, which is the fixed prefix P
plus everything appended by earlier calls. Each call appends Δ_i = r_i + o_i + h_i (tool results it receives,
visible output and thinking it emits). Every appended token is written to the prompt cache once and read back on every
later call.

```
C_run = P·(1.25·u + 0.1·N)                       prefix: system prompt + tool defs + rules + task
      + Σ_i Δ_i·(1.25 + 0.1·(N − i))             growth: tool output, own output and thinking, re-read every call
      + 5·Σ_i (o_i + h_i)                        output: visible output o_i and thinking h_i

E[C_task] = C_run / p_success                    failed attempts and retries multiply everything
```

u = share of P not already in cache (≈ 0.29 here: 14k of 48.5k; the rest is shared across agents).
Uncached input is ≈ 0 in a cached harness (18 tokens per run on average) and drops out.

Effective price per token by where it sits:

| token kind | price | why |
|---|---|---|
| prefix token | 0.1·N (+1.25 once if not shared) | re-read on every call |
| tool-result token arriving at call i | 1.25 + 0.1·(N − i) ≈ 1.6 | written once, re-read after |
| visible output token (code, commands, text) | 5 + 1.25 + 0.1·(N − i) ≈ 6.6 | billed as output, then carried as context |
| thinking token | 5 + 1.25 + 0.1·(N − i) ≈ 6.6 | billed as output, then carried as context |
| one extra call | ≈ 12.5k units (measured, OLS) | 0.1·(P + current context) + its own output |

## 2. Fit to the data (means per run, all languages)

| arm | N | P | G = Σ Δ | prefix | growth | output (visible) | thinking | total | vs base |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 8.7 | 48.5k | 30.3k | 58.3k | 50.6k | 49.5k | 12.9k | 171.3k | 1.000× |
| ponytail | 9.6 | 48.5k | 33.5k | 62.8k | 58.0k | 53.1k | 12.3k | 186.2k | 1.087× |
| dense v1 | 8.8 | 48.5k | 29.2k | 58.7k | 53.4k | 40.2k | 16.4k | 168.7k | 0.985× |
| both | 9.4 | 48.5k | 32.6k | 61.9k | 57.0k | 49.8k | 15.7k | 184.4k | 1.077× |

- The decomposition reproduces every run's billed total to within 28 units (of ~170k).
- **Cost shares: prefix 34%, growth 31%, visible output 27%, thinking 8%.** Code is part of the 27%.
- corr(N, cost) = 0.81 across runs; one extra call ≈ 12.5k units ≈ 7% of a run.
- dense v1 cut visible output by 19% but thinking rose 27%, so the net was −1.5%. Ponytail cost +8.7%: about
  one extra call per run plus the test files it writes (more output, more growth).

## 3. Levers, ranked by headroom (baseline run = 171k units)

| # | lever | term | elasticity (measured) | realistic change | est. saving | who controls it |
|---|---|---|---|---|---|---|
| 1 | **fewer calls** (batch independent tool calls, edit several hunks per call, narrow test first + one final full run, no re-reads) | N | 12.5k per call | 8.7 → 6 calls | **≈ −20%** | skill / agent policy |
| 2 | **smaller prefix** (fewer/deferred tool definitions, shorter system prompt, shorter rules) | P | 0.1·N = 0.87 per token | −30% of P | ≈ −10% | harness; a skill only adds to P (dense = 451 tok ≈ +0.5%) |
| 3 | **less visible output** (minimal diffs via Edit not Write, no comments/docstrings, no prose recap) | o | 6.6 per token | −20% | ≈ −6% | skill (dense v1 achieved −19%) |
| 4 | **bounded thinking** | h | 5 per token | back to baseline or −30% | ≈ −2 to −4% | harness effort/budget setting; prompt wording did not work (v1 +27%) |
| 5 | **quiet tool output** (-q flags, tail/grep, read line ranges) | r | ≈ 1.6 per token | −30% of 9k | ≈ −3% | skill |
| 6 | **cache hygiene** (stable prefix, no gaps over the cache TTL, shared prefix across parallel agents) | u, 1.25 vs 0.1 | 1.15 per rewritten token | avoid one 48k rewrite | ≈ −30% when it happens | harness / operator |
| 7 | **first-try success** (types, tests, reuse of guard helpers) | p_success | multiplies all | — | large when p < 1 | skill + model choice |
| 8 | price per token (model tier, effort) | all | linear | — | largest single multiplier | operator |

Levers 1, 3, 5 and 7 are in reach of a portable skill; 2, 4, 6 and 8 need harness or operator settings. Code
terseness (lever 3) is real but capped: even removing all code output saves under 10%.

## 4. What this predicts for dense v2 (to be tested, not measured)
- Turn discipline as the first rule (batch, single final suite run, no re-reads): −15 to −20%.
- Keep v1 terseness (−6%), but allow one small test per non-trivial change (Ponytail's quality point): +1 to 2%.
- Drop "think in terse notes" (it raised thinking); recommend an effort/thinking-budget setting instead.
- Quiet tool output: −3%.
- Net expectation: **≈ −20 to −25% billed cost at equal quality**, to be verified with the same 4-language
  benchmark and the billed-cost extractor (`billed.py`).

## 5. Caveats
- One model (Sonnet), one harness (Claude Code subagents, P ≈ 48.5k), feature tasks of similar size.
  P, u and the call count differ by harness; the equation's form does not.
- Cache TTL 5 min assumed; runs were short enough that no prefix rewrite after a gap was observed.
- Output share depends on task type: refactors and new files push it up; bug fixes push N and growth up.
