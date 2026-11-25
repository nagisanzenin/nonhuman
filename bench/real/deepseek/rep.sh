#!/bin/bash
cd ~/rbds
for t in h09 h10; do for a in baseline ponytail nonhuman; do for n in 10 11; do echo "$n $t $a"; done; done; done \
 | xargs -P 6 -L 1 bash -c 'RUN=$0 bench/ds/run_one.sh $1 $2' >> results/ds_logs/rep_runs.log 2>&1
for t in h09 h10; do RUNS="r10 r11" .venv/bin/python bench/ds/grade_ds.py $t > results/ds_logs/rep_grade_$t.log 2>&1; done
img=""; for t in h09 h10; do for a in baseline ponytail nonhuman; do for n in 10 11; do i=$(docker inspect rb-$t-$a-r$n --format '{{.Config.Image}}' 2>/dev/null); [ -n "$i" ] && img="$img $i"; docker rm -f rb-$t-$a-r$n >/dev/null 2>&1; done; done; done
for i in $(echo $img | tr ' ' '\n' | sort -u); do docker rmi "$i" >/dev/null 2>&1; done
echo REPDONE >> results/ds_logs/rep_runs.log
