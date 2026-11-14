#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/phone/zprobe_verify.py
# ВЕРСИЯ: v0.13 (выпуск B9)  СТАТУС: DRAFT
# v0.13 (2026-11-14 10:43 +02:00, проект B9 v0.9 раздел 2): серия принимается только при строке подтверждения сервера.
#   В папке серии (рядом с journal) обязателен start.out — вывод zprobe-start B9; в нём ровно одна строка
#   «ZPROBE_START CONFIRMED series=<серия> …», и её seg, seq и last_sha256 совпадают с тем, что телефон сам
#   вычислил по целому сегменту серии (функция confirmed_problem). Проверки verdict B8 и их порядок не менялись.
# v0.12 (2026-11-13 08:47 +02:00, аудит R12 M-R12-01): в режиме приёмки manifest.txt, refs_before.txt, refs_after.txt и якорь
#   (anchor_in.txt или «-») — только файлы корня серии: без «..», не ссылки и не junction, путь = <корень>/<имя>;
#   все входы читаются read_plain (NEW_NEGATIVE_R12_N01 — внешний снимок, N02 — внешний манифест).
# v0.11 (2026-11-13 08:32 +02:00, аудит R11): M-R11-01 в путях journal и --fetch запрещён «..» (через ссылку он уводит в
#   чужую папку, а abspath это скрывает — NEW_NEGATIVE_R11_N01); журнал читается только по проверенному пути
#   <корень>/journal, не по исходному аргументу; L-R11-01 на Windows ссылки и junction ищутся по признаку точки
#   повторной обработки (reparse point) у каждой папки пути, а не сравнением текстов путей (короткие имена 8.3 не
#   мешают); имя папки серии берётся настоящее (из списка папки-родителя) и обязано точно совпасть с серией.
# v0.10 (2026-11-13 08:17 +02:00, аудит R10): M-R10-01 корень серии и все папки над ним — не ссылки и не junction (связка
#   папок Windows), настоящий путь корня = абсолютному (NEW_NEGATIVE_R10_N01); M-R10-02 в режиме приёмки пути и
#   ссылки проверяются до чтения журнала и отметок, файлы открываются без перехода по ссылке (O_NOFOLLOW, где есть)
#   и только обычные — чужой файл не читается и его отпечаток не печатается (NEW_NEGATIVE_R10_N02).
# v0.9 (2026-11-13 07:55 +02:00, аудит R9): M-R9-01 программа не пишет кеш Python (sys.dont_write_bytecode до импорта правил;
#   в командах ещё и python3 -I -B) — в programs/ не появляется __pycache__ и верная серия не отвергается
#   (NEW_NEGATIVE_R9_01); M-R9-02 один корень серии — папка, где лежит journal (без раскрытия ссылок): её имя =
#   имя серии, journal, started, fetch.txt, programs.sha256, programs и файлы в них — не ссылки и не уводят из
#   корня; отметки начала читаются из того же корня (NEW_NEGATIVE_R9_02).
# v0.8 (2026-11-13 07:38 +02:00, аудит R8): M-R8-01 fetch.txt берётся только из папки серии, где лежит переданный journal:
#   путь --fetch обязан совпасть с <папка серии>/fetch.txt (realpath), иначе НЕВЕРНО (NEW_NEGATIVE_R8_N01);
#   M-R8-02 programs/ той же папки — ровно три файла (не ссылки), SHA-256 каждого по настоящим байтам = строке
#   programs.sha256 = манифесту; нет файла, лишний файл, другой байт — НЕВЕРНО (NEW_NEGATIVE_R8_N02).
# v0.7 (2026-11-13 07:24 +02:00, аудит R7 M-R7-01): приёмка шага на компьютере (--refs) требует ещё --fetch <fetch.txt>:
#   ровно «ZPROBE_FETCH ssh_rc=0 started_rc=0 journal_rc=0», иначе НЕВЕРНО; и programs.sha256 рядом с journal —
#   ровно три строки, суммы zprobe_verify.py и zprobe_rules.py = phone_* манифеста, zprobe_pins.txt = SHA-256
#   самого манифеста (манифест — 4-й аргумент: git show <коммит выпуска>:zavod/ops/zprobe_pins.txt).
# v0.6 (2026-11-13 05:59 +02:00, аудит R5): M-R5-03 рядом с копией journal — копия папки started (отметки начала
#   серий): серия без своей отметки — НЕВЕРНО; отметка без целого сегмента — «серия прервана»; недописанных
#   сегментов больше, чем отмеченных и не записанных серий, — НЕВЕРНО; M-R5-01 ключ --refs <до> <после>: снимки
#   веток сверяются (R.refs_problem) со временем прогона из записи START этой копии журнала, а не с набранной
#   строкой — так шаг принимается на компьютере по копии папки серии с телефона.
# v0.5 (2026-11-12 23:41 +02:00, аудит R4): журнал — папка сегментов, цепочка R.journal_chain (M-R4-04); якорь —
#   «число сегментов и SHA-256 описи» R.segments_digest; окно попытки session_window идёт в правила (C-R4-01,
#   M-R4-03); при «ВЕРНО» печатается строка ZPROBE_TIMES (серия, вызов, начало и конец прогона, SHA-256 pins) —
#   её проверяет на компьютере zprobe_refs_check.py против снимков веток (M-R4-01, L-R4-02); ключи pins pc_* —
#   программы компьютера, в отпечатки сервера не входят.
# v0.4 (2026-11-12 23:14 +02:00, аудит R3): номера строк сеанса session_seq идут в правила (M-R3-04); COMPLETE
#   засчитывается только при уборке SAFE в SERIES_END (M-R3-03); строки ядра kernel_log — в START (R.start_problem).
# ДАТА СОЗДАНИЯ: 2026-11-12 19:05 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-12 19:50 +02:00 (v0.3 по аудиту R2: полная
#   опись и форма START через R.start_problem (C-02, L-08), привязка попытки к назначению в R.judge (C-01), сверка
#   SHA-256 своих программ телефона с pins phone_* до проверки (L-09), любая ошибка типа — «НЕВЕРНО»). Прежняя (v0.2: аудит ChatGPT STAGE355 R1 —
#   точный перечень проб и попыток без пропусков, лишних и повторов, пустой перечень — отказ (M-03); исход каждой
#   попытки пересчитывается по сырым фактам правилами zprobe_rules.py (C-01); сверка отпечатков кода, аренды, шага,
#   окружения, здоровья посредника (M-09); якорь телефона — прежний журнал должен быть началом нового (C-02);
#   неверная строка — «НЕВЕРНО», а не сбой программы (L-11))
# ИСПОЛНИТЕЛЬ: Claude (чаты 87eee078-952e-4855-8936-7f4d449aa9ac, c7307e9c-8e0e-4e24-997c-12d9fd3b0c71)
# НАЗНАЧЕНИЕ: проверка журнала проб на телефоне оператора (Termux), протокол Завода v4 ред12, И.13 п. 3;
#   DESIGN_3_5_5_PB1_v0_2.md, раздел 6. Печатает «ВЕРНО» или «НЕВЕРНО: <причина>», затем chain=OK|BAD и
#   anchor=<байты>:<sha256>. Ничего не пишет: якорь обновляет zprobe_series.sh только при chain=OK.
# ВЫЗОВ: python3 -I -B zprobe_verify.py <папка journal> <серия> <вызов> <zprobe_pins.txt> <anchor.txt|->
#          [--refs refs_before.txt refs_after.txt --fetch fetch.txt]   (папки started, programs.sha256 — рядом с journal)
import hashlib
import json
import os
import re
import stat
import sys

