#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_export_rules.py
# ВЕРСИЯ: v0.4 (B13)  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 12:44 +02:00
# v0.4 (Claude, терминал zavod; B13, REL123): dropin_check.json формата zprobe_dropin v0.2 — новые поля rule,
#   raw_changed, reordered, runtime, unparsed (списки имён), stop_reason (overflow | unparsed | null); в cage_partial —
#   raw_changed_props. Файл формата v0.1 (без этих полей) по-прежнему принимается: новые поля не обязательны.
# v0.3 (2026-11-15, терминал zavod, сменщик cb6b67c5; REL67 M-01): journal_segments 0..MAX_LINES; CHAIN_HASH_ONLY —
#   только непустой журнал (сегментов ≥ 1, last_seq ≥ 1); пустой журнал — PARTIAL_HASH_ONLY.
# v0.2 (2026-11-15, терминал zavod, чат cb6b67c5): REL65 M-02 — свободный текст ALLOW → только длина;
#   REL65 M-01 — журнал проб только HASH_ONLY (CHAIN_HASH_ONLY | PARTIAL_HASH_ONLY), FULL_RAW журнала запрещён.
# ДАТА СОЗДАНИЯ: 2026-11-14 23:55 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 5 п.1 — ОДНИ таблицы и разборщики для сервера (zprobe_export.py) и ПК
#   (zprobe_verify_export.py): таблица классов и режимов, закрытая таблица имён по формату и месту, списки ALLOW и
#   KNOWN_DENY каждого JSON серии (пересборка), схемы anchor_run.json и anchor.json, грамматика (A) preserve
#   MANIFEST, строка MANIFEST пакета, bundle.json v2, режим журнала проб, связи идентификаторов, порядок курсоров.
#   Чистые функции без системы — проверяются тестами везде. Грамматика (B) и схема proof — zprobe_seal.py.
# ДОПУЩЕНИЯ (на аудит): 1) поле KNOWN_DENY в пересобранном JSON заменяется объектом {"known_deny_count": n}
#   (n — число элементов списка/словаря/строки, 1 у прочего) — так ПК видит, что поле было, но без содержимого;
#   2) KNOWN_DENY строки аренды anchor.json (row_to_json R1) — все столбцы chat_lease вне ALLOW проекта;
#   3) READY — ровно 64 знака суммы MANIFEST и перевод строки; 4) b_probe — boot_id proof (или якоря без печати),
#   boot_id — загрузка в момент выгрузки; 5) значения dropin_check.values — печатные ASCII ≤ 512 знаков;
#   6) (v0.2, REL65 M-02) любое свободное текстовое поле ALLOW (reason, env.*, systemd, before/after drop-in)
#   выгружается только как {"text_len": n} — сам текст не попадает в пакет даже при допустимом виде.
import hashlib
import json
import re

import zprobe_rules as R
import zprobe_seal as S

MATRICES = ('B9R2.v2', 'B10.v2')
ALLOW_VERSION = 'allow.v1'
MODES = ('ALLOW', 'FULL_RAW', 'HASH_ONLY')
PLACES = ('final', 'journal', 'package', 'proof', 'sealed/meta', 'sealed/source')
NAME_RE = re.compile(r'\A[a-z0-9_][a-z0-9_.-]{0,63}\Z')
ARCH_NAME = re.compile(r'\Aarchive\.50-zprobe\.conf(?:\.([1-9][0-9]{0,2}))?\Z')
ARCH_FILE = re.compile(r'\A50-zprobe\.conf(?:\.([1-9][0-9]{0,2}))?\Z')
HEX32 = re.compile(r'[0-9a-f]{32}')
HEX40 = re.compile(r'[0-9a-f]{40}')
HEX64 = re.compile(r'[0-9a-f]{64}')
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
SERIES = re.compile(r'[0-9A-Za-z_-]{1,40}')
ISO = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')
PGTS = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})')
SINCE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} UTC')
PROP = re.compile(r'[A-Za-z]{1,64}')
CODE = re.compile(r'[A-Za-z0-9_.:-]{1,80}')
WORD = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,39}')
UPPER = re.compile(r'[A-Z][A-Z0-9_]{0,39}')
LOWER = re.compile(r'[a-z][a-z_-]{0,23}')
FILE_KEY = re.compile(r'[A-Za-z0-9@._-]{1,64}')
MODE_STR = re.compile(r'[0-9]{1,10}:[0-9]{1,10}:[0-7]{4}')
MAX_FILES, MAX_LINES, MAX_FILE, MAX_TOTAL = 32, 1100, 256 * 1024, 2 * 1024 * 1024


