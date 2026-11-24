"""Summarise the real-repo benchmark: per task and overall cost, calls, resolve rate, cost per resolved task.
usage: python bench/summarize.py  (after bench/billed.py)  -> results/SUMMARY.md + stdout"""
import csv, json, os, statistics as st
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = ["baseline", "ponytail", "nonhuman"]
B = list(csv.DictReader(open(os.path.join(R, "results", "billed_runs.csv"))))
G, EXCL = {}, {}
for l in open(os.path.join(R, "results", "grades.jsonl")):
    g = json.loads(l)
    if "excluded" in g: EXCL[g["task"]] = g["excluded"]; continue
    G[(g["task"], g["arm"], g["run"].lstrip("r"))] = g
tasks = [t for t in dict.fromkeys(r["lang"] for r in B) if t not in EXCL and (t, "gold", "0") in G or t == "ans1"]
tasks = [t for t in tasks if not ((t, "gold", "0") in G and not G[(t, "gold", "0")]["resolved"])]
out = ["| task | " + " | ".join(f"{a} cost (k) · calls · resolved" for a in ARMS) + " |", "|---|" + "---|" * len(ARMS)]
tot = {a: [0.0, 0, 0, 0.0] for a in ARMS}  # cost, resolved, runs, calls
for t in tasks:
    cells = []
    for a in ARMS:
        X = [r for r in B if r["lang"] == t and r["arm"] == a and (t, a, r["run"]) in G]
        c = sum(float(r["cost"]) for r in X); res = sum(G[(t, a, r["run"])]["resolved"] for r in X)
        n = sum(float(r["calls"]) for r in X)
        tot[a][0] += c; tot[a][1] += res; tot[a][2] += len(X); tot[a][3] += n
        cells.append(f"{c/len(X)/1e3:.0f} · {n/len(X):.1f} · {res}/{len(X)}")
    out.append(f"| {t} | " + " | ".join(cells) + " |")
out += ["", "| arm | cost vs baseline | calls/run | resolved | cost per resolved task (k) |", "|---|---|---|---|---|"]
for a in ARMS:
    c, res, n, k = tot[a]
    out.append(f"| {a} | {c/tot['baseline'][0]:.3f}× | {k/n:.1f} | {res}/{n} | {c/max(res,1)/1e3:.0f} |")
out += ["", "Excluded: " + "; ".join(f"{t}: {why}" for t, why in EXCL.items())]
open(os.path.join(R, "results", "SUMMARY.md"), "w").write("\n".join(out) + "\n"); print("\n".join(out))
