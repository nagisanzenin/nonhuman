"""Prepare one agent run: copies of the language's app (one per task) + a PROMPT.md for the agent.

usage: python bench/prep.py LANG ARM RUN      -> prints the run dir
Layout: bench/runs/<lang>/<arm>/r<run>/{PROMPT.md, <task_id>/ (app copy)}
Arms: baseline (no rules) | ponytail | nonhuman.
"""
import json, os, shutil, sys
NS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(NS)
PY = sys.executable
LANGS = {
    "py": {"bench": "fixtures/py", "test": f'"{PY}" -m pytest tests -q -p no:cacheprovider'},
    "ts": {"bench": "fixtures/ts", "test": "node --test 'test/*.test.ts'"},
    "rs": {"bench": "fixtures/rs", "test": "cargo test --offline -q"},
    "c":  {"bench": "fixtures/c", "test": "make test"},
}
RULES = {"baseline": [],
         "ponytail": [os.path.join(NS, "arms", "ponytail.SKILL.md")],
         "nonhuman": [os.path.join(ROOT, "skills", "nonhuman", "SKILL.md")]}


def prep(lang, arm, run):
    cfg = LANGS[lang]; b = os.path.join(NS, cfg["bench"])
    tasks = json.load(open(os.path.join(b, "tasks.json")))
    d = os.path.join(NS, "runs", lang, arm, f"r{run}")
    if os.path.exists(d):
        shutil.rmtree(d)
    for t in tasks:
        shutil.copytree(os.path.join(b, "app"), os.path.join(d, t["id"]),
                        ignore=shutil.ignore_patterns("target", "__pycache__", ".pytest_cache", "*.o", "*.a"))
    rules = ""
    if RULES[arm]:
        rules = ("## Working rules\nBefore anything else, read these rule files and follow them for the whole session:\n"
                 + "\n".join(f"- {p}" for p in RULES[arm]) + "\n\n")
    body = (f"# Assignment\nYou are the engineer on this codebase. Implement each task below in its own copy of the project: "
            f"task <id> lives in `{d}/<id>/` (already prepared; the copies are identical at the start). "
            f"Each copy has existing tests; run them from inside that copy with:\n\n    {cfg['test']}\n\n"
            "Work only inside these task directories. Do not read or open anything else on disk (no sibling benchmark "
            "folders, no reference solutions, no other runs). No git, no package installs, no web.\n"
            "Finish every task, then reply with one line per task.\n\n" + rules + "# Tasks\n")
    body += "".join(f"## {t['id']}\n{t['spec']}\n\n" for t in tasks)
    open(os.path.join(d, "PROMPT.md"), "w").write(body)
    return d


if __name__ == "__main__":
    print(prep(sys.argv[1], sys.argv[2], int(sys.argv[3])))
