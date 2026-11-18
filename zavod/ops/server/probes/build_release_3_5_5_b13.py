#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5_b13.py
# ВЕРСИЯ: v0.1 (выпуск B13)  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-11-18 13:45 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 13:45 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминал zavod (пускатель); автор, принять не может. Аудитор — ChatGPT.
# НАЗНАЧЕНИЕ: сборка выпуска B13 по проекту DESIGN_B13_RELEASE_v0_3.md (разделы 2, 2.3, 2.5, 3.1 б, 4) из коммита с
#   программами — тем же порядком, что build_release_3_5_5_b12.py (берёт его и через него сборщики B11, B10, B9 и основной):
#   zavod/ops/zprobe_pins_b13.txt — отпечатки B13 (ключи — 12 программ папки probes-b13, две службы, копия отпечатков
#   B9 и три ключа телефона phone_zprobe_series_b13.sh, phone_zprobe_verify.py, phone_zprobe_rules.py);
#   zavod/ops/server/probes/zprobe-release-3.5.5-b13.sh — файл для сервера (шаблон B12 v0.3: распаковка только в stage,
#   ворота Q, env -i; установка — zprobe_release_b13.py). В пакете — отпечатки B8, B9, B10, B11 и B12.
# ОГРАНИЧЕНИЯ: ничего на сервере не делает. Выпуск не собирается, если: 1) файлы отпечатков B8–B12 коммита не равны
#   известным суммам (или release_commit B12 чужой); 2) модуль «без изменений» (pb1_session, zprobe_rules, zprobe_seal,
#   zprobe_export) или phone-файл zprobe_verify.py не равен отпечатку B10 (rules и seal — и B12); 3) изменённый модуль
#   не равен закреплённой ACCEPTED-сумме; 4) в 12 программах и 2 службах найдено «probes-b10», «run-b10@»,
#   «journal-b10@» вне комментариев (допущена одна чужая служба zprobe-run-b10@ в zprobe_checks.py, п. 2.3).
#   Установщика zprobe_release_b13.py пока нет: он в FILES, сборка без него честно отказывает; проверки п. 1–4 —
#   отдельные функции (pins_problem, unchanged_problem, accepted_problem, b10_problem), они его не требуют.
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_release_3_5_5_b12 as B12B  # noqa: E402  — подключает сборщики B9–B12; ниже состав заменяется на B13

B = B12B.B
B9B = B12B.B9B
P = B.PROBES
PROGRAMS = ('pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py', 'zprobe-start',
            'zprobe_dropin.py', 'zprobe_checks.py', 'zprobe_seal.py', 'zprobe_unstarted.py', 'zprobe_export_rules.py',
            'zprobe_export.py', 'zevidence_send.py')              # п. 2.1: набор B10 без zprobe_r2.py
UNITS = ('zprobe-run-b13@.service', 'zprobe-journal-b13@.service')
UNCHANGED = ('pb1_session.py', 'zprobe_rules.py', 'zprobe_seal.py', 'zprobe_export.py')   # п. 2.5: байт в байт опоре
PHONE_DIR = 'zavod/ops/phone/'
PHONE_SERIES = PHONE_DIR + 'zprobe_series_b13.sh'
PHONE_VERIFY = PHONE_DIR + 'zprobe_verify.py'
INSTALLER_CHAIN = B12B.INSTALLER_CHAIN + ('zprobe_release_b13.py',)
B8_PINS, B9_PINS, B10_PINS = B12B.B8_PINS, B12B.B9_PINS, B12B.B10_PINS
B11_PINS, B12_PINS = B12B.B11_PINS, 'zavod/ops/zprobe_pins_b12.txt'
B.VERSION = '3.5.5-b13'
B.FILES = ([P + n for n in PROGRAMS + UNITS + INSTALLER_CHAIN] + [PHONE_SERIES, PHONE_VERIFY]
           + [B8_PINS, B9_PINS, B10_PINS, B11_PINS, B12_PINS])
