#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_seal.py
# ВЕРСИЯ: v0.2 (выпуск B10)  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 23:28 +02:00
# ДАТА СОЗДАНИЯ: 2026-11-14 23:04 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 09» (3037f186)
# v0.2 (чат «напарник · 03», d6c11f6b): общий порядок печати 4.4 — seal() (SELECT → повтор по сумме или первичная
#   печать: H1–H10, k = max+1, снимок src/ + опись (B), H8/H10, proof.json, вызов 4.2), snapshot(), verify_attempt();
#   опись (B): orig=- и orig_src=- только вместе и только у anchor.json (5 п.1а2). SQL вызывает переданная функция.
# НАЗНАЧЕНИЕ: проект B10 v0.18 разделы 4.3 и 4.4 — файл доказательств proof.json и папки попыток печати:
#   каноническая запись (одни и те же байты хешируются в proof_sha256), закрытая схема version 1, точная матрица
#   источников, опись снимка src/INVENTORY.sha256 (грамматика B, раздел 5 п.1а2), номер новой попытки k и поиск
#   попытки для повтора по сумме. Папки открываются только по дескриптору, без ссылок, root, без записи для группы
#   и всех. Сам модуль ничего не печатает в БД и не вызывает SQL: это делает общий порядок печати (4.4) бегунка B10.
# ДОПУЩЕНИЯ (на аудит): значение проверки H1–H10 — до 8 частей через пробел, каждая — число (≤20 цифр), сумма
#   64 hex, код [A-Z][A-Z0-9_]{0,39} или ключ=одно из этого; tool_version — [0-9A-Za-z._-]{1,40}.
import hashlib
import json
import os
import re
import stat

SEAL_ROOT = '/var/lib/zavod/seal'
VERSION = 1
FIELDS = {'version', 'series', 'lease_id', 'boot_id', 't0_utc', 'checks', 'journal_from_cursor', 'journal_to_cursor',
          'sources', 'inventory_sha256', 'preserve_manifest_sha256', 'tool_version', 'created_utc'}
CHECKS = tuple(f'H{i}' for i in range(1, 11))
SERIES = re.compile(r'[0-9A-Za-z_-]{1,40}')
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
HEX32 = re.compile(r'[0-9a-f]{32}')
HEX64 = re.compile(r'[0-9a-f]{64}')
UTC = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')
CURSOR = re.compile(r's=[0-9a-f]{32};i=[0-9a-f]+;b=[0-9a-f]{32};m=[0-9a-f]+;t=[0-9a-f]+;x=[0-9a-f]+')
TOKEN = r'(?:[0-9]{1,20}|[0-9a-f]{64}|[A-Z][A-Z0-9_]{0,39})'
VALUE = re.compile(rf'(?:[a-z_]{{1,16}}=)?{TOKEN}(?: (?:[a-z_]{{1,16}}=)?{TOKEN}){{0,7}}')
TOOL = re.compile(r'[0-9A-Za-z._-]{1,40}')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
ATTEMPT = re.compile(r'[1-9][0-9]{0,3}')
MODE = re.compile(r'[0-9]+:[0-9]+:[0-7]{4}')
PATH = re.compile(r'/[A-Za-z0-9@._/-]{1,250}')
MAX_PROOF = 256 * 1024
EXCLUDE = {'cleanup': {'cleanup.json'}, 'r2': {'MANIFEST.sha256'}}   # 4.3: единственные исключения матрицы


class Refused(Exception):
    """Нарушение закрытой схемы, матрицы или прав — для 4.4 это REFUSED_INCONSISTENT или отказ записи."""


