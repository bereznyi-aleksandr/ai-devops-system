#!/usr/bin/env bash
# ДОКУМЕНТ: ci/kernel_ci.sh
# ВЕРСИЯ: v0.5  СТАТУС: CANDIDATE
# v0.5 (2026-10-07 17:08 +03:00): проба подмены claim_outbox_batch — итоговая проверка обязана упасть (аудит Z3 M-Z3-01).
# v0.4 (2026-10-07 16:19 +03:00): парная дельта-проверка 05 + отличия Z-EXT-01 после установки расширения.
# v0.3 (2026-10-07 16:16 +03:00): установка расширения Z-EXT-01 после 01 со сверкой сборки.
# ДАТА СОЗДАНИЯ: 2026-10-07 13:30 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 13:49 +03:00 (v0.2: копия с сортировкой bem; штамп исправлен по реальному времени)
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
# Расширение Завода Z-EXT-01 поверх H1.31 (аудит Z2: M-Z2-01, M-Z2-02). Сначала сверка, что
# файл собран из этого же 01 и не правлен руками, затем установка одной транзакцией.
"$NODE" "$HERE/db/build_ext.mjs" 01_database_migration.sql --check || fail "Z-EXT-01 build stale"
psql -v ON_ERROR_STOP=1 -U postgres -d bem -f "$HERE/db/02_zavod_ext_01.sql" > chain_ext.out 2>&1 || { tail -5 chain_ext.out; fail "Z-EXT-01 failed"; }
tail -1 chain_ext.out
# Парная дельта-проверка: терминальная проверка H1.31 05 (её прошла обёртка ДО расширения) плюс
# точный список отличий Z-EXT-01; лишнее право или объект — отказ. До подъёма предела admin.
"$NODE" "$HERE/db/build_final_ext.mjs" 05_final_state_check.sql --check || fail "Z-EXT-01 final check build stale"
psql -v ON_ERROR_STOP=1 --single-transaction -U postgres -d bem -f "$HERE/db/05_final_state_check_ext01.sql" > chain_final_ext.out 2>&1 || { grep -m3 -E 'ERROR|ОШИБКА' chain_final_ext.out; fail "Z-EXT-01 final state check"; }
echo "ZAVOD_FINAL_EXT_CHECK=done"
# Проба (аудит Z3 M-Z3-01): подменённое тело claim_outbox_batch ловит именно итоговая проверка,
# без функциональных тестов. Подмена в транзакции и не фиксируется.
if psql -v ON_ERROR_STOP=1 -U postgres -d bem -f "$HERE/db/probe_final_ext_mutation.sql" > chain_probe_ext.out 2>&1; then
  fail "Z-EXT-01 mutation of claim_outbox_batch not caught"
elif grep -q "FINAL_ZAVOD_FN_BODY_MISMATCH: claim_outbox_batch" chain_probe_ext.out; then
  echo "ZAVOD_FINAL_EXT_MUTATION_PROBE=caught"
else
  grep -m3 -E "ERROR|ОШИБКА" chain_probe_ext.out; fail "Z-EXT-01 mutation probe: wrong failure"
fi
# После пробы исходное тело на месте: итоговая проверка снова проходит.
psql -v ON_ERROR_STOP=1 --single-transaction -U postgres -d bem -f "$HERE/db/05_final_state_check_ext01.sql" > chain_final_ext2.out 2>&1 || fail "Z-EXT-01 final check after probe"
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
# Копия создаётся с той же кодировкой и сортировкой, что у bem (00: UTF8, C, template0):
# data_digest сортирует строки по тексту, и при другой сортировке отпечаток расходится
# (CI run 37609718755: копия по умолчанию en_US.utf8 -> «restore digest differs»).
read -r ENC COLL CTYPE <<< "$(q bem "select pg_encoding_to_char(encoding)||' '||datcollate||' '||datctype from pg_database where datname = current_database()")"
echo "restore db: encoding=$ENC collate=$COLL ctype=$CTYPE"
createdb -U postgres --template=template0 --encoding="$ENC" --lc-collate="$COLL" --lc-ctype="$CTYPE" "$RDB" || fail "createdb"
[ "$(q "$RDB" "select datcollate||' '||datctype from pg_database where datname = current_database()")" = "$COLL $CTYPE" ] || fail "restore db collation differs"
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
