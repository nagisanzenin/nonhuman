# DeepSeek V4.1 Flash on the 16 held-out SWE-Bench Pro tasks

Second model, same tasks, same skill text (v1.2), same grader. Not pre-registered; this is a generalisation check.

| 16 tasks, `deepseek-flash`, n=1 per arm | no skill | Ponytail | nonhuman v1.2 |
|---|---|---|---|
| cost, USD at DeepSeek prices (95% CI over tasks) | 1.00× | 1.00× (0.89–1.11) | **0.84× (0.70–0.97)** |
| cost, Anthropic price weights | 1.00× | 1.06× (0.90–1.21) | **0.82× (0.64–0.96)** |
| model calls per run | 52.7 | 54.2 | **39.2** |
| thinking tokens per run | 35.1k | 33.7k | **30.4k** |
| resolved | 14/16 | 12/16 | 12/16 |
| discordant pairs vs no skill | — | W0 / L2 | W0 / L2 |

- Gold patch resolved on all 16 tasks. All 48 runs ended normally (no turn-cap or timeout hits).
- **Losses (nonhuman):** h09 and h10. Each failed one hidden FAIL_TO_PASS test (h09: surname + dates author match; h10: `get_abbrev_from_full_lang_name`) that no-skill passed. Ponytail also failed the h10 test. h05 and h12 were failed by all three arms.
- **Where the money goes on DeepSeek:** output + thinking ≈ 68% of the bill. Cache reads cost 2% of base input, so re-reading context is cheap, and the calls lever acts mostly through fewer outputs.
- **Total spend:** $3.71 (prepaid balance drop, including a discarded first attempt).

## Harness (differs from the Opus runs)
- Headless Claude Code 2.1.261 in `--bare` mode, fresh config dir, pointed at `api.deepseek.com/anthropic`. Bash runs inside the Claude Code sandbox, and only the docker socket is reachable. Max 120 turns, 45 min per run. 6 runs in parallel.
- The rule file is copied into the run directory, and every rule-arm transcript contains the rule text (16/16 per arm).
- **Git history purge:** before each run, every ref except HEAD is deleted and unreachable objects are pruned. A first smoke run showed DeepSeek extracting the upstream fix from refs left in the official image. The 96 Opus transcripts were audited: none did this.
- **Discarded attempt:** a first full attempt was discarded and is not reported. Its Read permission used the wrong path syntax, so the rule arms never saw their rules.
- **Bash parser denials** remain at about 4 per run and are equal across arms (61 / 63 / 53 in total).

## Root cause of the two nonhuman losses
- **h09 (author match on surname + dates).** nonhuman queried only an explicit `surname~` field. Stored authors keep the surname inside `name` ("William Brewer"), so the surname path could never match. No skill also searched `name~ *surname*` and took the candidate's surname from its name. This is the class v1.2 already names ("smallest diff never means smallest behaviour", cover every case a requirement names), and the weaker model did not apply the guard. Ponytail passed.
- **h10 (`get_abbrev_from_full_lang_name`).** nonhuman read translations with `name_translated.values()`. That works on the plain dict it used in its own check, but the site's nested `Thing` has no `.values()`. The task's requirements warn about this shape. Three of its verification commands were blocked by the harness bash parser before the check ran. Ponytail failed the same test. This was a verification-depth miss on a known trap, made worse by harness noise.
- **Statistics:** 2 discordant pairs, both against nonhuman. A sign test gives p = 0.5. At n = 1, this cannot be told apart from noise, but h09 matches a failure class seen before.

## Replication of h09 and h10 (decision rule written before running)
2 more runs per arm on h09 and h10 (r10, r11), with the same harness.
- If nonhuman fails h09 in all 3 runs while no skill passes at least 2 of 3, call it a real skill-induced miss.
- If nonhuman passes h09 in at least 1 of the 2 new runs, call it noise.
- h10 is judged the same way.

### Replication result
| resolved / 3 runs | no skill | Ponytail | nonhuman |
|---|---|---|---|
| h09 | 3/3 | 3/3 | 2/3 |
| h10 | 2/3 | 0/3 | 0/3 |

- **h09 is noise** under the rule above: nonhuman passed both new runs.
- **h10 is a real miss** under the rule above: nonhuman failed 0/3, while no skill passed 2/3. Every failure, in every arm, is the same hidden test (`test_get_abbrev_from_full_lang_name`) and the same trap. The code reads `name_translated` as a dict, but the site returns a nested `Thing`. Ponytail fails it 0/3 as well. Both minimal-diff skills therefore lose the defensive shape handling that no skill tends to write.
- **Candidate principle (not applied; it would need a new held-out test):** verify against the codebase's own fixtures or mocks for the objects the spec describes, never against a hand-made stand-in.
- Extra spend for the replication: $0.50. Total DeepSeek spend: $4.21.
