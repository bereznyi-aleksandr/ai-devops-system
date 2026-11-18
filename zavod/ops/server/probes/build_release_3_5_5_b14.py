#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5_b14.py
# ВЕРСИЯ: v0.1 (выпуск B14)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-18 22:03 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 22:03 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может. Аудитор — ChatGPT.
# НАЗНАЧЕНИЕ: сборка выпуска B14 (REL139 AGREED: бегунок v0.18 ставит RUNNING сразу после start, окно collect — из
#   бюджета сеанса) тем же порядком, что build_release_3_5_5_b13.py (берёт его и через него сборщики B12…B9 и основной):
#   zavod/ops/zprobe_pins_b14.txt — отпечатки B14 (ключи — 12 программ папки probes-b14, две службы -b14@, 4 файла клетки,
#   три ключа телефона phone_zprobe_series_b14.sh, phone_zprobe_verify.py, phone_zprobe_rules.py и три ключа компьютера
#   pc_zprobe_refs.sh, pc_zprobe_refs_check.py, pc_zprobe_rules.py);
#   zavod/ops/server/probes/zprobe-release-3.5.5-b14.sh — файл для сервера (шаблон B13 с именами B14; установка —
#   zprobe_release_b14.py). В пакете — отпечатки B8, B9, B10, B11, B12 и B13.
# ОГРАНИЧЕНИЯ: ничего на сервере не делает. Выпуск не собирается, если: 1) файлы отпечатков B8–B13 коммита не равны
#   известным суммам (или release_commit B12/B13 чужой); 2) модуль «без изменений» (pb1_session, zprobe_rules, zprobe_seal,
#   zprobe_export, zprobe_dropin, zprobe_export_rules) не равен отпечатку B13 (первые четыре — и B10/B12, как в B13), файлы
#   телефона verify и rules — отпечаткам B13; 3) изменённый модуль (runner, checks, journal, zprobe-start, unstarted,
#   evidence_send) не равен закреплённой сумме ACCEPTED; 4) в 12 программах и 2 службах найдено «probes-b13», «run-b13@»,
#   «journal-b13@» или имена b10 вне комментариев (в B14 исключений нет: zprobe_checks строит чужие имена сам);
#   5) клетка, файлы компьютера — не равны отпечаткам B10 (как в B13). Установщика zprobe_release_b14.py пока нет:
#   он в FILES, сборка без него честно отказывает; проверки п. 1–5 — отдельные функции, они его не требуют.
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_release_3_5_5_b13 as B13B  # noqa: E402  — подключает сборщики B9–B13; ниже состав заменяется на B14

B = B13B.B
B9B = B13B.B9B
P = B.PROBES
PROGRAMS = B13B.PROGRAMS
UNITS = ('zprobe-run-b14@.service', 'zprobe-journal-b14@.service')
UNCHANGED = ('pb1_session.py', 'zprobe_rules.py', 'zprobe_seal.py', 'zprobe_export.py', 'zprobe_dropin.py',
             'zprobe_export_rules.py')                       # байт в байт отпечатку B13
PHONE_SERIES = B13B.PHONE_DIR + 'zprobe_series_b14.sh'
PHONE_VERIFY, PHONE_RULES = B13B.PHONE_VERIFY, B13B.PHONE_RULES
PC_KEYS, CELL, CELL_KEYS = B13B.PC_KEYS, B13B.CELL, B13B.CELL_KEYS
INSTALLER_CHAIN = B13B.INSTALLER_CHAIN + ('zprobe_release_b14.py',)
B8_PINS, B9_PINS, B10_PINS, B11_PINS, B12_PINS = (B13B.B8_PINS, B13B.B9_PINS, B13B.B10_PINS, B13B.B11_PINS,
                                                  B13B.B12_PINS)
B13_PINS = 'zavod/ops/zprobe_pins_b13.txt'
B.VERSION = '3.5.5-b14'
B.FILES = ([P + n for n in PROGRAMS + UNITS + INSTALLER_CHAIN] + [PHONE_SERIES, PHONE_VERIFY, PHONE_RULES]
           + [B8_PINS, B9_PINS, B10_PINS, B11_PINS, B12_PINS, B13_PINS])
B.FILES = list(dict.fromkeys(B.FILES))
B.EXEC = {P + n for n in ('zprobe-start',) + INSTALLER_CHAIN} | {PHONE_SERIES}
B.PINS_PATH = 'zavod/ops/zprobe_pins_b14.txt'


