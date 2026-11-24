#!/usr/bin/env bash
# Usage: run_hidden.sh <app_dir>
# Runs hidden/s1..s5 tests against the app and prints {"s1":{"func":[p,t],"sec":[p,t]},...}.
# Set VERBOSE=1 to see failure details on stderr.
set -u
if [ $# -ne 1 ] || [ ! -f "$1/api.ts" ]; then echo "usage: $0 <app_dir containing api.ts>" >&2; exit 2; fi
HERE="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$1" && pwd)"
export APP_DIR
out=""
for n in 1 2 3 4 5; do
  res="$(node --test --test-timeout=60000 --test-reporter="$HERE/hidden/reporter.mjs" "$HERE/hidden/s$n.test.ts" 2>/dev/null)"
  [ -n "${VERBOSE:-}" ] && node --test "$HERE/hidden/s$n.test.ts" >&2 2>&1
  # expected totals (functional, security) so a crashed file still reports totals
  read -r _ ef es < <(grep "^s$n " "$HERE/hidden/expected.txt")
  fp=$(printf '%s\n' "$res" | grep -c '^R functional pass')
  ff=$(printf '%s\n' "$res" | grep -c '^R functional fail')
  sp=$(printf '%s\n' "$res" | grep -c '^R security pass')
  sf=$(printf '%s\n' "$res" | grep -c '^R security fail')
  ft=$((fp+ff)); st=$((sp+sf))
  [ "$ft" -lt "$ef" ] && ft=$ef
  [ "$st" -lt "$es" ] && st=$es
  out="$out${out:+,}\"s$n\":{\"func\":[$fp,$ft],\"sec\":[$sp,$st]}"
done
echo "{$out}"
