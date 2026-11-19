#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5_b15.py
# ВЕРСИЯ: v0.2 (выпуск B15)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-19 14:29 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 16:10 +02:00
# v0.2 (REL156 L-355-REL156-01): суммы pb1_session.py v1.1 и zprobe_rules.py v0.15 (правка только текста окна).
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может. Аудитор — ChatGPT.
# НАЗНАЧЕНИЕ: сборка выпуска B15 (REL155 AGREED: связь git push с отказом ядра, записи старта startrec, zprobe-start
#   с --status) тем же порядком, что build_release_3_5_5_b14.py (берёт его и через него сборщики B13…B9 и основной):
#   zavod/ops/zprobe_pins_b15.txt — отпечатки B15 (ключи — 14 программ папки probes-b15: 12 программ B14 и два
#   модуля, которые бегунок, журнал и zprobe-start импортируют, — zprobe_start_status.py и zprobe_recstore.py; две
#   службы -b15@; 4 файла клетки; три ключа телефона phone_zprobe_series_b15.sh, phone_zprobe_verify.py,
#   phone_zprobe_rules.py и три ключа компьютера pc_zprobe_refs.sh, pc_zprobe_refs_check.py, pc_zprobe_rules.py);
#   zavod/ops/server/probes/zprobe-release-3.5.5-b15.sh — файл для сервера (шаблон B14 с именами B15; установка —
#   zprobe_release_b15.py). В пакете — отпечатки B8–B14. zprobe_gitlink.py и zprobe_sockwatch.py в выпуск не входят:
#   их функции встроены байт в байт в zprobe_rules.py и pb1_session.py (проверяют test_zprobe и test_zprobe_gitlink).
# ОГРАНИЧЕНИЯ: ничего на сервере не делает. Выпуск не собирается, если: 1) файлы отпечатков B8–B14 коммита не равны
#   известным суммам (или release_commit B12/B13/B14 чужой); 2) модуль «без изменений» (zprobe_seal, zprobe_export,
#   zprobe_dropin, zprobe_export_rules) и phone zprobe_verify.py не равны отпечаткам B14; 3) изменённый или новый модуль
#   (pb1_session, zprobe_rules, runner, checks, journal, zprobe-start, unstarted, evidence_send, start_status, recstore)
#   не равен закреплённой сумме ACCEPTED; 4) в 14 программах и 2 службах найдены имена b10/b13/b14 вне комментариев;
#   5) клетка — не равна отпечаткам B10; телефонный zprobe_rules.py — не те же байты, что серверный; pc_zprobe_refs.sh и
#   pc_zprobe_refs_check.py — не равны отпечаткам B10 (pc_zprobe_rules.py — серверный zprobe_rules.py, он в ACCEPTED).
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_release_3_5_5_b14 as B14B  # noqa: E402  — подключает сборщики B9–B14; ниже состав заменяется на B15

B13B = B14B.B13B
B = B14B.B
B9B = B14B.B9B
P = B.PROBES
PROGRAMS = B14B.PROGRAMS + ('zprobe_start_status.py', 'zprobe_recstore.py')
UNITS = ('zprobe-run-b15@.service', 'zprobe-journal-b15@.service')
UNCHANGED = ('zprobe_seal.py', 'zprobe_export.py', 'zprobe_dropin.py', 'zprobe_export_rules.py')   # байт в байт B14
PHONE_SERIES = B13B.PHONE_DIR + 'zprobe_series_b15.sh'
PHONE_VERIFY, PHONE_RULES = B14B.PHONE_VERIFY, B14B.PHONE_RULES
PC_KEYS, CELL, CELL_KEYS = B14B.PC_KEYS, B14B.CELL, B14B.CELL_KEYS
INSTALLER_CHAIN = B14B.INSTALLER_CHAIN + ('zprobe_release_b15.py',)
B8_PINS, B9_PINS, B10_PINS, B11_PINS, B12_PINS, B13_PINS = (B14B.B8_PINS, B14B.B9_PINS, B14B.B10_PINS, B14B.B11_PINS,
                                                            B14B.B12_PINS, B14B.B13_PINS)
B14_PINS = 'zavod/ops/zprobe_pins_b14.txt'
B.VERSION = '3.5.5-b15'
B.FILES = ([P + n for n in PROGRAMS + UNITS + INSTALLER_CHAIN] + [PHONE_SERIES, PHONE_VERIFY, PHONE_RULES]
           + [B8_PINS, B9_PINS, B10_PINS, B11_PINS, B12_PINS, B13_PINS, B14_PINS])
B.FILES = list(dict.fromkeys(B.FILES))
B.EXEC = {P + n for n in ('zprobe-start',) + INSTALLER_CHAIN} | {PHONE_SERIES}
B.PINS_PATH = 'zavod/ops/zprobe_pins_b15.txt'


