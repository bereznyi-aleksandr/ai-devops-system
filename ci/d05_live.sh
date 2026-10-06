#!/usr/bin/env bash
# ДОКУМЕНТ: ci/d05_live.sh
# ВЕРСИЯ: v1.0
# СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-06 19:35 +03:00
# ДАТА ОБНОВЛЕНИЯ: 2026-10-06 19:35 +03:00
# ИСПОЛНИТЕЛЬ: Claude (сессия 4401918c-de88-4db7-841e-b418568ae069)
# НАЗНАЧЕНИЕ: перенос локального run_r48_live_d05_v11.sh в GitHub Actions:
#   00_cluster_bootstrap.sql; обёртка run_migration.mjs дважды (отдельные копии пакета);
#   D-05 положительный (rc 0, D05_BLOCK_PASSED) и отрицательный
#   (rc 3, TRIGGER_TGQUAL_MISMATCH, откат одной транзакцией).
# ВЫЗОВ: bash ci/d05_live.sh <папка пакета> <рабочая папка>
# СРЕДА: PGHOST/PGPORT/PGUSER заданы заданием; пароль не нужен (одноразовый контейнер, trust).
set -u
PKG_SRC=$(cd "$1" && pwd)
R=$2
FAIL=0
fail() { echo "::error::$1"; FAIL=1; }
q() { psql -U postgres -d "$1" -Atc "$2"; }
run_wrapper() {
  echo "=== CMD ($1): node run_migration.mjs --files 01_database_migration.sql"
  node run_migration.mjs --files 01_database_migration.sql > chain_wrapper.out 2>&1
  local rc=$?
  echo "=== RC wrapper ($1) = $rc  (строк $(wc -l < chain_wrapper.out), ERROR-строк $(grep -c -E 'ERROR|ОШИБКА' chain_wrapper.out))"
  tail -2 chain_wrapper.out
  [ "$rc" -eq 0 ] || { cat chain_wrapper.out; fail "wrapper $1 rc=$rc"; }
}

mkdir -p "$R/first" "$R/second" "$R/d05"
cp -R "$PKG_SRC/." "$R/first/"
cp -R "$PKG_SRC/." "$R/second/"

echo "=== CI D-05, start $(date -u '+%Y-%m-%dT%H:%M:%SZ'); $(q postgres 'select version()')"
cd "$R/first" || exit 9
sha256sum 0*.sql migration_manifest.json run_migration.mjs
psql -v ON_ERROR_STOP=1 -U postgres -d postgres -f 00_cluster_bootstrap.sql > chain_00.out 2>&1
RC00=$?; echo "=== RC 00 = $RC00"
[ "$RC00" -eq 0 ] || { cat chain_00.out; fail "00_cluster_bootstrap rc=$RC00"; }
run_wrapper first
ROWS1=$(q bem "select string_agg(version, ',' order by version) from bem_core.schema_migration")
echo "=== schema_migration rows: $ROWS1"
cd "$R/second" || exit 9
run_wrapper second
ROWS2=$(q bem "select string_agg(version, ',' order by version) from bem_core.schema_migration")
echo "=== schema_migration rows: $ROWS2"
[ -n "$ROWS1" ] && [ "$ROWS1" = "$ROWS2" ] || fail "schema_migration differs after second run: '$ROWS1' vs '$ROWS2'"

cd "$R/d05" || exit 9
SQL01="$R/first/01_database_migration.sql"
MARK='DROP TABLE IF EXISTS pg_temp.subject_reference_shape;'
A=$(grep -n -F "$MARK" "$SQL01" | sed -n 1p | cut -d: -f1)
B=$(grep -n -F "$MARK" "$SQL01" | sed -n 2p | cut -d: -f1)
[ -n "$A" ] && [ -n "$B" ] || { fail "D-05 block markers not found in 01"; exit 1; }
echo "=== 01: $(sha256sum "$SQL01" | cut -c1-64); блок строк $A-$B"
sed -n "${A},${B}p" "$SQL01" > d05_block_from_01.sql
{
  printf 'DO $$\nDECLARE\n    v_tgqual_real text;\n    v_tgqual_ref  text;\nBEGIN\n'
  cat d05_block_from_01.sql
  printf "    RAISE NOTICE 'TGQUAL_ACTUAL=%%', v_tgqual_real;\n    RAISE NOTICE 'TGQUAL_REFERENCE=%%', v_tgqual_ref;\n    RAISE NOTICE 'D05_BLOCK_PASSED';\nEND\n\$\$;\n"
} > d05_positive.sql
{
  printf "DROP TRIGGER subject_requires_author ON bem_core.subject;\n"
  printf "CREATE CONSTRAINT TRIGGER subject_requires_author\n    AFTER INSERT OR UPDATE OF published_at ON bem_core.subject\n    DEFERRABLE INITIALLY DEFERRED\n    FOR EACH ROW\n    WHEN (NEW.published_at IS NULL)\n    EXECUTE FUNCTION bem_core.require_at_least_one_author();\n"
  cat d05_positive.sql
} > d05_negative.sql
TRG="select pg_get_triggerdef(oid) from pg_trigger where tgname='subject_requires_author'"
BEFORE=$(q bem "$TRG"); echo "=== триггер до: $BEFORE"

psql -v ON_ERROR_STOP=1 -U postgres -d bem -f d05_positive.sql > d05_positive.out 2>&1
RCP=$?; echo "=== POSITIVE rc=$RCP"; cat d05_positive.out
[ "$RCP" -eq 0 ] && grep -q D05_BLOCK_PASSED d05_positive.out || fail "D-05 positive: rc=$RCP or no D05_BLOCK_PASSED"

psql -v ON_ERROR_STOP=1 --single-transaction -U postgres -d bem -f d05_negative.sql > d05_negative.out 2>&1
RCN=$?; echo "=== NEGATIVE rc=$RCN"; cat d05_negative.out
[ "$RCN" -eq 3 ] && grep -q TRIGGER_TGQUAL_MISMATCH d05_negative.out || fail "D-05 negative: rc=$RCN (expected 3) or no TRIGGER_TGQUAL_MISMATCH"

AFTER=$(q bem "$TRG"); echo "=== триггер после (откат): $AFTER"
[ "$BEFORE" = "$AFTER" ] || fail "trigger not rolled back"
sha256sum d05_block_from_01.sql d05_positive.sql d05_negative.sql d05_positive.out d05_negative.out
[ "$FAIL" -eq 0 ] && echo "=== CI_D05_RESULT=PASS" || echo "=== CI_D05_RESULT=FAIL"
exit "$FAIL"
