#!/usr/bin/env bash
#
# mayhem/build.sh — build psycopg2's C extension twice (sanitized+SanCov for fuzzing, plain for the
# oracle) and the fuzz harnesses. Offline and re-runnable: apt/pip dependencies come from the Dockerfile.
set -euo pipefail

[ -n "${SOURCE_DATE_EPOCH:-}" ] || unset SOURCE_DATE_EPOCH

: "${SANITIZER_FLAGS=-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer}"
: "${DEBUG_FLAGS:=-g -gdwarf-3}"
: "${CC:=clang}" ; : "${CXX:=clang++}" ; : "${LIB_FUZZING_ENGINE:=-fsanitize=fuzzer}"
: "${MAYHEM_JOBS:=$(nproc)}"
: "${COVERAGE_FLAGS=}"
export CC CXX

cd "$SRC"

# 1) Test/oracle build: the project's normal flags, into build/oracle (build/ is gitignored upstream).
CFLAGS="$COVERAGE_FLAGS" LDFLAGS="$COVERAGE_FLAGS" \
  python3 setup.py -q build --build-base build/oracle --build-lib build/oracle/lib --parallel "$MAYHEM_JOBS"

# 2) Fuzz build: the extension itself carries the sanitizers, SanCov (libFuzzer feedback) and DWARF 3.
SAN_CFLAGS="$SANITIZER_FLAGS -fsanitize=fuzzer-no-link $DEBUG_FLAGS"
CFLAGS="$SAN_CFLAGS" LDFLAGS="$SANITIZER_FLAGS" \
  python3 setup.py -q build --build-base build/fuzz --build-lib build/lib --parallel "$MAYHEM_JOBS"

# 3) Native libFuzzer harnesses embedding CPython (+ a run-once -standalone reproducer each).
PYINC="$(python3-config --includes)"
PYLD="$(python3-config --embed --ldflags)"
$CXX $SANITIZER_FLAGS $DEBUG_FLAGS -c mayhem/lsan_off.cc -o /tmp/lsan_off.o
$CC $SANITIZER_FLAGS $DEBUG_FLAGS -c "$STANDALONE_FUZZ_MAIN" -o /tmp/standalone_main.o
for impl in typecast adapt; do
  # shellcheck disable=SC2086
  $CC $SANITIZER_FLAGS $DEBUG_FLAGS $PYINC -DIMPL="\"$impl\"" mayhem/fuzz_embed.c /tmp/lsan_off.o \
      $LIB_FUZZING_ENGINE $PYLD -o "/mayhem/fuzz_$impl"
  # shellcheck disable=SC2086
  $CC $SANITIZER_FLAGS $DEBUG_FLAGS $PYINC -DIMPL="\"$impl\"" mayhem/fuzz_embed.c /tmp/lsan_off.o \
      /tmp/standalone_main.o $PYLD -o "/mayhem/fuzz_$impl-standalone"
done

# 4) ELF launchers: Mayhem needs an ELF cmd for the atheris script; the test runner goes through one
#    too, so the sabotage check (which neuters non-system executables) can neuter the oracle.
launcher() {
  $CC $DEBUG_FLAGS -O1 -DPY_SCRIPT="\"$2\"" -o "/mayhem/$1" mayhem/launcher.c
}
launcher fuzz_sql /mayhem/mayhem/fuzz_sql.py
launcher psycopg2-tests /mayhem/mayhem/run_tests.py
chmod +x mayhem/fuzz_sql.py mayhem/run_tests.py 2>/dev/null || true

echo "build.sh complete"
