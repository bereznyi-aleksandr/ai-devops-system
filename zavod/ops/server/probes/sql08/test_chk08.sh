#!/usr/bin/env bash
# ДОКУМЕНТ: test_chk08.sh (испытание команды «проверка базы после SQL 08, только чтение» на PostgreSQL 16 CI)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-16 20:12 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель), сменщик после HANDOFF_20261116_1916.
# ЗАПУСК (от root, ПОСЛЕ test_sql08.sh — база уже с SQL 08): test_chk08.sh <строка команды CMD_CHK08> <chk08.sql>
# Строка команды испытывается своими байтами; меняется ровно одно место на проверку. Изменяющая проверка K09 — последней.
set -euo pipefail
CMD=$(cat "$1"); CHK=$2
export TERM=dumb
T=$(mktemp -d); chmod 755 "$T"
PSQL=(runuser -u postgres -- psql -X -A -t -q -v ON_ERROR_STOP=1 -d bem)
fails=0
ok() { echo "PASS $1"; }
bad() { echo "FAIL $1: $2"; fails=$((fails + 1)); }
run() { bash -c "$1" 2>&1 | tr -d '\r'; }
CNT=$(grep -o ' -v cnt=[0-9]* ' <<< "$CMD" | tr -dc 0-9)
EXP=$(grep -o 'expect=[0-9a-f]\{64\}' <<< "$CMD" | cut -d= -f2)
CSHA=$(sha256sum < "$CHK" | cut -c1-64)
direct() {  # $1 — файл проверки, $2 — база
  runuser -u postgres -- env -i PATH=/usr/bin:/bin LC_ALL=C.UTF-8 PGOPTIONS='-c default_transaction_read_only=on' \
    psql -X -A -t -q -v ON_ERROR_STOP=1 -h /var/run/postgresql -p 5432 -U postgres -d "$2" \
    -v cnt="$CNT" -v expect="$EXP" -f "$1" 2>&1 || true
}
none() { [ -z "$("${PSQL[@]}" -c "SELECT coalesce(to_regclass('bem_control.zz_ro')::text,'')||coalesce(to_regclass('bem_control.zz_ro2')::text,'')")" ]; }
[ "$CNT" = 20 ] && [ "${#EXP}" = 64 ] && grep -qF "$CSHA" <<< "$CMD" || { echo "FAIL setup cnt=$CNT exp=$EXP"; exit 1; }

# K00. Штатный прогон: три строки CHK08 и OK, rc=0
O=$(run "$CMD")
grep -qx 'CHK08 target=socket:5432/bem ro=on rows=0' <<< "$O" \
  && grep -qx "CHK08 seal_rows=$CNT digest=${EXP:0:16} fn=secdef,owner,execute_owner_only fk=2/2" <<< "$O" \
  && grep -q '^CHK08 rest_rows=[0-9]* rest_digest=[0-9a-f]\{16\}$' <<< "$O" \
  && [ "$(grep -v '^rc=' <<< "$O" | tail -1)" = ZPROBE_B10_CHK08=OK ] && grep -qx 'rc=0' <<< "$O" \
  && ok K00_ok || bad K00_ok "$O"
# K01. Запись внутри транзакции проверки невозможна: READ ONLY отвергает CREATE, объекта нет
sed 's/^SET LOCAL statement_timeout = .60s.;$/&\nCREATE TABLE bem_control.zz_ro (i int);/' "$CHK" > "$T/k1.sql"; chmod 644 "$T/k1.sql"
[ "$(grep -c zz_ro "$T/k1.sql")" = 1 ] || bad K01_setup "line not inserted"
O=$(direct "$T/k1.sql" bem)
grep -q 'read-only transaction' <<< "$O" && none && ok K01_transaction_read_only || bad K01_transaction_read_only "$O"
# K02. PGOPTIONS команды сам по себе запрещает запись (вне транзакции файла)
O=$(runuser -u postgres -- env -i PATH=/usr/bin:/bin LC_ALL=C.UTF-8 PGOPTIONS='-c default_transaction_read_only=on' \
  psql -X -A -t -q -v ON_ERROR_STOP=1 -h /var/run/postgresql -p 5432 -U postgres -d bem \
  -c 'CREATE TABLE bem_control.zz_ro2 (i int)' 2>&1 || true)
