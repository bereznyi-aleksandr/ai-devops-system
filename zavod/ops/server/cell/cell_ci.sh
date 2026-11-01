#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/cell/cell_ci.sh
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 13:47 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 15:57 +02:00 (v0.3: пробы C33-01 — зависший запуск, C33-02 — сбой systemctl, M33-02 — остановка по аренде; v0.2: ожидание проверяет состояние заново на каждом шаге; на время раскладки 101 файла будильники zagent-start выключены)
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: проверка ячейки на машине GitHub ubuntu-24.04 (карта 3.3.8.6) после install_cell.sh и цепочки
#   базы с Z-EXT-04: учётные записи, права папок, вход root → zstarter и отказ остальным, запуск сессии по
#   пустому файлу ядра, стены клетки изнутри, «занято», плохие имена, ссылка и папка вместо файла, остановка,
#   переполнение, база недоступна, первый проход после загрузки. Каждая проверка печатает строку CELL_* .
# ВЫЗОВ: sudo -n true && bash cell_ci.sh   (от пользователя CI с sudo; база bem уже стоит)
# ОГРАНИЧЕНИЯ: только для одноразовой машины CI: создаёт учебные аренды напрямую, останавливает PostgreSQL.
set -euo pipefail
FAILS=0
ok() { echo "CELL_OK $*"; }
bad() { echo "CELL_FAIL $*"; FAILS=$((FAILS + 1)); }
pgsu() { sudo -u postgres psql -X -A -t -q -v ON_ERROR_STOP=1 -d bem -c "$1"; }
newlease() { # → 32 hex; аренда OPEN напрямую (только CI)
  local id k
  id=$(cat /proc/sys/kernel/random/uuid)
  k=$(( $(pgsu "SELECT count(*) FROM bem_control.chat_lease") + 1 ))
  pgsu "INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
        holder_session, rules_commit, code_commit, status, opened_by)
        VALUES ('$id', gen_random_uuid(), '0${k}_ci_cell', 'C0000${k}', 1, gen_random_uuid(), 'ci-cell-$k',
        repeat('a', 40), repeat('b', 40), 'OPEN', 'ci')" >/dev/null
  echo "${id//-/}"
}
state() { pgsu "SELECT coalesce((SELECT status FROM bem_control.session_start WHERE lease_id = '$1'::uuid), 'NONE')"; }
pass() { sudo systemctl start zagent-start.service; }
active() { systemctl is-active "zagent@$1.service" 2>/dev/null || true; }
is_active() { [ "$(active "$1")" = active ]; }
wait_for() { # секунды команда… — ждать, пока команда не станет успешной
  local n=$1; shift
  for _ in $(seq 1 "$n"); do if "$@"; then return 0; fi; sleep 1; done
  return 1
}
marker() { sudo find "$1" -maxdepth 1 -name "*_$2" -printf . | wc -c; }

echo "=== учётные записи"
for a in zdb zkernel zgate zgithub ztelegram zquarantine zimport zbackup zbrowser; do
  [ "$(getent passwd "$a" | cut -d: -f7)" = /usr/sbin/nologin ] || bad "$a shell"
  if sudo -l -U "$a" 2>&1 | grep -q 'is not allowed to run sudo'; then :; else bad "$a has sudo rules"; fi
done
ok "accounts nologin, no sudo"

echo "=== папки запросов"
[ "$(stat -c '%U:%G %a' /run/zavod/start)" = 'root:zkernel 1730' ] && ok "start 1730 root:zkernel" || bad "start rights"
if touch /run/zavod/start/0123456789abcdef0123456789abcdef 2>/dev/null; then bad "runner wrote into start"; else ok "runner cannot write start"; fi
if sudo -u zkernel ls /run/zavod/start >/dev/null 2>&1; then bad "zkernel lists start"; else ok "zkernel cannot list start"; fi
if sudo -u zgate touch /run/zavod/start/0123456789abcdef0123456789abcdef 2>/dev/null; then bad "zgate wrote into start"; else ok "zgate cannot write start"; fi

echo "=== вход в базу ролью zstarter"
[ "$(sudo psql -X -A -t -U zstarter -d bem -c 'select current_user')" = zstarter ] && ok "root -> zstarter" || bad "root cannot log in as zstarter"
if psql -X -U zstarter -d bem -c 'select 1' >/dev/null 2>&1; then bad "runner logged in as zstarter"; else ok "runner refused as zstarter"; fi
if sudo -u zkernel psql -X -U zstarter -d bem -c 'select 1' >/dev/null 2>&1; then bad "zkernel logged in as zstarter"; else ok "zkernel refused as zstarter"; fi

echo "=== права запуска служб"
if sudo -u zkernel systemctl start zagent@0123456789abcdef0123456789abcdef.service >/dev/null 2>&1; then bad "zkernel started a unit"
else ok "zkernel cannot start units"; fi

