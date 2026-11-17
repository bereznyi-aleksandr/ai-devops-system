#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5_b11.py
# ВЕРСИЯ: v0.1 (выпуск B11)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-17 07:04 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-17 07:04 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат zavod (ee9861cd)
# НАЗНАЧЕНИЕ: сборка выпуска B11 (решение аудита REL96B PATH=A) из коммита с программами — тем же порядком, что
#   build_release_3_5_5_b10.py (берёт его и build_release_3_5_5.py, меняет состав):
#   zavod/ops/zprobe_pins_b11.txt — отпечатки B11 (ключи — семь модулей папки probes-b11 и копия отпечатков B9);
#   zavod/ops/server/probes/zprobe-release-3.5.5-b11.sh — файл для сервера (режимы preflight, verify-installed, report,
#   install; пакет в новой папке /var/lib/zavod/probes-pkg-<12 знаков коммита B11>; установка — zprobe_release_b11.py).
#   В пакете — отпечатки B8, B9 и B10: по ним B11 сверяет, что B8, B9 и B10 не тронуты. Новых служб нет, клетка 3.5.2
#   и SQL в пакет не входят.
# ОГРАНИЧЕНИЯ: ничего на сервере не делает. Выпуск не собирается, если любой модуль B11, кроме zprobe_checks.py и
#   zprobe_r2.py, не равен (байт в байт) отпечатку B10 в zavod/ops/zprobe_pins_b10.txt того же коммита.
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_release_3_5_5_b10 as B10B  # noqa: E402  — подключает сборщики B9 и B10; ниже состав заменяется на B11

B = B10B.B
B9B = B10B.B9B
P = B.PROBES
MODULES = ('zprobe_r2.py', 'zprobe_checks.py', 'zprobe_export_rules.py', 'zprobe_rules.py', 'zprobe_seal.py',
           'zprobe_unstarted.py', 'zprobe_dropin.py')
CHANGED = ('zprobe_checks.py', 'zprobe_r2.py')
INSTALLER_CHAIN = ('zprobe_journal.py', 'zprobe_release.py', 'zprobe_release_b9.py', 'zprobe_release_b10.py',
                   'zprobe_release_b11.py')      # то, что импортирует zprobe_release_b11.py (и модули, которых нет в MODULES)
B8_PINS, B9_PINS, B10_PINS = B10B.B8_PINS, B10B.B9_PINS, 'zavod/ops/zprobe_pins_b10.txt'
B.VERSION = '3.5.5-b11'
B.FILES = [P + n for n in MODULES + INSTALLER_CHAIN] + [B8_PINS, B9_PINS, B10_PINS]
B.FILES = list(dict.fromkeys(B.FILES))
B.EXEC = {P + n for n in ('zprobe_release.py', 'zprobe_release_b9.py', 'zprobe_release_b10.py', 'zprobe_release_b11.py')}
B.PINS_PATH = 'zavod/ops/zprobe_pins_b11.txt'
B.SH_PATH = P + 'zprobe-release-3.5.5-b11.sh'
B.PIN_KEYS = [(n, P + n) for n in MODULES] + [('zprobe_pins_b9.txt', B9_PINS)]
B.SH_TEMPLATE = (B.SH_TEMPLATE
                 .replace('zprobe_release_b10.py" "$M"', 'zprobe_release_b11.py" "$M"')
                 .replace('ВЫПУСК: 3.5.5 B10 (ПБ-1)', 'ВЫПУСК: 3.5.5 B11 (ПБ-1)')
                 .replace('#   Потом zprobe_release_b10.py: preflight, verify-installed, report — только чтение; install — '
                          'проверки и установка только новых целей B10 рядом с B8 и B9.',
                          '#   Потом zprobe_release_b11.py: preflight, verify-installed, report — только чтение; install — '
                          'проверки и установка только новых целей B11 (без служб) рядом с B8, B9 и B10.'))
assert all(w in B.SH_TEMPLATE for w in ('zprobe_release_b11.py" "$M"', 'ВЫПУСК: 3.5.5 B11',
                                         'Потом zprobe_release_b11.py')) \
    and 'zprobe_release_b10.py' not in B.SH_TEMPLATE, 'template'


def unchanged_problem(pins10, get):
    """Модули B11, кроме CHANGED, равны отпечаткам B10 (иначе строка отказа, иначе None)."""
    bad = [n for n in MODULES if n not in CHANGED and (n not in pins10 or B.sha(get(P + n)) != pins10[n])]
    return f'modules differ from B10 pins: {bad}' if bad else None


def build(root, commit):
    """Сборка B11: оригинальная сборка (без проверки клетки — клетки в пакете нет) и сверка модулей с отпечатками B10."""
    pins, tar, sh_b = B9B._build(root, commit)
    bad = unchanged_problem(B9B.parse(B.blob(root, commit, B10_PINS)), lambda p: B.blob(root, commit, p))
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad)
    return pins, tar, sh_b


B.build = build
if __name__ == '__main__':
    sys.exit(B.main())