def pins_text_b15(get, commit):
    """Отпечатки как в основном сборщике; строка «Манифест для приёмки» называет файл B15 (как в B13 и B14)."""
    text = B13B._pins_text_base(get, commit)
    old = 'git show <коммит этого файла>:zavod/ops/zprobe_pins.txt > manifest.txt'.encode('utf-8')
    new = ('git show <коммит этого файла>:' + 'zavod/ops/zprobe_pins_b15.txt > manifest.txt').encode('utf-8')
    assert text.count(old) == 1, 'manifest comment line'
    return text.replace(old, new)


B.pins_text = pins_text_b15
B.SH_PATH = P + 'zprobe-release-3.5.5-b15.sh'
B.PIN_KEYS = ([(n, P + n) for n in PROGRAMS] + [(n, P + n) for n in UNITS] + [(n, CELL + n) for n in CELL_KEYS]
              + [('phone_zprobe_series_b15.sh', PHONE_SERIES), ('phone_zprobe_verify.py', PHONE_VERIFY),
                 ('phone_zprobe_rules.py', PHONE_RULES)] + list(PC_KEYS))
STAGE_PHONE = (('phone_zprobe_series_b15.sh', PHONE_SERIES), ('phone_zprobe_verify.py', PHONE_VERIFY),
               ('phone_zprobe_rules.py', PHONE_RULES))
# Шаблон .sh — шаблон B14 (распаковка только в stage, ворота Q, env -i) с именами B15.
_T = B.SH_TEMPLATE
B.SH_TEMPLATE = _T.replace('b14', 'b15').replace('B14', 'B15')
assert B.SH_TEMPLATE.count('\nQ=/var/lib/zavod\n') == 1 and B.SH_TEMPLATE.count('/var/lib/zavod') == 1, 'template Q'
assert 'b14' not in B.SH_TEMPLATE and 'B14' not in B.SH_TEMPLATE and 'zprobe_release_b15.py" "$M"' in B.SH_TEMPLATE, \
    'template'

# Известные суммы файлов отпечатков: B8–B13 — как в сборщике B14; B14 — файл коммита 43451be79 и его release_commit.
PIN_FILES = dict(B14B.PIN_FILES)
PIN_FILES[B14_PINS] = 'f6da444f8e158dada92243139b9286eb70ca1e9aa4110ddd5414e0aeea36fc40'
B14_RELEASE_COMMIT = '3a0f20680119ed858ce2ee17a865840eab2a63bb'
B13_RELEASE_COMMIT, B12_RELEASE_COMMIT = B14B.B13_RELEASE_COMMIT, B14B.B12_RELEASE_COMMIT
# Закреплённые суммы изменённых и новых модулей — байты ветки B15 после REL155 AGREED (pb1_session v1.0, rules v0.14,
# runner v0.20, checks v0.11, journal v0.14, zprobe-start v0.15, start_status v0.3, recstore v0.2; unstarted и
# evidence_send — имена B15). Принимает их раунд REL156; новые байты без нового аудита — выпуск не собирается.
ACCEPTED = {'pb1_session.py': '5ea2e34af5bb7bb76de1db571cd27bf374e67e10e8b62b974e3f740d28815082',
            'zprobe_rules.py': '073040060b1dccda6646bb835ef9f7ea05f9d213d736d0d854e896923dd9e842',
            'zprobe_runner.py': 'cda0590b22d2a5dd9065adf15c90141013a791a3c1954ddb87794d16cd9dad22',
            'zprobe_checks.py': '8d254bc2de769630240a2515bffac17520daf438f2faa3096b5d9b0ccfaecbc0',
            'zprobe_journal.py': 'd85aa8d3ad228f983a8c8f21237342e29c03efb566374302a108cbf8159d1083',
            'zprobe-start': 'c809654c645140261c43f10503b2c7135961e15edc0347e6cb3f5ed50f0affc7',
            'zprobe_unstarted.py': '182f0f4ab3d3a855e491f6546a47e026f70cf4df93fc2c76528a2b51e84c6528',
            'zevidence_send.py': '24a2d87e45ddb13ad077bd255e2273f404b4bc15254f8deb37587bcf3237232e',
            'zprobe_start_status.py': '829bcfc5591c7b22f212ac17d8c863aa5a38b5d9c5d19b15a3c014c2692ddf92',
            'zprobe_recstore.py': '81d9295dae0a6bfca49d507e87dba31adefbf0f8e948c165b42eb0465f19d6b1'}