def canon(obj):
    """4.3: единственная каноническая форма; эти байты и только они хешируются."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def matrix(kind, names):
    """4.3: множество имён sources = все имена источника, кроме исключения своего вида (cleanup или r2)."""
    if kind not in EXCLUDE:
        raise Refused('matrix_kind')
    return sorted(set(names) - EXCLUDE[kind])


def check_proof(raw, series, lease_id, names):
    """Разбор proof.json по закрытой схеме 4.3; names — ожидаемая матрица. Возвращает объект или Refused."""
    if len(raw) > MAX_PROOF:
        raise Refused('proof_size')
    try:
        obj = json.loads(raw.decode('ascii'))
    except (UnicodeDecodeError, ValueError):
        raise Refused('proof_json')
    if not isinstance(obj, dict) or set(obj) != FIELDS:
        raise Refused('proof_fields')
    if canon(obj) != raw:
        raise Refused('proof_not_canonical')
    bad = [k for k, ok in (
        ('version', obj['version'] == VERSION and type(obj['version']) is int),
        ('series', isinstance(obj['series'], str) and SERIES.fullmatch(obj['series']) and obj['series'] == series),
        ('lease_id', isinstance(obj['lease_id'], str) and UUID.fullmatch(obj['lease_id']) and obj['lease_id'] == lease_id),
        ('boot_id', isinstance(obj['boot_id'], str) and HEX32.fullmatch(obj['boot_id'])),
        ('t0_utc', isinstance(obj['t0_utc'], str) and UTC.fullmatch(obj['t0_utc'])),
        ('created_utc', isinstance(obj['created_utc'], str) and UTC.fullmatch(obj['created_utc'])),
        ('journal_from_cursor', isinstance(obj['journal_from_cursor'], str) and CURSOR.fullmatch(obj['journal_from_cursor'])),
        ('journal_to_cursor', isinstance(obj['journal_to_cursor'], str) and CURSOR.fullmatch(obj['journal_to_cursor'])),
        ('inventory_sha256', isinstance(obj['inventory_sha256'], str) and HEX64.fullmatch(obj['inventory_sha256'])),
        ('preserve_manifest_sha256', obj['preserve_manifest_sha256'] is None or (
            isinstance(obj['preserve_manifest_sha256'], str) and HEX64.fullmatch(obj['preserve_manifest_sha256']))),
        ('tool_version', isinstance(obj['tool_version'], str) and TOOL.fullmatch(obj['tool_version']))) if not ok]
    if bad:
        raise Refused('proof_' + bad[0])
    for c in (obj['journal_from_cursor'], obj['journal_to_cursor']):
        if c.split(';')[2] != 'b=' + obj['boot_id']:
            raise Refused('proof_cursor_boot')
    ch = obj['checks']
    if not isinstance(ch, dict) or set(ch) != set(CHECKS):
        raise Refused('proof_checks')
    for k in CHECKS:
        v = ch[k]
        want = {'ok', 'value', 'src'} if k == 'H9' else {'ok', 'value'}
        if not isinstance(v, dict) or set(v) != want or v['ok'] is not True or not isinstance(v['value'], str) \
                or not VALUE.fullmatch(v['value']) or (k == 'H9' and v['src'] not in ('r1', 'run')):
            raise Refused('proof_check_' + k)
    src = obj['sources']
    if not isinstance(src, list) or not src:
        raise Refused('proof_sources')
    seen = []
    for s in src:
        if not isinstance(s, dict) or set(s) != {'name', 'sha256', 'size'} or not isinstance(s['name'], str) \
                or not NAME.fullmatch(s['name']) or not isinstance(s['sha256'], str) or not HEX64.fullmatch(s['sha256']) \
                or type(s['size']) is not int or s['size'] < 0:
            raise Refused('proof_source_entry')
        seen.append(s['name'])
    if seen != sorted(set(seen)) or seen != sorted(names):
        raise Refused('proof_sources_matrix')
    return obj


def inventory_line(sha, size, name, phys, orig, src, orig_src):
    """Строка описи (B): поля через два пробела. orig и orig_src равны '-' только вместе и только у anchor.json
    (B9 R2, 5 п.1а2); иначе orig — путь, orig_src — uid:gid:режим."""
    dash = orig == '-' and orig_src == '-' and name == 'anchor.json'
    if not (HEX64.fullmatch(sha) and type(size) is int and size >= 0 and NAME.fullmatch(name) and PATH.fullmatch(phys)
            and MODE.fullmatch(src) and (dash or (PATH.fullmatch(orig) and MODE.fullmatch(orig_src)))):
        raise Refused('inventory_field')
    return f'{sha}  {size}  {name}  phys={phys}  orig={orig}  src={src}  orig_src={orig_src}\n'


def parse_inventory(raw):
    """Разбор описи (B): строки по имени, без повторов, каждая — строго по грамматике. Возвращает {имя: (sha, size)}."""
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError:
        raise Refused('inventory_ascii')
    if not text.endswith('\n') or '\r' in text:
        raise Refused('inventory_eol')
    out, names = {}, []
    for ln in text[:-1].split('\n'):
        p = ln.split('  ')
        if len(p) != 7 or not p[1].isdigit() or str(int(p[1])) != p[1] or not p[3].startswith('phys=') \
                or not p[4].startswith('orig=') or not p[5].startswith('src=') or not p[6].startswith('orig_src='):
            raise Refused('inventory_line')
        if inventory_line(p[0], int(p[1]), p[2], p[3][5:], p[4][5:], p[5][4:], p[6][9:]) != ln + '\n':
            raise Refused('inventory_line')
        names.append(p[2])
        out[p[2]] = (p[0], int(p[1]))
    if names != sorted(set(names)):
        raise Refused('inventory_order')
    return out


def open_dir(path, dir_fd=None):
    """Каталог по дескриптору без ссылок; root:root, без записи для группы и всех, иначе Refused."""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    st = os.fstat(fd)
    if st.st_uid != 0 or st.st_gid != 0 or st.st_mode & 0o022:
        os.close(fd)
        raise Refused(f'dir_owner:{path}')
    return fd


def open_root(path=SEAL_ROOT):
    """Каждый шаг пути от / — root без записи для группы и всех (как R1 v7)."""
    fd = open_dir('/')
    for part in [p for p in path.split('/') if p]:
        try:
            nfd = open_dir(part, dir_fd=fd)
        finally:
            os.close(fd)
        fd = nfd
    return fd


def attempts(series_fd):
    """Имена попыток в seal/<серия>: только [1-9][0-9]{0,3}, только каталоги без ссылок; иное — Refused."""
    ks = []
    for name in os.listdir(series_fd):
        st = os.stat(name, dir_fd=series_fd, follow_symlinks=False)
        if not ATTEMPT.fullmatch(name) or not stat.S_ISDIR(st.st_mode):
            raise Refused(f'attempt_name:{name}')
        ks.append(int(name))
    return sorted(ks)


def new_attempt(series_fd):
    """4.4 п.3: k = наибольший + 1; создание эксклюзивное (занято — Refused, ничего не заменяется); 0700 root."""
    ks = attempts(series_fd)
    k = (ks[-1] if ks else 0) + 1
    if k > 9999:
        raise Refused('attempts_exhausted')
    try:
        os.mkdir(str(k), 0o700, dir_fd=series_fd)
    except FileExistsError:
        raise Refused('attempt_exists')
    os.fsync(series_fd)
    fd = open_dir(str(k), dir_fd=series_fd)
    if stat.S_IMODE(os.fstat(fd).st_mode) != 0o700:
        os.close(fd)
        raise Refused('attempt_mode')
    return k, fd


def write_proof(attempt_fd, obj):
    """proof.json: канонические байты, O_EXCL|O_NOFOLLOW, root 0600, fsync файла и папки. Возвращает SHA-256."""
    data = canon(obj)
    fd = os.open('proof.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
                 dir_fd=attempt_fd)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(attempt_fd)
    return hashlib.sha256(data).hexdigest()


def read_small(name, dir_fd, limit=MAX_PROOF):
    """Обычный файл по дескриптору, без ссылок, root:root 0600, не больше limit байт."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_gid != 0 or stat.S_IMODE(st.st_mode) != 0o600 \
                or st.st_size > limit:
            raise Refused(f'file_mode:{name}')
        got = b''
        while len(got) <= limit:
            part = os.read(fd, 65536)
            if not part:
                break
            got += part
    finally:
        os.close(fd)
    if len(got) > limit:
        raise Refused(f'file_size:{name}')
    return got


