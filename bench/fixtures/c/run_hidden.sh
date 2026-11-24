#!/bin/bash
# run_hidden.sh <app_dir>
# Builds each hidden test (hidden/c1.c .. c5.c) against the library sources in
# <app_dir> with ASan+UBSan and prints one JSON object on stdout:
#   {"c1":{"func":[passed,total],"sec":[passed,total]}, ...}
# A build/link failure scores 0 passed.  A crash, sanitizer report, timeout or
# non-zero abort scores only the checks that had already printed PASS.
# Totals come from the "TOTALS func=N sec=M" header of each hidden test.
# Build/run logs are kept in $HIDDEN_LOGDIR (default: a fresh temp dir).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="${1:?usage: run_hidden.sh <app_dir>}"
APP="$(cd "$APP" && pwd)" || exit 2
LOGDIR="${HIDDEN_LOGDIR:-$(mktemp -d "${TMPDIR:-/tmp}/strkit_hidden.XXXXXX")}"
mkdir -p "$LOGDIR"
CC="${CC:-clang}"
SAN="-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer"
export UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=1"
# Leak detection at exit exists on Linux only (not supported by Apple's ASan);
# the tests also check the allocator's live-byte count directly.
if [ "$(uname)" = "Linux" ]; then export ASAN_OPTIONS="detect_leaks=1"; fi

SRCS=()
for f in "$APP"/*.c; do [ -e "$f" ] && SRCS+=("$f"); done

count() { grep -c "^PASS $2" "$1" 2>/dev/null || true; }

out="{"
sep=""
for n in 1 2 3 4 5; do
  t="$HERE/hidden/c$n.c"
  ft=$(sed -n 's/.*TOTALS func=\([0-9]*\) sec=\([0-9]*\).*/\1/p' "$t" | head -1)
  st=$(sed -n 's/.*TOTALS func=\([0-9]*\) sec=\([0-9]*\).*/\2/p' "$t" | head -1)
  bin="$LOGDIR/c$n.bin"; log="$LOGDIR/c$n.run.log"
  fp=0; sp=0
  rm -f "$bin"
  if $CC -std=c11 -g -O1 -w $SAN -I"$APP" "$t" "${SRCS[@]}" -o "$bin" >"$LOGDIR/c$n.build.log" 2>&1; then
    # perl alarm = hard wall-clock cap in case a test's own alarm cannot fire
    ( perl -e 'alarm 120; exec @ARGV' "$bin" >"$log" 2>&1 </dev/null ) 2>/dev/null
    fp=$(count "$log" func); sp=$(count "$log" sec)
    [ "$fp" -gt "$ft" ] && fp=$ft
    [ "$sp" -gt "$st" ] && sp=$st
  fi
  out="$out$sep\"c$n\":{\"func\":[$fp,$ft],\"sec\":[$sp,$st]}"
  sep=","
done
echo "$out}"
echo "logs: $LOGDIR" >&2