class Refused(Exception):
    """EXPORT_REFUSED <файл>:<поле> на сервере; FAIL на ПК."""


# ---- таблица имён (раздел 5 п.1, REL58 M-03): имя → (класс, режим, {(формат, место): 'req'|'opt'}) ----
# формат: 'B9R2' | 'B10'; место: 'source' (sealed/source) | 'final'. Нет ключа — строки быть не должно («—»).
NAMES = {
    'state.json': ('json', 'ALLOW', {('B9R2', 'source'): 'req', ('B9R2', 'final'): 'req', ('B10', 'source'): 'req',
                                     ('B10', 'final'): 'req'}),
    'evidence.json': ('json', 'ALLOW', {('B9R2', 'source'): 'req', ('B9R2', 'final'): 'req',
                                        ('B10', 'source'): 'req', ('B10', 'final'): 'req'}),
    'cleanup.json': ('json', 'ALLOW', {('B9R2', 'source'): 'req', ('B9R2', 'final'): 'req', ('B10', 'final'): 'req'}),
    'dropin_check.json': ('json', 'ALLOW', {('B9R2', 'source'): 'opt', ('B9R2', 'final'): 'opt',
                                            ('B10', 'source'): 'opt', ('B10', 'final'): 'opt'}),
    'anchor.json': ('json', 'ALLOW', {('B9R2', 'source'): 'req'}),
    'anchor_run.json': ('json', 'ALLOW', {('B10', 'source'): 'req', ('B10', 'final'): 'req'}),
    'request.json': ('hash', 'HASH_ONLY', {('B9R2', 'source'): 'req', ('B9R2', 'final'): 'opt',
                                           ('B10', 'source'): 'opt', ('B10', 'final'): 'opt'}),
    'dropin_50-zprobe.conf': ('hash', 'HASH_ONLY', {('B9R2', 'source'): 'req'}),
    'started.marker': ('hash', 'HASH_ONLY', {('B9R2', 'final'): 'opt', ('B10', 'final'): 'opt'}),
}
ARCH_ROW = ('hash', 'HASH_ONLY', {('B9R2', 'final'): 'opt', ('B10', 'final'): 'opt'})


def fmt_of(matrix):
    if matrix not in MATRICES:
        raise Refused(f'bundle:matrix')
    return matrix.split('.')[0]


def name_row(name):
    """Строка таблицы имён для логического имени (archive.* — по шаблону); вне таблицы — None."""
    if not NAME_RE.match(name):
        return None
    if name in NAMES:
        return NAMES[name]
    return ARCH_ROW if ARCH_NAME.match(name) else None


def need(fmt, where, name):
    """'req' | 'opt' | None («—» — строки быть не должно)."""
    row = name_row(name)
    return None if row is None else row[2].get((fmt, where))


def required(fmt, where):
    return sorted(n for n, row in NAMES.items() if row[2].get((fmt, where)) == 'req')


# ---- валидаторы пересборки ----
def _deny_count(v):
    return len(v) if isinstance(v, (list, dict, str)) else 1


def rx(r):
    def f(v, path):
        if not isinstance(v, str) or not r.fullmatch(v):
            raise Refused(path)
        return v
    return f


def text(n):
    """Свободная строка (причина, версии, значения drop-in) в пакет НЕ попадает (REL65 M-02): сервер проверяет её
    (печатный ASCII ≤ n) и пишет только {'text_len': длина}; ПК принимает только эту закрытую форму."""
    def f(v, path):
        if _PC[0]:
            if not (isinstance(v, dict) and set(v) == {'text_len'} and type(v['text_len']) is int
                    and 0 <= v['text_len'] <= n):
                raise Refused(path)
            return v
        if not isinstance(v, str) or len(v) > n or any(not (32 <= ord(c) < 127) for c in v):
            raise Refused(path)
        return {'text_len': len(v)}
    return f


