#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/cell/egress_ci.sh
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 23:27 +02:00 (v0.2: вход zgate в базу проверяется прямо; отказ чтения таблицы — только «permission denied»; учебный список посредника «ci example.com» — адресов платных API в коде нет, проверка утечек; замечания shellcheck)
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: проверка шага 3.3.10 на машине GitHub ubuntu-24.04 после install_cell.sh, cell_ci.sh и intake_ci.sh:
#   привратник (ПБ-5) и выход только через посредника (ПБ-3) — изнутри настоящей клетки zagent@<аренда>
#   (egress_session_probe.py вместо заглушки сессии) и снаружи: чужой процесс у привратника, каждая из двух стен
#   (nftables и IPAddressDeny) по отдельности, службы без сети, посредник, вход на сервер только по SSH, журналы.
#   Каждая проверка печатает строку EGRESS_OK или EGRESS_FAIL.
# ВЫЗОВ: sudo -n true && bash egress_ci.sh
# ОГРАНИЧЕНИЯ: только для одноразовой машины CI: создаёт учебные аренды напрямую, ставит временную замену запуска
#   для одной сессии (/run/systemd/system, исчезает с перезагрузкой), создаёт и убирает сетевое пространство ci-zin.
set -euo pipefail
FAILS=0
ok() { echo "EGRESS_OK $*"; }
bad() { echo "EGRESS_FAIL $*"; FAILS=$((FAILS + 1)); }
pgsu() { sudo -u postgres psql -X -A -t -q -v ON_ERROR_STOP=1 -d bem -c "$1"; }
K=0
newlease() { # → 32 hex; аренда OPEN напрямую (только CI)
  local id
  id=$(cat /proc/sys/kernel/random/uuid); K=$((K + 1))
  pgsu "INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
        holder_session, rules_commit, code_commit, status, opened_by)
        VALUES ('$id', gen_random_uuid(), '09_ci_egress', 'E$(printf '%05d' "$K")', 1, gen_random_uuid(), 'ci-egress-$K',
        repeat('a', 40), repeat('b', 40), 'OPEN', 'ci')" >/dev/null
  echo "${id//-/}"
}
dash() { echo "${1:0:8}-${1:8:4}-${1:12:4}-${1:16:4}-${1:20:12}"; }
is_active() { [ "$(systemctl is-active "zagent@$1.service" 2>/dev/null || true)" = active ]; }
wait_for() { local n=$1; shift; for _ in $(seq 1 "$n"); do if "$@"; then return 0; fi; sleep 1; done; return 1; }
start_wait() { for _ in $(seq 1 20); do sudo systemctl start zagent-start.service; if is_active "$1"; then return 0; fi; sleep 5; done; return 1; }
PY_TCP='import socket,sys
try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=5).close(); print("OPEN")
except OSError as e:
    print("DENIED", e.errno)'
PY_GATE='import json,socket
s=socket.socket(socket.AF_UNIX); s.settimeout(10); s.connect("/run/zavod-gate/agent.sock")
s.sendall(b"{\"v\":1}\n"); print(json.loads(s.recv(200))["result"])'

# Список посредника в поставке пуст (его заполняет оператор); для CI — один учебный адрес без оплаты.
printf '# CI only\nci example.com\n' | sudo tee /etc/zavod/proxy-allow.conf >/dev/null
sudo systemctl restart zavod-proxy.service

echo "=== службы 3.3.10 стоят и работают"
for u in zavod-nft.service zavod-gate.service zavod-proxy.service; do
  [ "$(systemctl is-active "$u")" = active ] && ok "$u active" || { bad "$u $(systemctl is-active "$u" || true)"; sudo journalctl -u "$u" --no-pager | tail -5; }
done
[ "$(stat -c '%U:%G %a' /run/zavod-gate)" = 'zgate:zgate 755' ] && ok "gate dir zgate 755" || bad "gate dir $(stat -c '%U:%G %a' /run/zavod-gate)"
[ "$(stat -c '%U %a %F' /run/zavod-gate/agent.sock)" = 'zgate 666 socket' ] && ok "gate socket" || bad "gate socket $(stat -c '%U %a %F' /run/zavod-gate/agent.sock)"
[ "$(ps -o user= -C python3 | sort -u | grep -cE '^(zgate|zproxy)$')" = 2 ] && ok "gate and proxy run as zgate, zproxy" || bad "service users: $(ps -o user=,args= -C python3)"
sudo nft list table inet zavod | tee "$RUNNER_TEMP/zavod.nft.out" >/dev/null
grep -q 'policy drop' "$RUNNER_TEMP/zavod.nft.out" && grep -q 'tcp dport 22 accept' "$RUNNER_TEMP/zavod.nft.out" \
  && ok "nft: input policy drop, ssh only" || bad "nft input chain"
