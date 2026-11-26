#!/bin/bash
# usage: bench/real/step.sh DONE_TASK NEXT_TASK   -> grade DONE_TASK, free its image, prepare 6 containers for NEXT_TASK
set -u
cd "$(dirname "$0")/../.."; PY=${PY:-python3}
D=${1:?}; N=${2:-}
$PY bench/real/grade.py "$D" 2>&1 | grep "^{"
img=$(docker inspect "rb-$D-baseline-r1" --format '{{.Config.Image}}')
docker rm -f $(docker ps -aq --filter "name=rb-$D-") >/dev/null
docker rmi "$img" >/dev/null 2>&1
if [ -n "$N" ]; then
  for a in baseline ponytail nonhuman; do for r in ${RUNS:-1 2}; do $PY bench/real/prep.py "$N" "$a" "$r" >/dev/null || echo "FAIL $N $a $r"; done; done
  echo "ready: $(docker ps --format '{{.Names}}' | grep -c "rb-$N-")"
fi
df -h / | tail -1