grep -q 'read-only transaction' <<< "$O" && none && ok K02_session_read_only || bad K02_session_read_only "$O"
# K03. Чужая база → отказ
O=$(direct "$CHK" postgres)
grep -q 'CHK08_FAILED: wrong target' <<< "$O" && ok K03_wrong_target || bad K03_wrong_target "$O"
# K04. Переменные PG* у вызывающего не уводят команду
O=$(PGHOST=/nonexistent PGPORT=1 PGSERVICE=zz_none PGDATABASE=postgres PGUSER=nobody PGOPTIONS='-c search_path=zz' run "$CMD")
[ "$(grep -v '^rc=' <<< "$O" | tail -1)" = ZPROBE_B10_CHK08=OK ] && grep -qx 'rc=0' <<< "$O" && ok K04_env_ignored || bad K04_env_ignored "$O"
# K05. Сумма проверки в строке не совпадает с распакованной → отказ до базы, rc=1
O=$(run "${CMD/"$CSHA"/"$(printf '0%.0s' {1..64})"}")
grep -q '^REFUSED: check differs; nothing run' <<< "$O" && grep -qx 'rc=1' <<< "$O" && ok K05_check_differs || bad K05_check_differs "$O"
# K06. Неверное ожидаемое число строк → CHK08_FAILED, rc=3
O=$(run "${CMD/" -v cnt=$CNT "/" -v cnt=19 "}")
grep -q 'CHK08_FAILED: lease_seal rows 20 digest' <<< "$O" && grep -q '^ZPROBE_B10_CHK08=FAILED' <<< "$O" && grep -qx 'rc=3' <<< "$O" \
  && ok K06_wrong_count || bad K06_wrong_count "$O"
# K07/K08. Поддельный psql: код 0 без строки OK; код 3 с чужой ошибкой → FAILED, rc=3
printf '#!/bin/sh\ncat >/dev/null; echo "CHK08 target=socket:5432/bem ro=on rows=0"; exit 0\n' > "$T/fake1"
printf '#!/bin/sh\ncat >/dev/null; echo "psql:<stdin>:9: ERROR:  canceling statement due to user request"; exit 3\n' > "$T/fake2"
chmod 755 "$T/fake1" "$T/fake2"
[ "$(grep -o ' psql -X ' <<< "$CMD" | wc -l)" = 1 ] || bad K07_setup "psql call not found once"
O=$(run "${CMD/" psql -X "/" $T/fake1 -X "}")
grep -q '^ZPROBE_B10_CHK08=FAILED: last line differs' <<< "$O" && grep -qx 'rc=3' <<< "$O" && ok K07_no_ok_line || bad K07_no_ok_line "$O"
O=$(run "${CMD/" psql -X "/" $T/fake2 -X "}")
grep -q '^ZPROBE_B10_CHK08=FAILED: see the line above' <<< "$O" && grep -qx 'rc=3' <<< "$O" && ok K08_psql_error || bad K08_psql_error "$O"
# K09 (последней, меняет базу CI). Лишнее право INSERT на lease_seal → сумма строк lease_seal другая → FAILED, rc=3
"${PSQL[@]}" -c 'GRANT INSERT ON bem_control.lease_seal TO PUBLIC' > /dev/null
O=$(run "$CMD")
grep -q "CHK08_FAILED: lease_seal rows $CNT digest" <<< "$O" && grep -qx 'rc=3' <<< "$O" && ok K09_extra_grant || bad K09_extra_grant "$O"

echo "CHK08_CI fails=$fails"
[ "$fails" = 0 ] && echo CHK08_CI=PASS
[ "$fails" = 0 ]
