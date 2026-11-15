#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_verify_export.py (программа ПК, версия 1)
# ВЕРСИЯ: v0.6 (выпуск B10)  СТАТУС: DRAFT
# v0.6 (2026-11-15 12:48, терминал zavod, сменщик 3a6de98b; REL69 M-01): метка .pending есть на КАЖДОЙ ветке
#   state_persist_uncertain. Сбой последнего fsync папки (уже после снятия метки) → метка ставится заново;
#   если и это не удалось — причина с хвостом :marker_lost и строка STATE_PENDING none.
# v0.5 (2026-11-15 12:01, терминал zavod, сменщик 3a6de98b; REL68): M-01 — межпроцессная блокировка истории ПК
#   (<история>.lock: Windows — msvcrt.locking, иначе fcntl.flock) берётся ДО чтения истории и держится до конца
#   записи; чтение и сверка n/seq идут под ней; сбой блокировки → FAIL state_lock. M-02 — точка фиксации записи
#   истории = os.replace. До неё: копия прежнего файла <история>.prev и метка <история>.pending; сбой → FAIL
#   state_persist, прежняя история не тронута. После неё сбой fsync папки, чтения или снятия метки → FAIL
#   state_persist_uncertain: о прежней истории ничего не утверждается, печатается путь копии, метка остаётся,
#   следующие запуски дают FAIL state:uncertain, пока человек не сверит файлы и не уберёт метку.
# v0.4 (2026-11-15, терминал zavod, сменщик cb6b67c5; REL67): M-01 — число сегментов журнала сверяется до перебора
#   (предел MAX_LINES в check_bundle); M-02 — архив принимается только байт в байт равным каноническому
#   (canonical_tar = zevidence_send.tar_bytes): PAX/GNU-заголовки, иные поля и хвост → FAIL tar:not_canonical;
#   M-03 — история пишется (уникальный временный файл, fsync, replace, повторное чтение) ДО печати итога;
#   сбой записи → FAIL state_persist, код 1, без PASS.
# v0.3 (2026-11-15, терминал zavod, сменщик cb6b67c5; REL66): M-01 — у запечатанного пакета без --seal-sha итог
#   не выше INCOMPLETE (phone_seal_sha_absent), --seal-sha не 64 hex → FAIL; M-02 — --state обязателен,
#   нет записи серии → нужен --init (FIRST_RECEIPT), без истории итог не выше INCOMPLETE (history_absent),
#   битый файл истории → FAIL; M-03 — каталоги архива только корень и предки файлов, предел заголовков и
#   размера потока; L-01 — 2 МБ считаются по ВСЕМ файлам, вместе с MANIFEST.sha256 и READY.
# v0.2 (2026-11-15, терминал zavod, чат cb6b67c5; REL65 M-05): архив читается потоком, пределы числа файлов,
#   размера каждого, суммы и глубины проверяются до чтения файла. REL65 M-01: журнал CHAIN_HASH_ONLY —
#   цепочка — утверждение root (предупреждение journal_chain_root_claim), байтов журнала на ПК нет.
# ДАТА СОЗДАНИЯ: 2026-11-15 00:00 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 5 п.5 — проверка очищенного пакета на ПК (архив tar от zevidence-send).
#   Инварианты а–е; итог — первый подходящий из FAIL > INCOMPLETE > UNSEALED > PASS_SANITIZED. Таблицы и
#   разборщики — те же, что у сервера (zprobe_export_rules.py, zprobe_seal.py, zprobe_rules.py).
# ВЫЗОВ: python -I zprobe_verify_export.py <архив.tar> <серия> --state <файл истории ПК> [--init]
#        [--seal-sha <hex строки lease_seal с телефона>]
#   Файл истории — JSON {серия: {"n": .., "journal_last_seq": ..}}; меньшее значение → FAIL (откат). Нет файла
#   или записи серии — только с --init (первый приём, предупреждение FIRST_RECEIPT); --init при уже записанной
#   серии — ошибка вызова (код 2). Обновляется при итоге не FAIL и только если сумма печати сверена с телефоном
#   (или пакет не запечатан).
# ЧЕСТНАЯ ГРАНИЦА (пишется в отчёт): PASS_SANITIZED — полная внутренняя согласованность описи, proof и выгрузки;
#   что опись перечисляет всё, что было в папке сервера, ПК доказать не может (это утверждение root). Суммы HASH_ONLY
#   и строка телефона приходят от того же сервера.
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
import io
import errno
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_export_rules as E  # noqa: E402
import zprobe_seal as S  # noqa: E402