def pins_text_b14(get, commit):
    """Отпечатки как в основном сборщике; строка «Манифест для приёмки» называет файл B14 (как L-355-REL128-01 в B13)."""
    text = B13B._pins_text_base(get, commit)
    old = 'git show <коммит этого файла>:zavod/ops/zprobe_pins.txt > manifest.txt'.encode('utf-8')
    new = ('git show <коммит этого файла>:' + 'zavod/ops/zprobe_pins_b14.txt > manifest.txt').encode('utf-8')
    assert text.count(old) == 1, 'manifest comment line'
    return text.replace(old, new)


B.pins_text = pins_text_b14
B.SH_PATH = P + 'zprobe-release-3.5.5-b14.sh'
B.PIN_KEYS = ([(n, P + n) for n in PROGRAMS] + [(n, P + n) for n in UNITS] + [(n, CELL + n) for n in CELL_KEYS]
              + [('phone_zprobe_series_b14.sh', PHONE_SERIES), ('phone_zprobe_verify.py', PHONE_VERIFY),
                 ('phone_zprobe_rules.py', PHONE_RULES)] + list(PC_KEYS))
STAGE_PHONE = (('phone_zprobe_series_b14.sh', PHONE_SERIES), ('phone_zprobe_verify.py', PHONE_VERIFY),
               ('phone_zprobe_rules.py', PHONE_RULES))
# Шаблон .sh — шаблон B13 (распаковка только в stage, ворота Q, env -i) с именами B14.
_T = B.SH_TEMPLATE
B.SH_TEMPLATE = _T.replace('b13', 'b14').replace('B13', 'B14')
assert B.SH_TEMPLATE.count('\nQ=/var/lib/zavod\n') == 1 and B.SH_TEMPLATE.count('/var/lib/zavod') == 1, 'template Q'
assert 'b13' not in B.SH_TEMPLATE and 'B13' not in B.SH_TEMPLATE and 'zprobe_release_b14.py" "$M"' in B.SH_TEMPLATE, \
    'template'

# Известные суммы файлов отпечатков: B8–B12 — как в сборщике B13; B13 — файл коммита 917893350 и его release_commit.
PIN_FILES = dict(B13B.PIN_FILES)
PIN_FILES[B13_PINS] = '75f15f58683d71e4d37873dda268cb710138cb131e7c188d247f3efc4a665fe9'
B13_RELEASE_COMMIT = '0726d1bd43bbb0dd9d70043ed8985d25c3ae99b9'
B12_RELEASE_COMMIT = B13B.B12_RELEASE_COMMIT
# Закреплённые суммы изменённых модулей — байты коммита ae75fcdc3 (runner v0.18, checks v0.10, journal v0.12,
# zprobe-start v0.14, unstarted v0.4, evidence_send v0.5). Новые байты без нового аудита — выпуск не собирается.
ACCEPTED = {'zprobe_runner.py': '65ebe655f314fa00f6bc4fbbd405dc9855d019c136a4fa3ca653aeed9f56e54a',
            'zprobe_checks.py': '52881660359594df0ea19c26ee3af43bf19df3f08e4a4c9d3b1a8d79e016d7ab',
            'zprobe_journal.py': '0b9143992d269a5db903549c4683877f8dffdf8bfed696c6cc6f572831bf0251',
            'zprobe-start': '528c7ab7c7237c188c817fbc86401c7814215e504759b97cdc64473771c042b3',
            'zprobe_unstarted.py': 'e21d7ba4fc8db894a2b89bd6d46fb5aa800a9f35c04567c51de02ec9f1954cac',
            'zevidence_send.py': '0b1e7e28f5fc5dda7529fd58195e9e82462c1aaf9b81bd1064e93dd8aad9ad01'}
OLD_NAMES = ('probes-b13', 'run-b13@', 'journal-b13@') + B13B.OLD_NAMES


def pins_problem(get):
    """Файлы отпечатков B8–B13 — известные суммы; release_commit B12 и B13 — их коммиты (иначе строка отказа или None)."""
    bad = [p for p, h in sorted(PIN_FILES.items()) if B.sha(get(p)) != h]
    if bad:
        return f'pins files differ from the known B8-B13 sums: {bad}'
    bad = B13B.pins_problem(get)
    if bad:
        return bad
    rc = B9B.parse(get(B13_PINS)).get('release_commit')
    return None if rc == B13_RELEASE_COMMIT else f'B13 pins release_commit {rc} is not {B13_RELEASE_COMMIT}'


