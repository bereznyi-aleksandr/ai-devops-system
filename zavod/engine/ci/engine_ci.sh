#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/engine/ci/engine_ci.sh
# ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-09 06:40 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 08:05 +03:00 (v0.3: E4-4 e44_hostile_request.mjs; v0.2: E4-5 e45_limits.mjs; точный префикс act_)
# ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
# НАЗНАЧЕНИЕ: Завод, этап 4, E4-3 на чистом PostgreSQL 16: установка H1.31 + Z-EXT-01 (как kernel_ci.sh),
#   тесты проверщика графа, Flowable 8.0.0 на PostgreSQL (схема bem_engine в отдельной базе, как
#   ci/engine_pg.sh: суммы архива, war и драйвера сверяются), учебный заказ e43_training_order.mjs.
# ВЫЗОВ: bash ci/engine_ci.sh <папка пакета H1.31> <рабочая папка>   (из zavod/engine)
# СРЕДА: PGHOST/PGPORT, вход trust (одноразовый контейнер); ZAVOD_ENGINE_USER/ZAVOD_ENGINE_PASS —
#   одноразовая учётка движка, создаётся заданием и скрыта маской.
set -u
PKG_SRC=$(cd "$1" && pwd)
WORK=$2
HERE=$(cd "$(dirname "$0")/.." && pwd)
KERNEL="$HERE/../kernel"
NODE=${NODE:-node}
NPM=${NPM:-npm}
FAIL=0
fail() { echo "::error::$1"; FAIL=1; }
q() { psql -U postgres -d "$1" -Atc "$2"; }
FLOWABLE_ZIP_URL=https://github.com/flowable/flowable-engine/releases/download/flowable-8.0.0/flowable-8.0.0.zip
FLOWABLE_ZIP_SHA256=d0f9ad0b7b2170881d66928178cf31c66084f1d6e3ffe6237afb32d8e9f4ad1d
WAR_SHA256=9d49ea5ddd8ecd1220c9f42978f8dfb4576399f5830b92a5b7ae872f2f9947e4
PGJDBC_VER=42.7.13
PGJDBC_SHA256=6e0e4cc2d8cae902084f8a2b18728b073a6fd9d1f87c9d8bff8f298c18185b93
PGJDBC_URL=https://repo1.maven.org/maven2/org/postgresql/postgresql/$PGJDBC_VER/postgresql-$PGJDBC_VER.jar

mkdir -p "$WORK/pkg" "$WORK/dl" "$WORK/run" "$WORK/e43"
cp -R "$PKG_SRC/." "$WORK/pkg/"
echo "=== ENGINE CI start $(date -u '+%Y-%m-%dT%H:%M:%SZ'); $(q postgres 'select version()')"

echo "=== H1.31 + Z-EXT-01"
cd "$WORK/pkg" || exit 9
psql -v ON_ERROR_STOP=1 -U postgres -d postgres -f 00_cluster_bootstrap.sql > chain_00.out 2>&1 || { tail -5 chain_00.out; fail "00 failed"; }
"$NODE" run_migration.mjs --files 01_database_migration.sql > chain_wrapper.out 2>&1 || { tail -5 chain_wrapper.out; fail "wrapper failed"; }
tail -1 chain_wrapper.out
"$NODE" "$KERNEL/db/build_ext.mjs" 01_database_migration.sql --check || fail "Z-EXT-01 build stale"
psql -v ON_ERROR_STOP=1 -U postgres -d bem -f "$KERNEL/db/02_zavod_ext_01.sql" > chain_ext.out 2>&1 || { tail -5 chain_ext.out; fail "Z-EXT-01 failed"; }
"$NODE" "$KERNEL/db/build_final_ext.mjs" 05_final_state_check.sql --check || fail "Z-EXT-01 final check build stale"
psql -v ON_ERROR_STOP=1 --single-transaction -U postgres -d bem -f "$KERNEL/db/05_final_state_check_ext01.sql" > chain_final_ext.out 2>&1 || { grep -m3 -E 'ERROR|ОШИБКА' chain_final_ext.out; fail "Z-EXT-01 final state check"; }
[ "$FAIL" -eq 0 ] || { echo "=== ENGINE_CI_RESULT=FAIL"; exit 1; }
q bem "ALTER ROLE bem_bootstrap_admin CONNECTION LIMIT 2" >/dev/null || fail "cannot open bootstrap admin"

echo "=== зависимости Kernel (pg) по блокировке"
cd "$KERNEL" || exit 9
if [ -d node_modules ]; then "$NPM" ls --all > "$WORK/npm.out" 2>&1 || fail "npm ls"; else "$NPM" ci --ignore-scripts --no-fund > "$WORK/npm.out" 2>&1 || { cat "$WORK/npm.out"; fail "npm ci"; }; fi