B.FILES = list(dict.fromkeys(B.FILES))
B.EXEC = {P + n for n in ('zprobe-start', 'zprobe_release.py', 'zprobe_release_b9.py', 'zprobe_release_b10.py',
                          'zprobe_release_b11.py', 'zprobe_release_b12.py', 'zprobe_release_b13.py')} | {PHONE_SERIES}
B.PINS_PATH = 'zavod/ops/zprobe_pins_b13.txt'
B.SH_PATH = P + 'zprobe-release-3.5.5-b13.sh'
B.PIN_KEYS = ([(n, P + n) for n in PROGRAMS] + [(n, P + n) for n in UNITS] + [('zprobe_pins_b9.txt', B9_PINS)]
              + [('phone_zprobe_series_b13.sh', PHONE_SERIES), ('phone_zprobe_verify.py', PHONE_VERIFY),
                 ('phone_zprobe_rules.py', P + 'zprobe_rules.py')])
# Шаблон .sh — B12 v0.3 (распаковка только в stage, ворота Q, env -i) с именами и паспортом B13.
_T = B.SH_TEMPLATE
B.SH_TEMPLATE = (_T.replace('b12', 'b13').replace('B12', 'B13')
                 .replace('(собран build_release_3_5_5_b13.py v0.3', '(собран build_release_3_5_5_b13.py v0.1')
                 .replace('ВЕРСИЯ: v0.3  СТАТУС: DRAFT', 'ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE')
                 .replace('(без служб)', 'и две службы /etc/systemd/system/zprobe-*-b13@.service'))
assert B.SH_TEMPLATE.count('\nQ=/var/lib/zavod\n') == 1 and B.SH_TEMPLATE.count('/var/lib/zavod') == 1, 'template Q'
assert 'b12' not in B.SH_TEMPLATE and 'B12' not in B.SH_TEMPLATE and 'zprobe_release_b13.py" "$M"' in B.SH_TEMPLATE, 'template'

# Известные суммы файлов отпечатков B8–B12 (B8–B11 — те же, что zprobe_release_b12.PINS_FILE_SHA) и коммит B12.
PIN_FILES = {B8_PINS: 'ef5c9962fd5aa15ce11a1832529693bbcbecc85353ed2687b426e5088bc61fe1',
             B9_PINS: '91ed266ae21a3719463a4b49d20c5d9f5ed797cd6dbbdaf9dbbaa60d4fbaa712',
             B10_PINS: 'a86ea709d6de2c789a39efeb047a6fc5f25365a200dc3df39e0d3924aed883db',
             B11_PINS: 'f0a989d642ce1f459ad64b205743b82a8012ace6eac905082ef75b9d759c1089',
             B12_PINS: '5d5b5bb09a9afb008646fa905f4e121e72ef3e6a37b66a8f2b0efe495884596d'}
B12_RELEASE_COMMIT = '20ae4a839adcb6e98babd06f3fa344bce1f17f83'
# Закреплённые ACCEPTED-суммы байтов коммита 123e58422 (zprobe-start v0.13) (изменённые смыслом и только-имена; п. 2.5). Новые байты
# без нового аудита — выпуск не собирается.
ACCEPTED = {'zprobe_dropin.py': '54d1e899fafaaea62e4dc572114c6730861a70fc7299ceaea201da9674c0258b',
            'zprobe_runner.py': '6e8f91ea6a10b44c7a2399c2b64283dbf0869ff42c16a80738f14caba2088838',
            'zprobe_export_rules.py': 'e0fd54ffe5b0ecbe527472908e6538f0a690e15277d8adf51280e4faf5483af2',
            'zprobe_checks.py': 'cdbdaa573d37c8b5a8f8174de2765064bbc4fa896c17c885d51f7b4851d3f24d',
            'zprobe_journal.py': '61561714145bbefde230b723ae79e9bf68d0270908e13cd40cfc2acb0757d770',
            'zprobe-start': 'ddd7eece0d31bba60c28762b4d6c8ad18c3fc51dfdda404431e9e08e55d68dca',
            'zprobe_unstarted.py': 'a6e3a2ec71c69bad0d9703386b97087ac114b783cce4c7ad10489cd102f319ba',
            'zevidence_send.py': '3973c08bb1cbfd49677e0a33adefc92169380de698f2ca4aee8547f30a623216'}