echo "=== запуск сессии по файлу ядра (через zagent-start.path)"
L1=$(newlease)
sudo -u zkernel touch "/run/zavod/start/$L1"
if wait_for 30 is_active "$L1"; then ok "session $L1 active"; else bad "session not started"; sudo journalctl -u zagent-start.service --no-pager | tail -20; fi
[ "$(state "$L1")" = STARTING ] && ok "lease STARTING" || bad "lease state $(state "$L1")"
[ "$(marker /var/lib/zavod/start-archive "${L1}_STARTED")" = 1 ] && ok "request archived" || bad "no archive marker"
if sudo test -e "/run/zavod/start/$L1"; then bad "request left in start"; fi
wait_for 20 sh -c "sudo journalctl -u 'zagent@$L1.service' --no-pager | grep -q 'ZAGENT_SESSION ready'" || bad "session not ready"
J=$(sudo journalctl -u "zagent@$L1.service" --no-pager)
for p in write_etc write_var_lib write_home read_shadow net_public net_db sudo; do
  echo "$J" | grep -q "ZAGENT_PROBE $p=DENIED" && ok "cage $p denied" || bad "cage $p not denied"
done
echo "$J" | grep -q 'ZAGENT_PROBE write_own=OK' && ok "cage own workdir writable" || bad "cage own workdir"
uid=$(echo "$J" | sed -n 's/.*ZAGENT_SESSION start .* uid=\([0-9]*\) .*/\1/p' | head -1)
[ -n "$uid" ] && [ "$uid" -ge 61184 ] && [ "$uid" -le 65519 ] && ok "dynamic uid $uid" || bad "uid $uid not dynamic"
[ "$(systemctl show -p RuntimeMaxUSec --value "zagent@$L1.service")" = 4h ] && ok "RuntimeMaxSec 4h" || bad "RuntimeMaxSec"
systemd-analyze security --no-pager "zagent@$L1.service" | tail -1 || true
[ "$(pgsu "SELECT bem_control.lease_mark_running('$L1'::uuid)")" = RUNNING ] && ok "marked RUNNING" || bad "mark running"

echo "=== одна сессия за раз"
L2=$(newlease)
sudo -u zkernel touch "/run/zavod/start/$L2"
pass
if sudo test -e "/run/zavod/start/$L2" && [ "$(state "$L2")" = NONE ] && [ "$(active "$L2")" != active ]; then ok "second request waits (BUSY)"
else bad "second request not held"; fi

echo "=== отказы по виду записи"
sudo -u zkernel touch /run/zavod/start/not-a-lease
sudo -u zkernel ln -s /etc/shadow /run/zavod/start/abcdefabcdefabcdefabcdefabcdefab
sudo -u zkernel mkdir /run/zavod/start/fedcbafedcbafedcbafedcbafedcbafe
pass
[ "$(marker /var/lib/zavod/start-rejected BADNAME_BAD_NAME)" -ge 1 ] && ok "bad name rejected" || bad "bad name"
[ "$(marker /var/lib/zavod/start-rejected abcdefabcdefabcdefabcdefabcdefab_NOT_REGULAR)" = 1 ] && ok "symlink rejected" || bad "symlink"
[ "$(marker /var/lib/zavod/start-rejected fedcbafedcbafedcbafedcbafedcbafe_NOT_REGULAR)" = 1 ] && ok "directory rejected" || bad "directory"
sudo test -r /etc/shadow && sudo grep -q '^root:' /etc/shadow && ok "symlink target untouched" || bad "shadow changed"

echo "=== остановка, сверка, следующий запуск"
sudo -u zkernel touch "/run/zavod/stop/$L1"
pass
[ "$(active "$L1")" != active ] && ok "session stopped" || bad "session still active"
[ "$(marker /var/lib/zavod/start-archive "${L1}_STOPPED")" = 1 ] && ok "stop archived" || bad "stop marker"
pass
[ "$(state "$L1")" = INTERRUPTED ] && ok "lease INTERRUPTED after stop" || bad "L1 state $(state "$L1")"
wait_for 30 is_active "$L2" && ok "waiting request started" || bad "L2 not started"
[ "$(pgsu "SELECT bem_control.lease_mark_running('$L2'::uuid)")" = RUNNING ] && ok "L2 marked RUNNING" || bad "L2 mark running"
sudo -u zkernel touch "/run/zavod/stop/$L2"
pass

echo "=== переполнение"
# Будильники на время раскладки выключены: иначе проход разбирает файлы по частям, пока их меньше 101.
sudo systemctl stop zagent-start.path zagent-start.timer
for i in $(seq 1 101); do sudo -u zkernel touch "/run/zavod/stop/$(printf '%032x' "$i")"; done
sudo systemctl start zagent-start.path zagent-start.timer
pass
[ "$(marker /var/lib/zavod/start-rejected OVERFLOW)" -ge 101 ] && ok "overflow: all rejected" || bad "overflow"
sudo journalctl -t zagent-start --no-pager | grep -q 'ZAVOD_ALERT stop: 101 entries' && ok "overflow alert" || bad "no alert"

