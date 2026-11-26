"""Build data/tasks.json, the task records prep.py and grade.py read, from the SWE-Bench Pro dataset.

usage: python3 bench/real/build_tasks.py DATASET.parquet      (needs pandas and pyarrow)
DATASET.parquet is the public SWE-Bench Pro test split (Hugging Face dataset ScaleAI/SWE-bench_Pro) saved as parquet.
Keeps the instances listed in results/real/task_ids.json and adds each one's short id (h01..h16 are the held-out set).
"""
import json, os, sys
import pandas as pd

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repository root
ids = json.load(open(os.path.join(R, "results", "real", "task_ids.json")))
rows = {r["instance_id"]: r for r in json.loads(pd.read_parquet(sys.argv[1]).to_json(orient="records"))}
missing = [t["short"] for t in ids if t["instance_id"] not in rows]
if missing:
    sys.exit(f"not in the dataset: {missing}")
os.makedirs(os.path.join(R, "data"), exist_ok=True)
out = os.path.join(R, "data", "tasks.json")
json.dump([{**rows[t["instance_id"]], "short": t["short"]} for t in ids], open(out, "w"))
print(f"{len(ids)} tasks -> {out}")