sys.dont_write_bytecode = True           # R9 M-01: импорт правил не создаёт programs/__pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_rules as R  # noqa: E402

ZERO = '0' * 64


def read_pins(path):
    pins = {}
    if True:                              # R12: без перехода по ссылке, только обычный файл
        for ln in read_plain(path).decode('utf-8').splitlines():
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                k, v = ln.split()
                pins[k] = v
    return pins


def read_plain(p):
    """R10 M-02: файл открывается без перехода по ссылке (O_NOFOLLOW, где есть) и только обычный; иначе ValueError."""
    if os.path.islink(p) or _isjunction(p):
        raise ValueError('link instead of a file')
    fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    with os.fdopen(fd, 'rb') as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise ValueError('not a plain file')
        return f.read()


def _isjunction(p):
    return getattr(os.path, 'isjunction', lambda q: False)(p)


def read_segments(path):
    """Копия папки журнала с сервера: только NNNNNN.jsonl и .lock; иначе ValueError."""
    out = []
    for n in sorted(os.listdir(path)):
        if n == '.lock':
            continue
        if not R.SEG_NAME.match(n):
            raise ValueError('foreign file in journal')
        out.append((n, read_plain(os.path.join(path, n))))
    return out


def read_markers(path):
    """Копия папки отметок начала: имя файла — имя серии, содержимое — строка ZPROBE_STARTED; иначе ValueError."""
    out = {}
    for n in sorted(os.listdir(path)):
        if not R.SERIES_NAME.match(n):
            raise ValueError('foreign file in started')
        out[n] = read_plain(os.path.join(path, n))
    return out


