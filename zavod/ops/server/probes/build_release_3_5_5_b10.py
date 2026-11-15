#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5_b10.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-15 00:18 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-15 00:18 +02:00
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9), помощник
# НАЗНАЧЕНИЕ: сборка выпуска B10 (проект DESIGN_B10_3_5_5_20261114_v0_18.md раздел 7) из коммита с программами —
#   тем же порядком, что build_release_3_5_5_b9.py (берёт его и build_release_3_5_5.py, меняет состав):
#   zavod/ops/zprobe_pins_b10.txt — отпечатки B10 (ключи = PINNED zprobe_runner.py B10, модули B10, phone_*, pc_*);
#   zavod/ops/server/probes/zprobe-release-3.5.5-b10.sh — файл для сервера (режимы preflight, verify-installed,
#   report, install; пакет в новой папке /var/lib/zavod/probes-pkg-<12 знаков коммита B10>; установка —
#   zprobe_release_b10.py). В пакете — отпечатки B8 и B9: по ним B10 сверяет, что B8 и B9 не тронуты; копия
#   отпечатков B9 ставится в папку программ B10 (zprobe_r2.py). SQL пакета — zavod/kernel/db/08_zavod_ext_06.sql.
# ОГРАНИЧЕНИЯ: ничего на сервере не делает; клетка 3.5.2 не ставится заново — её отпечатки в B10 обязаны быть равны
#   отпечаткам B8 и B9 (иначе выпуск не собирается).
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_release_3_5_5_b9 as B9B  # noqa: E402

B = B9B.B
P = B.PROBES
CELL = B9B.CELL
B8_PINS = B9B.B8_PINS
B9_PINS = 'zavod/ops/zprobe_pins_b9.txt'
SQL = 'zavod/kernel/db/08_zavod_ext_06.sql'          # у B9 — B9B.SQL (06_zavod_ext_04.sql)
NEW_MODULES = ('zprobe_dropin.py', 'zprobe_checks.py', 'zprobe_seal.py', 'zprobe_unstarted.py',
               'zprobe_export_rules.py', 'zprobe_export.py', 'zprobe_r2.py', 'zevidence_send.py')
UNITS = ('zprobe-run-b10@.service', 'zprobe-journal-b10@.service')
B9B.SQL = SQL
B.VERSION = '3.5.5-b10'
B.FILES = [P + n for n in ('pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py',
                           'zprobe-start') + UNITS + ('test_zprobe.py', 'zprobe_release.py', 'zprobe_release_b9.py',
                                                    'zprobe_release_b10.py', 'zprobe_verify_export.py') + NEW_MODULES]
B.FILES += [CELL + n for n in ('zavod-egress.nft', 'zavod-gate', 'zavod-proxy', 'zavod-gate.service',
                               'zavod-proxy.service', 'zagent@.service')]
B.FILES += ['zavod/ops/phone/zprobe_verify.py', 'zavod/ops/phone/zprobe_series.sh', 'zavod/ops/pc/zprobe_refs.sh',
            'zavod/ops/pc/zprobe_refs_check.py', SQL, B8_PINS, B9_PINS]
B.EXEC = set(B9B.B.EXEC) | {P + 'zprobe_release_b10.py'}
B.PINS_PATH = 'zavod/ops/zprobe_pins_b10.txt'
B.SH_PATH = P + 'zprobe-release-3.5.5-b10.sh'
B.PIN_KEYS = [('pb1_session.py', P + 'pb1_session.py'), ('zprobe_rules.py', P + 'zprobe_rules.py'),
              ('zprobe_runner.py', P + 'zprobe_runner.py'), ('zprobe_journal.py', P + 'zprobe_journal.py'),
              ('zprobe-start', P + 'zprobe-start'), ('zprobe-run-b10@.service', P + 'zprobe-run-b10@.service'),
              ('zprobe-journal-b10@.service', P + 'zprobe-journal-b10@.service')]
B.PIN_KEYS += [(n, P + n) for n in NEW_MODULES]
B.PIN_KEYS += [('zagent@.service', CELL + 'zagent@.service'), ('zavod-proxy', CELL + 'zavod-proxy'),
               ('zavod-gate', CELL + 'zavod-gate'), ('zavod-egress.nft', CELL + 'zavod-egress.nft'),
               ('phone_zprobe_verify.py', 'zavod/ops/phone/zprobe_verify.py'),
               ('phone_zprobe_rules.py', P + 'zprobe_rules.py'),
               ('pc_zprobe_refs.sh', 'zavod/ops/pc/zprobe_refs.sh'),
               ('pc_zprobe_refs_check.py', 'zavod/ops/pc/zprobe_refs_check.py'),
               ('pc_zprobe_rules.py', P + 'zprobe_rules.py'),
               ('pc_zprobe_verify_export.py', P + 'zprobe_verify_export.py'),
               ('pc_zprobe_export_rules.py', P + 'zprobe_export_rules.py'),
               ('pc_zprobe_seal.py', P + 'zprobe_seal.py')]
B.SH_TEMPLATE = (B.SH_TEMPLATE
                 .replace('zprobe_release_b9.py" "$M"', 'zprobe_release_b10.py" "$M"')
                 .replace('ВЫПУСК: 3.5.5 B9 (ПБ-1)', 'ВЫПУСК: 3.5.5 B10 (ПБ-1)')
                 .replace('#   Потом zprobe_release_b9.py: preflight, verify-installed, report — только чтение; install — '
                          'проверки и установка только новых целей B9 рядом с B8.',
                          '#   Потом zprobe_release_b10.py: preflight, verify-installed, report — только чтение; install — '
                          'проверки и установка только новых целей B10 рядом с B8 и B9.'))
assert all(w in B.SH_TEMPLATE for w in ('zprobe_release_b10.py" "$M"', 'ВЫПУСК: 3.5.5 B10',
                                         'Потом zprobe_release_b10.py')) \
    and 'zprobe_release_b9.py' not in B.SH_TEMPLATE, 'template'

_b9_build = B.build     # сборка B9-порядка: сборка build_release_3_5_5 и сверка клетки с B8


def build(root, commit):
    """Сборка B10: клетка равна отпечаткам B8 (сборка B9-порядка) и отпечаткам B9 (здесь)."""
    pins, tar, sh_b = _b9_build(root, commit)
    bad = B9B.cell_problem(B9B.parse(pins), B9B.parse(B.blob(root, commit, B9_PINS)))
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad.replace('B8 pins', 'B9 pins'))
    return pins, tar, sh_b


B.build = build
if __name__ == '__main__':
    sys.exit(B.main())
