#!/bin/sh
# Usage: run_hidden.sh <app_dir> [extra pytest args, e.g. -k t3]
# Runs bench/hidden/test_t1..t8.py against <app_dir> (the dir containing notesvc/)
# and prints {"t1":{"func":[passed,total],"sec":[passed,total]},...} on stdout.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${BENCH_PYTHON:-python3}"
[ $# -ge 1 ] || { echo "usage: $0 <app_dir>" >&2; exit 2; }
PYTHONDONTWRITEBYTECODE=1 exec "$PY" "$HERE/run_hidden_py.py" "$@"
