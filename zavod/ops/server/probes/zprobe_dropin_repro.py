# DOCUMENT: zprobe_dropin_repro.py
# VERSION: v0.1
# STATUS: CANDIDATE
# CREATED_AT: 2026-11-18 12:08 +02:00
# EXECUTOR: Claude (терминал zavod, пускатель) — B13, проект B10 раздел 3 (REL45 §6б)
# PURPOSE: ВОСПРОИЗВЕДЕНИЕ шага drop-in пробы ПБ-1 на настоящем systemd (только CI, НЕ сервер): какие свойства
#   `systemctl show zagent@<L>.service` меняются, кроме ExecStart/ExecStartEx/DropInPaths (DROPIN_KEYS), после того же
#   дополнения и daemon-reload. Причина отказа pb1trial2 14.11 (dropin_changed_other_props) не записана; без ответа
#   новая проба снова остановится. Печатает: версию systemd, «шум» (два чтения без изменений), итог reload без
#   дополнения, итог с дополнением (три повтора с разными экземплярами), значения изменённых свойств (CI — без секретов).
# LIMITS: запускать только на одноразовой машине CI от root. Ставит zagent@.service и zagent.slice в /etc/systemd/system,
#   пишет дополнения в /run/systemd/system. Ничего не запускает (start не вызывается), ничего не удаляет.
# USAGE: sudo python3 -I -B zprobe_dropin_repro.py <каталог с zagent@.service и zagent.slice>
import base64
import json
import os
import shutil
import subprocess
import sys
import time

DROPIN_KEYS = {'ExecStart', 'ExecStartEx', 'DropInPaths'}
LIB = '/usr/local/lib/zavod/probes-b10'
DUMMY = 'zagent@' + '0' * 32 + '.service'


def sh(*a):
    return subprocess.run(a, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout


def show(unit):
    out = sh('systemctl', 'show', unit)
    return dict(ln.split('=', 1) for ln in out.splitlines() if '=' in ln)


def diff(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def cut(v):
    v = '<absent>' if v is None else v
    return v if len(v) <= 200 else v[:200] + '…(len=%d)' % len(v)


def line(tag, names):
    print('%s n=%d names=%s' % (tag, len(names), ','.join(names) or '-'), flush=True)


def main():
    if os.geteuid() != 0:
        print('DREPRO_REFUSED not root')
        return 2
    src = sys.argv[1]
    for n in ('zagent@.service', 'zagent.slice'):
        shutil.copyfile(os.path.join(src, n), '/etc/systemd/system/' + n)
    sh('systemctl', 'daemon-reload')
    print('DREPRO_SYSTEMD ' + sh('systemctl', '--version').splitlines()[0][:80], flush=True)
    print('DREPRO_PKG ' + sh('dpkg-query', '-W', '-f=${Version}', 'systemd').strip(), flush=True)

    all_extra = set()
    for i in range(1, 4):
        L = ('%x' % (0xabc000 + i)).rjust(32, 'a')
        unit = f'zagent@{L}.service'
        a = show(unit)
        time.sleep(2)
        b = show(unit)
        line(f'DREPRO_NOISE#{i}', diff(a, b))
        sh('systemctl', 'daemon-reload')
        c = show(unit)
        line(f'DREPRO_RELOAD_ONLY#{i}', diff(b, c))
        d_before = show(DUMMY)
        plan = {'challenge': 'repro', 'i': i}
        b64 = base64.b64encode(json.dumps(plan, sort_keys=True).encode()).decode()
        text = '[Service]\nExecStart=\nExecStart=/usr/bin/python3 -I -B ' + LIB + '/pb1_session.py ' + b64 + '\n'
        ddir = f'/run/systemd/system/{unit}.d'
        p_before = show(unit)          # как в бегунке (zprobe_runner.py): чтение ДО записи файла и daemon-reload
        os.makedirs(ddir, 0o755, exist_ok=True)
        with open(ddir + '/50-zprobe.conf', 'x') as f:
            f.write(text)
        sh('systemctl', 'daemon-reload')
        p_after = show(unit)
        ch = diff(p_before, p_after)
        line(f'DREPRO_DROPIN#{i}', ch)
        extra = [k for k in ch if k not in DROPIN_KEYS]
        line(f'DREPRO_EXTRA#{i}', extra)
        all_extra |= set(extra)
        for k in extra:
            print('DREPRO_VAL#%d %s before=%s after=%s' % (i, k, cut(p_before.get(k)), cut(p_after.get(k))), flush=True)
        line(f'DREPRO_DUMMY_CHANGED#{i}', diff(d_before, show(DUMMY)))
    line('DREPRO_EXTRA_ALL', sorted(all_extra))
    print('DREPRO_DONE', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
