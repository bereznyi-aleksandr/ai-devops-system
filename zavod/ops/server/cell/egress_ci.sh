#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/cell/egress_ci.sh
# ВЕРСИЯ: v0.5  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-02 03:33 +02:00 (v0.5: аудит M3310-R7-03 — запросы к базе только постоянным текстом, значения переменными psql (pgv, pgk); v0.4: аудит M3310-R2-02 — посредник отказывает службе с динамическим uid вне zagent@ и в zagent.slice без zagent@; журнал посредника называет аренду сессии; v0.3: аудит M3310-R1B-01 — команда после выхода соединившегося процесса; M3310-R1B-03 — службы без сети не достают посредника, петлю IPv4/IPv6 и DNS по UDP, посредник отказывает не-сессии; M3310-R1B-04 — GitHub по окончанию имени в списке и в запросе; v0.2: вход zgate в базу проверяется прямо; отказ чтения таблицы — только «permission denied»; учебный список посредника «ci example.com» — адресов платных API в коде нет, проверка утечек; замечания shellcheck)
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
# Запрос к базе — только постоянный текст: значения идут переменными psql (-v имя=значение), в тексте
# запроса — :'имя' (psql сам берёт значение в кавычки). Текст запроса из подстановок оболочки не собирается
# (карта 3.3.10.2, аудит M3310-R7-03); проверка сборки sql_concat_scan.py читает и этот файл.
pgv() { # $1 — постоянный текст запроса, дальше — имя=значение
  local q=$1 a v=(); shift
  for a in "$@"; do v+=(-v "$a"); done
  printf '%s\n' "$q" | sudo -u postgres psql -X -A -t -q -v ON_ERROR_STOP=1 -d bem "${v[@]}"
}
pgk() { # то же от имени ядра (zkernel → bem_kernel_rw)
  local q=$1 a v=(); shift
  for a in "$@"; do v+=(-v "$a"); done
  printf '%s\n' "$q" | sudo -u zkernel psql -X -A -t -q -v ON_ERROR_STOP=1 -h /var/run/postgresql -U bem_kernel_rw -d bem "${v[@]}"
}
K=0
newlease() { # → 32 hex; аренда OPEN напрямую (только CI)
  local id
  id=$(cat /proc/sys/kernel/random/uuid); K=$((K + 1))
  pgv "INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
        holder_session, rules_commit, code_commit, status, opened_by)
        VALUES (:'id', gen_random_uuid(), '09_ci_egress', :'chat', 1, gen_random_uuid(), :'holder',
        repeat('a', 40), repeat('b', 40), 'OPEN', 'ci')" "id=$id" "chat=E$(printf '%05d' "$K")" "holder=ci-egress-$K" >/dev/null
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
PY_DNS='import os,socket,sys
q=os.urandom(2)+b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01"
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(3)
try:
    s.connect((sys.argv[1],53)); s.send(q); s.recv(512); print("ANSWER")
except socket.timeout:
    print("TIMEOUT")
except OSError as e:
    print("DENIED", e.errno)'
