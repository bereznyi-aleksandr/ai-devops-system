#!/usr/bin/env bash
# ДОКУМЕНТ: ci/engine_pg.sh
# ВЕРСИЯ: v1.2 (v1.2: SHA-256 драйвера закреплена по прогону 37502140080; v1.1: путь war в архиве)
# СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-06 19:55 +03:00
# ДАТА ОБНОВЛЕНИЯ: 2026-10-06 20:18 +03:00
# ИСПОЛНИТЕЛЬ: Claude (сессия 4401918c-de88-4db7-841e-b418568ae069)
# НАЗНАЧЕНИЕ: проба движка процессов Flowable 8.0.0 на PostgreSQL 16 (схема bem_engine, H1.28 §8.4, §22.2):
#   сверка сумм архива Flowable и war; JDBC-драйвер PostgreSQL из Maven Central (сверка SHA-1 Maven,
#   SHA-256 пишется в журнал); драйвер кладётся в копию war; проба п.5 — жёсткое убийство java и
#   перезапуск: экземпляр жив, та же работа, один эффект, процесс доходит до конца.
# ВЫЗОВ: bash ci/engine_pg.sh <рабочая папка>
# СРЕДА: PGHOST/PGPORT/PGUSER; ENGINE_USER/ENGINE_PASS — одноразовая учётка, создаётся заданием.
set -u
W=$1; mkdir -p "$W/dl" "$W/run"
HERE=$(cd "$(dirname "$0")" && pwd)
FLOWABLE_ZIP_URL=https://github.com/flowable/flowable-engine/releases/download/flowable-8.0.0/flowable-8.0.0.zip
FLOWABLE_ZIP_SHA256=d0f9ad0b7b2170881d66928178cf31c66084f1d6e3ffe6237afb32d8e9f4ad1d
WAR_SHA256=9d49ea5ddd8ecd1220c9f42978f8dfb4576399f5830b92a5b7ae872f2f9947e4
PGJDBC_VER=42.7.13
PGJDBC_SHA256=6e0e4cc2d8cae902084f8a2b18728b073a6fd9d1f87c9d8bff8f298c18185b93
PGJDBC_URL=https://repo1.maven.org/maven2/org/postgresql/postgresql/$PGJDBC_VER/postgresql-$PGJDBC_VER.jar
FAIL=0
fail() { echo "::error::$1"; FAIL=1; }

cd "$W/dl" || exit 9
curl -fsSL -o flowable-8.0.0.zip "$FLOWABLE_ZIP_URL" || { echo "::error::flowable download"; exit 1; }
echo "$FLOWABLE_ZIP_SHA256  flowable-8.0.0.zip" | sha256sum -c - || { echo "::error::flowable zip sha256"; exit 1; }
unzip -q -j flowable-8.0.0.zip 'wars/flowable-rest.war' -d . || { echo "::error::war not in zip"; exit 1; }
echo "$WAR_SHA256  flowable-rest.war" | sha256sum -c - || { echo "::error::war sha256"; exit 1; }
curl -fsSL -o "postgresql-$PGJDBC_VER.jar" "$PGJDBC_URL" && curl -fsSL -o pgjdbc.sha1 "$PGJDBC_URL.sha1" || { echo "::error::pgjdbc download"; exit 1; }
echo "$(cut -c1-40 pgjdbc.sha1)  postgresql-$PGJDBC_VER.jar" | sha1sum -c - || { echo "::error::pgjdbc sha1 (Maven)"; exit 1; }
echo "=== PGJDBC_SHA256 $(sha256sum "postgresql-$PGJDBC_VER.jar" | cut -c1-64) postgresql-$PGJDBC_VER.jar ($(wc -c < "postgresql-$PGJDBC_VER.jar") bytes)"
echo "$PGJDBC_SHA256  postgresql-$PGJDBC_VER.jar" | sha256sum -c - || { echo "::error::pgjdbc sha256 pin"; exit 1; }

