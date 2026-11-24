"""Collect each run's diff from its container and grade it with the official SWE-Bench Pro evaluator.
usage: .venv/bin/python bench/grade.py TASK      -> results/grades.jsonl (one line per run)
Agent edits to files that the hidden test patch touches are dropped (the test patch must apply cleanly)."""
import csv, json, os, re, subprocess, sys
import pandas as pd
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = {t["short"]: t for t in json.load(open(os.path.join(R, "tasks.json")))}


def split_diff(p):
    return re.split(r"(?m)^(?=diff --git )", p)


def collect(t, name):
    sh = lambda c: subprocess.run(["docker", "exec", name, "bash", "-c", c], capture_output=True, text=True).stdout
    raw = sh(f"cd /app && git add -A >/dev/null 2>&1 && git diff --cached {t['base_commit']}")
    test_files = set(re.findall(r"^diff --git a/(\S+)", t["test_patch"], re.M))
    keep = [h for h in split_diff(raw) if h.strip() and re.match(r"diff --git a/(\S+)", h).group(1) not in test_files
            and "GIT binary patch" not in h and "Binary files" not in h]
    return "".join(keep)


def grade(short):
    t = TASKS[short]; out = os.path.join(R, "eval", short); os.makedirs(out, exist_ok=True)
    patches = []
    for arm in sorted(os.listdir(os.path.join(R, "runs", short))):
        for run in sorted(os.listdir(os.path.join(R, "runs", short, arm))):
            name = f"rb-{short}-{arm}-{run}"; p = collect(t, name)
            open(os.path.join(R, "runs", short, arm, run, "patch.diff"), "w").write(p)
            patches.append({"instance_id": t["instance_id"], "patch": p, "prefix": f"{arm}_{run}"})
    patches.append({"instance_id": t["instance_id"], "patch": t["patch"], "prefix": "gold_r0"})  # control: reference fix
    json.dump(patches, open(os.path.join(out, "patches.json"), "w"))
    pd.DataFrame([{k: v for k, v in t.items() if k != "short"}]).to_csv(os.path.join(out, "sample.csv"), index=False)
    subprocess.run([os.path.join(R, ".venv", "bin", "python"), "swe_bench_pro_eval.py", f"--raw_sample_path={out}/sample.csv",
                    f"--patch_path={out}/patches.json", f"--output_dir={out}", "--scripts_dir=run_scripts",
                    "--dockerhub_username=jefzda", "--use_local_docker", "--docker_platform=linux/amd64", "--num_workers=3"],
                   cwd=os.path.join(R, "data", "pro-os"))
    f2p, p2p = (set(json.loads(t[k]) if isinstance(t[k], str) else t[k]) for k in ("fail_to_pass", "pass_to_pass"))
    with open(os.path.join(R, "results", "grades.jsonl"), "a") as g:
        for pt in patches:
            o = os.path.join(out, t["instance_id"], f"{pt['prefix']}_output.json")
            st = {x["name"]: x["status"] for x in json.load(open(o))["tests"]} if os.path.exists(o) else {}
            lg = os.path.join(out, t["instance_id"], f"{pt['prefix']}_stdout.log")
            if os.path.exists(lg):  # official parsers drop pytest ids containing spaces; recover them from the -v log
                for m in re.finditer(r"^(\S+::.*?) (PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)(?: +\[ *\d+%\])?$", open(lg).read(), re.M):
                    st.setdefault(m.group(1), m.group(2))
            ok = lambda s: sum(st.get(n) == "PASSED" for n in s)
            row = {"task": short, "arm": pt["prefix"].rsplit("_", 1)[0], "run": pt["prefix"].rsplit("_", 1)[1],
                   "f2p": [ok(f2p), len(f2p)], "p2p": [ok(p2p), len(p2p)], "patch_lines": pt["patch"].count("\n"),
                   "resolved": ok(f2p) == len(f2p) and ok(p2p) == len(p2p), "graded": bool(st)}
            g.write(json.dumps(row) + "\n"); print(row)


if __name__ == "__main__":
    for s in sys.argv[1:]:
        grade(s)
