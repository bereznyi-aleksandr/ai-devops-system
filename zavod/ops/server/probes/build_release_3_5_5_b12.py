#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5_b12.py
# ВЕРСИЯ: v0.1 (выпуск B12)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-17 23:50 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-17 23:50 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат zavod (ad796548)
# НАЗНАЧЕНИЕ: сборка выпуска B12 (REL111 AGREED: B12_RELEASE_BUILD_ALLOWED=YES) из коммита с программами — тем же
#   порядком, что build_release_3_5_5_b11.py (берёт его и через него сборщики B10, B9 и основной), меняет состав:
#   zavod/ops/zprobe_pins_b12.txt — отпечатки B12 (ключи — семь модулей папки probes-b12 и копия отпечатков B9);
#   zavod/ops/server/probes/zprobe-release-3.5.5-b12.sh — файл для сервера (режимы preflight, verify-installed, report,
#   install; пакет в новой папке /var/lib/zavod/probes-pkg-<12 знаков коммита B12>; установка — zprobe_release_b12.py).
#   В пакете — отпечатки B8, B9, B10 и B11: по ним B12 сверяет, что B8–B11 не тронуты. Новых служб нет, SQL нет.
# ОГРАНИЧЕНИЯ: ничего на сервере не делает. Выпуск не собирается, если: 1) любой из четырёх файлов отпечатков коммита
#   не равен известной сумме (PIN_FILES — файлы замороженного выпуска B11 abb1575f9);
#   2) отпечатки B11 коммита — не выпуск B11 76db3a69c…; 3) любой модуль B12, кроме zprobe_checks.py и zprobe_r2.py,
#   не равен (байт в байт) отпечатку B11.
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_release_3_5_5_b11 as B11B  # noqa: E402  — подключает сборщики B9, B10, B11; ниже состав заменяется на B12

B = B11B.B
B9B = B11B.B9B
P = B.PROBES
MODULES = B11B.MODULES
CHANGED = ('zprobe_checks.py', 'zprobe_r2.py')
INSTALLER_CHAIN = B11B.INSTALLER_CHAIN + ('zprobe_release_b12.py',)   # то, что импортирует zprobe_release_b12.py
B8_PINS, B9_PINS, B10_PINS = B11B.B8_PINS, B11B.B9_PINS, B11B.B10_PINS
B11_PINS = 'zavod/ops/zprobe_pins_b11.txt'
B.VERSION = '3.5.5-b12'
B.FILES = [P + n for n in MODULES + INSTALLER_CHAIN] + [B8_PINS, B9_PINS, B10_PINS, B11_PINS]
B.FILES = list(dict.fromkeys(B.FILES))
B.EXEC = {P + n for n in ('zprobe_release.py', 'zprobe_release_b9.py', 'zprobe_release_b10.py', 'zprobe_release_b11.py',
                          'zprobe_release_b12.py')}
B.PINS_PATH = 'zavod/ops/zprobe_pins_b12.txt'
B.SH_PATH = P + 'zprobe-release-3.5.5-b12.sh'
B.PIN_KEYS = [(n, P + n) for n in MODULES] + [('zprobe_pins_b9.txt', B9_PINS)]
B.SH_TEMPLATE = (B.SH_TEMPLATE
                 .replace('zprobe_release_b11.py" "$M"', 'zprobe_release_b12.py" "$M"')
                 .replace('ВЫПУСК: 3.5.5 B11 (ПБ-1)', 'ВЫПУСК: 3.5.5 B12 (ПБ-1)')
                 .replace('#   Потом zprobe_release_b11.py: preflight, verify-installed, report — только чтение; install — '
                          'проверки и установка только новых целей B11 (без служб) рядом с B8, B9 и B10.',
                          '#   Потом zprobe_release_b12.py: preflight, verify-installed, report — только чтение; install — '
                          'проверки и установка только новых целей B12 (без служб) рядом с B8, B9, B10 и B11.'))
assert all(w in B.SH_TEMPLATE for w in ('zprobe_release_b12.py" "$M"', 'ВЫПУСК: 3.5.5 B12',
                                         'Потом zprobe_release_b12.py')) \
    and 'zprobe_release_b11.py' not in B.SH_TEMPLATE and 'B11 (ПБ-1)' not in B.SH_TEMPLATE, 'template'
# Известные суммы файлов отпечатков и коммит B11 — те же, что zprobe_release_b12.PINS_FILE_SHA и B11_RELEASE_COMMIT
# (установщик здесь не импортируется: ему нужны модули Linux; равенство проверяет тест test_zprobe_release_b12 W16).
B11_RELEASE_COMMIT = '76db3a69c7819c370000b58524cf672a10d48057'
PIN_FILES = {B8_PINS: 'ef5c9962fd5aa15ce11a1832529693bbcbecc85353ed2687b426e5088bc61fe1',
             B9_PINS: '91ed266ae21a3719463a4b49d20c5d9f5ed797cd6dbbdaf9dbbaa60d4fbaa712',
             B10_PINS: 'a86ea709d6de2c789a39efeb047a6fc5f25365a200dc3df39e0d3924aed883db',
             B11_PINS: 'f0a989d642ce1f459ad64b205743b82a8012ace6eac905082ef75b9d759c1089'}


def pins_problem(get):
    """Четыре файла отпечатков — известные суммы; отпечатки B11 — коммит выпуска B11 (иначе строка отказа, иначе None)."""
    bad = [p for p, h in sorted(PIN_FILES.items()) if B.sha(get(p)) != h]
    if bad:
        return f'pins files differ from the known B11-release sums: {bad}'
    rc = B9B.parse(get(B11_PINS)).get('release_commit')
    return None if rc == B11_RELEASE_COMMIT else f'B11 pins release_commit {rc} is not {B11_RELEASE_COMMIT}'


def unchanged_problem(pins11, get):
    """Модули B12, кроме CHANGED, равны отпечаткам B11 (иначе строка отказа, иначе None)."""
    bad = [n for n in MODULES if n not in CHANGED and (n not in pins11 or B.sha(get(P + n)) != pins11[n])]
    return f'modules differ from B11 pins: {bad}' if bad else None


def build(root, commit):
    """Сборка B12: оригинальная сборка, затем сверка файлов отпечатков с известными суммами и модулей с отпечатками B11."""
    get = lambda p: B.blob(root, commit, p)  # noqa: E731
    bad = pins_problem(get)
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad)
    pins, tar, sh_b = B9B._build(root, commit)
    bad = unchanged_problem(B9B.parse(get(B11_PINS)), get)
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad)
    return pins, tar, sh_b


B.build = build
if __name__ == '__main__':
    sys.exit(B.main())