sudo nft -f /etc/zavod/zavod-egress.nft && [ "$(sudo nft list tables | grep -c 'inet zavod')" = 1 ] && ok "nft: reload replaces the table" || bad "nft reload"

echo "=== 3.3.10.1 и 3.3.10.4–5 изнутри клетки сессии"
sudo systemctl stop 'zagent@*.service' || true
sudo systemctl start zagent-start.service
LP=$(newlease); LO=$(newlease)
D="/run/systemd/system/zagent@$LP.service.d"
sudo install -d -m 0755 /usr/local/lib/zavod-ci "$D"
sudo install -m 0755 zavod/ops/server/cell/egress_session_probe.py /usr/local/lib/zavod-ci/egress_session_probe.py
printf '[Service]\nExecStart=\nExecStart=/usr/bin/python3 -I /usr/local/lib/zavod-ci/egress_session_probe.py\nEnvironment=ZCI_LEASE=%s ZCI_OTHER=%s\n' \
  "$(dash "$LP")" "$(dash "$LO")" | sudo tee "$D/ci-probe.conf" >/dev/null
sudo systemctl daemon-reload
sudo touch "/run/zavod/start/$LP"
if start_wait "$LP"; then ok "probe session started"; else bad "probe session not started"; sudo journalctl -u zagent-start.service --no-pager | tail -20; fi
[ "$(pgsu "SELECT bem_control.lease_mark_running('$(dash "$LP")'::uuid)")" = RUNNING ] && ok "probe session RUNNING" || bad "mark running"
wait_for 120 sh -c "sudo journalctl -u 'zagent@$LP.service' --no-pager | grep -q EGRESS_PROBE_DONE" || bad "session probes did not finish"
J=$(sudo journalctl -u "zagent@$LP.service" --no-pager -o cat)
echo "$J" | grep EGRESS_PROBE || true
sudo journalctl -u zavod-gate.service --no-pager -o cat | tail -15 | sed "s/^/EGRESS_INFO gate: /"
want() { # имя ожидаемое — ожидаемое: точное слово или шаблон DENIED_*
  local got
  got=$(echo "$J" | sed -n "s/^EGRESS_PROBE $1=//p" | tail -1)
  # shellcheck disable=SC2254  # второй аргумент — нарочно шаблон (DENIED_*)
  case "$got" in $2) ok "$1=$got" ;; *) bad "$1=$got (want $2)" ;; esac
}
want gate_first ACCEPTED
want gate_replay NONCE_REPLAY
want gate_bad_sha SHA_MISMATCH
want gate_other_lease PEER_MISMATCH
for p in gate_dup_keys gate_unknown_kind gate_extra_arg gate_extra_field gate_not_json; do want "$p" BAD_COMMAND; done
want gate_sql_text ACCEPTED
for p in net_direct_https net_dns_local_udp net_dns_public_udp net_dns_local_tcp net_resolve_name net_db_tcp net_db_socket \
         net_dbus net_resolved_varlink; do want "$p" 'DENIED_*'; done
want proxy_allowed 200
want proxy_github 403
want proxy_ip_literal 403
want proxy_plain_get 405
want proxy_other_port 403

echo "=== база: записи привратника и правила строк"
LPD=$(dash "$LP")
[ "$(pgsu "SELECT string_agg(kind, ',' ORDER BY received_at) FROM bem_control.gate_command WHERE lease_id = '$LPD'")" = HEARTBEAT,PROGRESS ] \
  && ok "two commands stored for the probe lease" || bad "stored commands: $(pgsu "SELECT string_agg(kind, ',') FROM bem_control.gate_command WHERE lease_id = '$LPD'")"
[ "$(pgsu "SELECT args->>'text' FROM bem_control.gate_command WHERE lease_id = '$LPD' AND kind = 'PROGRESS'")" = "x'); DROP TABLE bem_control.gate_command; --" ] \
  && ok "SQL text kept as data, table in place" || bad "SQL text"
