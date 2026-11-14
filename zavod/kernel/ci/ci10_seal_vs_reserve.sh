#!/usr/bin/env bash
# ДОКУМЕНТ: ci/ci10_seal_vs_reserve.sh
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-15 00:20 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проверка CI 10 проекта B10 v0.18 (раздел 6): печать аренды (lease_seal_unstarted) и бронь запуска
#   (lease_reserve_start) одновременно в двух сеансах — ровно одно из SEALED_NOW и RESERVED, без взаимной
#   блокировки. Два прохода, порядок задан явно (без расчёта на удачу):
#   A) сеанс 1 печатает и держит транзакцию; сеанс 2 зовёт бронь и ЖДЁТ замок (видно в pg_stat_activity);
#      COMMIT сеанса 1 → бронь отвечает ALREADY_STARTED;
#   B) сеанс 1 бронирует и держит транзакцию; сеанс 2 зовёт печать и ЖДЁТ; COMMIT → печать REFUSED_HAS_SESSION.
#   После каждого прохода у аренды ровно одна строка session_start; строки lease_seal — только в проходе A.
# ОГРАНИЧЕНИЯ: всё идёт в одноразовой копии базы (CREATE DATABASE … TEMPLATE bem), копия в конце убирается;
#   база bem не меняется. Каждое ожидание — не дольше 20 с (lock_timeout и опрос).
# ВЫЗОВ: bash ci/ci10_seal_vs_reserve.sh <рабочая папка>; итог — строка ZAVOD_CI10_SEAL_VS_RESERVE=PASS, код 0.
set -u
WORK=$1
DB=bem_ci10
mkdir -p "$WORK"
cd "$WORK" || exit 1
q() { psql -X -U postgres -d "$1" -Atc "$2"; }
die() { echo "CI10_FAIL $1"; q postgres "DROP DATABASE IF EXISTS $DB WITH (FORCE)" >/dev/null 2>&1; exit 1; }

q postgres "DROP DATABASE IF EXISTS $DB WITH (FORCE)" >/dev/null || die drop_old
q postgres "CREATE DATABASE $DB TEMPLATE bem" >/dev/null || die create_copy

L1=a10a10a1-aaaa-4aaa-8aaa-aaaaaaaaa010
L2=b10b10b1-bbbb-4bbb-8bbb-bbbbbbbbb010
P=$(printf '1%.0s' $(seq 64))
q $DB "INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
       holder_session, rules_commit, code_commit, status, opened_by)
       VALUES ('$L1', gen_random_uuid(), '01_install_probe', 'Z00101', 1, gen_random_uuid(), 'zprobe-pb1ci10',
               repeat('a', 40), repeat('b', 40), 'OPEN', 'zprobe-run'),
              ('$L2', gen_random_uuid(), '01_install_probe', 'Z00102', 1, gen_random_uuid(), 'zprobe-pb1ci11',
               repeat('a', 40), repeat('b', 40), 'OPEN', 'zprobe-run')" >/dev/null || die leases
[ "$(q $DB "SELECT count(*) FROM bem_control.session_start WHERE status IN ('STARTING','RUNNING')")" = 0 ] || die busy_before

# wait_for <файл> <строка>: строка появилась в файле за ≤20 с.
wait_for() { for _ in $(seq 100); do grep -qx "$2" "$1" 2>/dev/null && return 0; sleep 0.2; done; return 1; }
# waiting <часть запроса>: есть сеанс, который ждёт замок на запросе с этой частью (≤20 с).
waiting() {
  for _ in $(seq 100); do
    [ "$(q $DB "SELECT count(*) FROM pg_stat_activity WHERE datname = '$DB' AND wait_event_type = 'Lock'
                AND query LIKE '%$1%' AND pid <> pg_backend_pid()")" = 1 ] && return 0
    sleep 0.2
  done
  return 1
}

# run_pass <имя> <запрос сеанса 1> <ответ 1> <запрос сеанса 2> <часть запроса 2> <ответ 2>
run_pass() {
  local n=$1 s1=$2 a1=$3 s2=$4 part=$5 a2=$6
  rm -f "f_$n" "o1_$n" "o2_$n"
  mkfifo "f_$n" || die "fifo_$n"
  psql -X -q -At -v ON_ERROR_STOP=1 -U postgres -d $DB < "f_$n" > "o1_$n" 2>&1 &
  local p1=$!
  exec 3>"f_$n"
  printf "BEGIN;\nSELECT 'S1=' || %s;\n" "$s1" >&3
  wait_for "o1_$n" "S1=$a1" || { exec 3>&-; kill $p1 2>/dev/null; die "${n}_s1:$(tr '\n' ' ' < "o1_$n")"; }
  psql -X -q -At -v ON_ERROR_STOP=1 -U postgres -d $DB \
       -c "SET lock_timeout = '20s'" -c "SELECT 'S2=' || $s2" > "o2_$n" 2>&1 &
  local p2=$!
  waiting "$part" || { exec 3>&-; kill $p1 $p2 2>/dev/null; die "${n}_s2_not_waiting:$(tr '\n' ' ' < "o2_$n")"; }
  [ -s "o2_$n" ] && { exec 3>&-; kill $p1 $p2 2>/dev/null; die "${n}_s2_answered_early"; }
  printf "COMMIT;\n" >&3
  exec 3>&-
  wait $p1 || die "${n}_s1_rc"
  wait $p2 || die "${n}_s2_rc:$(tr '\n' ' ' < "o2_$n")"
  grep -qx "S2=$a2" "o2_$n" || die "${n}_s2_answer:$(tr '\n' ' ' < "o2_$n")"
  grep -qi deadlock "o1_$n" "o2_$n" && die "${n}_deadlock"
  echo "CI10_PASS_$n s1=$a1 s2=$a2"
}

run_pass A "bem_control.lease_seal_unstarted('pb1ci10', '$L1', '$P')" SEALED_NOW \
         "bem_control.lease_reserve_start('$L1')" "lease_reserve_start('$L1')" ALREADY_STARTED
run_pass B "bem_control.lease_reserve_start('$L2')" RESERVED \
         "bem_control.lease_seal_unstarted('pb1ci11', '$L2', '$P')" "lease_seal_unstarted('pb1ci11'" REFUSED_HAS_SESSION

[ "$(q $DB "SELECT status FROM bem_control.session_start WHERE lease_id = '$L1'")" = START_FAILED ] || die a_start_row
[ "$(q $DB "SELECT count(*) FROM bem_control.lease_seal WHERE lease_id = '$L1'")" = 1 ] || die a_seal_row
[ "$(q $DB "SELECT string_agg(outcome, ',' ORDER BY at, outcome) FROM bem_control.session_start_log
            WHERE lease_id = '$L1'")" = START_FAILED,ALREADY_STARTED ] || die a_log
[ "$(q $DB "SELECT status FROM bem_control.session_start WHERE lease_id = '$L2'")" = STARTING ] || die b_start_row
[ "$(q $DB "SELECT count(*) FROM bem_control.lease_seal WHERE lease_id = '$L2'")" = 0 ] || die b_seal_row
[ "$(q $DB "SELECT string_agg(outcome, ',') FROM bem_control.session_start_log WHERE lease_id = '$L2'")" = RESERVED ] \
  || die b_log

q postgres "DROP DATABASE $DB WITH (FORCE)" >/dev/null || { echo "CI10_FAIL drop_copy"; exit 1; }
echo "ZAVOD_CI10_SEAL_VS_RESERVE=PASS"
