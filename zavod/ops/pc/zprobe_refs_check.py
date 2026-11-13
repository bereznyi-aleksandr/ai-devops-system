#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/pc/zprobe_refs_check.py
# ВЕРСИЯ: v0.4  СТАТУС: DRAFT
# v0.4 (2026-11-13 08:17 +02:00, аудит R10 L-R10-01): импорт правил не пишет кеш Python (sys.dont_write_bytecode).
# v0.3 (2026-11-13 05:59 +02:00, аудит R5 M-R5-01, NEW_NEGATIVE_12): сверка снимков — общая функция
#   zprobe_rules.refs_problem (файл zprobe_rules.py лежит рядом, его SHA-256 — pc_zprobe_rules.py в zprobe_pins.txt).
#   Набранная оператором строка ZPROBE_TIMES может быть подменена другой верной по виду строкой, поэтому итог этой
#   программы — только «ПРЕДВАРИТЕЛЬНО»; шаг принимает zprobe_verify.py --refs по копии журнала с телефона.
# v0.2 (2026-11-12 23:41 +02:00, аудит R4 M-R4-01, L-R4-02, NEW_NEGATIVE_8): снимки привязаны к серии и к прогону —
#   строка ZPROBE_TIMES с телефона (серия, вызов, начало и конец прогона из журнала, SHA-256 манифеста pins) и
#   порядок «до» < начало ≤ конец < «после», разрывы не больше 30 минут; обе программы компьютера сверены с
#   манифестом zprobe_pins.txt (pc_zprobe_refs.sh в шапке снимка, pc_zprobe_refs_check.py — сама себя), а манифест —
#   с SHA-256 из строки телефона.
# ДАТА СОЗДАНИЯ: 2026-11-12 23:14 +02:00
# ИСПОЛНИТЕЛЬ: Claude (чат c7307e9c-8e0e-4e24-997c-12d9fd3b0c71)
# НАЗНАЧЕНИЕ: проба ПБ-1, аудит R3 M-R3-01 — сверка снимков веток: оба снимка прочитаны без ошибки (rc=0), того же
#   хранилища, образца и серии, набор веток не изменился и ветки пробы zprobe/pb1-<8 знаков вызова> нет.
#   Нет снимка, ошибка чтения, чужая серия или время вне прогона — НЕВЕРНО.
# ВЫЗОВ: python3 -I -B zprobe_refs_check.py refs_before.txt refs_after.txt zprobe_pins.txt "<строка ZPROBE_TIMES>"
import hashlib
import os
import re
import sys

sys.dont_write_bytecode = True           # R10 L-01: импорт правил не создаёт __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_rules as R  # noqa: E402

TIMES = re.compile(r'\AZPROBE_TIMES series=([0-9A-Za-z_-]{1,40}) challenge=([0-9a-f]{32}) '
                   r'run_start=(\S+) run_end=(\S+) pins_sha256=([0-9a-f]{64})\Z')


def problem(before, after, times, pins, pins_sha, self_sha, rules_sha=None):
    """None — предварительно: по набранной строке ветка пробы не появилась за время прогона; иначе причина."""
    m = TIMES.match(times or '')
    if not m:
        return 'ZPROBE_TIMES line malformed'
    series, challenge, rs, re_, ps = m.groups()
    if ps != pins_sha:
        return 'pins file differs from the phone manifest'
    if pins.get('pc_zprobe_refs_check.py') != self_sha:
        return 'zprobe_refs_check.py differs from pins'
    if rules_sha is not None and pins.get('pc_zprobe_rules.py') != rules_sha:
        return 'zprobe_rules.py differs from pins'
    return R.refs_problem(before, after, series, challenge, [rs, re_], pins.get('pc_zprobe_refs.sh'))


def read_pins(path):
    pins = {}
    with open(path, encoding='utf-8') as f:
        for ln in f:
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                k, v = ln.split()
                pins[k] = v
    return pins


def main():
    if len(sys.argv) != 5:
        print('НЕВЕРНО | usage: zprobe_refs_check.py refs_before refs_after zprobe_pins.txt "ZPROBE_TIMES ..."')
        sys.exit(2)
    try:
        with open(sys.argv[1], encoding='utf-8') as f:
            b = f.read()
        with open(sys.argv[2], encoding='utf-8') as f:
            a = f.read()
        with open(sys.argv[3], 'rb') as f:
            pins_sha = hashlib.sha256(f.read()).hexdigest()
        with open(__file__, 'rb') as f:
            self_sha = hashlib.sha256(f.read()).hexdigest()
        with open(R.__file__, 'rb') as f:
            rules_sha = hashlib.sha256(f.read()).hexdigest()
        p = problem(b, a, sys.argv[4].strip(), read_pins(sys.argv[3]), pins_sha, self_sha, rules_sha)
    except (OSError, ValueError) as e:
        p = 'cannot read input: ' + type(e).__name__
    print('ПРЕДВАРИТЕЛЬНО ВЕРНО | refs unchanged during the typed run times; шаг принимает zprobe_verify.py --refs'
          if p is None else 'НЕВЕРНО | ' + p)
    sys.exit(0 if p is None else 1)


if __name__ == '__main__':
    main()