echo "=== база недоступна — ничего не запускается"
L3=$(newlease)
sudo systemctl stop postgresql.service
sudo -u zkernel touch "/run/zavod/start/$L3"
pass
if [ "$(active "$L3")" != active ] && sudo test -e "/run/zavod/start/$L3"; then ok "db down: not started, request kept"; else bad "db down"; fi
sudo systemctl start postgresql.service
wait_for 30 sudo -u postgres psql -X -d bem -c 'select 1' >/dev/null 2>&1 || bad "postgres back"
pass
wait_for 30 is_active "$L3" && ok "db back: started" || bad "L3 not started"

echo "=== первый проход после загрузки (живая служба место не теряет — аудит C33-01)"
fakeboot() { echo 00000000-0000-0000-0000-000000000000 | sudo tee /var/lib/zavod/start-state/boot_id >/dev/null; }
fakeboot; pass
if [ "$(state "$L3")" = STARTING ] && is_active "$L3"; then ok "boot: live STARTING kept"; else bad "boot live: $(state "$L3")"; fi
sudo -u zkernel touch "/run/zavod/stop/$L3"; pass
fakeboot; pass
[ "$(state "$L3")" = START_FAILED ] && ok "boot: dead STARTING -> START_FAILED" || bad "boot state $(state "$L3")"

echo "=== аудит C33-01: запуск дольше 2 минут — служба останавливается, второй сеанс не стартует"
older() { pgsu "UPDATE bem_control.session_start SET reserved_at = now() - interval '3 minutes' WHERE lease_id = '$1'::uuid" >/dev/null; }
L6=$(newlease); sudo -u zkernel touch "/run/zavod/start/$L6"; pass
wait_for 30 is_active "$L6" && ok "C33-01: L6 started" || bad "C33-01: L6 not started"
older "$L6"
[ "$(pgsu "SELECT bem_control.lease_mark_running('$L6'::uuid)")" = TOO_LATE ] && ok "C33-01: late mark refused" || bad "C33-01: late mark"
[ "$(state "$L6")" = STARTING ] && ok "C33-01: TOO_LATE keeps the slot" || bad "C33-01: L6 state $(state "$L6")"
L7=$(newlease); sudo -u zkernel touch "/run/zavod/start/$L7"
pass
[ "$(active "$L6")" != active ] && ok "C33-01: overdue session stopped" || bad "C33-01: L6 still active"
[ "$(state "$L6")" = STARTING ] && ok "C33-01: slot held until service gone" || bad "C33-01: L6 state $(state "$L6")"
if [ "$(active "$L7")" != active ] && sudo test -e "/run/zavod/start/$L7"; then ok "C33-01: no second session"; else bad "C33-01: second session"; fi
sudo journalctl -t zagent-start --no-pager | grep -q "ZAVOD_ALERT start overdue $L6" && ok "C33-01: alert" || bad "C33-01: no alert"
pass
[ "$(state "$L6")" = START_FAILED ] && ok "C33-01: released after stop" || bad "C33-01: L6 state $(state "$L6")"
wait_for 30 is_active "$L7" && ok "C33-01: next lease started" || bad "C33-01: L7 not started"
sudo -u zkernel touch "/run/zavod/stop/$L7"; pass
older "$L7"; pass
[ "$(state "$L7")" = START_FAILED ] && ok "C33-01: stopped L7 released" || bad "C33-01: L7 state $(state "$L7")"

echo "=== аудит M33-02: остановка только при открытой аренде"
L8=$(newlease); sudo -u zkernel touch "/run/zavod/start/$L8"; pass
wait_for 30 is_active "$L8" && ok "M33-02: L8 started" || bad "M33-02: L8 not started"
X=$(printf '%032x' 777777)
sudo -u zkernel touch "/run/zavod/stop/$X"; pass
[ "$(marker /var/lib/zavod/start-archive "${X}_STOP_LEASE_NOT_OPEN")" = 1 ] && ok "M33-02: no lease — archived, nothing stopped" || bad "M33-02: unknown lease stop"
pgsu "UPDATE bem_control.chat_lease SET status = 'COMPLETED', closed_at = clock_timestamp(),
      completion_evidence_id = gen_random_uuid(), result_evidence_id = gen_random_uuid(),
      memory_evidence_id = gen_random_uuid(), next_evidence_id = gen_random_uuid(), report_id = gen_random_uuid()
      WHERE lease_id = '$L8'::uuid" >/dev/null
