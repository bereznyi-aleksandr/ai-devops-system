#!/usr/bin/env bash
# ДОКУМЕНТ: ci/kernel_ci.sh
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-07 13:30 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 13:30 +03:00
# ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
# НАЗНАЧЕНИЕ: Завод, этап 3 — полный прогон Kernel на чистом PostgreSQL 16:
#   установка пакета H1.31 (00 + обёртка), SR-08 (npm ci по блокировке, npm audit),
#   SR-02 (сканер утечек), тесты Kernel (E3-1, E3-3, E3-4), SR-09 (копия → восстановление →
#   сверка отпечатков + проверка, что подмена данных ловится).
# ВЫЗОВ: bash ci/kernel_ci.sh <папка пакета H1.31> <рабочая папка>
# СРЕДА: PGHOST/PGPORT заданы; вход trust (одноразовый контейнер или локальный стенд 127.0.0.1).
#   Предел подключений bem_bootstrap_admin поднимается сознательно на время прогона
#   (H1.31 §4.3) и в конце возвращается к 0.
set -u
PKG_SRC=$(cd "$1" && pwd)
WORK=$2
HERE=$(cd "$(dirname "$0")/.." && pwd)
NODE=${NODE:-node}
NPM=${NPM:-npm}
FAIL=0
fail() { echo "::error::$1"; FAIL=1; }
q() { psql -U postgres -d "$1" -Atc "$2"; }

mkdir -p "$WORK/pkg" "$WORK/backup"
cp -R "$PKG_SRC/." "$WORK/pkg/"
echo "=== KERNEL CI start $(date -u '+%Y-%m-%dT%H:%M:%SZ'); $(q postgres 'select version()')"

cd "$WORK/pkg" || exit 9
psql -v ON_ERROR_STOP=1 -U postgres -d postgres -f 00_cluster_bootstrap.sql > chain_00.out 2>&1 || { tail -5 chain_00.out; fail "00 failed"; }
"$NODE" run_migration.mjs --files 01_database_migration.sql > chain_wrapper.out 2>&1 || { tail -5 chain_wrapper.out; fail "wrapper failed"; }
tail -1 chain_wrapper.out
q bem "ALTER ROLE bem_bootstrap_admin CONNECTION LIMIT 2" >/dev/null || fail "cannot open bootstrap admin"

cd "$HERE" || exit 9
echo "=== SR-08: npm ci по блокировке, без скриптов установки"
# npm ci стирает существующую node_modules; локально (папка уже есть) вместо него сверка дерева
# с блокировкой — правило «ничего не удалять» (P4.702). В CI папки нет, npm ci ничего не стирает.
if [ -d node_modules ]; then
  "$NPM" ls --all > "$WORK/npm_ci.out" 2>&1 || { cat "$WORK/npm_ci.out"; fail "npm ls: tree differs from lock"; }
else
  "$NPM" ci --ignore-scripts --no-fund > "$WORK/npm_ci.out" 2>&1 || { cat "$WORK/npm_ci.out"; fail "npm ci"; }
fi
"$NPM" audit --audit-level=high > "$WORK/npm_audit.out" 2>&1 || { cat "$WORK/npm_audit.out"; fail "npm audit high+"; }
tail -1 "$WORK/npm_audit.out"

echo "=== SR-02: сканер утечек"
"$NODE" ci/leak_scan.mjs . --allow ci/leak_scan_allow.txt || fail "leak scan"

echo "=== Тесты Kernel"
"$NODE" --test --test-concurrency=1 --test-reporter=spec tests/*.test.mjs > "$WORK/tests.out" 2>&1
RC=$?
grep -E '^\s*(✔|✖)|^ℹ (tests|pass|fail)' "$WORK/tests.out"
[ "$RC" -eq 0 ] || { cat "$WORK/tests.out"; fail "kernel tests rc=$RC"; }

echo "=== SR-09: копия → восстановление → сверка"
cd "$WORK/backup" || exit 9
DIG="select md5(string_agg(table_name||shape_sha256||data_sha256, ',' order by table_name)) from bem_control.database_digest()"
pg_dump -U postgres -d bem -Fc -f bem.dump || fail "pg_dump"
RDB="bem_restore_ci_$(date +%s)"   # новое имя на каждый прогон: ничего не удаляется
createdb -U postgres "$RDB" || fail "createdb"
pg_restore -U postgres -d "$RDB" --exit-on-error bem.dump > restore.log 2>&1 || { tail -5 restore.log; fail "pg_restore"; }
D1=$(psql -U bem_kernel_rw -d bem -Atc "$DIG"); D2=$(psql -U bem_kernel_rw -d "$RDB" -Atc "$DIG")
echo "digest bem=$D1 restore=$D2"
[ -n "$D1" ] && [ "$D1" = "$D2" ] || fail "restore digest differs"
psql -U postgres -d "$RDB" -Atc "UPDATE bem_core.work_item SET criticality = CASE criticality WHEN 'NORMAL' THEN 'CRITICAL' ELSE 'NORMAL' END WHERE id = (SELECT id FROM bem_core.work_item LIMIT 1)" >/dev/null
D3=$(psql -U bem_kernel_rw -d "$RDB" -Atc "$DIG")
[ "$D3" != "$D1" ] || fail "digest did not notice tampering"
echo "tamper digest=$D3 (must differ)"

q bem "ALTER ROLE bem_bootstrap_admin CONNECTION LIMIT 0" >/dev/null || fail "cannot close bootstrap admin"
[ "$FAIL" -eq 0 ] && echo "=== KERNEL_CI_RESULT=PASS" || echo "=== KERNEL_CI_RESULT=FAIL"
exit "$FAIL"