PY_PROXY='import socket
try:
    s=socket.create_connection(("127.0.0.2",3128),timeout=10); s.sendall(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
    d=s.recv(200); print(d.split(b" ",2)[1].decode() if d.startswith(b"HTTP/1.") else "BAD_ANSWER")
except OSError as e:
    print("DENIED", e.errno)'
PY_LISTEN='import socket,threading
def serve(fam,host):
    s=socket.socket(fam); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind((host,18443)); s.listen(64)
    while True: s.accept()[0].close()
threading.Thread(target=serve,args=(socket.AF_INET6,"::1"),daemon=True).start()
serve(socket.AF_INET,"127.0.0.1")'
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
[ "$(pgv "SELECT bem_control.lease_mark_running(:'l'::uuid)" "l=$(dash "$LP")")" = RUNNING ] && ok "probe session RUNNING" || bad "mark running"
wait_for 120 sh -c 'sudo journalctl -u "zagent@$1.service" --no-pager | grep -q EGRESS_PROBE_DONE' sh "$LP" || bad "session probes did not finish"
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
want gate_first_exited NOT_A_SESSION
want gate_sql_text ACCEPTED
for p in net_direct_https net_dns_local_udp net_dns_public_udp net_dns_local_tcp net_resolve_name net_db_tcp net_db_socket \
         net_dbus net_resolved_varlink net_ipv6_direct net_ipv6_loopback; do want "$p" 'DENIED_*'; done
want proxy_allowed 200
want proxy_github 403
want proxy_github_api 403
want proxy_github_raw 403
want proxy_ip_literal 403
want proxy_plain_get 405
want proxy_other_port 403

echo "=== база: записи привратника и правила строк"
LPD=$(dash "$LP")
[ "$(pgv "SELECT string_agg(kind, ',' ORDER BY received_at) FROM bem_control.gate_command WHERE lease_id = :'l'" "l=$LPD")" = HEARTBEAT,PROGRESS ] \
  && ok "two commands stored for the probe lease" || bad "stored commands: $(pgv "SELECT string_agg(kind, ',') FROM bem_control.gate_command WHERE lease_id = :'l'" "l=$LPD")"
[ "$(pgv "SELECT args->>'text' FROM bem_control.gate_command WHERE lease_id = :'l' AND kind = 'PROGRESS'" "l=$LPD")" = "x'); DROP TABLE bem_control.gate_command; --" ] \
  && ok "SQL text kept as data, table in place" || bad "SQL text"
# Строгий вид проверяет сам привратник до базы; в журнал базы попадают решения базы. Чужая аренда пишется под
# номером из команды (вторая аренда), а не под номером собеседника.
LOD=$(dash "$LO")
[ "$(pgv "SELECT bool_and(o IN (SELECT outcome FROM bem_control.gate_command_log WHERE lease_id = :'l'))
            FROM unnest(ARRAY['ACCEPTED', 'NONCE_REPLAY', 'SHA_MISMATCH']) o" "l=$LPD")" = t ] \
  && [ "$(pgv "SELECT string_agg(outcome, ',') FROM bem_control.gate_command_log WHERE lease_id = :'l'" "l=$LOD")" = PEER_MISMATCH ] \
  && ok "gate decisions logged in the database" || bad "gate log: $(pgv "SELECT string_agg(lease_id || ':' || outcome, ',') FROM bem_control.gate_command_log")"
TEN=$(pgv "SELECT tenant_id FROM bem_control.chat_lease WHERE lease_id = :'l'" "l=$LPD")
[ "$(pgk "SELECT count(*) FROM bem_control.gate_command")" = 0 ] \
  && ok "RLS: kernel without tenant sees nothing" || bad "RLS: kernel without tenant sees rows"
[ "$(pgk "SET app.tenant_id = :'t'; SELECT count(*) FROM bem_control.gate_command" "t=$(cat /proc/sys/kernel/random/uuid)" | tail -1)" = 0 ] \
  && ok "RLS: other tenant sees nothing" || bad "RLS: other tenant sees rows"
[ "$(pgk "SET app.tenant_id = :'t'; SELECT count(*) FROM bem_control.gate_command" "t=$TEN" | tail -1)" = 2 ] \
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
r=$(sudo -u zproxy python3 -I -c "$PY_DNS" 127.0.0.53); [ "$r" = ANSWER ] && ok "zproxy uses local DNS" || echo "EGRESS_INFO zproxy local DNS $r"

echo "=== M3310-R1B-03: порядок правил — службы без сети и сессии: посредник, петля IPv4/IPv6, DNS по UDP"
python3 -I -c "$PY_LISTEN" & LISTEN_PID=$!
sleep 1
for h in 127.0.0.1 ::1; do
  [ "$(python3 -I -c "$PY_TCP" "$h" 18443)" = OPEN ] && ok "control: runner reaches $h:18443" || bad "control listener $h:18443 not reachable"
  r=$(sudo systemd-run --quiet --wait --pipe -p DynamicUser=yes /usr/bin/python3 -I -c "$PY_TCP" "$h" 18443)
  case "$r" in DENIED*) ok "nft alone: dynamic user to $h:18443 -> $r" ;; *) bad "nft alone: dynamic user to $h:18443 $r" ;; esac
