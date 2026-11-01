#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/cell/cell_ci.sh
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 13:47 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 13:47 +02:00
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
if wait_for 30 test "$(active "$L1")" = active; then ok "session $L1 active"; else bad "session not started"; sudo journalctl -u zagent-start.service --no-pager | tail -20; fi
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
wait_for 30 test "$(active "$L2")" = active && ok "waiting request started" || bad "L2 not started"
[ "$(pgsu "SELECT bem_control.lease_mark_running('$L2'::uuid)")" = RUNNING ] && ok "L2 marked RUNNING" || bad "L2 mark running"
sudo -u zkernel touch "/run/zavod/stop/$L2"
pass

echo "=== переполнение"
for i in $(seq 1 101); do sudo -u zkernel touch "/run/zavod/stop/$(printf '%032x' "$i")"; done
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
wait_for 30 test "$(active "$L3")" = active && ok "db back: started" || bad "L3 not started"

echo "=== первый проход после загрузки"
echo 00000000-0000-0000-0000-000000000000 | sudo tee /var/lib/zavod/start-state/boot_id >/dev/null
pass
[ "$(state "$L3")" = START_FAILED ] && ok "boot: STARTING -> START_FAILED" || bad "boot state $(state "$L3")"
sudo -u zkernel touch "/run/zavod/stop/$L3"
pass

echo "=== итог"
if [ "$FAILS" = 0 ]; then echo "CELL_CI=PASS"; else echo "CELL_CI=FAIL ($FAILS)"; exit 1; fi
