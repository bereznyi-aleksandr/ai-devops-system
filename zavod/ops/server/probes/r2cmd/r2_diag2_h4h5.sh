# ДОКУМЕНТ: r2_diag2_h4h5.sh (второй разбор H4/H5 только чтением: перезапуск journald и 6 чужих упоминаний аренды)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-17 06:26 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-17 06:26 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель).
# НАЗНАЧЕНИЕ: разбор 1 (17.11 06:21) показал: H4 — journald запущен через 15,7 ч после T0 (~15.11 08:28 по Киеву);
#   H5 — 6 записей журнала с номером аренды вне службы пробы, все session-1514.scope|runuser|runuser. Этот скрипт
#   печатает: точное время запуска journald; записи systemd/apt/dpkg/unattended-upgrades за 3 мин до и 30 с после;
#   строки /var/log/apt/history.log этого дня с systemd; 6 записей «чужих упоминаний» (время, сообщение, командная
#   строка). Номер аренды заменяется на LID. Ничего не пишет: python3 -I -B, journalctl и чтение файла.
# ЗАПУСК: только через транспорт mk_r2_cmd.py (env -i, PATH=/usr/sbin:/usr/bin), от root. Вывод ≤ 20 строк.
set -u
[ "$(/usr/bin/id -u)" = 0 ] || { echo 'DIAG2=REFUSED not_root'; exit 2; }
cd /tmp || exit 2
export PGOPTIONS='-c default_transaction_read_only=on'
exec /usr/bin/python3 -I -B -c '
import sys, json, time, datetime
sys.path.insert(0, "/usr/local/lib/zavod/probes-b10")
import zprobe_r2 as R, zprobe_checks as C
lid, man_raw, man, entries = R.inputs(R.PATHS)
L = lid.replace("-", "")
K = datetime.timezone(datetime.timedelta(hours=2))
def red(s, n): return " ".join(str(s).replace(lid, "LID").replace(L, "LID").split())[:n]
def ts(e): return datetime.datetime.fromtimestamp(int(e.get("__REALTIME_TIMESTAMP", "0")) // 1000000, K).strftime("%m-%d %H:%M:%S")
row = C.psql_stdin("SELECT floor(extract(epoch FROM opened_at))::bigint FROM bem_control.chat_lease WHERE lease_id = :'"'"'id'"'"'::uuid", id=lid)
T0 = int(row)
bt = int(next(x.split()[1] for x in open("/proc/stat") if x.startswith("btime ")))
jd = C.show("systemd-journald.service", "ExecMainStartTimestampMonotonic", "NRestarts")
js = bt + int(jd["ExecMainStartTimestampMonotonic"]) // 1000000
print("JD_START", datetime.datetime.fromtimestamp(js, K).strftime("%Y-%m-%d %H:%M:%S"), "NRestarts=" + jd.get("NRestarts", "?"))
ctx = []
ID = ("systemd", "apt", "apt-get", "dpkg", "unattended-upgrade", "unattended-upgrades", "systemd-journald", "needrestart", "zprobe-release")
def on_ctx(e):
    if e.get("SYSLOG_IDENTIFIER") in ID and len(ctx) < 7:
        ctx.append("CTX %s %s %s" % (ts(e), e.get("SYSLOG_IDENTIFIER"), red(e.get("MESSAGE"), 60)))
C.journal_stream(["--since", "@%d" % (js - 180), "--until", "@%d" % (js + 30)], on_ctx, timeout=120)
for x in ctx: print(x)
day = datetime.datetime.fromtimestamp(js, K).strftime("%Y-%m-%d")
try:
    h = [x.strip() for x in open("/var/log/apt/history.log", errors="replace")]
    hit = [x for i, x in enumerate(h) if (x.startswith("Start-Date: " + day) or ("systemd" in x and any(h[j].startswith("Start-Date: " + day) for j in range(max(0, i - 4), i))))]
    for x in hit[:3]: print("APT", red(x, 90))
    if not hit: print("APT none_on", day)
except OSError as e:
    print("APT", type(e).__name__)
oth = []
U, _ = C.units("b9", R.SERIES)
def on_scan(e):
    d = json.dumps(e)
    if (L in d or lid in d) and e.get("_SYSTEMD_UNIT") not in (U, "zagent-start.service") and len(oth) < 6:
        oth.append("OTH %s m=%s c=%s" % (ts(e), red(e.get("MESSAGE"), 45), red(e.get("_CMDLINE"), 50)))
C.journal_stream(["-b", "0", "--since", "@%d" % T0], on_scan)
for x in oth: print(x)
'