def integer(v, path):
    if type(v) is not int or v < 0:
        raise Refused(path)
    return v


def boolean(v, path):
    if type(v) is not bool:
        raise Refused(path)
    return v


def enum(*xs):
    def f(v, path):
        if v not in xs or not isinstance(v, (str, bool)):
            raise Refused(path)
        return v
    return f


def null_or(g):
    def f(v, path):
        return None if v is None else g(v, path)
    return f


def lst(g, n):
    def f(v, path):
        if not isinstance(v, list) or len(v) > n:
            raise Refused(path)
        return [g(x, f'{path}[{i}]') for i, x in enumerate(v)]
    return f


def pair(g):
    def f(v, path):
        if not isinstance(v, list) or len(v) != 2:
            raise Refused(path)
        return [g(x, f'{path}[{i}]') for i, x in enumerate(v)]
    return f


def mapping(key_re, g, n):
    def f(v, path):
        if not isinstance(v, dict) or len(v) > n:
            raise Refused(path)
        out = {}
        for k, x in v.items():
            if not isinstance(k, str) or not key_re.fullmatch(k):
                raise Refused(f'{path}.?')
            out[k] = g(x, f'{path}.{k}')
        return out
    return f


_PC = [False]   # True — проверка уже очищенного файла на ПК: поле KNOWN_DENY обязано быть {'known_deny_count': n}


def obj(allow, deny=(), need_all=False):
    """Закрытый объект: поле из ALLOW — проверка и пересборка; из KNOWN_DENY — только {'known_deny_count': n};
    любое иное поле → Refused '<путь>.<поле>'. need_all — все поля ALLOW обязательны (закрытые схемы)."""
    deny = frozenset(deny)

    def f(v, path):
        if not isinstance(v, dict):
            raise Refused(path)
        out = {}
        for k, x in v.items():
            if k in allow:
                out[k] = allow[k](x, f'{path}.{k}')
            elif k in deny and _PC[0]:
                if not (isinstance(x, dict) and set(x) == {'known_deny_count'} and type(x['known_deny_count']) is int
                        and x['known_deny_count'] >= 0):
                    raise Refused(f'{path}.{k}')
                out[k] = x
            elif k in deny:
                out[k] = {'known_deny_count': _deny_count(x)}
            else:
                raise Refused(f'{path}.{k}')
        if need_all and set(v) != set(allow):
            raise Refused(f'{path}:fields')
        return out
    return f


CURSOR = rx(S.CURSOR)
DROPIN = rx(re.compile(r'/run/systemd/system/zagent@[0-9a-f]{32}\.service\.d/50-zprobe\.conf'))
KEPT = rx(re.compile(r'absent|/var/lib/zavod/probes/archive/[0-9A-Za-z_-]{1,40}/50-zprobe\.conf(?:\.[1-9][0-9]{0,2})?'
                     r'|failed_[A-Za-z0-9_.:-]{1,80}'))
VALUE = obj({'redacted': enum(True), 'len_before': integer, 'len_after': integer,
             'before': null_or(text(512)), 'after': null_or(text(512)),
             'before_truncated': boolean, 'after_truncated': boolean})
