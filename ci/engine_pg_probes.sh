#!/usr/bin/env bash
# ДОКУМЕНТ: ci/engine_pg_probes.sh
# ВЕРСИЯ: v1.0
# СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-07 06:35 +03:00
# ИСПОЛНИТЕЛЬ: Claude (сессия f19e07a7-6edd-48a5-9ede-88086c949326)
# НАЗНАЧЕНИЕ: остальные пробы движка раздела 22 (пункты 1–4, 6–9, 12–14) на Flowable 8.0.0 + PostgreSQL 16, схема bem_engine.
#   Пункт 5 — отдельным заданием (ci/engine_pg.sh). Загрузки и их суммы — как в ci/engine_pg.sh v1.2.
#   Каждая проверка пишет строку в checks.jsonl с ожидаемым итогом; итог задания — все строки ok.
# ВЫЗОВ: bash ci/engine_pg_probes.sh <рабочая папка>
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
export ENGINE_WORK="$W/run"
CHECKS="$W/run/checks.jsonl"; : > "$CHECKS"
shcheck() { # id ok(0/1) detail
  local ok=false; [ "$2" = 1 ] && ok=true
  printf '{"id":"%s","ok":%s,"detail":"%s"}\n' "$1" "$ok" "$3" >> "$CHECKS"
  echo "$([ "$ok" = true ] && echo CHECK_PASS || echo CHECK_FAIL) $1: $3"
}

cd "$W/dl" || exit 9
curl -fsSL -o flowable-8.0.0.zip "$FLOWABLE_ZIP_URL" || { echo "::error::flowable download"; exit 1; }
echo "$FLOWABLE_ZIP_SHA256  flowable-8.0.0.zip" | sha256sum -c - || { echo "::error::flowable zip sha256"; exit 1; }
unzip -q -j flowable-8.0.0.zip 'wars/flowable-rest.war' -d . || { echo "::error::war not in zip"; exit 1; }
echo "$WAR_SHA256  flowable-rest.war" | sha256sum -c - || { echo "::error::war sha256"; exit 1; }
unzip -p flowable-8.0.0.zip license.txt > "$W/run/license.txt" || echo "::warning::license.txt not at zip root"
curl -fsSL -o "postgresql-$PGJDBC_VER.jar" "$PGJDBC_URL" && curl -fsSL -o pgjdbc.sha1 "$PGJDBC_URL.sha1" || { echo "::error::pgjdbc download"; exit 1; }
echo "$(cut -c1-40 pgjdbc.sha1)  postgresql-$PGJDBC_VER.jar" | sha1sum -c - || { echo "::error::pgjdbc sha1 (Maven)"; exit 1; }
echo "$PGJDBC_SHA256  postgresql-$PGJDBC_VER.jar" | sha256sum -c - || { echo "::error::pgjdbc sha256 pin"; exit 1; }

mkdir -p inj/WEB-INF/lib && cp "postgresql-$PGJDBC_VER.jar" inj/WEB-INF/lib/ && cp flowable-rest.war "$W/run/flowable-rest-pg.war"
unzip -p flowable-rest.war WEB-INF/classpath.idx > inj/WEB-INF/classpath.idx
printf -- '- "WEB-INF/lib/postgresql-%s.jar"\n' "$PGJDBC_VER" >> inj/WEB-INF/classpath.idx
(cd inj && zip -q -0 "$W/run/flowable-rest-pg.war" "WEB-INF/lib/postgresql-$PGJDBC_VER.jar" && zip -q "$W/run/flowable-rest-pg.war" WEB-INF/classpath.idx)

psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "CREATE DATABASE bem_engine_ci" -q || exit 1
psql -v ON_ERROR_STOP=1 -U postgres -d bem_engine_ci -c "CREATE SCHEMA bem_engine" -q || exit 1

HEALTH=http://127.0.0.1:8091/flowable-rest/actuator/health
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

start_engine run1 || exit 1
node "$HERE/engine/p01_p13.mjs" || echo "::warning::p01_p13 exit $?"
node "$HERE/engine/p02_p14.mjs" || echo "::warning::p02_p14 exit $?"
node "$HERE/engine/p07_p08.mjs" || echo "::warning::p07_p08 exit $?"
node "$HERE/engine/p12.mjs" || echo "::warning::p12 exit $?"

# п.12(б): сигнал 1 — health без учётки отвечает (жив); убитый движок не отвечает; после перезапуска снова отвечает.
H1=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$HEALTH" || true)
kill -9 "$ENGINE_PID"; wait "$ENGINE_PID" 2>/dev/null
H2=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$HEALTH"); RC2=$?
start_engine run2 || exit 1
H3=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$HEALTH" || true)
[ "$H1" != "000" ] && [ "$RC2" -ne 0 ] && [ "$H3" != "000" ] && ok=1 || ok=0
shcheck p12b_signal1_health "$ok" "живой ${H1}; убит kill -9: curl rc ${RC2} код ${H2}; после перезапуска ${H3}"
ALIVE=$(curl -s -u "$ENGINE_USER:$ENGINE_PASS" "http://127.0.0.1:8091/flowable-rest/service/runtime/process-instances?businessKey=W-CI-12a" | grep -o '"total":[0-9]*' | cut -d: -f2)
[ "${ALIVE:-0}" = 1 ] && ok=1 || ok=0
shcheck p12b_instance_survives_restart "$ok" "W-CI-12a после kill -9 и перезапуска: найдено ${ALIVE:-0}"
kill "$ENGINE_PID" 2>/dev/null

TABLES_ENGINE=$(psql -U postgres -d bem_engine_ci -Atc "select count(*) from information_schema.tables where table_schema='bem_engine' and table_name like 'act_%'")
TABLES_PUBLIC=$(psql -U postgres -d bem_engine_ci -Atc "select count(*) from information_schema.tables where table_schema='public' and table_name like 'act_%'")
[ "${TABLES_ENGINE:-0}" -gt 0 ] && [ "${TABLES_PUBLIC:-1}" -eq 0 ] && ok=1 || ok=0
shcheck schema_bem_engine_only "$ok" "таблиц ACT_* в bem_engine ${TABLES_ENGINE}; в public ${TABLES_PUBLIC}"

TOTAL=$(grep -c . "$CHECKS"); FAILED=$(grep -c '"ok":false' "$CHECKS")
echo "=== проверок: $TOTAL из ожидаемых 45; не прошло: $FAILED"
grep '"ok":false' "$CHECKS" | cut -c1-400
# Ожидаемый состав — 45 проверок: p01_p13 17, p02_p14 15, p07_p08 7, p12 3, этот сценарий 3.
# Меньше 45 — программа упала посреди проб; это тоже FAIL.
EXPECTED=45
[ "$FAILED" -eq 0 ] && [ "$TOTAL" -eq "$EXPECTED" ] && { echo "=== ENGINE_PG_PROBES_RESULT=PASS"; exit 0; }
echo "=== ENGINE_PG_PROBES_RESULT=FAIL"; exit 1
