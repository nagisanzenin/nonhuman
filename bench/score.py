"""Score agent runs: hidden functional/security tests per task copy + size of what the agent wrote.

usage: python3 bench/score.py LANG [LANG...]   -> results/quality_<lang>.json
For each runs/<lang>/<arm>/r<n>/<task>/ the bench's own run_hidden.sh is executed from a temp copy of the
bench whose hidden/ holds only that task's test file (plus shared helpers), so each copy is graded only on
its own task. "added_tok" = o200k tokens of lines added or changed vs the bench app (all files, incl. new
tests the agent wrote; build artefacts excluded).
"""
import difflib, glob, json, os, re, shutil, subprocess, sys, tempfile
import tiktoken
NS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, NS)
from prep import LANGS
ENC = tiktoken.get_encoding("o200k_base")
TEST_FILE = {"py": "test_{t}.py", "ts": "{t}.test.ts", "rs": "{t}.rs", "c": "{t}.c"}
SKIP = re.compile(r"(/target/|__pycache__|\.pytest_cache|Cargo\.lock$|\.o$|\.a$|\.dSYM|/a\.out$|\.DS_Store$)")


def files(root):
    out = {}
    for p in glob.glob(os.path.join(root, "**", "*"), recursive=True):
        if os.path.isfile(p) and not SKIP.search(p):
            try:
                out[os.path.relpath(p, root)] = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                pass  # binaries (test executables) are not agent-written text
    return out


def added_tokens(app, copy):
    a, b = files(app), files(copy)
    n = 0
    for rel, txt in b.items():
        old = a.get(rel, "").splitlines()
        added = [l[2:] for l in difflib.ndiff(old, txt.splitlines()) if l.startswith("+ ")]
        n += len(ENC.encode("\n".join(added), disallowed_special=())) if added else 0
    return n


def grade(lang, task, copy):
    bench = os.path.join(NS, LANGS[lang]["bench"])
    tmp = tempfile.mkdtemp(prefix=f"grade_{lang}_")
    try:
        for f in os.listdir(bench):
            if f.startswith("run_hidden"):
                shutil.copy(os.path.join(bench, f), tmp)
        os.makedirs(os.path.join(tmp, "hidden"))
        own = TEST_FILE[lang].format(t=task)
        for f in os.listdir(os.path.join(bench, "hidden")):
            is_task_file = re.fullmatch(TEST_FILE[lang].replace(".", r"\.").format(t=r"[a-z]\d+"), f)
            if f == own or not is_task_file:
                shutil.copy(os.path.join(bench, "hidden", f), os.path.join(tmp, "hidden", f))
        work = os.path.join(tmp, "app"); shutil.copytree(copy, work, ignore=shutil.ignore_patterns("target", "*.o"))
        r = subprocess.run(["bash", os.path.join(tmp, "run_hidden.sh"), work], capture_output=True, text=True, timeout=900)
        # other tasks' files are absent, so their entries may be malformed: extract only this task's entry
        m = re.search(rf'"{task}"\s*:\s*\{{\s*"func"\s*:\s*\[(\d+),\s*(\d+)\]\s*,\s*"sec"\s*:\s*\[(\d+),\s*(\d+)\]', r.stdout)
        if m:
            a, b, c, d = map(int, m.groups())
            return {"func": [a, b], "sec": [c, d]}
        return {"func": [0, 0], "sec": [0, 0], "error": r.stderr[-300:]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for lang in sys.argv[1:]:
        app = os.path.join(NS, LANGS[lang]["bench"], "app")
        rows = []
        sel = re.compile(os.environ.get("RUNSEL", r"r\d+$"))  # e.g. RUNSEL='r1[1-3]$' for the Opus runs
        for run in sorted(r for r in glob.glob(os.path.join(NS, "runs", lang, "*", "r*")) if sel.search(r)):
            arm, rn = run.split(os.sep)[-2], run.split(os.sep)[-1]
            for copy in sorted(d for d in glob.glob(os.path.join(run, "*")) if os.path.isdir(d)):
                task = os.path.basename(copy)
                g = grade(lang, task, copy)
                rows.append({"lang": lang, "arm": arm, "run": rn, "task": task, **g, "added_tok": added_tokens(app, copy)})
                print(lang, arm, rn, task, g.get("func"), g.get("sec"), rows[-1]["added_tok"], flush=True)
        json.dump(rows, open(os.path.join(os.path.dirname(NS), "results", f"quality_{lang}{os.environ.get('OUTSUFFIX', '')}.json"), "w"), indent=0)