def marker_problem(recs, broken, markers, series, challenge):
    """R5 M-03: серия отмечена с тем же вызовом; каждому недописанному сегменту есть отмеченная, но не записанная
    серия; своя отмеченная, но не записанная серия — «прервана»."""
    if markers.get(series) != f'ZPROBE_STARTED series={series} challenge={challenge}\n'.encode('ascii'):
        return 'series not reserved with this challenge'
    written = {r.get('series') for r in recs}
    orphan = [n for n in markers if n not in written]
    if len(broken) > len(orphan):
        return 'torn segment not matched to a reserved series'
    if series in orphan:
        return 'series interrupted: no complete segment'
    return None


def self_problem(pins):
    """R2 L-09: программы телефона должны совпасть с доверенным манифестом до любой проверки."""
    for key, path in (('phone_zprobe_verify.py', os.path.abspath(__file__)), ('phone_zprobe_rules.py', R.__file__)):
        with open(path, 'rb') as f:
            if pins.get(key) != hashlib.sha256(f.read()).hexdigest():
                return f'{key} differs from pins (phone program not trusted)'
    return None


def series_check(recs, series, challenge, pins):
    try:
        return _series_check(recs, series, challenge, pins)
    except (KeyError, TypeError, ValueError, AttributeError) as e:   # R2 L-08: не авария, а отказ
        return 'malformed series record: ' + type(e).__name__


def _series_check(recs, series, challenge, pins):
    idx = [i for i, r in enumerate(recs) if r.get('series') == series]
    if not idx:
        return 'series not found'
    if idx != list(range(idx[0], idx[-1] + 1)):
        return 'series records are not contiguous'
    mine = [recs[i] for i in idx]
    start, end, atts = mine[0], mine[-1], mine[1:-1]
    if start.get('kind') != 'SERIES_START' or end.get('kind') != 'SERIES_END':
        return 'series must be START … END'
    if any(r.get('kind') != 'ATTEMPT' for r in atts):
        return 'unknown or repeated START/END inside series'
    if any(r.get('challenge') != challenge for r in mine):
        return 'foreign challenge in series'
    if end.get('status') != 'COMPLETE':
        return f"series {end.get('status')}: {end.get('reason')}"
    cb = R.cleanup_problem(end.get('cleanup'))      # R3 M-03: COMPLETE только после подтверждённой уборки
    if cb:
        return 'series cleanup not proven: ' + cb
    if end.get('records') != len(mine) - 1:
        return 'SERIES_END record count does not match'
    if start.get('probes') != R.PROBES:
        return f"probe list must be exactly {R.PROBES}"
    code = start.get('code_sha256')
    want = {k: v for k, v in pins.items() if k != 'release_commit' and not k.startswith(('phone_', 'pc_'))}
    if code != want:
        return 'code fingerprints differ from pins'
    if (start.get('release') or {}).get('commit') != pins.get('release_commit'):
        return 'release commit differs from pins'
    if (start.get('control') or {}).get('proxy_health') != 'OK':
        return 'proxy health not confirmed'
    if start.get('lease_state') != 'INTERRUPTED':
        return f"probe lease state {start.get('lease_state')}"
    bad = R.start_problem(start)
    if bad:
        return bad
    names = [r.get('name') for r in atts]
    exp = R.expected(start)
    if len(names) != len(set(names)):
        dup = sorted({n for n in names if names.count(n) > 1})[0]
        return f'duplicate attempt {dup}'
    if set(names) != set(exp):
        miss, extra = sorted(set(exp) - set(names)), sorted(set(names) - set(exp))
        return f'attempt {miss[0]} missing' if miss else f'attempt {extra[0]} outside the matrix'
    ctx = {'lease': start.get('lease'), 'control': start.get('control'), 'proxy_log': start.get('proxy_log', []),
           'start': start}
    judged = R.judge([dict({'name': r['name'], 'kind': r.get('attempt_kind'), 'facts': r.get('facts'),
                            'window': r.get('session_window')},
                           **({'seq': r['session_seq']} if 'session_seq' in r else {})) for r in atts], ctx)
    env = hashlib.sha256(json.dumps(start.get('env'), sort_keys=True).encode()).hexdigest()
    for r, (name, oc, why) in zip(atts, judged):
        if r.get('outcome') != oc:
            return f'{name}: recorded {r.get("outcome")}, rules give {oc} ({why})'
        if oc not in R.allowed(name):
            return f'{name} = {oc} ({why})'
        if r.get('step') != R.step_of(name) or r.get('lease') != start.get('lease') or r.get('env') != env \
                or r.get('code_sha256') != code.get('pb1_session.py') or r.get('probe') != 'ПБ-1':
            return f'{name}: step, lease, env, probe or code fingerprint mismatch'
    return None


