#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5_b9.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-14 10:51 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 10:51 +02:00
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 05» (c241e855)
# НАЗНАЧЕНИЕ: сборка выпуска B9 (проект DESIGN_B9_3_5_5_20261114_v0_9.md и разделы по его §0) из коммита с
#   программами — тем же порядком, что build_release_3_5_5.py (его функции, другой состав):
#   zavod/ops/zprobe_pins_b9.txt — отпечатки B9 (ключи = PINNED zprobe_runner.py B9, phone_*, pc_*);
#   zavod/ops/server/probes/zprobe-release-3.5.5-b9.sh — файл для сервера (режимы preflight, verify-installed,
#   report, install; пакет в новой папке /var/lib/zavod/probes-pkg-<12 знаков коммита B9>).
#   В пакете — отпечатки B8 (zavod/ops/zprobe_pins_b8.txt, копия 3bd33252c): по ним B9 сверяет, что B8 не тронут.
# ОГРАНИЧЕНИЯ: ничего на сервере не делает; клетка 3.5.2 не ставится заново — её отпечатки в B9 обязаны быть равны B8.
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_release_3_5_5 as B  # noqa: E402

P = B.PROBES
CELL = 'zavod/ops/server/cell/'
B8_PINS = 'zavod/ops/zprobe_pins_b8.txt'
B.VERSION = '3.5.5-b9'
B.FILES = [P + n for n in ('pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py',
                           'zprobe-start', 'zprobe-run-b9@.service', 'zprobe-journal-b9@.service', 'test_zprobe.py',
                           'zprobe_release.py', 'zprobe_release_b9.py')]
B.FILES += [CELL + n for n in ('zavod-egress.nft', 'zavod-gate', 'zavod-proxy', 'zavod-gate.service',
                               'zavod-proxy.service', 'zagent@.service')]
B.FILES += ['zavod/ops/phone/zprobe_verify.py', 'zavod/ops/phone/zprobe_series.sh', 'zavod/ops/pc/zprobe_refs.sh',
            'zavod/ops/pc/zprobe_refs_check.py', 'zavod/kernel/db/06_zavod_ext_04.sql', B8_PINS]
B.EXEC = {P + 'zprobe-start', P + 'zprobe_release.py', P + 'zprobe_release_b9.py', CELL + 'zavod-gate',
          CELL + 'zavod-proxy', 'zavod/ops/phone/zprobe_series.sh', 'zavod/ops/pc/zprobe_refs.sh'}
B.PINS_PATH = 'zavod/ops/zprobe_pins_b9.txt'
B.SH_PATH = P + 'zprobe-release-3.5.5-b9.sh'
B.PIN_KEYS = [('pb1_session.py', P + 'pb1_session.py'), ('zprobe_rules.py', P + 'zprobe_rules.py'),
              ('zprobe_runner.py', P + 'zprobe_runner.py'), ('zprobe_journal.py', P + 'zprobe_journal.py'),
              ('zprobe-start', P + 'zprobe-start'), ('zprobe-run-b9@.service', P + 'zprobe-run-b9@.service'),
              ('zprobe-journal-b9@.service', P + 'zprobe-journal-b9@.service'),
              ('zagent@.service', CELL + 'zagent@.service'), ('zavod-proxy', CELL + 'zavod-proxy'),
              ('zavod-gate', CELL + 'zavod-gate'), ('zavod-egress.nft', CELL + 'zavod-egress.nft'),
              ('phone_zprobe_verify.py', 'zavod/ops/phone/zprobe_verify.py'),
              ('phone_zprobe_rules.py', P + 'zprobe_rules.py'),
              ('pc_zprobe_refs.sh', 'zavod/ops/pc/zprobe_refs.sh'),
              ('pc_zprobe_refs_check.py', 'zavod/ops/pc/zprobe_refs_check.py'),
              ('pc_zprobe_rules.py', P + 'zprobe_rules.py')]
B.SH_TEMPLATE = (B.SH_TEMPLATE
                 .replace('M=${1:-}\ncase "$M" in check|install) ;; *) echo "usage: bash $0 check|install"; exit 2;; esac',
                          'M=${1:-}\nR=${2:-}\ncase "$M" in preflight|verify-installed|install) [ -z "$R" ] || M=bad;; '
                          'report) case "$R" in preflight|verify-installed) ;; *) M=bad;; esac;; *) M=bad;; esac\n'
                          '[ "$M" != bad ] || { echo "usage: bash $0 preflight|verify-installed|install|'
                          'report preflight|report verify-installed"; exit 2; }')
                 .replace('exec python3 -I -B "$P/zavod/ops/server/probes/zprobe_release.py" "$M" "$P"',
                          'exec python3 -I -B "$P/zavod/ops/server/probes/zprobe_release_b9.py" "$M" "$P" ${R:+"$R"}')
                 .replace('ВЫПУСК: 3.5.5 (ПБ-1)', 'ВЫПУСК: 3.5.5 B9 (ПБ-1)')
                 .replace('#   Потом zprobe_release.py: check — проверки §11 и план установки; install — check и установка '
                          'только новых файлов.',
                          '#   Потом zprobe_release_b9.py: preflight, verify-installed, report — только чтение; install — '
                          'проверки и установка только новых целей B9 рядом с B8.')
                 .replace('bash <этот файл> check   |   bash <этот файл> install',
                          'bash <этот файл> preflight | verify-installed | install | report preflight|verify-installed'))
assert all(w in B.SH_TEMPLATE for w in ('report) case', 'zprobe_release_b9.py" "$M"', 'ВЫПУСК: 3.5.5 B9', 'Потом zprobe_release_b9.py',
                                         '<этот файл> preflight |')), \
    'template'
CELL_KEYS = ('zagent@.service', 'zavod-proxy', 'zavod-gate', 'zavod-egress.nft')


def cell_problem(pins_b9, pins_b8):
    """Клетка 3.5.2 не ставится заново: её отпечатки в B9 равны отпечаткам B8 (иначе выпуск не собирается)."""
    bad = [k for k in CELL_KEYS if pins_b9.get(k) != pins_b8.get(k)]
    return f'cell fingerprints differ from B8 pins: {bad}' if bad else None


def parse(b):
    return dict(ln.split(' ', 1) for ln in b.decode('utf-8').split('\n') if ln and not ln.startswith('#'))


_build = B.build


def build(root, commit):
    pins, tar, sh_b = _build(root, commit)
    bad = cell_problem(parse(pins), parse(B.blob(root, commit, B8_PINS)))
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad)
    return pins, tar, sh_b


B.build = build
if __name__ == '__main__':
    sys.exit(B.main())
