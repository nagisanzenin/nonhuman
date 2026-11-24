# Pre-registration: nonhuman v1.2 held-out benchmark (written 2026-11-24, before any v1.2 run)

**Skill under test:** `rules/nonhuman_v12.md`, sha256 `b9cc1de7af4a9443f839134748f564b4df16a676afb1640115b7b654f9b843da`. It is identical to `skills/nonhuman/SKILL.md` v1.2.0.
**Comparators:** no skill; Ponytail (`rules/ponytail.md`, sha256 `3868c7aa…f379`).
**Model and harness:** Opus subagents in Claude Code. One task per session. One no-network container per run, built from the official SWE-Bench Pro image, with hidden tests removed. Grading uses the official evaluator with per-run workspaces and the test patch injected through `/workspace`. The gold patch is graded on every task as a control.

**Tasks (held-out, never used for any skill change):** all 16 Python instances of the SWE-Bench Pro public `hard` split that were not used in the pilot, task ids h01–h16 in `tasks.json`:
- ansible ×6
- openlibrary ×6
- qutebrowser ×4

n = 1 run per arm per task.

**Exclusion rule (applied before looking at arm results):** a task is excluded if its gold patch is not resolved, or if the run of any arm crashes for infrastructure reasons (hang, OOM). The exclusion applies to all arms.

**Primary metrics:**
1. Billed cost of nonhuman relative to no skill, as a sum over the valid tasks, with a bootstrap 95% CI over tasks.
2. Discordant pairs against no skill: W = tasks nonhuman resolves and no skill does not; L = the reverse.

**Pass criteria (all must hold to publish):**
- cost ratio ≤ 0.95;
- L − W ≤ 2;
- nonhuman resolve count ≥ no-skill resolve count − 2.

**Prediction:** cost 0.82–0.90×, 2–4 discordant pairs that are roughly balanced, and no significant difference in resolve rate.

**If the criteria pass:** update README and SKILL.md v1.2.0 and push the public repo. **If they fail:** keep everything local and write up the root cause of each L pair.
