"""DeepSeek V4.1 Flash results on the 16 held-out tasks: cost (USD at DeepSeek peak prices), calls, resolved, paired W/L.
usage: python3 bench/ds/analyze.py  -> results/ds_runs.csv + printed summary"""
import csv, glob, json, os, random
R = os.path.expanduser("~/rbds"); ARMS = ["baseline", "ponytail", "nonhuman"]; TASKS = [f"h{i:02d}" for i in range(1, 17)]
P = {"miss": 0.30, "hit": 0.006, "out": 1.20}
grades = {}
for line in open(f"{R}/results/grades_ds.jsonl"):
    g = json.loads(line); grades[(g["task"], g["arm"])] = g
rows = []
for t in TASKS:
    for a in ARMS:
        f = f"{R}/runs/{t}/{a}/r9/out.jsonl"
        if not os.path.exists(f):
            continue
        ids, res = set(), None
        for line in open(f):
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if j.get("type") == "assistant":
                ids.add(j["message"].get("id"))
            elif j.get("type") == "result":
                res = j
        u = (res or {}).get("usage") or {}
        miss = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0); hit = u.get("cache_read_input_tokens", 0)
        out = u.get("output_tokens", 0); think = (u.get("output_tokens_details") or {}).get("thinking_tokens", 0)
        g = grades.get((t, a), {})
        rows.append({"task": t, "arm": a, "calls": len(ids), "miss": miss, "hit": hit, "out": out, "think": think,
                     "usd": (miss * P["miss"] + hit * P["hit"] + out * P["out"]) / 1e6,
                     "anthropic_units": miss * 1.25 + hit * 0.1 + out * 5,  # same weights as the Opus bill, for comparison
                     "resolved": g.get("resolved"), "gold_ok": grades.get((t, "gold"), {}).get("resolved"),
                     "subtype": (res or {}).get("subtype"), "duration_s": round((res or {}).get("duration_ms", 0) / 1000)})
with open(f"{R}/results/ds_runs.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
by = {(r["task"], r["arm"]): r for r in rows}
done = [t for t in TASKS if all((t, a) in by and by[(t, a)]["resolved"] is not None for a in ARMS) and by[(t, "baseline")]["gold_ok"]]
print(f"tasks complete with gold control resolved: {len(done)}/16  total ${sum(r['usd'] for r in rows):.2f}")
random.seed(0)
for key in ("usd", "anthropic_units"):
    base = sum(by[(t, "baseline")][key] for t in done)
    for a in ARMS:
        tot = sum(by[(t, a)][key] for t in done)
        boots = []
        for _ in range(5000):
            s = [random.choice(done) for _ in done]
            boots.append(sum(by[(t, a)][key] for t in s) / sum(by[(t, "baseline")][key] for t in s))
        boots.sort()
        print(f"{key:16s} {a:9s} rel={tot / base:.3f} CI95=({boots[125]:.2f}-{boots[4875]:.2f})")
for a in ARMS:
    calls = sum(by[(t, a)]["calls"] for t in done) / len(done)
    res = sum(bool(by[(t, a)]["resolved"]) for t in done)
    W = sum(bool(by[(t, a)]["resolved"]) and not by[(t, "baseline")]["resolved"] for t in done)
    L = sum(not by[(t, a)]["resolved"] and bool(by[(t, "baseline")]["resolved"]) for t in done)
    th = sum(by[(t, a)]["think"] for t in done) / len(done)
    print(f"{a:9s} calls/run={calls:.1f} resolved={res}/{len(done)} vs-baseline W{W}/L{L} think/run={th:.0f}")
