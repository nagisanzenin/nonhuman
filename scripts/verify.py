"""Recompute the README's real-repository table from the published files. Standard library only.

usage: python3 scripts/verify.py [--cache-read 0.05] [--tasks] [--runs CSV] [--grades JSONL]

Reads results/real/billed_runs.csv (token counts per run) and results/real/grades_heldout.jsonl (official-evaluator
grades). Cost is recomputed from the token columns, never read from the CSV's own `cost` column:
    cost = in + 1.25*cw + CACHE_READ*cr + 5*out      (units of one fresh input token; `out` includes thinking)
Claude Opus 5.5 list prices give CACHE_READ = 0.05. Pass --cache-read 0.1 for the weight used before 2026-11-25.
A task counts only if its gold patch resolved (the control) and every arm has one graded run.
The interval is a percentile bootstrap over tasks (10,000 resamples, seed 0) of the ratio of summed costs.
Exits 1 if a pre-registered criterion (results/real/PREREG.md) fails.
"""
import argparse, csv, json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = ["baseline", "ponytail", "nonhuman"]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--runs", default=os.path.join(ROOT, "results", "real", "billed_runs.csv"))
ap.add_argument("--grades", default=os.path.join(ROOT, "results", "real", "grades_heldout.jsonl"))
ap.add_argument("--cache-read", type=float, default=0.05)
ap.add_argument("--tasks", action="store_true", help="also print one row per task")
a = ap.parse_args()

G = {}
for line in open(a.grades):
    g = json.loads(line)
    if "excluded" not in g:
        G[(g["task"], g["arm"])] = g
B = {}
for r in csv.DictReader(open(a.runs)):
    r["cost"] = float(r["in"]) + 1.25 * float(r["cw"]) + a.cache_read * float(r["cr"]) + 5 * float(r["out"])
    B.setdefault((r["task"], r["arm"]), []).append(r)
tasks = [t for t in sorted({t for t, _ in G})
         if G.get((t, "gold"), {}).get("resolved") and all((t, x) in G and len(B.get((t, x), [])) == 1 for x in ARMS)]
if not tasks:
    sys.exit("no task has a resolved gold control and one graded run per arm")
cost = {(t, x): B[(t, x)][0]["cost"] for t in tasks for x in ARMS}
ratio = lambda x, T: sum(cost[(t, x)] for t in T) / sum(cost[(t, "baseline")] for t in T)
random.seed(0)
res, ci = {}, {}
for x in ARMS:
    boots = sorted(ratio(x, random.choices(tasks, k=len(tasks))) for _ in range(10000))
    ci[x] = (boots[250], boots[9749])
    res[x] = sum(bool(G[(t, x)]["resolved"]) for t in tasks)

print(f"{len(tasks)} tasks ({tasks[0]}..{tasks[-1]}), n=1 per arm, cache read weight {a.cache_read}\n")
print("| arm | cost vs no skill (95% CI over tasks) | calls per run | resolved | cheaper than no skill on |")
print("|---|---|---|---|---|")
for x in ARMS:
    calls = sum(float(B[(t, x)][0]["calls"]) for t in tasks) / len(tasks)
    below = sum(cost[(t, x)] < cost[(t, "baseline")] for t in tasks)
    c = "1.000×" if x == "baseline" else f"{ratio(x, tasks):.3f}× ({ci[x][0]:.3f}–{ci[x][1]:.3f})"
    print(f"| {x} | {c} | {calls:.1f} | {res[x]}/{len(tasks)} | {'-' if x == 'baseline' else f'{below}/{len(tasks)}'} |")
if a.tasks:
    print("\n| task | " + " | ".join(f"{x} cost (k) · calls · resolved" for x in ARMS) + " | nonhuman / no skill |\n|---|" + "---|" * 4)
    for t in tasks:
        cells = [f"{cost[(t, x)] / 1e3:.0f} · {B[(t, x)][0]['calls']} · {'yes' if G[(t, x)]['resolved'] else 'no'}" for x in ARMS]
        print(f"| {t} | " + " | ".join(cells) + f" | {cost[(t, 'nonhuman')] / cost[(t, 'baseline')]:.3f} |")

W = sum(bool(G[(t, "nonhuman")]["resolved"]) and not G[(t, "baseline")]["resolved"] for t in tasks)
L = sum(not G[(t, "nonhuman")]["resolved"] and bool(G[(t, "baseline")]["resolved"]) for t in tasks)
checks = [(f"cost ratio <= 0.95 (got {ratio('nonhuman', tasks):.3f})", ratio("nonhuman", tasks) <= 0.95),
          (f"lost minus won discordant pairs <= 2 (W={W}, L={L})", L - W <= 2),
          (f"resolved >= no skill - 2 ({res['nonhuman']} vs {res['baseline']})", res["nonhuman"] >= res["baseline"] - 2)]
print("\nPre-registered criteria for nonhuman (results/real/PREREG.md):")
for label, ok in checks:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
sys.exit(0 if all(ok for _, ok in checks) else 1)
