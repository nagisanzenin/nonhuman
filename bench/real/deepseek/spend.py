"""Running DeepSeek spend from all r9 transcripts (peak prices, the upper bound). usage: spend.py [cap_usd]
Writes STOP (no new runs start) when spend >= 0.8*cap and kills claude processes when spend >= cap."""
import glob, json, os, subprocess, sys
R = os.path.expanduser("~/rbds"); cap = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
P = {"miss": 0.30, "hit": 0.006, "out": 1.20}  # USD per 1M tokens, peak
tot = {"miss": 0, "hit": 0, "out": 0}; per = {}
for f in glob.glob(f"{R}/runs/*/*/r9/out.jsonl"):
    last = {}
    for line in open(f):
        try:
            j = json.loads(line)
        except ValueError:
            continue
        m = j.get("message") or {}
        if j.get("type") == "assistant" and m.get("usage"):
            last[m.get("id")] = m["usage"]
        if j.get("type") == "result" and j.get("usage"):
            last = {"result": j["usage"]}; break  # per-message usage is partial in stream-json; the result event is final
    c = {"miss": 0, "hit": 0, "out": 0}
    for u in last.values():
        c["miss"] += u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        c["hit"] += u.get("cache_read_input_tokens", 0); c["out"] += u.get("output_tokens", 0)
    per[f.split("/runs/")[1].rsplit("/r9", 1)[0]] = c
    for k in tot:
        tot[k] += c[k]
usd = sum(tot[k] * P[k] for k in P) / 1e6
try:  # ground truth: prepaid balance drop since start (balance0 file)
    import urllib.request
    rq = urllib.request.Request("https://api.deepseek.com/user/balance", headers={"Authorization": "Bearer " + open(os.path.expanduser("~/.config/realbench/ds.key")).read().strip()})
    bal = float(json.load(urllib.request.urlopen(rq, timeout=20))["balance_infos"][0]["total_balance"])
    b0 = os.path.join(R, "ds_balance0")
    if not os.path.exists(b0):
        open(b0, "w").write(str(bal))
    drop = float(open(b0).read()) - bal; print(f"balance=${bal:.2f} drop=${drop:.3f}"); usd = max(usd, drop)
except Exception as e:
    print("balance check failed:", e)
print(f"runs={len(per)} spend=${usd:.3f} (peak) miss={tot['miss']/1e6:.2f}M hit={tot['hit']/1e6:.1f}M out={tot['out']/1e6:.2f}M")
if usd >= 0.8 * cap:
    open(f"{R}/STOP", "w").write(f"{usd}\n"); print("STOP written")
if usd >= cap:
    subprocess.run(["pkill", "-f", "rbds/ds_cfg"]); subprocess.run(["pkill", "-f", "claude -p # Assignment"]); print("KILLED")
