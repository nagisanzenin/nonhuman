"""Per-call billed-token breakdown from subagent transcripts (JSONL), joined to results/usage.csv.

usage: python3 bench/billed.py <transcripts_dir>   -> results/billed_calls.csv, results/billed_runs.csv
Each API call's usage is counted once (dedup by message id). Prices are relative to base input = 1:
cache write (5m) 1.25, cache read 0.1, output 5 (thinking is billed as output).
Also measures what entered the context: tool_result text and the model's own tool_use inputs/text.
"""
import csv, glob, json, os, sys
import tiktoken
ENC = tiktoken.get_encoding("o200k_base")
NS = os.path.dirname(os.path.abspath(__file__))
W = {"in": 1.0, "cw": 1.25, "cr": 0.1, "out": 5.0}
OUT = os.path.join(os.path.dirname(NS), "results")
meta = {r["agent"]: r for r in csv.DictReader(open(os.path.join(OUT, "usage.csv")))}
tok = lambda s: len(ENC.encode(s, disallowed_special=()))


def text_of(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(text_of(x.get("text", x.get("content", ""))) if isinstance(x, dict) else str(x) for x in c)
    return ""


calls, runs = [], []
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.output"))):
    aid = os.path.basename(f)[:6]
    if aid not in meta:
        continue
    m = meta[aid]; seen = set(); k = 0
    tool_res = tool_in = text_out = 0
    for line in open(f):
        try:
            j = json.loads(line)
        except ValueError:
            continue
        msg = j.get("message") or {}
        if j.get("type") == "user" and isinstance(msg.get("content"), list):
            for c in msg["content"]:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    tool_res += tok(text_of(c.get("content", "")))
        if j.get("type") != "assistant":
            continue
        for c in msg.get("content", []):
            if c.get("type") == "tool_use":
                tool_in += tok(json.dumps(c.get("input", {})))
            elif c.get("type") == "text":
                text_out += tok(c.get("text", ""))
        mid = msg.get("id")
        if mid in seen or not msg.get("usage"):
            continue
        seen.add(mid); u = msg["usage"]; k += 1
        row = {"agent": aid, "lang": m["lang"], "arm": m["arm"], "run": m["run"], "call": k,
               "in": u.get("input_tokens", 0), "cw": u.get("cache_creation_input_tokens", 0),
               "cr": u.get("cache_read_input_tokens", 0), "out": u.get("output_tokens", 0),
               "think": (u.get("output_tokens_details") or {}).get("thinking_tokens", 0)}
        row["ctx"] = row["in"] + row["cw"] + row["cr"]
        row["cost"] = sum(W[x] * row[x] for x in W)
        calls.append(row)
    C = [c for c in calls if c["agent"] == aid]
    if not C:
        continue
    runs.append({"agent": aid, "lang": m["lang"], "arm": m["arm"], "run": m["run"], "calls": len(C),
                 "ctx0": C[0]["ctx"], "ctx_last": C[-1]["ctx"],
                 **{x: sum(c[x] for c in C) for x in ["in", "cw", "cr", "out", "think", "cost"]},
                 "tool_result_tok": tool_res, "tool_use_tok": tool_in, "text_tok": text_out})
for name, rows in (("billed_calls.csv", calls), ("billed_runs.csv", runs)):
    with open(os.path.join(OUT, name), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(runs), "runs,", len(calls), "calls")