# Копия war с драйвером: вложенный jar кладётся без сжатия (-0) и вписывается в WEB-INF/classpath.idx.
mkdir -p inj/WEB-INF/lib && cp "postgresql-$PGJDBC_VER.jar" inj/WEB-INF/lib/ && cp flowable-rest.war "$W/run/flowable-rest-pg.war"
unzip -p flowable-rest.war WEB-INF/classpath.idx > inj/WEB-INF/classpath.idx
printf -- '- "WEB-INF/lib/postgresql-%s.jar"\n' "$PGJDBC_VER" >> inj/WEB-INF/classpath.idx
(cd inj && zip -q -0 "$W/run/flowable-rest-pg.war" "WEB-INF/lib/postgresql-$PGJDBC_VER.jar" && zip -q "$W/run/flowable-rest-pg.war" WEB-INF/classpath.idx)
echo "=== war с драйвером: $(sha256sum "$W/run/flowable-rest-pg.war" | cut -c1-64)"

psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "CREATE DATABASE bem_engine_ci" -q || exit 1
psql -v ON_ERROR_STOP=1 -U postgres -d bem_engine_ci -c "CREATE SCHEMA bem_engine" -q || exit 1

start_engine() {
  java -Xmx768m -jar "$W/run/flowable-rest-pg.war" --server.address=127.0.0.1 --server.port=8091 \
    "--spring.datasource.url=jdbc:postgresql://${PGHOST}:${PGPORT}/bem_engine_ci?currentSchema=bem_engine" \
    --spring.datasource.username=postgres --spring.datasource.password= \
    --flowable.database-schema=bem_engine \
    --flowable.rest.app.create-demo-definitions=false \
    --flowable.async-executor-activate=true > "$W/run/engine_$1.log" 2>&1 &
  ENGINE_PID=$!
  for i in $(seq 1 90); do
    code=$(curl -s -o /dev/null -w '%{http_code}' -u "$ENGINE_USER:$ENGINE_PASS" http://127.0.0.1:8091/flowable-rest/service/management/engine || true)
    [ "$code" = "200" ] && { echo "=== engine $1 up after $((i*2)) s (pid $ENGINE_PID)"; return 0; }
    kill -0 "$ENGINE_PID" 2>/dev/null || break
    sleep 2
  done
  tail -60 "$W/run/engine_$1.log"; echo "::error::engine $1 did not start"; return 1
}

export ENGINE_WORK="$W/run"
start_engine run1 || exit 1
grep -m3 -i -E "postgres|database type|DatabaseType" "$W/run/engine_run1.log" | cut -c1-220
node "$HERE/engine/p05a_before_kill.mjs" || fail "p05a"
kill -9 "$ENGINE_PID"; wait "$ENGINE_PID" 2>/dev/null; echo "=== java убит kill -9 $(date -u +%H:%M:%SZ)"
start_engine run2 || exit 1
node "$HERE/engine/p05b_after_restart.mjs" || fail "p05b"
kill "$ENGINE_PID" 2>/dev/null

TABLES_ENGINE=$(psql -U postgres -d bem_engine_ci -Atc "select count(*) from information_schema.tables where table_schema='bem_engine' and table_name like 'act_%'")
TABLES_PUBLIC=$(psql -U postgres -d bem_engine_ci -Atc "select count(*) from information_schema.tables where table_schema='public' and table_name like 'act_%'")
echo "=== таблиц ACT_* в bem_engine: $TABLES_ENGINE; в public: $TABLES_PUBLIC"
[ "${TABLES_ENGINE:-0}" -gt 0 ] && [ "${TABLES_PUBLIC:-1}" -eq 0 ] || fail "engine tables not in schema bem_engine"
cat "$W/run/p05_result.json" 2>/dev/null
[ "$FAIL" -eq 0 ] && echo "=== ENGINE_PG_RESULT=PASS" || echo "=== ENGINE_PG_RESULT=FAIL"
exit "$FAIL"