MAX_SRC, MAX_FILES = 1 << 20, 64
RESULTS = {'SEALED_NOW', 'ALREADY_SEALED', 'REFUSED_CALLER', 'REFUSED_ARGS', 'REFUSED_INCONSISTENT',
           'REFUSED_HAS_SESSION', 'REFUSED_NOT_OWN', 'REFUSED_HAS_LOG', 'REFUSED_HAS_GATE'}


def mode_str(st):
    return f'{st.st_uid}:{st.st_gid}:{stat.S_IMODE(st.st_mode):04o}'


def read_src(name, dir_fd):
    """Источник снимка: обычный файл по дескриптору без ссылок, ≤1 МБ, размер не менялся. (байты, fstat)."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_SRC:
            raise Refused(f'src_file:{name}')
        got = b''
        while True:
            part = os.read(fd, 65536)
            if not part:
                break
            got += part
            if len(got) > MAX_SRC:
                raise Refused(f'src_size:{name}')
        if len(got) != st.st_size:
            raise Refused(f'src_changed:{name}')
        return got, st
    finally:
        os.close(fd)


def put_excl(name, data, dir_fd):
    """Новый файл root:root 0600 (O_EXCL|O_NOFOLLOW), запись целиком, fsync."""
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dir_fd)
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def src_names(src_fd):
    """Имена обычных файлов папки-источника; ссылки и прочее — Refused."""
    names = sorted(os.listdir(src_fd))
    if len(names) > MAX_FILES:
        raise Refused('src_count')
    for n in names:
        if not NAME.fullmatch(n) or not stat.S_ISREG(os.stat(n, dir_fd=src_fd, follow_symlinks=False).st_mode):
            raise Refused(f'src_entry:{n}')
    return names


def snapshot(attempt_fd, kind, src_fd, src_path, entries, fixed_src=None):
    """4.3: снимок src/ и опись (B). entries — {имя: (orig, orig_src)}; (None, None) значит orig = phys и
    orig_src = src (уборка B10). Имена entries обязаны равняться матрице kind по составу папки ДО и ПОСЛЕ.
    fixed_src — обязательный src у каждого файла (B9 R2: '0:0:0600'). Возвращает (sources, опись, её SHA-256)."""
    want = sorted(entries)
    if matrix(kind, src_names(src_fd)) != want or not want:
        raise Refused('src_matrix_before')
    os.mkdir('src', 0o700, dir_fd=attempt_fd)
    os.fsync(attempt_fd)
    sfd = open_dir('src', dir_fd=attempt_fd)
    try:
        sources, lines = [], []
        for name in want:
            data, st = read_src(name, src_fd)
            h = hashlib.sha256(data).hexdigest()
            src = mode_str(st)
            if fixed_src is not None and src != fixed_src:
                raise Refused(f'src_mode:{name}')
            put_excl(name, data, sfd)
            again, st2 = read_src(name, src_fd)
            if hashlib.sha256(read_small(name, sfd, MAX_SRC)).hexdigest() != h \
                    or hashlib.sha256(again).hexdigest() != h or mode_str(st2) != src:
                raise Refused(f'src_copy:{name}')
            orig, orig_src = entries[name]
            phys = f'{src_path}/{name}'
            lines.append(inventory_line(h, len(data), name, phys, orig or phys, src, orig_src or src))
            sources.append({'name': name, 'sha256': h, 'size': len(data)})
        if matrix(kind, src_names(src_fd)) != want:
            raise Refused('src_matrix_after')
        inv = ''.join(lines).encode('ascii')
        put_excl('INVENTORY.sha256', inv, sfd)
        os.fsync(sfd)
    finally:
        os.close(sfd)
    os.fsync(attempt_fd)
    return sources, inv, hashlib.sha256(inv).hexdigest()


def verify_attempt(attempt_fd, raw, series, lease_id, kind):
    """4.4 п.2: proof по закрытой схеме и СНИМОК той же попытки (не /run): опись = proof.inventory_sha256,
    имена описи = sources = матрица kind, каждый src/<имя> — та же сумма и размер, root:root 0600."""
    sfd = open_dir('src', dir_fd=attempt_fd)
    try:
        inv_raw = read_small('INVENTORY.sha256', sfd, MAX_SRC)
        inv = parse_inventory(inv_raw)
        names = sorted(inv)
        if matrix(kind, names) != names:
            raise Refused('retry_matrix')
        obj = check_proof(raw, series, lease_id, names)
        if hashlib.sha256(inv_raw).hexdigest() != obj['inventory_sha256']:
            raise Refused('retry_inventory_sha')
        if sorted(os.listdir(sfd)) != sorted(names + ['INVENTORY.sha256']):
            raise Refused('retry_src_set')
        for s in obj['sources']:
            data = read_small(s['name'], sfd, MAX_SRC)
            if (hashlib.sha256(data).hexdigest(), len(data)) != (s['sha256'], s['size']) \
                    or inv[s['name']] != (s['sha256'], s['size']):
                raise Refused(f'retry_src:{s["name"]}')
        return obj
    finally:
        os.close(sfd)


def seal(kind, series, lease_id, select_row, call_seal, run_checks, recheck, open_source, tool_version,
         now_utc, preserve_manifest_sha256=None, fixed_src=None, root=SEAL_ROOT):
    """4.4: одна функция для R2 (kind='r2') и уборки (kind='cleanup'). Внешние шаги передаются функциями:
    select_row(lease_id) -> None | {'series', 'proof_sha256'} (SELECT lease_seal; исключение = код psql ≠ 0);
    call_seal(series, lease_id, sha) -> ответ функции 4.2; run_checks() -> {'ok', 'checks', 'boot_id', 't0_utc',
    'journal_from_cursor', 'journal_to_cursor'} (H1–H10); recheck() -> bool (H8 и H10 после заморозки);
    open_source() -> (fd папки-источника, её путь, entries для snapshot). Возвращает словарь с 'result'."""
    if kind not in EXCLUDE or not SERIES.fullmatch(series) or not UUID.fullmatch(lease_id):
        return {'result': 'REFUSED_ARGS', 'reason': 'args'}
    try:
        row = select_row(lease_id)
    except Exception as e:  # код psql ≠ 0 или ответ не разобран — новый proof не создаётся
        return {'result': 'BLOCKED_SESSION_UNKNOWN', 'reason': f'select:{type(e).__name__}'}
    rfd = open_root(root)
    try:
        if row is not None:                                     # п.2: ветка повтора, новый k не создаётся
            try:
                if row.get('series') != series or not HEX64.fullmatch(str(row.get('proof_sha256'))):
                    raise Refused('retry_row')
                sfd = open_dir(series, dir_fd=rfd)
                try:
                    hits = find_retry(sfd, row['proof_sha256'])
                    if len(hits) != 1:
                        raise Refused(f'retry_hits:{len(hits)}')
                    afd = open_dir(str(hits[0]), dir_fd=sfd)
                    try:
                        verify_attempt(afd, read_small('proof.json', afd), series, lease_id, kind)
                    finally:
                        os.close(afd)
                finally:
                    os.close(sfd)
            except (Refused, OSError, ValueError, KeyError) as e:
                return {'result': 'REFUSED_INCONSISTENT', 'reason': f'{type(e).__name__}:{e}'[:120]}
            ans = call_seal(series, lease_id, row['proof_sha256'])
            return {'result': ans if ans in RESULTS else 'BLOCKED_SESSION_UNKNOWN', 'k': hits[0],
                    'sha': row['proof_sha256'], 'reason': 'retry'}
        res = run_checks()                                      # п.3: первичная печать
        if not res.get('ok'):
            return {'result': 'BLOCKED_SESSION_UNKNOWN', 'reason': 'checks'}
        try:
            try:
                os.mkdir(series, 0o700, dir_fd=rfd)
                os.fsync(rfd)
            except FileExistsError:
                pass
            sfd = open_dir(series, dir_fd=rfd)
            try:
                k, afd = new_attempt(sfd)
            finally:
                os.close(sfd)
            try:
                src_fd, src_path, entries = open_source()
                try:
                    sources, _inv, inv_sha = snapshot(afd, kind, src_fd, src_path, entries, fixed_src)
                finally:
                    os.close(src_fd)
                if not recheck():
                    return {'result': 'BLOCKED_SESSION_UNKNOWN', 'k': k, 'reason': 'recheck'}
                obj = {'version': VERSION, 'series': series, 'lease_id': lease_id, 'boot_id': res['boot_id'],
                       't0_utc': res['t0_utc'], 'checks': res['checks'],
                       'journal_from_cursor': res['journal_from_cursor'],
                       'journal_to_cursor': res['journal_to_cursor'], 'sources': sources, 'inventory_sha256': inv_sha,
                       'preserve_manifest_sha256': preserve_manifest_sha256, 'tool_version': tool_version,
                       'created_utc': now_utc()}
                check_proof(canon(obj), series, lease_id, [s['name'] for s in sources])
                sha = write_proof(afd, obj)
            finally:
                os.close(afd)
        except (Refused, OSError, ValueError, KeyError) as e:
            return {'result': 'BLOCKED_SESSION_UNKNOWN', 'reason': f'{type(e).__name__}:{e}'[:120]}
        ans = call_seal(series, lease_id, sha)
        return {'result': ans if ans in RESULTS else 'BLOCKED_SESSION_UNKNOWN', 'k': k, 'sha': sha, 'reason': 'first'}
    finally:
        os.close(rfd)


def find_retry(series_fd, proof_sha):
    """4.4 п.2: попытки, у которых SHA-256 proof.json = proof_sha (попытка без proof.json пропускается).
    Вызывающий требует ровно одну; ни одной или больше — REFUSED_INCONSISTENT."""
    hit = []
    for k in attempts(series_fd):
        afd = open_dir(str(k), dir_fd=series_fd)
        try:
            try:
                raw = read_small('proof.json', afd)
            except FileNotFoundError:
                continue
            if hashlib.sha256(raw).hexdigest() == proof_sha:
                hit.append(k)
        finally:
            os.close(afd)
    return hit