BOUNDARY = ('Честная граница: PASS_SANITIZED — полная внутренняя согласованность описи и выгрузки, '
            'а не независимое чтение папки сервера; суммы HASH_ONLY и строка телефона — от того же сервера.')
RANK = ('FAIL', 'INCOMPLETE', 'UNSEALED', 'PASS_SANITIZED')


class Fail(Exception):
    pass


def limit_of(rel):
    """Предел одного файла пакета: MANIFEST — 1 МБ, READY — 128 байт, остальные — E.MAX_FILE (256 КБ)."""
    return {'MANIFEST.sha256': 1 << 20, 'READY': 128}.get(rel, E.MAX_FILE)


TOTAL_CAP = E.MAX_TOTAL                       # REL66 L-01: сумма ВСЕХ файлов пакета (с MANIFEST и READY) ≤ 2 МБ
MAX_DEPTH = 3                                 # sealed/source/<имя> — глубже в пакете ничего нет
MAX_HEADERS = 64                              # REL66 M-03: заголовков tar (файлы + каталоги) не больше
MAX_TAR_BYTES = TOTAL_CAP + MAX_HEADERS * 1024 + 20480   # поток: данные + заголовки и выравнивание + конец
HEX64 = re.compile(r'[0-9a-f]{64}')
LOCK_WAIT = 30.0                              # REL68 M-01: сколько секунд ждать чужую блокировку истории


def read_tar(path, series):
    """а) архив: только папки и обычные файлы под <серия>/<n>/, без «..», ссылок и повторов. → (n, {путь: байты}).
    Пределы (REL65 M-05) — ДО чтения каждого файла и потоком, без getmembers целиком: ≤ E.MAX_FILES файлов,
    каждый ≤ своего предела, сумма ≤ TOTAL_CAP, глубина ≤ MAX_DEPTH; иначе FAIL. REL66 M-03: размер архива
    ≤ MAX_TAR_BYTES до открытия, заголовков ≤ MAX_HEADERS; каталог допустим только корень <серия>/<n> и предок
    принятого файла, без повторов; лишний, пустой или слишком глубокий каталог → FAIL."""
    files, n, total, dirs, heads = {}, None, 0, set(), 0
    if os.path.getsize(path) > MAX_TAR_BYTES:
        raise Fail('tar:stream_size')
    with tarfile.open(path, mode='r:') as tf:
        for m in tf:
            heads += 1
            if heads > MAX_HEADERS:
                raise Fail('tar:headers')
            parts = m.name.split('/')
            if len(parts) < 2 or parts[0] != series or not re.fullmatch(r'[1-9][0-9]{0,3}', parts[1]) \
                    or any(p in ('', '.', '..') for p in parts):
                raise Fail(f'tar:name:{m.name}')
            if n is None:
                n = int(parts[1])
            elif int(parts[1]) != n:
                raise Fail('tar:two_roots')
            if m.isdir():
                drel = '/'.join(parts[2:])
                if drel in dirs or len(parts) - 2 >= MAX_DEPTH:
                    raise Fail(f'tar:dir:{drel}')
                dirs.add(drel)
                continue
            if not m.isreg():
                raise Fail(f'tar:type:{m.name}')
            rel = '/'.join(parts[2:])
            if rel in files:
                raise Fail(f'tar:duplicate:{rel}')
            total += m.size
            if len(parts) - 2 > MAX_DEPTH or len(files) + 1 > E.MAX_FILES or m.size > limit_of(rel) \
                    or total > TOTAL_CAP:
                raise Fail(f'tar:limits:{rel}')
            data = tf.extractfile(m).read(m.size + 1)
            if len(data) != m.size:
                raise Fail(f'tar:size:{rel}')
            files[rel] = data
    if n is None:
        raise Fail('tar:empty')
    allowed = {''} | {'/'.join(k.split('/')[:i]) for k in files for i in range(1, k.count('/') + 1)}
    extra = sorted(dirs - allowed)
    if extra:
        raise Fail(f'tar:dir:{extra[0]}')
    with open(path, 'rb') as f:                    # REL67 M-02: размер уже ≤ MAX_TAR_BYTES
        if f.read(MAX_TAR_BYTES + 1) != canonical_tar(series, n, files):
            raise Fail('tar:not_canonical')
    return n, files


