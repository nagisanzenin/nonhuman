# Real-repository benchmark harness

To check the published numbers you need none of this: `python3 scripts/verify.py` recomputes the README table from
`results/real/` with the standard library.

This folder is for re-running the benchmark. Every script resolves paths from the repository root.

## Layout

| path | what | in git |
|---|---|---|
| `results/real/` | published data, see [`results/real/README.md`](../../results/real/README.md) | yes |
| `data/pro-os/` | clone of `scaleapi/SWE-bench_Pro-os` with the changes in [`EVALUATOR_PATCH.md`](EVALUATOR_PATCH.md) | no |
| `data/tasks.json` | task records, built by `build_tasks.py` | no |
| `data/ponytail.md` | Ponytail's `SKILL.md`, only for the `ponytail` arm (sha256 in `results/real/PREREG.md`) | no |
| `runs/` | one folder per run, plus `grades.jsonl` and `billed_*.csv` from your own runs | no |
| `eval/`, `eval_v2/` | evaluator workspaces | no |

## Steps

1. `git clone https://github.com/scaleapi/SWE-bench_Pro-os data/pro-os`, then apply `EVALUATOR_PATCH.md`.
2. `python3 bench/real/build_tasks.py DATASET.parquet` writes `data/tasks.json` (needs pandas and pyarrow).
3. `python3 bench/real/prep.py TASK ARM RUN` starts a no-network container and writes `runs/TASK/ARM/rRUN/PROMPT.md`.
   `TASK` is a short id such as `h01`; `ARM` is `baseline`, `ponytail` or `nonhuman`.
4. Run your agent once on that `PROMPT.md`, one task per session.
5. `python3 bench/real/grade.py TASK` grades every run of the task plus the gold patch, into `runs/grades.jsonl`.
6. `python3 bench/real/billed.py TRANSCRIPTS_DIR MANIFEST.csv` writes `runs/billed_calls.csv` and `runs/billed_runs.csv`
   (needs tiktoken). The manifest maps agent ids to runs: columns `agent,task,arm,run`.
7. `python3 scripts/verify.py --runs runs/billed_runs.csv --grades runs/grades.jsonl` prints the table.

`step.sh` chains steps 5 and 3 for the next task and frees the finished task's image. `regrade.py` re-grades saved
patches with per-run workspaces.

## Before you run it

- **Strip the git history.** The task images keep refs from after the fix, so an agent can look the answer up. `prep.py`
  does not remove them. The purge is in [`deepseek/run_one.sh`](deepseek/run_one.sh); run it in each container before
  the agent starts. The published Opus transcripts were checked and none read past the base commit.
- `deepseek/` is the harness as it ran for the DeepSeek check. It still points at the author's workspace (`~/rbds`) and
  is kept as a record, not as a runnable script.
- Each task image is 1 to 2 GB and runs under x86 emulation on Apple silicon.