done
[ "$(python3 -I -c "$PY_DNS" 127.0.0.53)" = ANSWER ] && ok "control: runner gets a DNS answer over UDP" || echo "EGRESS_INFO runner local DNS: UDP probes below prove nothing alone"
r=$(sudo systemd-run --quiet --wait --pipe -p DynamicUser=yes /usr/bin/python3 -I -c "$PY_DNS" 127.0.0.53)
[ "$r" != ANSWER ] && ok "nft alone: dynamic user DNS over UDP -> $r" || bad "nft alone: dynamic user DNS over UDP answered"
for a in zgate zdb zquarantine zimport zbrowser; do
  r=$(sudo -u "$a" python3 -I -c "$PY_TCP" 127.0.0.2 3128)
  case "$r" in DENIED*) ok "$a cannot reach the proxy ($r)" ;; *) bad "$a reaches the proxy: $r" ;; esac
  for h in 127.0.0.1 ::1; do
    r=$(sudo -u "$a" python3 -I -c "$PY_TCP" "$h" 18443)
    case "$r" in DENIED*) ok "$a cannot reach $h:18443 ($r)" ;; *) bad "$a reaches $h:18443: $r" ;; esac
  done
  r=$(sudo -u "$a" python3 -I -c "$PY_DNS" 127.0.0.53)
  [ "$r" != ANSWER ] && ok "$a has no DNS over UDP ($r)" || bad "$a DNS over UDP answered"
done
kill "$LISTEN_PID"
r=$(python3 -I -c "$PY_PROXY")
[ "$r" = 403 ] && ok "proxy refuses a non-session uid (runner) -> 403" || bad "proxy to runner: $r"
# M3310-R2-02: динамический uid из диапазона сессий, но не служба zagent@<аренда> — тоже отказ (фильтр его пропускает).
r=$(sudo systemd-run --quiet --wait --pipe -p DynamicUser=yes /usr/bin/python3 -I -c "$PY_PROXY")
[ "$r" = 403 ] && ok "proxy refuses a dynamic user outside zagent@ -> 403" || bad "proxy to a foreign dynamic user: $r"
r=$(sudo systemd-run --quiet --wait --pipe -p DynamicUser=yes -p Slice=zagent.slice /usr/bin/python3 -I -c "$PY_PROXY")
[ "$r" = 403 ] && ok "proxy refuses a dynamic user in zagent.slice, not zagent@ -> 403" || bad "proxy to zagent.slice non-session: $r"

echo "=== M3310-R1B-04: GitHub по окончанию имени — список с поддоменом не принимается"
P=/usr/local/lib/zavod/zavod-proxy
for n in github.com api.github.com raw.githubusercontent.com objects.githubusercontent.com x.github.io ghcr.io codeload.github.com; do
  printf 'ci %s\n' "$n" > "$RUNNER_TEMP/allow_gh.conf"
  if python3 -I "$P" --check-allow "$RUNNER_TEMP/allow_gh.conf" 2>/dev/null; then bad "allow list with $n accepted"; else ok "allow list with $n refused"; fi
done
for n in example.com notgithub.com github.com.example.org; do
  printf 'ci %s\n' "$n" > "$RUNNER_TEMP/allow_gh.conf"
  if python3 -I "$P" --check-allow "$RUNNER_TEMP/allow_gh.conf" >/dev/null; then ok "allow list with $n accepted"; else bad "allow list with $n refused"; fi
done

echo "=== посредник: журнал каждого соединения"
PJ=$(sudo journalctl -u zavod-proxy.service --no-pager -o cat)
for d in '"decision": "ALLOWED".*"target": "example.com:443"' '"decision": "NOT_ALLOWED".*"target": "github.com:443"' \
         '"decision": "NOT_ALLOWED".*"target": "1.1.1.1:443"' '"decision": "METHOD_REFUSED"' \
         '"decision": "NOT_ALLOWED".*"target": "api.github.com:443"' '"decision": "NOT_A_SESSION"'; do
  echo "$PJ" | grep -qE "$d" && ok "proxy log: $d" || bad "proxy log missing: $d"
done
echo "$PJ" | grep -qE "\"decision\": \"ALLOWED\".*\"lease\": \"$LP\".*\"target\": \"example.com:443\"" \
  && ok "proxy log names the session lease" || bad "proxy log has no session lease for the allowed tunnel"
[ "$(echo "$PJ" | grep -c '"decision": "NOT_A_SESSION"')" -ge 3 ] && ok "proxy log: three NOT_A_SESSION refusals" \
  || bad "proxy log NOT_A_SESSION count $(echo "$PJ" | grep -c '"decision": "NOT_A_SESSION"')"
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
