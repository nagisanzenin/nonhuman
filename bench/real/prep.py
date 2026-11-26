"""Prepare one agent run on a SWE-Bench Pro task: a no-network container from the official instance image,
hidden tests removed, plus runs/<task>/<arm>/r<n>/{x, PROMPT.md}.
usage: python3 bench/real/prep.py TASK ARM RUN    (TASK = short id, e.g. h01; ARM = baseline | ponytail | nonhuman)
Needs data/pro-os and data/tasks.json (see bench/real/README.md). The nonhuman arm uses the pre-registered text
results/real/skill_under_test.md; the ponytail arm needs Ponytail's SKILL.md saved as data/ponytail.md."""
import json, os, subprocess, sys
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repository root
sys.path.insert(0, os.path.join(R, "data", "pro-os"))
from helper_code.image_uri import get_dockerhub_image_uri
TASKS = {t["short"]: t for t in json.load(open(os.path.join(R, "data", "tasks.json")))}
RULES = {"baseline": None, "ponytail": os.path.join(R, "data", "ponytail.md"),
         "nonhuman": os.path.join(R, "results", "real", "skill_under_test.md")}
sh = lambda *a: subprocess.run(a, check=True, capture_output=True, text=True).stdout


def prep(short, arm, run):
    t = TASKS[short]; name = f"rb-{short}-{arm}-r{run}"
    if RULES[arm] and not os.path.exists(RULES[arm]):
        sys.exit(f"missing rule file for arm {arm}: {RULES[arm]}")
    img = get_dockerhub_image_uri(t["instance_id"], "jefzda", t["repo"])
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    sh("docker", "run", "-d", "--platform", "linux/amd64", "--network", "none", "--name", name,
       "--entrypoint", "/bin/bash", img, "-c", "sleep infinity")
    sh("docker", "exec", name, "bash", "-c",
       f"rm -rf /tests /workspace; cd /app && git reset -q --hard {t['base_commit']} && git clean -qfd && git log --oneline -1 >/dev/null")
    d = os.path.join(R, "runs", short, arm, f"r{run}"); os.makedirs(d, exist_ok=True)
    x = os.path.join(d, "x")
    open(x, "w").write(f'#!/bin/bash\nexec docker exec -i -w /app {name} bash -lc "$*"\n'); os.chmod(x, 0o755)
    rules = (f"## Working rules\nBefore anything else, read this rule file and follow it for the whole session:\n- {RULES[arm]}\n\n"
             if RULES[arm] else "")
    body = (f"# Assignment\nYou are the engineer on the `{t['repo']}` codebase. Resolve the issue below.\n\n"
            "## Environment\n"
            f"The repository is checked out at `/app` inside a Linux container (no network). Run every shell command "
            f"inside it with:\n\n    \"{x}\" '<command>'\n\n"
            "This runs `bash -lc '<command>'` with `/app` as the working directory. All reading, editing and testing "
            "happens through it (for example `cat`, `sed -n`, `grep -rn`, heredocs or `python` to write files, the "
            "repository's own test runner). Stdin is forwarded, so quote-heavy content can be piped in, e.g. "
            f"`\"{x}\" 'cat > path/file.py' <<'EOF'` ... `EOF` or `\"{x}\" 'python -' < script`. Do not use your file tools on the host. Leave your changes uncommitted "
            "in `/app`. No network, no package installs, no git fetch. Put any scratch or helper files inside the container "
            "(e.g. `/tmp`), never on the host: other agents share the host scratch folders.\n"
            "Your change is graded with hidden tests, including tests for behaviour stated in the requirements.\n"
            "When finished, reply with a short summary.\n\n" + rules +
            f"# Issue\n{t['problem_statement'].strip()}\n\n# Requirements\n{t['requirements'].strip()}\n\n"
            f"# New interfaces\n{(t.get('interface') or 'None').strip()}\n")
    open(os.path.join(d, "PROMPT.md"), "w").write(body)
    return d


if __name__ == "__main__":
    print(prep(sys.argv[1], sys.argv[2], int(sys.argv[3])))