# Строгий вид проверяет сам привратник до базы; в журнал базы попадают решения базы. Чужая аренда пишется под
# номером из команды (вторая аренда), а не под номером собеседника.
LOD=$(dash "$LO")
[ "$(pgsu "SELECT bool_and(o IN (SELECT outcome FROM bem_control.gate_command_log WHERE lease_id = '$LPD'))
            FROM unnest(ARRAY['ACCEPTED', 'NONCE_REPLAY', 'SHA_MISMATCH']) o")" = t ] \
  && [ "$(pgsu "SELECT string_agg(outcome, ',') FROM bem_control.gate_command_log WHERE lease_id = '$LOD'")" = PEER_MISMATCH ] \
  && ok "gate decisions logged in the database" || bad "gate log: $(pgsu "SELECT string_agg(lease_id || ':' || outcome, ',') FROM bem_control.gate_command_log")"
TEN=$(pgsu "SELECT tenant_id FROM bem_control.chat_lease WHERE lease_id = '$LPD'")
[ "$(sudo -u zkernel psql -X -A -t -h /var/run/postgresql -U bem_kernel_rw -d bem -c "SELECT count(*) FROM bem_control.gate_command")" = 0 ] \
  && ok "RLS: kernel without tenant sees nothing" || bad "RLS: kernel without tenant sees rows"
[ "$(sudo -u zkernel psql -X -A -t -h /var/run/postgresql -U bem_kernel_rw -d bem -c "SET app.tenant_id = '$(cat /proc/sys/kernel/random/uuid)'; SELECT count(*) FROM bem_control.gate_command" | tail -1)" = 0 ] \
  && ok "RLS: other tenant sees nothing" || bad "RLS: other tenant sees rows"
[ "$(sudo -u zkernel psql -X -A -t -h /var/run/postgresql -U bem_kernel_rw -d bem -c "SET app.tenant_id = '$TEN'; SELECT count(*) FROM bem_control.gate_command" | tail -1)" = 2 ] \
  && ok "RLS: own tenant sees its 2 commands" || bad "RLS: own tenant"
r=$(sudo -u zgate psql -X -A -t -U zgate -d bem -c 'SELECT current_user' 2>&1 || true)
[ "$r" = zgate ] && ok "zgate logs in to the database as zgate" || bad "zgate login: $r"
r=$(sudo -u zgate psql -X -A -t -U zgate -d bem -c "SELECT count(*) FROM bem_control.gate_command" 2>&1 || true)
case "$r" in *'permission denied'*) ok "zgate cannot read gate_command" ;; *) bad "zgate reads gate_command: $r" ;; esac
if psql -X -U zgate -d bem -c 'select 1' >/dev/null 2>&1; then bad "runner logged in as zgate"; else ok "runner refused as zgate"; fi
sudo journalctl -u zavod-gate.service --no-pager -o cat | grep -q "\"peer_lease\": \"$LPD\"" && ok "gate journal names the peer lease" || bad "gate journal"
if sudo journalctl -u zavod-gate.service --no-pager -o cat | grep -q 'DROP TABLE'; then bad "gate journal holds command text"; else ok "gate journal holds no command text"; fi

echo "=== привратник: чужие процессы"
[ "$(python3 -I -c "$PY_GATE")" = NOT_A_SESSION ] && ok "runner -> NOT_A_SESSION" || bad "runner at gate"
[ "$(sudo systemd-run --quiet --wait --pipe -p DynamicUser=yes -p Slice=zagent.slice /usr/bin/python3 -I -c "$PY_GATE")" = NOT_A_SESSION ] \
  && ok "dynamic user in zagent.slice, not zagent@ -> NOT_A_SESSION" || bad "foreign unit at gate"

