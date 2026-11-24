"""Recompute the README tables from results/. usage: python3 scripts/summarize.py -> results/SUMMARY.md
Opus runs = run >= 11 (arms baseline / ponytail / nonhuman). Cost units = base input tokens:
cache write 1.25, cache read 0.1, output 5 (thinking billed as output)."""
import csv, json, os, statistics as st
R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
runs = [r for r in csv.DictReader(open(os.path.join(R, "billed_runs.csv"))) if int(r["run"]) >= 11]
ARMS = ["baseline", "ponytail", "nonhuman"]; LANG = {"py": "Python", "ts": "TypeScript", "rs": "Rust", "c": "C"}
m = lambda X, k: st.mean(float(r[k]) for r in X)
L = ["| | baseline | Ponytail | **nonhuman** |", "|---|---|---|---|"]
for l in list(LANG) + ["all"]:
    c = {a: m([r for r in runs if r["arm"] == a and l in (r["lang"], "all")], "cost") for a in ARMS}
    L.append(f"| {LANG.get(l, '**All**')} | {c['baseline']/1e3:,.0f}k | {c['ponytail']/1e3:,.0f}k ({c['ponytail']/c['baseline']:.2f}×) | "
             f"**{c['nonhuman']/1e3:,.0f}k ({c['nonhuman']/c['baseline']:.2f}×)** |")
L += ["", "| per run (all languages) | baseline | Ponytail | nonhuman |", "|---|---|---|---|"]
for k, lab in (("calls", "model calls"), ("out", "output tokens"), ("think", "thinking tokens")):
    L.append(f"| {lab} | " + " | ".join(f"{m([r for r in runs if r['arm']==a], k):,.1f}" if k == "calls" else f"{m([r for r in runs if r['arm']==a], k):,.0f}" for a in ARMS) + " |")
L += ["", "| hidden tests passed | baseline | Ponytail | nonhuman |", "|---|---|---|---|"]
for kind in ("func", "sec"):
    cells = []
    for a in ARMS:
        p = t = 0
        for l in LANG:
            for x in json.load(open(os.path.join(R, f"quality_{l}_opus.json"))):
                if x["arm"] == a: p += x[kind][0]; t += x[kind][1]
        cells.append(f"{p}/{t}")
    L.append(f"| {'functional' if kind == 'func' else 'security'} | " + " | ".join(cells) + " |")
txt = "\n".join(L) + "\n"; open(os.path.join(R, "SUMMARY.md"), "w").write(txt); print(txt)
