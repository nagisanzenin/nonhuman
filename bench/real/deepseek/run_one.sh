#!/bin/bash
# usage: bench/ds/run_one.sh TASK ARM   -> headless Claude Code on DeepSeek, run id r9, transcript runs/TASK/ARM/r9/out.jsonl
# Isolation: fresh CLAUDE_CONFIG_DIR (no user CLAUDE.md, plugins or hooks); only the run's x wrapper and the rules dir are allowed.
set -u
R=$HOME/rbds; T=${1:?}; A=${2:?}; N=${RUN:-9}; D=$R/runs/$T/$A/r$N
[ -f "$D/DONE" ] && grep -q "\"type\":\"result\"" "$D/out.jsonl" && { echo "skip $T $A (done)"; exit 0; }
[ -f "$R/STOP" ] && { echo "STOP present, skip $T $A"; exit 3; }
"$R/.venv/bin/python" "$R/bench/prep.py" "$T" "$A" "$N" >/dev/null || { echo "prep fail $T $A"; exit 2; }
# purge post-base history (upstream refs/tags hold the fix); keep only HEAD's ancestry
n=$(docker exec "rb-$T-$A-r$N" bash -c 'cd /app && for s in $(git for-each-ref --format="%(refname) %(symref)" | awk "NF==2{print \$1}"); do git symbolic-ref -d $s; done; git for-each-ref --format="delete %(refname)" | git update-ref --stdin && git reflog expire --expire=now --all && git gc -q --prune=now && git stash clear; git for-each-ref | wc -l')
[ "$n" = "0" ] || { echo "purge fail $T $A refs=$n"; exit 2; }
# rule file inside the run dir (cwd), so the default Read permission covers it
if [ "$A" != baseline ]; then rf=$(grep -o "$R/rules/[a-z0-9_]*\.md" "$D/PROMPT.md"); cp "$rf" "$D/RULES.md"; sed -i '' "s#$rf#$D/RULES.md#" "$D/PROMPT.md"; fi
mkdir -p "$R/ds_cfg"
cd "$D" || exit 2
KEY=$(cat "$HOME/.config/realbench/ds.key")
env -u ANTHROPIC_AUTH_TOKEN \
  CLAUDE_CONFIG_DIR="$R/ds_cfg" ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic ANTHROPIC_API_KEY="$KEY" \
  ANTHROPIC_MODEL="${DS_MODEL:-deepseek-flash}" ANTHROPIC_DEFAULT_HAIKU_MODEL="${DS_MODEL:-deepseek-flash}" \
  ANTHROPIC_DEFAULT_SONNET_MODEL="${DS_MODEL:-deepseek-flash}" ANTHROPIC_DEFAULT_OPUS_MODEL="${DS_MODEL:-deepseek-flash}" \
  CLAUDE_CODE_SUBAGENT_MODEL="${DS_MODEL:-deepseek-flash}" CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
  timeout 2700 claude --bare -p "$(cat PROMPT.md)" --output-format stream-json --verbose --max-turns 120 --settings "$R/bench/ds/settings.json" \
    --allowedTools "Bash($D/x:*)" "Bash($D/x *)" "Read($R/rules/**)" \
  < /dev/null > out.jsonl 2> err.log
rc=$?; echo "$rc" > "$D/DONE"; echo "done $T $A rc=$rc"