def unchanged_problem(get):
    """Модули «без изменений» и файлы телефона verify/rules равны отпечаткам B13; первые четыре — и B10/B12 (как в B13)."""
    bad = B13B.unchanged_problem(get)
    if bad:
        return bad
    p13 = B9B.parse(get(B13_PINS))
    bad = [n for n in UNCHANGED if n not in p13 or B.sha(get(P + n)) != p13[n]]
    for k, p in (('phone_zprobe_verify.py', PHONE_VERIFY), ('phone_zprobe_rules.py', PHONE_RULES)):
        if k not in p13 or B.sha(get(p)) != p13[k]:
            bad.append(k)
    return f'unchanged modules differ from B13 pins: {bad}' if bad else None


def accepted_problem(get):
    """Изменённые модули — ровно закреплённые суммы ACCEPTED (иначе строка отказа или None)."""
    bad = [n for n in sorted(ACCEPTED) if B.sha(get(P + n)) != ACCEPTED[n]]
    return f'changed modules differ from the accepted sums: {bad}' if bad else None


def old_names_problem(get):
    """Имена b13 и b10 вне комментариев (строк с «#» первым знаком) в 12 программах и 2 службах — отказ."""
    found = []
    for n in PROGRAMS + UNITS:
        text = get(P + n).decode('utf-8')
        for name in OLD_NAMES:
            c = sum(ln.count(name) for ln in text.split('\n') if not ln.lstrip().startswith('#'))
            if c:
                found.append(f'{n}:{name}x{c}')
    return f'unexpected old b13/b10 names outside comments: {found}' if found else None


def stage_problem(tar_bytes, pins):
    """Готовый tar несёт все четыре файла телефона по путям проекта, суммы трёх равны ключам отпечатков, файл отпечатков
    B14 в нём — те же байты, что собранные отпечатки (иначе строка отказа или None)."""
    import io
    import tarfile
    want = B9B.parse(pins)
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as t:
            got = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
    except (tarfile.TarError, OSError) as e:
        return f'package tar unreadable: {type(e).__name__}'
    bad = [p for k, p in STAGE_PHONE if p not in got or B.sha(got[p]) != want.get(k)]
    if B.PINS_PATH not in got or got[B.PINS_PATH] != pins:
        bad.append(B.PINS_PATH)
    return f'stage package lacks or changes phone files: {bad}' if bad else None


# Клетка, rules телефона, файлы компьютера — те же проверки, что в B13 (равенство отпечаткам B10).
cell_problem, phone_rules_problem, pc_problem = B13B.cell_problem, B13B.phone_rules_problem, B13B.pc_problem


def source_problem(get):
    """Все проверки, не требующие установщика (первая найденная — строка отказа, иначе None)."""
    return (pins_problem(get) or unchanged_problem(get) or accepted_problem(get) or old_names_problem(get)
            or cell_problem(get) or phone_rules_problem(get) or pc_problem(get))


LAST = {}


def build(root, commit):
    """Сборка B14: проверки источников, затем оригинальная сборка (без установщика b14 она откажет «нет файла»)."""
    get = lambda p: B.blob(root, commit, p)  # noqa: E731
    bad = source_problem(get)
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad)
    pins, tar, sh_b = B9B._build(root, commit)
    bad = stage_problem(tar, pins)
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad)
    LAST.update(pins=pins, tar=tar, sh=sh_b, get=get)
    return pins, tar, sh_b


def main():
    rc = B.main()
    if LAST:
        g, s = LAST['get'], B.sha
        print(f'RELEASE_B14_REPORT sh_sha256={s(LAST["sh"])} tar_sha256={s(LAST["tar"])} pins_b14_sha256={s(LAST["pins"])} '
              f'phone_zprobe_series_b14.sh={s(g(PHONE_SERIES))} phone_zprobe_verify.py={s(g(PHONE_VERIFY))} '
              f'phone_zprobe_rules.py={s(g(PHONE_RULES))}')
    return rc


B.build = build
if __name__ == '__main__':
    sys.exit(main())