sudo -u zkernel touch "/run/zavod/stop/$L8"; pass
is_active "$L8" && ok "M33-02: closed lease — request does not stop" || bad "M33-02: closed lease stopped"
[ "$(marker /var/lib/zavod/start-archive "${L8}_STOP_LEASE_NOT_OPEN")" = 1 ] && ok "M33-02: closed lease request archived" || bad "M33-02: closed lease marker"
sudo systemctl stop "zagent@$L8.service"; older "$L8"; pass
[ "$(state "$L8")" = START_FAILED ] && ok "M33-02: L8 released" || bad "M33-02: L8 state $(state "$L8")"
L9=$(newlease); sudo -u zkernel touch "/run/zavod/start/$L9"; pass
wait_for 30 is_active "$L9" && ok "M33-02: L9 started" || bad "M33-02: L9 not started"
sudo systemctl stop postgresql.service
sudo -u zkernel touch "/run/zavod/stop/$L9"
pass || true
if is_active "$L9" && sudo test -e "/run/zavod/stop/$L9"; then ok "M33-02: db down — not stopped, request kept"; else bad "M33-02: db down stop"; fi
sudo systemctl start postgresql.service
wait_for 30 sudo -u postgres psql -X -d bem -c 'select 1' >/dev/null 2>&1 || bad "postgres back"
pass
[ "$(active "$L9")" != active ] && ok "M33-02: db back — stopped" || bad "M33-02: L9 still active"
older "$L9"; pass
[ "$(state "$L9")" = START_FAILED ] && ok "M33-02: L9 released" || bad "M33-02: L9 state $(state "$L9")"

echo "=== аудит C33-02: сбой systemctl — живая сессия не теряется, новых запусков нет"
# Подменный systemctl только для прохода zagent-start (через PATH службы): list-units падает или даёт мусор.
L4=$(newlease); sudo -u zkernel touch "/run/zavod/start/$L4"; pass
wait_for 30 is_active "$L4" && ok "C33-02: L4 started" || bad "C33-02: L4 not started"
[ "$(pgsu "SELECT bem_control.lease_mark_running('$L4'::uuid)")" = RUNNING ] && ok "C33-02: L4 RUNNING" || bad "C33-02: L4 mark running"
for mode in fail garbage; do
  sudo install -d -m 0755 /usr/local/lib/zavod-ci-fakebin
  if [ "$mode" = fail ]; then body='[ "$1" = list-units ] && exit 1'; else body='[ "$1" = list-units ] && { echo "garbage"; exit 0; }'; fi
  printf '#!/bin/sh\n%s\nexec /usr/bin/systemctl "$@"\n' "$body" | sudo tee /usr/local/lib/zavod-ci-fakebin/systemctl >/dev/null
  sudo chmod 0755 /usr/local/lib/zavod-ci-fakebin/systemctl
  sudo install -d -m 0755 /run/systemd/system/zagent-start.service.d
  printf '[Service]\nEnvironment=PATH=/usr/local/lib/zavod-ci-fakebin:/usr/sbin:/usr/bin\n' | sudo tee /run/systemd/system/zagent-start.service.d/ci-fakebin.conf >/dev/null
  sudo systemctl daemon-reload
  L5=$(newlease); sudo -u zkernel touch "/run/zavod/start/$L5"
  pass || true
  [ "$(state "$L4")" = RUNNING ] && ok "C33-02 $mode: L4 stays RUNNING" || bad "C33-02 $mode: L4 state $(state "$L4")"
  is_active "$L4" && ok "C33-02 $mode: L4 still active" || bad "C33-02 $mode: L4 not active"
  if [ "$(active "$L5")" != active ] && sudo test -e "/run/zavod/start/$L5"; then ok "C33-02 $mode: no new start, request kept"; else bad "C33-02 $mode: second start"; fi
  sudo journalctl -t zagent-start --no-pager | grep -q 'ZAVOD_ALERT systemctl list-units failed' && ok "C33-02 $mode: alert" || bad "C33-02 $mode: no alert"
  sudo mv /run/systemd/system/zagent-start.service.d/ci-fakebin.conf "/run/ci-fakebin-$mode.conf.off"
  sudo systemctl daemon-reload
  pass
  [ "$(state "$L4")" = RUNNING ] && ok "C33-02 $mode: after repair L4 RUNNING" || bad "C33-02 $mode: after repair L4 $(state "$L4")"
  [ "$(active "$L5")" != active ] && ok "C33-02 $mode: L5 waits for L4" || bad "C33-02 $mode: L5 started beside L4"
  sudo -u zkernel touch "/run/zavod/stop/$L5"; pass
done
sudo -u zkernel touch "/run/zavod/stop/$L4"; pass

echo "=== итог"
if [ "$FAILS" = 0 ]; then echo "CELL_CI=PASS"; else echo "CELL_CI=FAIL ($FAILS)"; exit 1; fi