STATE_B9 = {'lease': rx(HEX32), 'lease_id': rx(UUID), 'dropin': DROPIN}
STATE_B10 = dict(STATE_B9, series=rx(SERIES), runner=enum('b10'))
EVIDENCE = obj({
    'series': rx(SERIES), 'status': enum('RUNNING', 'ABORTED', 'RUN_DONE'), 'step': rx(LOWER),
    'reason': text(240), 'probes': lst(rx(WORD), 64), 'code_sha256': mapping(FILE_KEY, rx(HEX64), 32),
    'release': obj({'commit': rx(HEX40), 'version': rx(re.compile(r'[0-9][0-9.]{0,15}'))}),
    'env': obj({'kernel': text(120), 'systemd': text(160), 'python': text(40), 'git': text(160)}, deny=('host',)),
    'since': rx(SINCE), 'run_utc': pair(null_or(rx(ISO))), 'meta_sha256': rx(HEX64), 'lease': rx(HEX32),
    'lease_state': rx(UPPER),
    'dropin_check': obj({'result': enum('OK', 'REFUSED', 'STOP'), 'code': rx(CODE),
                         'diag_status': enum('OK', 'DIAGNOSTICS_INCOMPLETE'), 'logged': boolean}),
    'diag_status': enum('OK', 'DIAGNOSTICS_INCOMPLETE'),
    'cage_partial': obj({'dropin_sha256': rx(HEX64), 'changed_props': lst(rx(PROP), 4096), 'props_ok': boolean,
                         'raw_changed_props': lst(rx(PROP), 4096), 'dropin_ok': boolean, 'isolated_ok': boolean}),
    'exit_code': integer, 'anchor_sha256': rx(HEX64), 'start_request_s': integer},
    deny=('challenge', 'cred_paths', 'gh_names', 'targets', 'dns', 'control', 'proxy_log', 'kernel_log', 'attempts'))
CLEANUP = obj({
    'series': rx(SERIES), 'found_by': enum('state', 'database'), 'lease': rx(HEX32), 'unit_active_after': rx(LOWER),
    'lease_db_status': rx(re.compile(r'[A-Za-z_]{1,24}')), 'kept_copy': KEPT, 'load_state': rx(LOWER),
    'session_state': rx(UPPER), 'status': rx(UPPER),
    'pre_start': obj({'status': rx(UPPER), 'seal': null_or(rx(UPPER)), 'failed': lst(rx(UPPER), 16),
                      'reason': text(160), 'k': null_or(integer), 'sha': null_or(rx(HEX64))})})
DROPIN_CHECK = obj({
    'systemd': text(160), 'at': rx(ISO), 'compared': integer, 'changed': lst(rx(PROP), 4096),
    'values': mapping(PROP, VALUE, 200), 'allowed': lst(rx(PROP), 4096), 'extra': lst(rx(PROP), 4096),
    'complete': boolean, 'result': enum('OK', 'REFUSED', 'STOP'),
    'rule': enum('B13.v0.2'), 'raw_changed': lst(rx(PROP), 4096), 'reordered': lst(rx(PROP), 4096),
    'runtime': lst(rx(PROP), 4096), 'unparsed': lst(rx(PROP), 4096),
    'stop_reason': null_or(enum('overflow', 'unparsed'))})
ANCHOR_RUN = obj({'series': rx(SERIES), 'lease': rx(HEX32), 'lease_id': rx(UUID), 'boot_id': rx(HEX32),
                  'cursor': CURSOR, 'cursor_us': integer, 'utc': rx(ISO)}, need_all=True)
LEASE_ROW = obj({'lease_id': rx(UUID), 'status': enum('OPEN', 'COMPLETED'), 'holder_session': rx(re.compile(
    r'zprobe-[0-9A-Za-z_-]{1,40}')), 'opened_by': rx(WORD), 'role_key': rx(re.compile(r'0[1-9]_[a-z0-9_]{1,60}')),
    'opened_at': rx(PGTS), 'closed_at': null_or(rx(PGTS))},
    deny=('tenant_id', 'chat_number', 'generation', 'work_item_id', 'rules_commit', 'code_commit',
          'completion_evidence_id', 'result_evidence_id', 'memory_evidence_id', 'next_evidence_id', 'report_id'))