OLD_NAMES = ('probes-b14', 'run-b14@', 'journal-b14@') + B14B.OLD_NAMES
assert set(ACCEPTED) | set(UNCHANGED) == set(PROGRAMS) and not set(ACCEPTED) & set(UNCHANGED), 'program split'


def pins_problem(get):
    """Файлы отпечатков B8–B14 — известные суммы; release_commit B12, B13, B14 — их коммиты (иначе строка отказа)."""
    bad = [p for p, h in sorted(PIN_FILES.items()) if B.sha(get(p)) != h]
    if bad:
        return f'pins files differ from the known B8-B14 sums: {bad}'
    bad = B14B.pins_problem(get)
    if bad:
        return bad
    rc = B9B.parse(get(B14_PINS)).get('release_commit')
    return None if rc == B14_RELEASE_COMMIT else f'B14 pins release_commit {rc} is not {B14_RELEASE_COMMIT}'


def unchanged_problem(get):
    """Модули «без изменений» и phone zprobe_verify.py равны отпечаткам B14 (иначе строка отказа или None)."""
    p14 = B9B.parse(get(B14_PINS))
    bad = [n for n in UNCHANGED if n not in p14 or B.sha(get(P + n)) != p14[n]]
    if 'phone_zprobe_verify.py' not in p14 or B.sha(get(PHONE_VERIFY)) != p14['phone_zprobe_verify.py']:
        bad.append('phone_zprobe_verify.py')
    return f'unchanged modules differ from B14 pins: {bad}' if bad else None


def accepted_problem(get):
    """Изменённые и новые модули — ровно закреплённые суммы ACCEPTED (иначе строка отказа или None)."""
    bad = [n for n in sorted(ACCEPTED) if B.sha(get(P + n)) != ACCEPTED[n]]
    return f'changed modules differ from the accepted sums: {bad}' if bad else None


def old_names_problem(get):
    """Имена b14, b13 и b10 вне комментариев (строк с «#» первым знаком) в 14 программах и 2 службах — отказ."""
    found = []
    for n in PROGRAMS + UNITS:
        text = get(P + n).decode('utf-8')
        for name in OLD_NAMES:
            c = sum(ln.count(name) for ln in text.split('\n') if not ln.lstrip().startswith('#'))
            if c:
                found.append(f'{n}:{name}x{c}')
    return f'unexpected old b14/b13/b10 names outside comments: {found}' if found else None


def phone_rules_problem(get):
    """B15: телефонный zprobe_rules.py — те же байты, что серверный (а серверный — в ACCEPTED)."""
    ok = B.sha(get(PHONE_RULES)) == B.sha(get(P + 'zprobe_rules.py'))
    return None if ok else 'phone zprobe_rules.py differs from the server zprobe_rules.py'


def pc_problem(get):
    """Файлы компьютера refs.sh и refs_check.py равны отпечаткам B10; pc_zprobe_rules.py — серверный zprobe_rules.py."""
    p10 = B9B.parse(get(B10_PINS))
    bad = [k for k, p in PC_KEYS if k != 'pc_zprobe_rules.py' and (k not in p10 or B.sha(get(p)) != p10[k])]
    if dict(PC_KEYS).get('pc_zprobe_rules.py') != P + 'zprobe_rules.py':
        bad.append('pc_zprobe_rules.py')
    return f'pc files differ from B10 pins: {bad}' if bad else None


def stage_problem(tar_bytes, pins):
    """Готовый tar несёт файлы телефона B15 по путям проекта, суммы трёх равны ключам отпечатков, файл отпечатков B15 в
    нём — те же байты, что собранные отпечатки (иначе строка отказа или None)."""
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


# Клетка — та же проверка, что в B13 и B14 (равенство отпечаткам B10).
cell_problem = B13B.cell_problem


def source_problem(get):
    """Все проверки, не требующие установщика (первая найденная — строка отказа, иначе None)."""
    return (pins_problem(get) or unchanged_problem(get) or accepted_problem(get) or old_names_problem(get)
            or cell_problem(get) or phone_rules_problem(get) or pc_problem(get))


LAST = {}


def build(root, commit):
    """Сборка B15: проверки источников, затем оригинальная сборка (без установщика b15 она откажет «нет файла»)."""
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
        print(f'RELEASE_B15_REPORT sh_sha256={s(LAST["sh"])} tar_sha256={s(LAST["tar"])} pins_b15_sha256={s(LAST["pins"])} '
              f'phone_zprobe_series_b15.sh={s(g(PHONE_SERIES))} phone_zprobe_verify.py={s(g(PHONE_VERIFY))} '
              f'phone_zprobe_rules.py={s(g(PHONE_RULES))}')
    return rc


B.build = build
if __name__ == '__main__':
    sys.exit(main())