echo "=== 3.3.10.5 две стены по отдельности (ПБ-3)"
[ "$(python3 -I -c "$PY_TCP" 1.1.1.1 443)" = OPEN ] && ok "control: runner reaches 1.1.1.1:443" || echo "EGRESS_INFO runner has no internet: wall probes below prove nothing alone"
r=$(sudo systemd-run --quiet --wait --pipe -p DynamicUser=yes /usr/bin/python3 -I -c "$PY_TCP" 1.1.1.1 443)
case "$r" in DENIED*) ok "nft alone: dynamic user without IPAddressDeny -> $r" ;; *) bad "nft alone: $r" ;; esac
r=$(sudo systemd-run --quiet --wait --pipe -p DynamicUser=yes /usr/bin/python3 -I -c "$PY_TCP" 127.0.0.53 53)
case "$r" in DENIED*) ok "nft alone: dynamic user to local DNS -> $r" ;; *) bad "nft alone local DNS: $r" ;; esac
r=$(sudo systemd-run --quiet --wait --pipe -p User="$(id -un)" -p IPAddressDeny=any -p IPAddressAllow=127.0.0.2 /usr/bin/python3 -I -c "$PY_TCP" 1.1.1.1 443)
case "$r" in DENIED*) ok "IPAddressDeny alone: runner uid (no nft rule) -> $r" ;; *) bad "IPAddressDeny alone: $r" ;; esac
for a in zgate zdb zquarantine zimport zbrowser; do
  r=$(sudo -u "$a" python3 -I -c "$PY_TCP" 1.1.1.1 443)
  case "$r" in DENIED*) ok "$a has no network ($r)" ;; *) bad "$a network: $r" ;; esac
done
r=$(sudo -u zproxy python3 -I -c "$PY_TCP" 1.1.1.1 443); [ "$r" = OPEN ] && ok "zproxy reaches :443" || echo "EGRESS_INFO zproxy :443 $r"
r=$(sudo -u zproxy python3 -I -c "$PY_TCP" 1.1.1.1 80); case "$r" in DENIED*) ok "zproxy cannot reach :80 ($r)" ;; *) bad "zproxy :80 $r" ;; esac
r=$(sudo -u zproxy python3 -I -c "$PY_TCP" 8.8.8.8 53); case "$r" in DENIED*) ok "zproxy cannot use public DNS ($r)" ;; *) bad "zproxy public DNS $r" ;; esac

echo "=== посредник: журнал каждого соединения"
PJ=$(sudo journalctl -u zavod-proxy.service --no-pager -o cat)
for d in '"decision": "ALLOWED".*"target": "example.com:443"' '"decision": "NOT_ALLOWED".*"target": "github.com:443"' \
         '"decision": "NOT_ALLOWED".*"target": "1.1.1.1:443"' '"decision": "METHOD_REFUSED"'; do
  echo "$PJ" | grep -qE "$d" && ok "proxy log: $d" || bad "proxy log missing: $d"
done
PU=$(echo "$PJ" | grep '"target": "github.com:443"' | sed -n 's/.*"uid": \([0-9]*\).*/\1/p' | tail -1)
[ -n "$PU" ] && [ "$PU" -ge 61184 ] && [ "$PU" -le 65519 ] && ok "proxy log names the session uid $PU" || bad "proxy log uid '$PU'"

echo "=== вход на сервер: только SSH (сетевое пространство ci-zin)"
sudo ip netns add ci-zin
sudo ip link add ci-zh type veth peer name ci-zp
sudo ip link set ci-zp netns ci-zin
sudo ip addr add 10.231.0.1/30 dev ci-zh; sudo ip link set ci-zh up
sudo ip netns exec ci-zin ip addr add 10.231.0.2/30 dev ci-zp; sudo ip netns exec ci-zin ip link set ci-zp up
python3 -I -c 'import socket,time
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("0.0.0.0", 8099)); s.listen(4); time.sleep(40)' &
LST=$!
sleep 1
r=$(sudo ip netns exec ci-zin python3 -I -c "$PY_TCP" 10.231.0.1 8099)
case "$r" in DENIED*) ok "inbound to a non-SSH port refused ($r)" ;; *) bad "inbound :8099 $r" ;; esac
if ss -ltn | grep -qE '[:.]22[[:space:]]'; then
  r=$(sudo ip netns exec ci-zin python3 -I -c "$PY_TCP" 10.231.0.1 22); [ "$r" = OPEN ] && ok "inbound SSH :22 open" || bad "inbound SSH $r"
else
  echo "EGRESS_INFO sshd not listening on this runner: SSH door checked by rule text only"
fi
kill "$LST" 2>/dev/null || true
sudo ip link set ci-zh down
sudo ip netns del ci-zin

sudo systemctl stop "zagent@$LP.service" || true
sudo mv "$D/ci-probe.conf" "$RUNNER_TEMP/ci-probe.conf.used"
sudo systemctl daemon-reload

echo "=== итог"
if [ "$FAILS" = 0 ]; then echo "EGRESS_CI=PASS"; else echo "EGRESS_CI=FAIL ($FAILS)"; exit 1; fi
