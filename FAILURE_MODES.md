# Failure modes

nonhuman only removes things. Each rule can therefore break a result only in a few known ways, and the skill carries one guard for each. New rules must be added here first; a change to the skill needs a row in this table, not a benchmark win.

| rule | how it could break a correct result | guard in SKILL.md |
|---|---|---|
| Fewer calls: batch, read once | missing context from skipped exploration | merge steps, never skip them; locate first, then read what is needed |
| Fewer calls: verify once | stopping before every requirement is met | requirement check against the diff before the final reply (no extra call) |
| Fewer calls: stop when done | an uncovered caller, variant or file | the same requirement check; "cover every case each requirement names" |
| Less output: smallest diff | doing less than the spec ("smallest behaviour") | "smallest diff never means smallest behaviour" |
| Less output: terse code | renamed identifiers drifting from the spec or codebase | "keep the exact names the spec, interface and codebase use" |
| Less output: no comments | a lost non-obvious invariant | one-line comment allowed for invariants and security reasons |
| Less output: types optional | missing types costing the next agent lookups | keep typed signatures; follow the codebase |
| Less output: ≤ 1 test | an untested new behaviour | one compact test for new non-trivial logic |
| Small tool output | a truncated failure line | never cut off the failing line |
| (all) | dropped validation, auth, escaping or bounds | "Never cut" list; if unsure, keep the guard |

Observed so far (real-repo pilot): one renamed-identifier miss and one incomplete-cleanup miss, both in the "terseness leaking into the contract" rows. The v1.2 guards were written for those rows, not for those tasks.
