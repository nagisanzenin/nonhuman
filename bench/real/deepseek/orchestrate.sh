#!/bin/bash
# Runs all 48 DeepSeek runs (16 held-out tasks x 3 arms), 6 at a time; grades each task once its 3 runs finish; spend guard every 60 s.
cd ~/rbds; mkdir -p results/ds_logs
TASKS=$(seq -f "h%02g" 1 16)
( while :; do python3 bench/ds/spend.py 10 >> results/ds_logs/spend.log 2>&1; sleep 60; done ) & G=$!
( for t in $TASKS; do
    until [ -f runs/$t/baseline/r9/DONE ] && [ -f runs/$t/ponytail/r9/DONE ] && [ -f runs/$t/nonhuman/r9/DONE ]; do
      [ -f STOP ] && [ -z "$(pgrep -f run_one.sh)" ] && break; sleep 20; done
    [ -f runs/$t/nonhuman/r9/DONE ] || continue
    .venv/bin/python bench/ds/grade_ds.py $t > results/ds_logs/grade_$t.log 2>&1
    img=$(docker inspect rb-$t-baseline-r9 --format '{{.Config.Image}}' 2>/dev/null)
    docker rm -f rb-$t-baseline-r9 rb-$t-ponytail-r9 rb-$t-nonhuman-r9 >/dev/null 2>&1; docker rmi "$img" >/dev/null 2>&1
    echo "graded $t $(date +%H:%M) $(df -h / | awk 'NR==2{print $4}')" >> results/ds_logs/progress.log
  done ) & W=$!
for t in $TASKS; do for a in baseline ponytail nonhuman; do echo "$t $a"; done; done | xargs -P 6 -L 1 bench/ds/run_one.sh >> results/ds_logs/runs.log 2>&1
wait $W; kill $G; python3 bench/ds/spend.py 10 >> results/ds_logs/spend.log; echo ALLDONE >> results/ds_logs/progress.log
