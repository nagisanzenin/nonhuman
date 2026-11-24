#!/usr/bin/env bash
# Usage: run_hidden.sh <app_dir>
# Copies <app_dir> (without target/) to a temp dir, drops each hidden test file
# into its tests/, runs it offline and prints
#   {"r1":{"func":[passed,total],"sec":[passed,total]},...}
# A task file that fails to compile counts as 0 passed (totals come from the
# #[test] counts in the hidden source). Cargo output is kept on stderr only
# when HIDDEN_VERBOSE=1.
set -u
if [ $# -ne 1 ] || [ ! -f "$1/Cargo.toml" ]; then
  echo "usage: $0 <app_dir>" >&2
  exit 2
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$(cd "$1" && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/kvhidden.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/app"
tar -C "$APP" --exclude=target --exclude=Cargo.lock -cf - . | tar -C "$TMP/app" -xf -
mkdir -p "$TMP/app/tests"
export CARGO_TARGET_DIR="$TMP/target"
cd "$TMP/app" || exit 2

count_total() { # file mod
  awk -v m="$2" '
    /^mod[ \t]+(functional|security)/ { cur = $2; sub(/[ \t{]+.*/, "", cur) }
    /^[ \t]*#\[test\]/ { if (cur == m) n++ }
    END { print n + 0 }' "$1"
}
count_pass() { # logfile mod
  grep -E "^test $2::.* \.\.\. ok$" "$1" | wc -l | tr -d ' '
}

printf '{'
first=1
for n in 1 2 3 4 5; do
  src="$HERE/hidden/r$n.rs"
  [ -f "$src" ] || continue
  cp "$src" "tests/r$n.rs"
  log="$TMP/r$n.log"
  cargo test --offline --test "r$n" >"$log" 2>&1
  [ "${HIDDEN_VERBOSE:-0}" = 1 ] && cat "$log" >&2
  rm -f "tests/r$n.rs"
  fp=$(count_pass "$log" functional); ft=$(count_total "$src" functional)
  sp=$(count_pass "$log" security);   st=$(count_total "$src" security)
  [ $first -eq 1 ] || printf ','
  first=0
  printf '"r%s":{"func":[%s,%s],"sec":[%s,%s]}' "$n" "$fp" "$ft" "$sp" "$st"
done
printf '}\n'
