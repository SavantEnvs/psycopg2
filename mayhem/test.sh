#!/usr/bin/env bash
#
# mayhem/test.sh — RUN upstream's own unittest suite (749 tests) against the normally-built extension
# (build/oracle, made by mayhem/build.sh) and a throwaway PostgreSQL server on a unix socket.
# The runner is the ELF /mayhem/psycopg2-tests, so a neutered program yields no RESULT line and fails.
set -uo pipefail
[ -n "${SOURCE_DATE_EPOCH:-}" ] || unset SOURCE_DATE_EPOCH
cd "$SRC"

emit_ctrf() {
  local tool="$1" passed="$2" failed="$3" skipped="${4:-0}" pending="${5:-0}" other="${6:-0}"
  local tests=$(( passed + failed + skipped + pending + other ))
  cat > "${CTRF_REPORT:-$SRC/ctrf-report.json}" <<JSON
{
  "results": {
    "tool": { "name": "$tool" },
    "summary": {
      "tests": $tests,
      "passed": $passed,
      "failed": $failed,
      "pending": $pending,
      "skipped": $skipped,
      "other": $other
    }
  }
}
JSON
  printf 'CTRF {"results":{"tool":{"name":"%s"},"summary":{"tests":%d,"passed":%d,"failed":%d,"pending":%d,"skipped":%d,"other":%d}}}\n' \
    "$tool" "$tests" "$passed" "$failed" "$pending" "$skipped" "$other"
  [ "$failed" -eq 0 ]
}

[ -x /mayhem/psycopg2-tests ] || { echo "missing /mayhem/psycopg2-tests (build.sh bug)" >&2; emit_ctrf unittest 0 1 0; exit 1; }

PGB="$(ls -d /usr/lib/postgresql/*/bin | tail -1)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/psycopg2-test.XXXXXX")"
stop_pg() { "$PGB/pg_ctl" -D "$WORK/data" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap stop_pg EXIT

"$PGB/initdb" -D "$WORK/data" -A trust -U psycopg2 -E UTF8 --locale=C.UTF-8 >/dev/null \
  && "$PGB/pg_ctl" -D "$WORK/data" -o "-k $WORK -c listen_addresses=''" -l "$WORK/log" -w start >/dev/null \
  && "$PGB/createdb" -h "$WORK" -U psycopg2 psycopg2_test \
  || { echo "could not start a PostgreSQL server" >&2; cat "$WORK/log" 2>/dev/null >&2; emit_ctrf unittest 0 1 0; exit 1; }

export PGHOST="$WORK" PGUSER=psycopg2 PYTHONPATH=/mayhem/build/oracle/lib
/mayhem/psycopg2-tests 2>&1 | tee "$WORK/out.log"

line="$(grep -E '^RESULT tests=' "$WORK/out.log" | tail -1 || true)"
if [ -z "$line" ]; then
  echo "test runner produced no RESULT line" >&2
  emit_ctrf unittest 0 1 0; exit 1
fi
passed="$(sed -E 's/.* passed=([0-9]+).*/\1/' <<<"$line")"
failed="$(sed -E 's/.* failed=([0-9]+).*/\1/' <<<"$line")"
skipped="$(sed -E 's/.* skipped=([0-9]+).*/\1/' <<<"$line")"
emit_ctrf unittest "$passed" "$failed" "$skipped"