ANCHOR_B9 = obj({'series': enum('pb1trial2'), 'lease': rx(HEX32), 'lease_id': rx(UUID),
                 'boot_id': rx(HEX32), 'utc': rx(ISO), 'cursor_before': CURSOR, 'cursor_before_us': integer,
                 'cursor_after': CURSOR, 'cursor_after_us': integer,
                 'source_names': lst(rx(re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')), 64),
                 'source_modes': mapping(re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}'), rx(MODE_STR), 65),
                 'mask_link': rx(re.compile(r'/dev/null|absent|not_link')), 'lease_row': LEASE_ROW}, need_all=True)
SCHEMAS = {('B9R2', 'state.json'): obj(STATE_B9, need_all=True), ('B10', 'state.json'): obj(STATE_B10, need_all=True),
           'evidence.json': EVIDENCE, 'cleanup.json': CLEANUP, 'dropin_check.json': DROPIN_CHECK,
           ('B9R2', 'anchor.json'): ANCHOR_B9, ('B10', 'anchor_run.json'): ANCHOR_RUN}


def sanitize(fmt, name, raw):
    """Пересборка JSON серии по ALLOW/KNOWN_DENY своего формата → (объект, канонические байты). Иное → Refused."""
    g = SCHEMAS.get((fmt, name)) or SCHEMAS.get(name)
    if g is None:
        raise Refused(f'{name}:schema')
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise Refused(f'{name}:json')
    out = g(doc, name)
    if name == 'anchor_run.json' and f";b={out['boot_id']};" not in out['cursor']:
        raise Refused(f'{name}:cursor_boot')
    return out, S.canon(out)


def check_sanitized(fmt, name, data):
    """ПК: файл ALLOW обязан быть уже очищенным — разбор, пересборка, те же канонические байты; KNOWN_DENY-поле
    только в виде {'known_deny_count': n}."""
    try:
        doc = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        raise Refused(f'{name}:json')
    if S.canon(doc) != data:
        raise Refused(f'{name}:not_canonical')
    _PC[0] = True
    try:
        out, again = sanitize(fmt, name, data)
    finally:
        _PC[0] = False
    if again != data:
        raise Refused(f'{name}:not_sanitized')
    return out


# ---- описи ----
def parse_manifest_a(raw, series='pb1trial2', lease=None):
    """(A) preserve MANIFEST.sha256 R1 v6/v7: строки копий '<sha>  <размер>  <имя>  <путь>  src=<u:g:режим>' с корнем
    /run/zprobe/<серия>/ или /run/systemd/system/zagent@<L>.service.d/; ровно одна 'anchor.json  -'; перевод строки
    в конце. → {имя: (sha, размер, путь|'-', src|'-')} по порядку записи."""
    try:
        text_ = raw.decode('ascii')
    except UnicodeDecodeError:
        raise Refused('MANIFEST.sha256:ascii')
    if not text_.endswith('\n'):
        raise Refused('MANIFEST.sha256:eol')
    out, anchors = {}, 0
    for ln in text_[:-1].split('\n'):
        p = ln.split('  ')
        if len(p) == 4 and p[2] == 'anchor.json' and p[3] == '-':
            sha, size, name, path, src = p[0], p[1], p[2], '-', '-'
            anchors += 1
        elif len(p) == 5 and p[4].startswith('src='):
            sha, size, name, path, src = p[0], p[1], p[2], p[3], p[4][4:]
            lz = lease if lease is not None else '[0-9a-f]{32}'
            ok_path = path == f'/run/zprobe/{series}/{name}' or (
                name == 'dropin_50-zprobe.conf' and
                re.fullmatch(rf'/run/systemd/system/zagent@{lz}\.service\.d/50-zprobe\.conf', path))
            if not MODE_STR.fullmatch(src) or not ok_path:
                raise Refused(f'MANIFEST.sha256:{name}')
        else:
            raise Refused('MANIFEST.sha256:line')
        if not HEX64.fullmatch(sha) or not size.isdigit() or name in out or not NAME_RE.match(name):
            raise Refused(f'MANIFEST.sha256:{name}')
        out[name] = (sha, int(size), path, src)
    if anchors != 1:
        raise Refused('MANIFEST.sha256:anchor')
    return out


def inventory_b_problem(fmt, series, inv_raw, man_a=None):
    """(B) строки снимка: B10 — phys = orig = /run/zprobe/<S>/<имя>, orig_src = src; B9 R2 — phys =
    /var/lib/zavod/preserve/pb1trial2/<имя>, src = 0:0:0600, orig/orig_src = (A) того же имени (anchor.json: '-')."""
    try:
        S.parse_inventory(inv_raw)
    except S.Refused:
        return 'INVENTORY.sha256:grammar'
    for ln in inv_raw.decode('ascii').split('\n')[:-1]:
        p = ln.split('  ')
        name = p[2]
        f = dict(x.split('=', 1) for x in p[3:])
        if fmt == 'B10':
            want = f'/run/zprobe/{series}/{name}'
            if f['phys'] != want or f['orig'] != want or f['orig_src'] != f['src']:
                return f'INVENTORY.sha256:{name}'
        else:
            a = (man_a or {}).get(name)
            if a is None or f['phys'] != f'/var/lib/zavod/preserve/{series}/{name}' or f['src'] != '0:0:0600' \
                    or f['orig'] != a[2] or f['orig_src'] != a[3]:
                return f'INVENTORY.sha256:{name}'
    return None


# ---- строка MANIFEST пакета (п.1е) ----
def manifest_line(mode, place, name, raw, out):
    """raw/out — байты (out=None у HASH_ONLY)."""
    rs = hashlib.sha256(raw).hexdigest()
    if mode == 'HASH_ONLY':
        o, osz = '-', '-'
    else:
        o, osz = hashlib.sha256(out).hexdigest(), str(len(out))
    return f'{mode}  {place}/{name}  raw={rs}  raw_size={len(raw)}  out={o}  out_size={osz}'


LINE = re.compile(r'(ALLOW|FULL_RAW|HASH_ONLY)  (final|journal|package|proof|sealed/meta|sealed/source)/([^ /]+)  '
                  r'raw=([0-9a-f]{64})  raw_size=([0-9]+)  out=([0-9a-f]{64}|-)  out_size=([0-9]+|-)')


def place_mode_ok(fmt, place, name, mode, journal_mode=None):
    """Таблица классов × место: допустимый режим для имени в месте."""
    if place in ('sealed/source', 'final'):
        row = name_row(name)
        where = 'source' if place == 'sealed/source' else 'final'
        return row is not None and row[2].get((fmt, where)) is not None and mode == row[1]
    if place == 'sealed/meta':
        return mode == 'FULL_RAW' and name in (('INVENTORY.sha256', 'MANIFEST.sha256') if fmt == 'B9R2'
                                               else ('INVENTORY.sha256',))
    if place == 'proof':
        return name == 'proof.json' and mode == 'FULL_RAW'
    if place == 'package':
        return name == 'bundle.json' and mode == 'FULL_RAW'
    if place == 'journal':
        # REL65 M-01: журнал проб физически не выгружается (каждая запись несёт challenge) — только HASH_ONLY
        return bool(R.SEG_NAME.match(name)) and mode == 'HASH_ONLY' \
            and journal_mode in ('CHAIN_HASH_ONLY', 'PARTIAL_HASH_ONLY')
    return False


def parse_manifest(raw):
    """Строки MANIFEST пакета → [(режим, место, имя, raw, raw_size, out, out_size)]; порядок (место, имя),
    без повторов; HASH_ONLY — out '-'; FULL_RAW — out = raw; ALLOW — out есть."""
    try:
        t = raw.decode('ascii')
    except UnicodeDecodeError:
        raise Refused('MANIFEST:ascii')
    if not t.endswith('\n'):
        raise Refused('MANIFEST:eol')
    rows = []
    for ln in t[:-1].split('\n'):
        m = LINE.fullmatch(ln)
        if not m:
            raise Refused('MANIFEST:line')
        mode, place, name, r, rsz, o, osz = m.groups()
        if (mode == 'HASH_ONLY') != (o == '-') or (o == '-') != (osz == '-') \
                or (mode == 'FULL_RAW' and (o != r or osz != rsz)):
            raise Refused(f'MANIFEST:{place}/{name}')
        rows.append((mode, place, name, r, int(rsz), None if o == '-' else o, None if osz == '-' else int(osz)))
    keys = [(x[1], x[2]) for x in rows]
    if keys != sorted(set(keys)):
        raise Refused('MANIFEST:order')
    if len(rows) > MAX_LINES:
        raise Refused('MANIFEST:lines')
    return rows


# ---- bundle.json v2 (п.1е, L-02) ----
BUNDLE_FIELDS = {'bundle_version', 'manifest_schema_version', 'matrix', 'allow_version', 'series', 'lease_id', 'n',
                 'b_probe', 'boot_id', 'journal_cursor', 'journal_mode', 'journal_segments', 'journal_last_seq',
                 'journal_last_sha256', 'seal'}


def check_bundle(b):
    """Закрытая схема bundle.json; каноническая запись проверяет вызывающий."""
    if not isinstance(b, dict) or set(b) != BUNDLE_FIELDS:
        raise Refused('bundle:fields')
    seal = b['seal']
    ok = b['bundle_version'] == 2 and b['manifest_schema_version'] == 2 and b['matrix'] in MATRICES \
        and b['allow_version'] == ALLOW_VERSION and isinstance(b['series'], str) and SERIES.fullmatch(b['series']) \
        and isinstance(b['lease_id'], str) and UUID.fullmatch(b['lease_id']) and type(b['n']) is int \
        and 1 <= b['n'] <= 9999 and isinstance(b['b_probe'], str) and HEX32.fullmatch(b['b_probe']) \
        and isinstance(b['boot_id'], str) and HEX32.fullmatch(b['boot_id']) \
        and b['journal_mode'] in ('CHAIN_HASH_ONLY', 'PARTIAL_HASH_ONLY') and type(b['journal_segments']) is int \
        and 0 <= b['journal_segments'] <= MAX_LINES      # REL67 M-01: предел до любого перебора
    if not ok:
        raise Refused('bundle:value')
    if b['journal_mode'] == 'CHAIN_HASH_ONLY':
        # REL67 M-01: цепочка — только непустой журнал (≥ 1 сегмента, last_seq ≥ 1)
        if b['journal_segments'] < 1 or type(b['journal_last_seq']) is not int or b['journal_last_seq'] < 1 \
                or not (isinstance(b['journal_last_sha256'], str) and
                                                          HEX64.fullmatch(b['journal_last_sha256'])):
            raise Refused('bundle:journal_last')
    elif b['journal_last_seq'] is not None or b['journal_last_sha256'] is not None:
        raise Refused('bundle:journal_last')
    if seal is None:
        if b['journal_cursor'] is not None:
            raise Refused('bundle:journal_cursor')
    else:
        if not isinstance(seal, dict) or set(seal) != {'series', 'proof_sha256', 'sealed_at'} \
                or seal['series'] != b['series'] or not (isinstance(seal['proof_sha256'], str) and
                                                         HEX64.fullmatch(seal['proof_sha256'])) \
                or not (isinstance(seal['sealed_at'], str) and PGTS.fullmatch(seal['sealed_at'])):
            raise Refused('bundle:seal')
        if not (isinstance(b['journal_cursor'], str) and S.CURSOR.fullmatch(b['journal_cursor'])):
            raise Refused('bundle:journal_cursor')
    return b


# ---- журнал проб (п.1в) ----
J_BASE = {'series', 'challenge', 'probe', 'kind', 'seq', 'prev_sha256', 'time'}
J_KIND = {
    'SERIES_START': ({'probes'}, {'skipped_segments', 'targets', 'gh_names', 'cred_paths', 'meta_sha256', 'dns',
                                  'code_sha256', 'env', 'release', 'lease', 'control', 'lease_state', 'kernel_log',
                                  'run_utc', 'proxy_log'}),
    'ATTEMPT': ({'name', 'attempt_kind', 'facts', 'outcome', 'why', 'step', 'code_sha256', 'env', 'lease',
                 'session_window'}, {'session_seq', 'skipped_segments'}),
    'SERIES_END': ({'records', 'status', 'reason', 'cleanup'}, {'skipped_segments'}),
}


def journal_mode(segments):
    """segments — [(имя, байты)] по порядку. CHAIN_HASH_ONLY только если R.journal_chain принимает журнал целиком
    (нет отказа, нет недописанных сегментов) и поля каждой записи = схеме zprobe_journal.py своего вида; иначе
    PARTIAL_HASH_ONLY. → (режим, last_seq | None, last_sha256 | None). В обоих режимах байты журнала в пакет не
    идут (REL65 M-01: в каждой записи challenge): строки HASH_ONLY; цепочку проверяет root на сервере, ПК получает
    last_seq и last_sha256 как утверждение root (проверка отката по last_seq)."""
    recs, broken, why, tail = R.journal_chain(segments)
    if why is not None or broken or not recs:        # REL67 M-01: пустой журнал — не цепочка
        return 'PARTIAL_HASH_ONLY', None, None
    for rec in recs:
        must, may = J_KIND.get(rec.get('kind'), (None, None))
        keys = set(rec)
        if must is None or not (J_BASE | must) <= keys or keys - J_BASE - must - may:
            return 'PARTIAL_HASH_ONLY', None, None
    return 'CHAIN_HASH_ONLY', tail[0], tail[1]


def segments_problem(names):
    """Имена папки журнала: только NNNNNN.jsonl подряд с 000001 и файл замка .lock. None — состав верен."""
    segs = sorted(n for n in names if n != '.lock')
    for i, n in enumerate(segs, 1):
        if n != '%06d.jsonl' % i:
            return f'journal:{n}'
    return None


# ---- связи идентификаторов (M-02) и курсоры (п.1е) ----
def links_problem(fmt, series, lid, docs, bundle=None):
    """docs — {имя: пересобранный объект} одного места. Проверяются только имеющиеся поля."""
    L = lid.replace('-', '')
    st, ev, cl = docs.get('state.json'), docs.get('evidence.json'), docs.get('cleanup.json')
    checks = []
    if st:
        checks += [('state.lease_id', st.get('lease_id') == lid), ('state.lease', st.get('lease') == L)]
        if fmt == 'B10':
            checks += [('state.series', st.get('series') == series), ('state.runner', st.get('runner') == 'b10')]
    if ev and 'lease' in ev:
        checks.append(('evidence.lease', ev['lease'] == L))
    if ev and 'series' in ev:
        checks.append(('evidence.series', ev['series'] == series))
    if cl and 'lease' in cl:
        checks.append(('cleanup.lease', cl['lease'] == L))
    a = docs.get('anchor.json')
    if a:
        checks += [('anchor.lease_id', a.get('lease_id') == lid), ('anchor.lease', a.get('lease') == L),
                   ('anchor.series', a.get('series') == series == 'pb1trial2'),
                   ('anchor.lease_row', (a.get('lease_row') or {}).get('lease_id') == lid)]
    ar = docs.get('anchor_run.json')
    if ar:
        checks += [('anchor_run.lease_id', ar.get('lease_id') == lid), ('anchor_run.series', ar.get('series') == series)]
    if bundle:
        checks += [('bundle.series', bundle['series'] == series), ('bundle.lease_id', bundle['lease_id'] == lid)]
    for k, ok in checks:
        if not ok:
            return k
    return None


def _cur(c):
    d = dict(x.split('=', 1) for x in c.split(';'))
    return d['s'], int(d['i'], 16), d['b']


def cursors_problem(proof, anchor_curs, b_probe):
    """from/to proof: одно s=, b= = b_probe, i(from) ≤ i(to); каждый курсор якоря — то же s=, b=, from ≤ якорь ≤ to."""
    try:
        sf, i_f, bf = _cur(proof['journal_from_cursor'])
        st_, i_t, bt = _cur(proof['journal_to_cursor'])
        if not (sf == st_ and bf == bt == b_probe and i_f <= i_t):
            return 'cursor:proof'
        for c in anchor_curs:
            sa, ia, ba = _cur(c)
            if not (sa == sf and ba == b_probe and i_f <= ia <= i_t):
                return 'cursor:anchor'
    except (KeyError, ValueError, TypeError):
        return 'cursor:form'
    return None
