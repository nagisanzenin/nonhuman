# Changes to the official SWE-Bench Pro evaluator (scaleapi/SWE-bench_Pro-os, `swe_bench_pro_eval.py`)

1. **Test patch injection.** The Docker Hub instance images have no `/tests/test_patch.patch`, so the patch is written into `/workspace/test_patch.patch` and the last `before_repo_set_cmd` line points there.
2. **Per-run workspace.** In local-Docker mode every patch of one instance shared `<out>/<instance>/workspace`, so `--num_workers>1` raced and graded one run's patch with another run's logs. The fix uses `workspace_{prefix}`.
3. **pytest ids with spaces.** Some official parsers drop pytest node ids that contain spaces. `grade.py` recovers them from the `-v` log.

The reference (gold) patch is graded on every task as a control. Tasks whose gold patch fails are excluded for all arms.
