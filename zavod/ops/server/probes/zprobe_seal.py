#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_seal.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-14 23:04 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 09» (3037f186)
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
    """Строка описи (B): поля через два пробела; orig_src — режим или '-'."""
    if not (HEX64.fullmatch(sha) and type(size) is int and size >= 0 and NAME.fullmatch(name) and PATH.fullmatch(phys)
            and PATH.fullmatch(orig) and MODE.fullmatch(src) and (orig_src == '-' or MODE.fullmatch(orig_src))):
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
