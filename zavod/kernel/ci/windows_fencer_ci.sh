#!/usr/bin/env bash
# ДОКУМЕНТ: ci/windows_fencer_ci.sh
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-09 11:12 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 11:12 +03:00
# ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
# НАЗНАЧЕНИЕ: аудит E4-6, M-E46-03 — полный сценарий ограждения E4-8 на Windows Job Object: установка H1.31 и
#   Z-EXT-01 на PostgreSQL 16, сборка win/zavod_jobhost.exe, полный tests/fencer.test.mjs и tests/jobhost.test.mjs
#   при CI=true (пропуск запрещён). Проход требует: fail 0, skipped 0, сценарий с живым потомком и мутация
#   «только ведущий» прошли, в журнале строки ZAVOD_E48_EVIDENCE с UNKNOWN_OUTCOME, RECONCILE_NOT_FENCED,
#   JOB_OBJECT_TERMINATED и ровно одним эффектом.
# ВЫЗОВ: bash ci/windows_fencer_ci.sh <папка пакета H1.31> <рабочая папка>
# СРЕДА: PGHOST/PGPORT/PGUSER заданы; кластер с входом trust только на 127.0.0.1; psql и node в PATH.
#   Предел подключений bem_bootstrap_admin поднимается на время прогона и в конце возвращается к 0.
set -u
PKG_SRC=$(cd "$1" && pwd)
WORK=$2
HERE=$(cd "$(dirname "$0")/.." && pwd)
FAIL=0
fail() { echo "::error::$1"; FAIL=1; }

mkdir -p "$WORK/pkg"
cp -R "$PKG_SRC/." "$WORK/pkg/"
echo "=== WINDOWS FENCER CI start $(date -u '+%Y-%m-%dT%H:%M:%SZ'); $(psql -U postgres -d postgres -Atc 'select version()')"
psql -U postgres -d postgres -Atc 'show server_version' | grep -q '^16\.' || { echo "::error::PostgreSQL 16 required"; exit 2; }

cd "$WORK/pkg" || exit 9
psql -v ON_ERROR_STOP=1 -U postgres -d postgres -f 00_cluster_bootstrap.sql > chain_00.out 2>&1 || { tail -5 chain_00.out; fail "00 failed"; }
node run_migration.mjs --files 01_database_migration.sql > chain_wrapper.out 2>&1 || { tail -20 chain_wrapper.out; fail "wrapper failed"; }
tail -1 chain_wrapper.out
node "$HERE/db/build_ext.mjs" 01_database_migration.sql --check || fail "Z-EXT-01 build stale"
psql -v ON_ERROR_STOP=1 -U postgres -d bem -f "$HERE/db/02_zavod_ext_01.sql" > chain_ext.out 2>&1 || { tail -5 chain_ext.out; fail "Z-EXT-01 failed"; }
tail -1 chain_ext.out
[ "$FAIL" -eq 0 ] || { echo "=== WINDOWS_FENCER_CI_RESULT=FAIL (install)"; exit 1; }
psql -U postgres -d bem -Atc "ALTER ROLE bem_bootstrap_admin CONNECTION LIMIT 2" >/dev/null || fail "cannot open bootstrap admin"

cd "$HERE" || exit 9
# npm ci стирает существующую node_modules; локально (папка уже есть) — сверка дерева с блокировкой (P4.702).
if [ -d node_modules ]; then
  npm ls --all > "$WORK/npm_ci.out" 2>&1 || { cat "$WORK/npm_ci.out"; fail "npm ls: tree differs from lock"; }
else
  npm ci --ignore-scripts --no-fund > "$WORK/npm_ci.out" 2>&1 || { cat "$WORK/npm_ci.out"; fail "npm ci"; }
fi
bash win/build_jobhost.sh || fail "jobhost build"

OUT="$WORK/win_fencer_tests.out"
CI=true node --test --test-concurrency=1 tests/jobhost.test.mjs tests/fencer.test.mjs > "$OUT" 2>&1
RC=$?
cat "$OUT"
[ "$RC" -eq 0 ] || fail "fencer/jobhost tests rc=$RC"
grep -q '^# fail 0$' "$OUT" || fail "fencer/jobhost: failures"
grep -q '^# skipped 0$' "$OUT" || fail "fencer/jobhost: skipped tests are not allowed (M-E46-03)"
for T in 'M-Z5-01 / E4-8: живой потомок' 'M-Z5-01 мутация E4-8' 'Job Object: потомок внутри' 'Job Object: гибель хозяина'; do
  grep -F "$T" "$OUT" | grep -q '^ok ' || fail "must pass on Job Object: $T"
  ! grep -F "$T" "$OUT" | grep -q 'SKIP' || fail "skipped on Job Object: $T"
done
TREE=$(grep -F 'ZAVOD_E48_EVIDENCE scenario=tree' "$OUT" || true)
for W in 'unit=JOB_OBJECT' 'lease_expired=UNKNOWN_OUTCOME' 'reconcile_unfenced=RECONCILE_NOT_FENCED' \
  'fence_method=JOB_OBJECT_TERMINATED' 'unit_empty=true' 'go_after_fence_effects=0' 'effects=1'; do
  printf '%s\n' "$TREE" | grep -qF "$W" || fail "evidence line lacks $W"
done
grep -F 'ZAVOD_E48_EVIDENCE scenario=leader_only' "$OUT" | grep -qF 'fence=FENCE_RUNTIME_ALIVE' || fail "leader-only mutation evidence"

psql -U postgres -d bem -Atc "ALTER ROLE bem_bootstrap_admin CONNECTION LIMIT 0" >/dev/null || fail "cannot close bootstrap admin"
[ "$FAIL" -eq 0 ] && echo "=== WINDOWS_FENCER_CI_RESULT=PASS" || echo "=== WINDOWS_FENCER_CI_RESULT=FAIL"
exit "$FAIL"