def verdict(segments, series, challenge, pins, anchor, markers=None, refs=None):
    """→ (причина или None, цепочка цела, запись START серии или None). markers — отметки начала (main передаёт
    всегда), refs — (снимок до, снимок после) для приёмки шага."""
    if anchor:
        n, h = anchor
        if len(segments) < n or R.segments_digest(segments[:n])[1] != h:
            return 'journal history differs from phone anchor', False, None
    recs, broken, why, _ = R.journal_chain(segments)
    if why:
        return why, False, None
    why = self_problem(pins)
    if why:
        return why, True, None
    if not any(r.get('series') == series for r in recs):
        key = json.dumps({'series': series}, ensure_ascii=False, separators=(',', ':'))[1:-1].encode('utf-8')
        hit = [n for n, d in segments if n in broken and key in d]
        if hit:
            return f'series interrupted: segment {hit[0]} is not complete', True, None
    if markers is not None:
        why = marker_problem(recs, broken, markers, series, challenge)
        if why:
            return why, True, None
    why = series_check(recs, series, challenge, pins)
    start = next((r for r in recs if r.get('series') == series and r.get('kind') == 'SERIES_START'), None)
    if why is None and refs is not None:
        why = R.refs_problem(refs[0], refs[1], series, challenge, start.get('run_utc'), pins.get('pc_zprobe_refs.sh'))
    return why, True, start


FETCH_OK = 'ZPROBE_FETCH ssh_rc=0 started_rc=0 journal_rc=0'


def confirmed_problem(start_text, segments, series):
    """B9: строка ZPROBE_START CONFIRMED ровно одна и совпадает с целым сегментом серии (seg, seq, last_sha256)."""
    lines = [ln for ln in start_text.splitlines() if ln.startswith('ZPROBE_START CONFIRMED ')]
    if len(lines) != 1:
        return f'zprobe-start CONFIRMED line count is {len(lines)}, must be 1'
    f = dict(x.split('=', 1) for x in lines[0].split() if '=' in x)
    for n, d in segments:
        rows = d.split(b'\n')
        if rows[-1] != b'' or len(rows) < 3:
            continue
        try:
            recs = [json.loads(x) for x in rows[:-1]]
        except ValueError:
            continue
        if recs[0].get('series') == series:
            want = {'series': series, 'seg': n, 'seq': str(recs[-1].get('seq')),
                    'last_sha256': hashlib.sha256(rows[-2]).hexdigest()}
            bad = [k for k, v in want.items() if f.get(k) != v]
            return ('zprobe-start CONFIRMED differs from the journal: ' + ','.join(bad)) if bad else None
    return 'zprobe-start CONFIRMED names a series that has no whole segment'


PROGRAMS = ('zprobe_pins.txt', 'zprobe_rules.py', 'zprobe_verify.py')


def series_root(journal_path):
    """R9 M-02: корень серии — папка, где лежит переданный journal, без раскрытия ссылок (как и для started)."""
    return os.path.dirname(os.path.abspath(journal_path))


def raw_problem(arg):
    """R11 M-01: в пути нет «..» — иначе ссылка в пути уводит в чужую папку, а abspath это скрывает."""
    if '..' in re.split(r'[\\/]+', arg):
        return "path must not contain '..'"
    return None


def _reparse(q):
    """R11 L-01: на Windows — признак точки повторной обработки (ссылка, junction и подобное) у самой папки."""
    try:
        return bool(getattr(os.lstat(q), 'st_file_attributes', 0) & 0x400)
    except OSError:
        return False


