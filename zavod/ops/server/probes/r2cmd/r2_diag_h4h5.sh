# ДОКУМЕНТ: r2_diag_h4h5.sh (разбор отказа R2 v4 failed=H4,H5 только чтением)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-17 06:20 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-17 06:20 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель).
# НАЗНАЧЕНИЕ: R2 v4 на сервере 17.11 06:12 — BLOCKED_SESSION_UNKNOWN failed=H4,H5 reason=checks (печати нет). Этот
#   скрипт собирает ТЕ ЖЕ факты тем же кодом выпуска (zprobe_r2.inputs/deps → zprobe_checks.collect → evaluate) и
#   печатает значения H1–H10 и сырые факты H4/H5: возраст загрузки, первую запись загрузки, journald, --verify, проход
#   журнала (rc, n, loss, unit/start/other) и сравнение курсоров (только да/нет, сами курсоры не печатаются), плюс до
#   двух сообщений journald о потере и до двух источников чужих упоминаний аренды. Номер аренды не печатается
#   (заменяется на LID). Ничего не пишет: python3 -I -B (без __pycache__), SQL под default_transaction_read_only=on,
#   journalctl только читает. Не вызывает seal, call_seal, mkdir. Вывод ≤ 20 строк (обёртка режет tail -20).
# ЗАПУСК: только через транспорт mk_r2_cmd.py (env -i, PATH=/usr/sbin:/usr/bin), от root.
set -u
[ "$(/usr/bin/id -u)" = 0 ] || { echo 'DIAG=REFUSED not_root'; exit 2; }
cd /tmp || exit 2
export PGOPTIONS='-c default_transaction_read_only=on'
exec /usr/bin/python3 -I -B -c '
import sys, os, re, json, time, subprocess, collections
sys.path.insert(0, "/usr/local/lib/zavod/probes-b10")
import zprobe_r2 as R, zprobe_checks as C
lid, man_raw, man, entries = R.inputs(R.PATHS)
L = lid.replace("-", "")
def red(s): return str(s).replace(lid, "LID").replace(L, "LID")[:110]
f = R.deps(lid, man_raw, man, entries, R.PATHS)["collect"]()
ev = C.evaluate(f)
print("DIAG failed=" + ",".join(ev.get("failed") or []) or "-")
for k, v in (ev.get("checks") or {}).items():
    print(k, "OK" if v["ok"] else "FAIL", red(v["value"]))
T0 = (f.get("lease_row") or {}).get("opened_at_s") or 0
bt, now, fe, mono = f["btime"], int(time.time()), f.get("first_entry_s"), f.get("journald_mono_us")
h = lambda x: "-" if x is None else round(x / 3600, 1)
print("H4RAW boot_age_h=%s t0_after_boot_h=%s first_gap_s=%s jd=%s jd_start_minus_t0_h=%s verify=%s"
      % (h(now - bt), h(T0 - bt), "-" if fe is None else fe - bt, f.get("journald_active"),
         h(bt + mono // 1000000 - T0) if isinstance(mono, int) else "-", f.get("verify_rc")))
sc = f.get("scan") or {}
cf, cl = C.cursor_parts(sc.get("first_cursor")), C.cursor_parts(sc.get("last_cursor"))
a = f.get("anchor") or {}
ca = C.cursor_parts(a.get("cursor_after"))
b = f.get("boot_now")
cmp = lambda x, y: "-" if not (x and y) else ("Y" if x == y else "N")
print("H5RAW rc=%s n=%s loss=%s unit=%s start=%s other=%s anchor_ok=%s"
      % (sc.get("rc"), sc.get("n"), sc.get("loss"), sc.get("unit_hits"), sc.get("start_hits"), sc.get("other"),
         f.get("anchor_cursor_ok")))
print("CURS have=%s%s%s s_f=l:%s s_f=a:%s b_f:%s b_l:%s b_a:%s i_f<=a:%s i_a<=l:%s"
      % (int(bool(cf)), int(bool(cl)), int(bool(ca)), cmp(cf and cf[0], cl and cl[0]), cmp(cf and cf[0], ca and ca[0]),
         cmp(cf and cf[2], b), cmp(cl and cl[2], b), cmp(ca and ca[2], b),
         "-" if not (cf and ca) else ("Y" if cf[1] <= ca[1] else "N"),
         "-" if not (ca and cl) else ("Y" if ca[1] <= cl[1] else "N")))
loss, oth = [], collections.Counter()
U, _ = C.units("b9", R.SERIES)
def each(e):
    m = e.get("MESSAGE"); m = m if isinstance(m, str) else str(m)
    if e.get("SYSLOG_IDENTIFIER") == "systemd-journald" and C.LOSS.search(m.lower()) and len(loss) < 2:
        loss.append(red(m))
    d = json.dumps(e)
    if (L in d or lid in d) and e.get("_SYSTEMD_UNIT") not in (U, "zagent-start.service"):
        oth[red("%s|%s|%s" % (e.get("_SYSTEMD_UNIT"), e.get("SYSLOG_IDENTIFIER"), e.get("_COMM")))] += 1
C.journal_stream(["-b", "0", "--since", "@%d" % T0], each)
for m in loss: print("LOSS", m)
for k, n in oth.most_common(2): print("OTHER", n, k)
du = subprocess.run(["journalctl", "--disk-usage"], capture_output=True, text=True, timeout=60).stdout.strip()
print("DU", du[-90:])
'
