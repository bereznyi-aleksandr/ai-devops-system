#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_unit_ci.sh
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-14 09:00 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 09:00 +02:00
# ИСПОЛНИТЕЛЬ: Claude (чат «Завод 3.5.5 ПБ-1 · 05», c241e855-e4a2-48da-a99f-e35a33809cf1)
# НАЗНАЧЕНИЕ: проверка службы zprobe-run@.service в НАСТОЯЩЕМ systemd (машина CI, только CI). Проба pb1trial1 на
#   zavod-1 (2026-11-14) показала два дефекта, которые обычные тесты не ловили: D1 — строка с «+» не имела сети
#   хоста; D2 — UMask=0077 срезал права файлов прогонщика до 0600, и запись журнала (zprobe) их не читала.
#   Служба для проверки собирается из настоящего файла службы: все строки [Service] берутся как есть, меняются
#   только команды ExecStart/ExecStopPost (на проверочные) и убираются зависимости от zavod-proxy.
#   Строка «+» (как прогонщик): put_new() НАСТОЯЩЕГО zprobe_runner.py пишет evidence.json, соединение TCP
#   с слушателем хоста 127.0.0.1, разрешение имени github.com. Строка «-+» (как уборка): put_new() пишет cleanup.json.
#   Строка без «+» (как журнал, от zprobe): читает оба файла; сокет AF_INET должен быть запрещён.
# ВЫЗОВ: sudo bash zprobe_unit_ci.sh <папка zavod/ops/server/probes>
# ОГРАНИЧЕНИЯ: только для одноразовой машины CI: создаёт пользователя zprobe, папки /run/zprobe и /var/lib/zavod.
set -euo pipefail
SRC=$(cd "$1" && pwd)
S=ciunit1
LIB=/usr/local/lib/zavod/probes
id zprobe >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin zprobe
install -d -m 0755 "$LIB" /run/zprobe /var/lib/zavod
install -d -m 0750 -o zprobe -g zprobe /var/lib/zavod/probes
install -m 0644 "$SRC/zprobe_runner.py" "$SRC/zprobe_rules.py" "$LIB/"
install -d -m 0750 -o root -g zprobe /run/zprobe/$S
printf '{}' > /run/zprobe/$S/request.json

cat > "$LIB/ci_plus.py" <<'EOF'
import grp, json, os, socket, sys
sys.path.insert(0, '/usr/local/lib/zavod/probes')
import zprobe_runner as N
what, s, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
gid = grp.getgrnam('zprobe').gr_gid
d = os.path.join('/run/zprobe', s)
res = {'uid': os.getuid(), 'umask': None}
m = os.umask(0); os.umask(m); res['umask'] = oct(m)
if what == 'run':
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=5):
            res['tcp_host'] = 'OK'
    except OSError as e:
        res['tcp_host'] = type(e).__name__ + ':' + str(e)
    try:
        res['dns'] = 'OK' if socket.getaddrinfo('github.com', 443, type=socket.SOCK_STREAM) else 'EMPTY'
    except OSError as e:
        res['dns'] = type(e).__name__ + ':' + str(e)
    N.put_new(os.path.join(d, 'evidence.json'), json.dumps(res), 0o640, gid)
else:
    N.put_new(os.path.join(d, 'cleanup.json'), json.dumps(res), 0o640, gid)
EOF

cat > "$LIB/ci_commit.py" <<'EOF'
import json, os, socket, sys
s = sys.argv[1]
res = {'uid': os.getuid()}
for n in ('evidence', 'cleanup'):
    try:
        with open(os.path.join('/run/zprobe', s, n + '.json'), encoding='utf-8') as f:
            res[n] = json.load(f)
    except OSError as e:
        res[n] = 'UNREADABLE:' + type(e).__name__
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM).close()
    res['af_inet'] = 'ALLOWED'
except OSError as e:
    res['af_inet'] = 'DENIED:' + type(e).__name__
with open('/var/lib/zavod/probes/ci_commit.json', 'x', encoding='utf-8') as f:
    json.dump(res, f)
EOF

# слушатель хоста: виден строке «+» только если у неё сеть хоста
python3 -I -c "import socket,time; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('127.0.0.1', 47811)); s.listen(5); time.sleep(120)" &
LPID=$!
sleep 1

UNIT_IN="$SRC/zprobe-run@.service"
UNIT=/run/systemd/system/zprobe-ci@.service
{
  echo '[Unit]'
  echo 'Description=zprobe unit CI check %i'
  echo 'ConditionPathExists=/run/zprobe/%i/request.json'
  echo '[Service]'
  sed -n '/^\[Service\]/,$p' "$UNIT_IN" | sed '1d' | grep -vE '^(ExecStart|ExecStopPost)='
  echo "ExecStart=+/usr/bin/python3 -I $LIB/ci_plus.py run %i 47811"
  echo "ExecStopPost=-+/usr/bin/python3 -I $LIB/ci_plus.py cleanup %i 47811"
  echo "ExecStopPost=/usr/bin/python3 -I $LIB/ci_commit.py %i"
} > "$UNIT"
echo '--- unit under test'; cat "$UNIT"
grep -q '^UMask=0077$' "$UNIT"
grep -q '^RestrictAddressFamilies=AF_UNIX$' "$UNIT"
grep -q '^User=zprobe$' "$UNIT"
systemctl daemon-reload
rc=0; systemctl start zprobe-ci@$S.service || rc=$?
kill "$LPID" 2>/dev/null || true
echo "start_rc=$rc"
journalctl -u zprobe-ci@$S.service --no-pager -o cat | tail -n 20
ls -la /run/zprobe/$S
echo '--- evidence'; cat /run/zprobe/$S/evidence.json; echo
echo '--- commit'; cat /var/lib/zavod/probes/ci_commit.json; echo

fail=0
chk() { if [ "$2" = "$3" ]; then echo "OK $1"; else echo "BAD $1: '$2' != '$3'"; fail=1; fi; }
chk start_rc "$rc" 0
for f in evidence cleanup; do
  chk "$f.mode" "$(stat -c '%a %U %G' /run/zprobe/$S/$f.json)" '640 root zprobe'
done
J=/var/lib/zavod/probes/ci_commit.json
chk evidence.tcp_host "$(python3 -I -c "import json;print(json.load(open('$J'))['evidence']['tcp_host'])")" OK
chk evidence.dns "$(python3 -I -c "import json;print(json.load(open('$J'))['evidence']['dns'])")" OK
chk evidence.umask "$(python3 -I -c "import json;print(json.load(open('$J'))['evidence']['umask'])")" 0o77
chk cleanup.readable "$(python3 -I -c "import json;print(type(json.load(open('$J'))['cleanup']).__name__)")" dict
chk commit.uid "$(python3 -I -c "import json;print(json.load(open('$J'))['uid'])")" "$(id -u zprobe)"
chk commit.af_inet "$(python3 -I -c "import json;print(json.load(open('$J'))['af_inet'].split(':')[0])")" DENIED
[ "$fail" = 0 ] && echo ZPROBE_UNIT_CI_OK || { echo ZPROBE_UNIT_CI_FAIL; exit 1; }