def ancestor_problem(root):
    """R10 M-01, R11 L-01: корень серии и все папки над ним — не ссылки и не junction (NEW_NEGATIVE_R10_N01: B/s1 —
    ссылка на исправную A/s1). На Linux ещё настоящий путь корня = абсолютному; на Windows вместо сравнения текстов
    (его ломают короткие имена 8.3 и регистр) — признак reparse point у каждой папки пути."""
    q = os.path.abspath(root)
    if os.name != 'nt' and os.path.realpath(q) != q:
        return 'series folder path goes through a link (give the real folder path)'
    while True:
        if os.path.islink(q) or _isjunction(q) or (os.name == 'nt' and _reparse(q)):
            return 'series folder path goes through a link (give the real folder path)'
        up = os.path.dirname(q)
        if up == q:
            return None
        q = up


def link_problem(root, series):
    """R9 M-02: имя корня = серия; входы приёмки и всё внутри journal, started, programs — не ссылки и не уводят
    из корня (NEW_NEGATIVE_R9_02: journal-ссылка на чужую исправную серию)."""
    base, up = os.path.basename(root), os.path.dirname(root)
    try:                                  # R11 L-01: настоящее имя папки (Windows не различает регистр в пути)
        real = [n for n in os.listdir(up) if os.path.normcase(n) == os.path.normcase(base)]
    except OSError:
        real = [base]
    if base != series or real != [series]:
        return 'series folder name differs from series'
    why = ancestor_problem(root)
    if why:
        return why
    rr = os.path.realpath(root)
    for x in ('journal', 'started', 'fetch.txt', 'programs.sha256', 'programs'):
        q = os.path.join(root, x)
        if os.path.islink(q) or _isjunction(q) or (os.path.lexists(q) and os.path.realpath(q) != os.path.join(rr, x)):
            return f'{x} is a link or leaves the series folder'
    for x in ('journal', 'started', 'programs'):
        q = os.path.join(root, x)
        if os.path.isdir(q):
            for n in os.listdir(q):
                if os.path.islink(os.path.join(q, n)) or _isjunction(os.path.join(q, n)):
                    return f'{x}/{n} is a link'
    return None


SERIES_FILES = {'manifest.txt', 'refs_before.txt', 'refs_after.txt', 'anchor_in.txt'}


def series_inputs(journal_path, fetch_arg, series, others=None):
    """R8 M-01, M-02, R9 M-02: fetch.txt, programs.sha256 и programs/ — только из корня серии, где лежит journal.
    → (причина или None, текст fetch.txt, текст programs.sha256, {имя: SHA-256 настоящих байтов} или None)."""
    why = raw_problem(journal_path) or raw_problem(fetch_arg)   # R11 M-01: до любых путей и чтения
    if why:
        return why, None, None, None
    root = series_root(journal_path)
    if os.path.abspath(journal_path) != os.path.join(root, 'journal'):
        return 'journal must be <series folder>/journal', None, None, None
    why = link_problem(root, series)
    if why:
        return why, None, None, None
    for name, arg in sorted((others or {}).items()):   # R12 M-01: манифест, снимки, якорь — файлы этого корня
        q = os.path.join(root, name)
        if (raw_problem(arg) or os.path.abspath(arg) != q or os.path.islink(q) or _isjunction(q)
                or (os.name == 'nt' and _reparse(q)) or not os.path.isfile(q)):
            return f'{name} is not the plain file of this series folder', None, None, None
    fp = os.path.join(root, 'fetch.txt')
    if os.path.islink(fetch_arg) or os.path.realpath(fetch_arg) != os.path.realpath(fp):
        return 'fetch.txt is not the one of this series folder', None, None, None
    texts = []
    for q in (fp, os.path.join(root, 'programs.sha256')):
        if os.path.isfile(q) and not os.path.islink(q):
            with open(q, encoding='utf-8') as f:
                texts.append(f.read())
        else:
            texts.append(None)
    pd, actual = os.path.join(root, 'programs'), None
    if os.path.isdir(pd) and not os.path.islink(pd) and tuple(sorted(os.listdir(pd))) == PROGRAMS and all(
            os.path.isfile(os.path.join(pd, n)) and not os.path.islink(os.path.join(pd, n)) for n in PROGRAMS):
        actual = {}
        for n in PROGRAMS:
            with open(os.path.join(pd, n), 'rb') as f:
                actual[n] = hashlib.sha256(f.read()).hexdigest()
    return None, texts[0], texts[1], actual