echo "=== проверщик графа H1.31 §12 (E4-3)"
cd "$HERE" || exit 9
"$NODE" "$KERNEL/ci/leak_scan.mjs" . "$HERE/../../.github/workflows/zavod-engine.yml" || fail "leak scan (SR-02)"
"$NODE" src/graph_check.mjs bpmn/bem_work.bpmn20.xml || fail "graph check on model"
"$NODE" --test --test-reporter=spec tests/*.test.mjs > "$WORK/engine_tests.out" 2>&1 || { cat "$WORK/engine_tests.out"; fail "engine tests"; }
grep -E '^ℹ (tests|pass|fail)' "$WORK/engine_tests.out"

echo "=== Flowable 8.0.0 + драйвер PostgreSQL (суммы закреплены, как ci/engine_pg.sh)"
cd "$WORK/dl" || exit 9
curl -fsSL -o flowable-8.0.0.zip "$FLOWABLE_ZIP_URL" || { echo "::error::flowable download"; exit 1; }
echo "$FLOWABLE_ZIP_SHA256  flowable-8.0.0.zip" | sha256sum -c - || { echo "::error::flowable zip sha256"; exit 1; }
unzip -q -j flowable-8.0.0.zip 'wars/flowable-rest.war' -d . || { echo "::error::war not in zip"; exit 1; }
echo "$WAR_SHA256  flowable-rest.war" | sha256sum -c - || { echo "::error::war sha256"; exit 1; }
curl -fsSL -o "postgresql-$PGJDBC_VER.jar" "$PGJDBC_URL" || { echo "::error::pgjdbc download"; exit 1; }
echo "$PGJDBC_SHA256  postgresql-$PGJDBC_VER.jar" | sha256sum -c - || { echo "::error::pgjdbc sha256 pin"; exit 1; }
mkdir -p inj/WEB-INF/lib && cp "postgresql-$PGJDBC_VER.jar" inj/WEB-INF/lib/ && cp flowable-rest.war "$WORK/run/flowable-rest-pg.war"
unzip -p flowable-rest.war WEB-INF/classpath.idx > inj/WEB-INF/classpath.idx
printf -- '- "WEB-INF/lib/postgresql-%s.jar"\n' "$PGJDBC_VER" >> inj/WEB-INF/classpath.idx
(cd inj && zip -q -0 "$WORK/run/flowable-rest-pg.war" "WEB-INF/lib/postgresql-$PGJDBC_VER.jar" && zip -q "$WORK/run/flowable-rest-pg.war" WEB-INF/classpath.idx)

# Движок — в своей базе и схеме bem_engine (H1.28 §8.4): bem_core ему не виден.
psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "CREATE DATABASE bem_engine_e43" -q || exit 1
psql -v ON_ERROR_STOP=1 -U postgres -d bem_engine_e43 -c "CREATE SCHEMA bem_engine" -q || exit 1
FLOWABLE_REST_APP_ADMIN_USERID="$ZAVOD_ENGINE_USER" FLOWABLE_REST_APP_ADMIN_PASSWORD="$ZAVOD_ENGINE_PASS" \
java -Xmx768m -jar "$WORK/run/flowable-rest-pg.war" --server.address=127.0.0.1 --server.port=8091 \
  "--spring.datasource.url=jdbc:postgresql://${PGHOST}:${PGPORT}/bem_engine_e43?currentSchema=bem_engine" \
  --spring.datasource.username=postgres --spring.datasource.password= \
  --flowable.database-schema=bem_engine \
  --flowable.rest.app.create-demo-definitions=false \
  --flowable.async-executor-activate=true > "$WORK/run/engine.log" 2>&1 &
ENGINE_PID=$!
UP=0
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -u "$ZAVOD_ENGINE_USER:$ZAVOD_ENGINE_PASS" http://127.0.0.1:8091/flowable-rest/service/management/engine || true)
  [ "$code" = "200" ] && { echo "=== engine up after $((i*2)) s"; UP=1; break; }
  kill -0 "$ENGINE_PID" 2>/dev/null || break
  sleep 2
done
[ "$UP" -eq 1 ] || { tail -60 "$WORK/run/engine.log"; fail "engine did not start"; }

if [ "$UP" -eq 1 ]; then
  echo "=== E4-3 учебный заказ"
  cd "$HERE" || exit 9
  PGDATABASE=bem E43_OUT="$WORK/e43" ZAVOD_ENGINE_BASE=http://127.0.0.1:8091/flowable-rest \
    "$NODE" ci/e43_training_order.mjs || fail "E4-3 training order"
  echo "=== E4-5 предел попыток и расход (SR-07)"
  PGDATABASE=bem E43_OUT="$WORK/e43" ZAVOD_ENGINE_BASE=http://127.0.0.1:8091/flowable-rest \
    "$NODE" ci/e45_limits.mjs || fail "E4-5 SR-07 limits"
  echo "=== E4-4 вредная заявка (T1)"
  PGDATABASE=bem E43_OUT="$WORK/e43" ZAVOD_ENGINE_BASE=http://127.0.0.1:8091/flowable-rest \
    "$NODE" ci/e44_hostile_request.mjs || fail "E4-4 T1 hostile request"
fi
kill "$ENGINE_PID" 2>/dev/null
TABLES_ENGINE=$(q bem_engine_e43 "select count(*) from information_schema.tables where table_schema='bem_engine' and left(table_name, 4) = 'act_'")
TABLES_BEM=$(q bem "select count(*) from information_schema.tables where left(table_name, 4) = 'act_'")
echo "=== таблиц ACT_* в bem_engine_e43.bem_engine: $TABLES_ENGINE; в базе bem: $TABLES_BEM"
[ "${TABLES_ENGINE:-0}" -gt 0 ] && [ "${TABLES_BEM:-1}" -eq 0 ] || fail "engine tables misplaced"

q bem "ALTER ROLE bem_bootstrap_admin CONNECTION LIMIT 0" >/dev/null || fail "cannot close bootstrap admin"
[ "$FAIL" -eq 0 ] && echo "=== ENGINE_CI_RESULT=PASS" || echo "=== ENGINE_CI_RESULT=FAIL"
exit "$FAIL"