def canonical_tar(series, n, files):
    """REL67 M-02: та же сериализация, что zevidence_send.tar_bytes (USTAR, каталоги-предки, режимы 0755/0644,
    время 0, хозяин 0, без имён). Архив, отличный хоть одним байтом (PAX, GNU, поля, хвост), не принимается."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.USTAR_FORMAT) as tf:
        dirs = set()
        for path in sorted(files):
            parts = path.split('/')[:-1]
            for i in range(len(parts) + 1):
                d = '/'.join([series, str(n)] + parts[:i])
                if d not in dirs:
                    dirs.add(d)
                    ti = tarfile.TarInfo(d)
                    ti.type, ti.mode, ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = \
                        tarfile.DIRTYPE, 0o755, 0, 0, 0, '', ''
                    tf.addfile(ti)
            ti = tarfile.TarInfo(f'{series}/{n}/{path}')
            ti.size, ti.mode, ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = len(files[path]), 0o644, 0, 0, 0, '', ''
            tf.addfile(ti, io.BytesIO(files[path]))
    return buf.getvalue()


def verify(n, files, series, seal_sha=None, history=None, first=False):
    """→ (итог, причины, предупреждения, HASH_ONLY-строки). REL66 M-02: history — принятая запись серии ПК;
    нет её и first=False → итог не выше INCOMPLETE (history_absent). REL66 M-01: запечатанный пакет без
    seal_sha → итог не выше INCOMPLETE (phone_seal_sha_absent)."""
    warn, why = [], []
    try:
        if seal_sha is not None and not (isinstance(seal_sha, str) and HEX64.fullmatch(seal_sha)):
            raise Fail('e:phone_seal_sha_format')
        man, ready = files.get('MANIFEST.sha256'), files.get('READY')
        if man is None or ready != (hashlib.sha256(man).hexdigest() + '\n').encode('ascii'):
            raise Fail('a:READY')
        rows = E.parse_manifest(man)
        phys = {f'{p}/{nm}': (o, osz) for m, p, nm, r, rsz, o, osz in rows if m != 'HASH_ONLY'}
        if set(files) != set(phys) | {'MANIFEST.sha256', 'READY'}:
            raise Fail('a:set')
        for path, (o, osz) in phys.items():
            if len(files[path]) != osz or hashlib.sha256(files[path]).hexdigest() != o:
                raise Fail(f'a:out:{path}')
        braw = files.get('package/bundle.json')
        if braw is None:
            raise Fail('e:bundle')
        try:
            b = json.loads(braw)
        except ValueError:
            raise Fail('e:bundle_json')
        if S.canon(b) != braw:
            raise Fail('e:bundle_canon')
        E.check_bundle(b)
        fmt = E.fmt_of(b['matrix'])
        if b['n'] != n or b['series'] != series:
            raise Fail('v:bundle_n_series')
        if history is not None and (n < history.get('n', 0) or (b['journal_last_seq'] is not None and
                                                     b['journal_last_seq'] < history.get('journal_last_seq', 0))):
            raise Fail('v:rollback')
        lid = b['lease_id']
        for m, p, nm, *_ in rows:
            if not E.place_mode_ok(fmt, p, nm, m, b['journal_mode']):
                raise Fail(f'd:mode:{p}/{nm}')
        docs = {'sealed/source': {}, 'final': {}}
        for m, p, nm, *_ in rows:
            if m == 'ALLOW':
                docs[p][nm] = E.check_sanitized(fmt, nm, files[f'{p}/{nm}'])
        names = {p: {nm for m, pp, nm, *_ in rows if pp == p} for p in E.PLACES}
        result = 'PASS_SANITIZED'
        for nm in E.required(fmt, 'final'):
            if nm not in names['final']:
                why.append(f'final_required_absent:{nm}')
                result = 'INCOMPLETE'
        for nm, row in E.NAMES.items():
            if row[1] == 'ALLOW' and E.need(fmt, 'final', nm) == 'opt' and nm not in names['final']:
                warn.append(f'FINAL_OPTIONAL_ABSENT {nm}')
        for place in ('sealed/source', 'final'):
            bad = E.links_problem(fmt, series, lid, docs[place], b)
            if bad:
                raise Fail(f'v:link:{place}:{bad}')
        seal = b['seal']
        proof = None
        if seal is None:
            if names['sealed/source'] or names['sealed/meta'] or names['proof']:
                raise Fail('e:unsealed_has_sealed')
            if result == 'PASS_SANITIZED':
                result = 'UNSEALED'
        else:
            if seal_sha is None:
                why.append('phone_seal_sha_absent')
                if result == 'PASS_SANITIZED':
                    result = 'INCOMPLETE'
            elif seal_sha != seal['proof_sha256']:
                raise Fail('e:phone_seal_sha')
            raw = files.get('proof/proof.json')
            if raw is None or hashlib.sha256(raw).hexdigest() != seal['proof_sha256']:
                raise Fail('e:proof')
            logical = sorted(names['sealed/source'])
            try:
                proof = S.check_proof(raw, series, lid, logical)
            except S.Refused as e:
                raise Fail(f'v:proof:{e}')
            want_meta = {'INVENTORY.sha256', 'MANIFEST.sha256'} if fmt == 'B9R2' else {'INVENTORY.sha256'}
            if names['sealed/meta'] != want_meta:
                raise Fail('e:meta')
            for nm in E.required(fmt, 'source'):
                if nm not in names['sealed/source']:
                    raise Fail(f'e:source_required:{nm}')
            inv_raw = files['sealed/meta/INVENTORY.sha256']
            if hashlib.sha256(inv_raw).hexdigest() != proof['inventory_sha256']:
                raise Fail('v:inventory_sha')
            try:
                inv = S.parse_inventory(inv_raw)
            except S.Refused as e:
                raise Fail(f'v:inventory:{e}')
            man_a = None
            if fmt == 'B9R2':
                mraw = files['sealed/meta/MANIFEST.sha256']
                if hashlib.sha256(mraw).hexdigest() != proof['preserve_manifest_sha256']:
                    raise Fail('v:manifest_a_sha')
                man_a = E.parse_manifest_a(mraw, series, lid.replace('-', ''))
                if sorted(man_a) != logical:
                    raise Fail('v:manifest_a_names')
            if sorted(inv) != logical:
                raise Fail('v:inventory_names')
            bad = E.inventory_b_problem(fmt, series, inv_raw, man_a)
            if bad:
                raise Fail(f'v:{bad}')
            raw_of = {nm: (r, rsz) for m, p, nm, r, rsz, *_ in rows if p == 'sealed/source'}
            for s in proof['sources']:
                if inv[s['name']] != (s['sha256'], s['size']) or raw_of[s['name']] != (s['sha256'], s['size']):
                    raise Fail(f'v:source:{s["name"]}')
            if b['journal_cursor'] != proof['journal_to_cursor']:
                raise Fail('v:journal_cursor')
        anc = docs['sealed/source'].get('anchor_run.json' if fmt == 'B10' else 'anchor.json') \
            or docs['final'].get('anchor_run.json')
        if anc is not None:
            if not (anc['boot_id'] == b['b_probe'] == b['boot_id']):
                raise Fail('v:boot_id')
            curs = [anc['cursor']] if fmt == 'B10' else [anc['cursor_before'], anc['cursor_after']]
            if proof is not None:
                bad = E.cursors_problem(proof, curs, b['b_probe'])
                if bad:
                    raise Fail(f'v:{bad}')
        elif proof is not None and proof['boot_id'] != b['b_probe']:
            raise Fail('v:b_probe')
        segs = sorted(nm for nm in names['journal'])
        if len(segs) != b['journal_segments'] or any(nm != '%06d.jsonl' % i for i, nm in enumerate(segs, 1)):
            raise Fail('g:segments')                # REL67 M-01: без большого списка
        if b['journal_mode'] == 'CHAIN_HASH_ONLY':
            warn.append('journal_chain_root_claim')     # REL65 M-01: цепочку проверил root, байтов на ПК нет
        else:
            why.append('journal_partial_hash_only')
            if result in ('PASS_SANITIZED', 'UNSEALED'):
                result = 'INCOMPLETE'
        if history is None:
            if first:
                warn.append('FIRST_RECEIPT')
            else:
                why.append('history_absent')
                if result in ('PASS_SANITIZED', 'UNSEALED'):
                    result = 'INCOMPLETE'
    except Fail as e:
        return 'FAIL', [str(e)], warn, []
    except E.Refused as e:
        return 'FAIL', [f'refused:{e}'], warn, []
    except (KeyError, TypeError, ValueError) as e:
        return 'FAIL', [f'{type(e).__name__}:{e}'], warn, []
    hashes = [f'{p}/{nm} {r} {rsz}' for m, p, nm, r, rsz, *_ in rows if m == 'HASH_ONLY']
    return result, why, warn, hashes


def load_state(path, series, init):
    """REL66 M-02 → (все записи, запись серии или None). Ошибка вызова → ValueError; битый файл → Fail."""
    if os.path.lexists(path + '.pending'):       # REL68 M-02: прошлая запись не подтверждена
        raise Fail('state:uncertain')
    if not os.path.exists(path):
        if not init:
            raise Fail('state:absent')
        return {}, None
    try:
        with open(path, encoding='utf-8') as f:
            hist_all = json.load(f)
    except (OSError, ValueError) as e:
        raise Fail(f'state:corrupt:{type(e).__name__}')
    if not isinstance(hist_all, dict):
        raise Fail('state:corrupt:type')
    for k, v in hist_all.items():
        if not (E.SERIES.fullmatch(k) and isinstance(v, dict) and set(v) == {'n', 'journal_last_seq'}
                and all(type(v[x]) is int and v[x] >= 0 for x in v) and v['n'] >= 1):
            raise Fail(f'state:corrupt:{k}')
    rec = hist_all.get(series)
    if rec is None and not init:
        raise Fail('state:series_absent')
    if rec is not None and init:
        raise ValueError('--init with recorded series')
    return hist_all, rec


class Uncertain(Exception):
    """REL68 M-02: сбой ПОСЛЕ точки фиксации (os.replace) — что лежит по пути истории, не подтверждено."""


def lock_try(f):
    """Одна попытка взять исключительную блокировку без ожидания; занято или сбой → OSError."""
    if os.name == 'nt':
        import msvcrt
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def lock_state(path):
    """REL68 M-01: исключительная межпроцессная блокировка на постоянном отдельном файле <история>.lock.
    → открытый файл (держать до конца записи истории). Занято дольше LOCK_WAIT или любой иной сбой → Fail."""
    try:
        f = open(path + '.lock', 'a+b')
    except OSError as e:
        raise Fail(f'state_lock:{type(e).__name__}')
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            lock_try(f)
            return f
        except OSError as e:
            busy = e.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK)
            if not busy or time.monotonic() >= deadline:
                f.close()
                raise Fail('state_lock:timeout' if busy else f'state_lock:{type(e).__name__}')
            time.sleep(0.05)


def unlock_state(f):
    try:
        if os.name == 'nt':
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    finally:
        f.close()                                  # закрытие снимает блокировку в обеих ОС


def fsync_dir(d):
    """fsync папки, где ОС это позволяет (в Windows такой операции нет)."""
    if hasattr(os, 'O_DIRECTORY'):
        dfd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)


def write_tmp(d, raw):
    """Свой уникальный временный файл рядом с историей: запись и fsync. → путь."""
    fd, tmp = tempfile.mkstemp(prefix='.zprobe_state_', suffix='.tmp', dir=d)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return tmp


def persist_state(path, hist_all):
    """REL67 M-03 + REL68 M-02. Вызывать только под lock_state. Точка фиксации — os.replace(новый, история).
    ДО неё: копия прежней истории → <история>.prev, новый файл (fsync), метка <история>.pending, fsync папки.
    Сбой до фиксации → исключение OSError/ValueError: история не тронута, свои временные файлы и метка убраны.
    ПОСЛЕ неё: fsync папки, повторное чтение, снятие метки. Сбой → Uncertain: метка остаётся, отката нет."""
    raw = json.dumps(hist_all, sort_keys=True).encode('utf-8')
    d = os.path.dirname(os.path.abspath(path))
    pending, tmps, marked = path + '.pending', [], False
    try:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                old = f.read()
            tmps.append(write_tmp(d, old))
            os.replace(tmps[-1], path + '.prev')
            tmps.pop()
        new = write_tmp(d, raw)
        tmps.append(new)
        tmps.append(write_tmp(d, b'state write not confirmed\n'))
        os.replace(tmps[-1], pending)
        tmps.pop()
        marked = True
        fsync_dir(d)
        os.replace(new, path)                      # ТОЧКА ФИКСАЦИИ
    except BaseException:
        for t in tmps:
            if os.path.exists(t):
                os.unlink(t)
        if marked:
            os.unlink(pending)                     # не снялась — следующий запуск честно даст state:uncertain
        raise
    try:
        fsync_dir(d)
        with open(path, 'rb') as f:
            if f.read() != raw:
                raise ValueError('state_readback')
        os.unlink(pending)
        fsync_dir(d)                               # REL69 M-01: сбой здесь — метки уже нет, её надо вернуть
    except (OSError, ValueError) as e:
        why = type(e).__name__
        if not os.path.lexists(pending):
            try:
                os.replace(write_tmp(d, b'state write not confirmed\n'), pending)
            except OSError:
                why += ':marker_lost'              # вернуть метку не удалось — об этом сказано прямо
        raise Uncertain(why)


def main(argv):
    args, opts = [], {}
    it = iter(argv[1:])
    for a in it:
        if a in ('--seal-sha', '--state'):
            opts[a] = next(it, None)
        elif a == '--init':
            opts[a] = True
        else:
            args.append(a)
    usage = 'usage: zprobe_verify_export.py <archive.tar> <series> --state FILE [--init] [--seal-sha HEX]'
    if len(args) != 2 or not E.SERIES.fullmatch(args[1]) or None in opts.values() or '--state' not in opts:
        print(usage)
        return 2
    series, seal_sha = args[1], opts.get('--seal-sha')
    if seal_sha is not None:
        seal_sha = seal_sha.strip().lower()
    try:
        lock = lock_state(opts['--state'])          # REL68 M-01: до чтения истории и до конца её записи
    except Fail as e:
        print(f'ZPROBE_VERIFY_EXPORT=FAIL series={series} n=None')
        print(f'REASON {e}')
        print(BOUNDARY)
        return 1
    try:
        return main_locked(args, opts, series, seal_sha, usage)
    finally:
        unlock_state(lock)


def main_locked(args, opts, series, seal_sha, usage):
    n, files, extra = None, {}, []
    try:
        hist_all, rec = load_state(opts['--state'], series, '--init' in opts)
    except ValueError:
        print(usage + '  (--init: only when the series has no record yet)')
        return 2
    except Fail as e:
        hist_all, rec = None, None
        res, why, warn, hashes = 'FAIL', [str(e)], [], []
    if hist_all is not None:
        try:
            n, files = read_tar(args[0], series)
            res, why, warn, hashes = verify(n, files, series, seal_sha, rec, first=rec is None)
        except (Fail, tarfile.TarError, OSError) as e:
            n, res, why, warn, hashes = None, 'FAIL', [str(e)], [], []
    if res != 'FAIL' and 'phone_seal_sha_absent' not in why:
        b = json.loads(files['package/bundle.json'])
        hist_all[series] = {'n': n, 'journal_last_seq': b['journal_last_seq'] or (rec or {}).get('journal_last_seq', 0)}
        try:                                       # REL67 M-03: сначала история, потом итог
            persist_state(opts['--state'], hist_all)
        except (OSError, ValueError) as e:      # сбой до точки фиксации: история не тронута
            res, why, hashes = 'FAIL', [f'state_persist:{type(e).__name__}'], []
        except Uncertain as e:                     # REL68 M-02: сбой после точки фиксации
            res, why, hashes = 'FAIL', [f'state_persist_uncertain:{e}'], []
    if why and why[0].startswith(('state_persist_uncertain', 'state:uncertain')):
        prev = opts['--state'] + '.prev'
        extra = ['STATE_UNCERTAIN the history file may hold the new or the old record; nothing is accepted',
                 'STATE_PREV ' + (prev if os.path.exists(prev) else 'none'),
                 'STATE_PENDING ' + (opts['--state'] + '.pending' if os.path.lexists(opts['--state'] + '.pending')
                                     else 'none (marker lost: check the history by hand before any new run)'),
                 'STATE_RECOVERY compare the history file with STATE_PREV by hand, keep the right one, '
                 'then remove STATE_PENDING; no automatic rollback']
    print(f'ZPROBE_VERIFY_EXPORT={res} series={series} n={n}')
    for w in why:
        print(f'REASON {w}')
    for w in warn:
        print(w)
    for x in extra:
        print(x)
    for h in hashes:
        print(f'HASH_ONLY {h}')
    print(BOUNDARY)
    return {'PASS_SANITIZED': 0, 'UNSEALED': 10, 'INCOMPLETE': 11}.get(res, 1)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
