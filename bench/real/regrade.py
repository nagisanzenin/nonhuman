"""Re-grade saved patches (eval/<task>/patches.json) with per-run workspaces. usage: regrade.py TASK -> results/grades_v2.jsonl"""
import json, os, re, shutil, subprocess, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = {t["short"]: t for t in json.load(open(os.path.join(R, "tasks.json")))}
for short in sys.argv[1:]:
    t = TASKS[short]; src = os.path.join(R, "eval", short); out = os.path.join(R, "eval_v2", short)
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    P = json.load(open(os.path.join(src, "patches.json")))
    if not any(p["prefix"] == "gold_r0" for p in P):
        P.append({"instance_id": t["instance_id"], "patch": t["patch"], "prefix": "gold_r0"})
    json.dump(P, open(os.path.join(out, "patches.json"), "w"))
    shutil.copy(os.path.join(src, "sample.csv"), out)
    subprocess.run([os.path.join(R, ".venv", "bin", "python"), "swe_bench_pro_eval.py", f"--raw_sample_path={out}/sample.csv",
                    f"--patch_path={out}/patches.json", f"--output_dir={out}", "--scripts_dir=run_scripts", "--dockerhub_username=jefzda",
                    "--use_local_docker", "--docker_platform=linux/amd64", "--num_workers=3"], cwd=os.path.join(R, "data", "pro-os"),
                   capture_output=True)
    f2p, p2p = (set(json.loads(t[k])) for k in ("fail_to_pass", "pass_to_pass"))
    with open(os.path.join(R, "results", "grades_v2.jsonl"), "a") as g:
        for pt in P:
            d = os.path.join(out, t["instance_id"]); o = os.path.join(d, f"{pt['prefix']}_output.json")
            st = {x["name"]: x["status"] for x in json.load(open(o))["tests"]} if os.path.exists(o) else {}
            lg = os.path.join(d, f"{pt['prefix']}_stdout.log")
            if os.path.exists(lg):
                for m in re.finditer(r"^(\S+::.*?) (PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)(?: +\[ *\d+%\])?$", open(lg).read(), re.M):
                    st.setdefault(m.group(1), m.group(2))
            ok = lambda s: sum(st.get(n) == "PASSED" for n in s)
            row = {"task": short, "arm": pt["prefix"].rsplit("_", 1)[0], "run": pt["prefix"].rsplit("_", 1)[1], "f2p": [ok(f2p), len(f2p)],
                   "p2p": [ok(p2p), len(p2p)], "resolved": ok(f2p) == len(f2p) and ok(p2p) == len(p2p), "graded": bool(st)}
            g.write(json.dumps(row) + "\n"); print(row, flush=True)
    imgs = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True, text=True).stdout.split()
    for i in imgs:
        if "sweap" in i: subprocess.run(["docker", "rmi", i], capture_output=True)