OLD_NAMES = ('probes-b10', 'run-b10@', 'journal-b10@')
# п. 2.3: единственное допущенное вхождение — чужая служба в zprobe_checks (не больше одного).
ALLOWED_B10 = {('zprobe_checks.py', 'run-b10@'): 1}


def pins_problem(get):
    """Файлы отпечатков B8–B12 — известные суммы; release_commit B12 — коммит выпуска B12 (иначе строка отказа или None)."""
    bad = [p for p, h in sorted(PIN_FILES.items()) if B.sha(get(p)) != h]
    if bad:
        return f'pins files differ from the known B8-B12 sums: {bad}'
    rc = B9B.parse(get(B12_PINS)).get('release_commit')
    return None if rc == B12_RELEASE_COMMIT else f'B12 pins release_commit {rc} is not {B12_RELEASE_COMMIT}'


def unchanged_problem(get):
    """Модули «без изменений» равны отпечаткам B10 (и B12, если ключ там есть); phone-файл verify — отпечатку B10."""
    p10, p12 = B9B.parse(get(B10_PINS)), B9B.parse(get(B12_PINS))
    bad = []
    for n in UNCHANGED:
        s = B.sha(get(P + n))
        if n not in p10 or s != p10[n] or (n in p12 and s != p12[n]):
            bad.append(n)
    if 'phone_zprobe_verify.py' not in p10 or B.sha(get(PHONE_VERIFY)) != p10['phone_zprobe_verify.py']:
        bad.append('phone zprobe_verify.py')
    return f'unchanged modules differ from B10/B12 pins: {bad}' if bad else None


def accepted_problem(get):
    """Изменённые модули — ровно закреплённые ACCEPTED-суммы (иначе строка отказа или None)."""
    bad = [n for n in sorted(ACCEPTED) if B.sha(get(P + n)) != ACCEPTED[n]]
    return f'changed modules differ from the accepted sums: {bad}' if bad else None


def b10_problem(get):
    """П. 2.3: «probes-b10», «run-b10@», «journal-b10@» вне комментариев (строк с «#» первым знаком) в 12 программах и
    2 службах — только допущенное число вхождений (иначе строка отказа или None)."""
    found = []
    for n in PROGRAMS + UNITS:
        text = get(P + n).decode('utf-8')
        for name in OLD_NAMES:
            c = sum(ln.count(name) for ln in text.split('\n') if not ln.lstrip().startswith('#'))
            if c > ALLOWED_B10.get((n, name), 0):
                found.append(f'{n}:{name}x{c}')
    return f'unexpected old b10 names outside comments: {found}' if found else None


def source_problem(get):
    """Все проверки, не требующие установщика (первая найденная — строка отказа, иначе None)."""
    return pins_problem(get) or unchanged_problem(get) or accepted_problem(get) or b10_problem(get)


LAST = {}


def build(root, commit):
    """Сборка B13: проверки источников, затем оригинальная сборка (без установщика b13 она откажет «нет файла»)."""
    get = lambda p: B.blob(root, commit, p)  # noqa: E731
    bad = source_problem(get)
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad)
    pins, tar, sh_b = B9B._build(root, commit)
    LAST.update(pins=pins, tar=tar, sh=sh_b, get=get)
    return pins, tar, sh_b


def main():
    rc = B.main()
    if LAST:
        g, s = LAST['get'], B.sha
        print(f'RELEASE_B13_REPORT sh_sha256={s(LAST["sh"])} tar_sha256={s(LAST["tar"])} pins_b13_sha256={s(LAST["pins"])} '
              f'phone_zprobe_series_b13.sh={s(g(PHONE_SERIES))} phone_zprobe_verify.py={s(g(PHONE_VERIFY))} '
              f'phone_zprobe_rules.py={s(g(P + "zprobe_rules.py"))}')
    return rc


B.build = build
if __name__ == '__main__':
    sys.exit(main())