def accept_problem(fetch_text, programs_text, pins, manifest_sha, actual):
    """R7 M-01, R8 M-02: связь телефона с сервером без сбоев; programs/ серии — ровно три файла, их настоящие
    байты = programs.sha256 = манифест выпуска."""
    if fetch_text is None or fetch_text.splitlines() != [FETCH_OK]:
        return 'fetch.txt missing or not all three codes 0 (phone could not fetch the series)'
    want = {'zprobe_verify.py': pins.get('phone_zprobe_verify.py'), 'zprobe_rules.py': pins.get('phone_zprobe_rules.py'),
            'zprobe_pins.txt': manifest_sha}
    got = {}
    for ln in (programs_text or '').splitlines():
        parts = ln.split()
        if len(parts) != 2 or parts[1].lstrip('*') in got:
            return 'programs.sha256 malformed'
        got[parts[1].lstrip('*')] = parts[0]
    if got != want or not all(want.values()):
        return 'programs.sha256 differs from release manifest (series programs not trusted)'
    if actual is None:
        return 'programs/ must hold exactly the three pinned files (missing, extra or link)'
    if actual != want:
        return 'programs/ file bytes differ from programs.sha256 and manifest'
    return None


def times_line(series, challenge, start, pins_path):
    """M-R4-01: строка для компьютера — границы прогона из журнала и SHA-256 доверенного манифеста."""
    with open(pins_path, 'rb') as f:
        ps = hashlib.sha256(f.read()).hexdigest()
    ru = start['run_utc']
    return f'ZPROBE_TIMES series={series} challenge={challenge} run_start={ru[0]} run_end={ru[1]} pins_sha256={ps}'


def main():
    a = sys.argv[1:]
    if len(a) not in (5, 10) or (len(a) == 10 and (a[5] != '--refs' or a[8] != '--fetch')):
        print('НЕВЕРНО: usage zprobe_verify.py <journal dir> <series> <challenge> <pins> <anchor|-> '
              '[--refs refs_before refs_after --fetch fetch.txt]')
        sys.exit(2)
    path, series, challenge, pins_path, anchor_path = a[:5]
    segs, start, refs = [], None, None
    why = None
    try:
        acc, chain_ok = None, False
        if len(a) == 10:                  # R10 M-02: корень, пути и ссылки — до любого чтения журнала и отметок
            oth = {'manifest.txt': pins_path, 'refs_before.txt': a[6], 'refs_after.txt': a[7],
                   'start.out': os.path.join(series_root(path), 'start.out')}
            if anchor_path != '-':
                oth['anchor_in.txt'] = anchor_path
            acc, ft, pt, actual = series_inputs(path, a[9], series, oth)
        if acc is None:                   # R11 M-01: журнал — только по проверенному пути <корень>/journal
            segs = read_segments(os.path.join(series_root(path), 'journal') if len(a) == 10 else path)
            markers = read_markers(os.path.join(series_root(path), 'started'))   # R9 M-02: тот же корень
            if len(a) == 10:
                refs = []
                for p in a[6:8]:
                    refs.append(read_plain(p).decode('utf-8'))
            pins = read_pins(pins_path)
            anchor = None
            if anchor_path != '-' and os.path.exists(anchor_path):
                n, h = read_plain(anchor_path).decode('ascii').split()
                anchor = (int(n), h)
            if refs is not None:          # R7 M-01, R8: коды связи и программы — из папки этой серии
                acc = accept_problem(ft, pt, pins, hashlib.sha256(read_plain(pins_path)).hexdigest(), actual)
            why, chain_ok, start = verdict(segs, series, challenge, pins, anchor, markers, refs)
        why = acc or why
        if why is None:                   # B9 раздел 2: только с подтверждением сервера
            why = confirmed_problem(read_plain(os.path.join(series_root(path), 'start.out')).decode('utf-8'),
                                    segs, series)
    except (OSError, ValueError) as e:
        why, chain_ok, segs = f'cannot read input: {type(e).__name__}', False, []
    n, digest = R.segments_digest(segs)
    what = 'ВЕРНО (журнал и ветки GitHub — шаг принят)' if refs is not None else 'ВЕРНО'
    print((what if why is None else 'НЕВЕРНО: ' + why)
          + f' | chain={"OK" if chain_ok else "BAD"} | anchor={n}:{digest}')
    if why is None:
        print(times_line(series, challenge, start, pins_path))
    sys.exit(0 if why is None else 1)


if __name__ == '__main__':
    main()
