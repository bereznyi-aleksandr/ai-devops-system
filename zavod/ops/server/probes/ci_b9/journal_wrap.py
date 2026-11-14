# ДОКУМЕНТ: zavod/ops/server/probes/ci_b9/journal_wrap.py
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-14 11:02 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 12:01 +02:00
# v0.2 (аудит REL32 M-03): вид «exitfail» — main журнала отработал (CONFIRMED напечатан), затем выход с кодом 1.
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 05» (c241e855)
# НАЗНАЧЕНИЕ: только для CI B9 (проект v0.9 раздел 3). Запускает НАСТОЯЩИЙ main zprobe_journal.py B9; подменяет только
#   os.fsync процесса: «fail» — сбой, «hold» — удержание до файла release-<серия>, если файл под fsync содержит серию;
#   «startfail» — выход до main (журнал сломан флагом). Управление — новые файлы в /run/zprobe/ci-control
#   (fault-<серия> с видом, clear-<серия> снимает, release-<серия> отпускает); ничего не удаляется.
import os
import sys
import time

sys.path.insert(0, '/usr/local/lib/zavod/probes-b9')
import zprobe_journal as J  # noqa: E402

CTL = '/run/zprobe/ci-control'
_real = os.fsync


def faults():
    out = []
    try:
        names = sorted(os.listdir(CTL))
    except OSError:
        return out
    for n in names:
        if n.startswith('fault-'):
            s = n[6:]
            if not os.path.exists(os.path.join(CTL, 'clear-' + s)):
                with open(os.path.join(CTL, n), encoding='ascii') as f:
                    out.append((s, f.read().strip()))
    return out


def fsync(fd):
    for s, kind in faults():
        try:
            with open(f'/proc/self/fd/{fd}', 'rb') as f:
                data = f.read()
        except OSError:
            data = b''
        if J.series_key(s) in data:
            if kind == 'fail':
                print(f'CI_FSYNC_FAIL series={s}', flush=True)
                raise OSError(5, 'ci injected fsync failure')
            if kind == 'hold':
                print(f'CI_HOLD series={s}', flush=True)
                while not os.path.exists(os.path.join(CTL, 'release-' + s)):
                    time.sleep(0.2)
    return _real(fd)


os.fsync = fsync
if any(k == 'startfail' and s == sys.argv[2] for s, k in faults()):
    print('CI_STARTFAIL', flush=True)
    sys.exit(1)
SERIES = sys.argv[2]
sys.argv = ['zprobe_journal.py'] + sys.argv[1:]
J.main()
if any(k == 'exitfail' and s == SERIES for s, k in faults()):   # REL32 M-03: CONFIRMED напечатан, служба — сбой
    print('CI_EXITFAIL', flush=True)
    sys.exit(1)
