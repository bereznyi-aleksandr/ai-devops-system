#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_release.py
# ВЕРСИЯ: v0.9  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-13 10:54 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-13 17:45 +02:00
# ИСПОЛНИТЕЛЬ: Claude (v0.1 — чат «Завод 3.5.5 ПБ-1 · 03», 1bcc7ca2; v0.2 — чат «· 04», 70d36cf5)
# НАЗНАЧЕНИЕ: выпуск пробы ПБ-1 на сервере zavod-1 (проект DESIGN_3_5_5_PB1_v0_13.md §3а, §10, §11; проект выпуска
#   DESIGN_3_5_5_RELEASE). Два режима, запускает только администратор (root) командой оператора:
#   check <пакет>   — проверки §11 только чтением + план установки (что поставит install) + test_zprobe.py под
#                     непривилегированной учётной записью nobody в НОВОЙ папке /var/lib/zavod/probes-tests/<время>-NN;
#                     отчёт — новый файл /root/zprobe-check-3.5.5-<время>-NN.txt;
#   install <пакет> — тот же check (любой FAIL — отказ), затем в два прохода: (1) план — все пути, владельцы, права,
#                     предки, учётная запись и файл службы проверяются ДО любой записи; любой конфликт — REFUSED,
#                     ничего не создано; (2) создание только новых объектов. Сбой посреди (2) — PARTIAL со списком
#                     созданного; повтор install продолжает (созданное верно — пропуск, ничего не удаляется).
#   Итог — строка ZPROBE_355_CHECK=OK|FAIL или ZPROBE_355_INSTALL=OK|ALREADY|REFUSED|PARTIAL.
#   v0.2 (аудит ChatGPT REL1): M-01 двухфазная установка; M-02 тело функции сравнивается байт в байт (hex из базы);
#   M-03 строгий разбор pins — все 16 ключей, без повторов и лишних; M-04 ровно 185 испытаний, обязательные Linux-
#   испытания без пропуска; M-05 сбой journalctl/psql — FAIL, WAIT только при успешном чтении без записей; M-07 владелец,
#   группа, права и предки каталогов; L-01 испытания не от root; L-02 уникальные имена (O_EXCL), явный итог при ошибке.
#   v0.3 (аудит ChatGPT REL2): M-01 каждый новый каталог и файл сначала готовится целиком (владелец, права, байты)
#   под новым скрытым именем .zprobe-new-<имя>.<время>-NN рядом, затем одним действием ядра renameat2 с запретом
#   замены (RENAME_NOREPLACE) получает своё имя: под настоящим именем он появляется только готовым; занятое имя —
#   отказ, ничего не заменяется. Обрыв оставляет только скрытую заготовку (в отчёте PARTIAL), повтор идёт с новой;
#   M-02 CHECK 12 — rc systemctl is-active = 0, полная запись: cgroup — целое больше 0, uid — целое не меньше 0,
#   peer «адрес:порт 1–65535»; поле неверного типа — FAIL; M-03 CHECK 14 — 185 разных имён испытаний, их список
#   совпадает с закреплённым (SHA-256 отсортированного списка EXPECTED_TEST_NAMES_SHA256).
#   v0.4 (аудит ChatGPT REL3): C-01 переименования нет совсем (заготовки и renameat2 убраны). Каждый запуск install,
#   которому есть что создать, пишет НОВЫЙ файл-дневник /root/zprobe-install-3.5.5-<время>-NN.journal: перед каждым
#   действием — строка INTENT (что и с какими владельцем, правами, суммой будет создано), после — DONE; fsync каждой
#   строки. Объект создаётся сразу под своим именем (mkdir; O_EXCL|O_NOFOLLOW), затем владелец и права через
#   дескриптор. Обрыв оставляет недоделанный объект; повтор install достраивает его вперёд ТОЛЬКО если в дневнике есть
#   его INTENT и он в одном из промежуточных состояний своего же создания (каталог пустой, владелец root или целевой,
#   права 0700 или целевые; файл — root, 0600 или целевые права, байты — начало байтов выпуска): дописываются
#   недостающие байты, ставятся владелец и права. Иначе — CONFLICT, ничего не тронуто. useradd оборвался после
#   создания группы — повтор при INTENT делает useradd --gid zprobe (группа системная, без участников).
#   M-01 CHECK 12: peer — канонический IPv4-адрес петли (посредник слушает только 127.0.0.2) и порт 1–65535.
#   v0.5 (аудит ChatGPT REL4 M-01): право достроить объект доказывается его личностью, а не одним INTENT. Сразу после
#   удачного mkdir/O_EXCL в дневник пишется CREATED с устройством и номером inode созданного объекта (для группы —
#   её gid после groupadd); достраивается только объект, у которого последняя запись — CREATED после INTENT (нет DONE)
#   и тот же inode (gid). INTENT без CREATED, DONE, другой inode — CONFLICT. Группа и учётная запись создаются двумя
#   шагами (groupadd, затем useradd --gid). Два install одновременно невозможны: исключительная блокировка flock на
#   папке дневников (файл не создаётся), занято — REFUSED.
#   v0.6 (аудит ChatGPT REL5 M-01): личность проверяется на самом открытом объекте, а не только при плане. Каждый
#   объект открывается через закреплённый дескриптор родительской папки (каталог root без записи для группы и
#   прочих); перед любой записью, fchown и fchmod по открытому дескриптору сверяются устройство и inode с CREATED,
#   тип, число ссылок, владелец, права, размер и (для файла) все уже записанные байты; для каталога — пустота.
#   Расхождение — отказ без изменения (PARTIAL с причиной; повтор — CONFLICT).
#   v0.7 (check на сервере zavod-1 2026-11-13, FAIL 12_proxy «bad peer None»): посредник пишет и служебные строки —
#   READY при запуске (ровно allow, decision, listen=127.0.0.2:3128) и BUSY (ровно decision, peer). Они проверяются
#   по своей форме и записями соединений не считаются; иная форма — FAIL. install не менялся.
#   v0.9 (2026-11-13 17:45, аудит ChatGPT REL8 1/2/1): M-01 — запись соединения посредника сверяется по полной схеме handle()
#   (cell/zavod-proxy): обязательные peer, uid, user, cgroup, lease, decision, ms, at; decision — из списка, для
#   каждого — свой набор необязательных полей; лишнее или пропавшее поле — FAIL. L-01 — at разбирается календарём
#   (месяц 99, час 25, 30 февраля — FAIL). Порядок install и check не менялся.
#   v0.8 (аудит ChatGPT REL7B 1/3/0): строки посредника несут поле at (log() его добавляет): READY — ровно allow, at,
#   decision, listen; BUSY — ровно at, decision, peer; at — время UTC; allow — упорядоченный список имён без повторов и
#   без имён GitHub (M-02). Любая строка с началом ZAVOD_PROXY — только «ZAVOD_PROXY {объект JSON}», иначе FAIL (M-01).
#   Повтор ключа в JSON — FAIL (M-02).
# ОГРАНИЧЕНИЯ: ничего не удаляет, не переименовывает, не перемещает и не перезаписывает (уже записанные байты не
#   меняются, только дописываются недостающие в свой недоделанный файл); nft, привратник, посредник, шаблон zagent@
#   и база только читаются; секретов не читает (файлы из zprobe_rules.CRED_PATHS не открываются).
#   Статус WAIT — факт можно увидеть только пробой на экземпляре-пустышке (отдельный шаг), это не отказ.
import datetime
import fcntl
import grp
import hashlib
import ipaddress
import json
import os
import pwd
import re
import socket
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_rules as R  # noqa: E402

# пути и владельцы — переменные модуля, испытания test_zprobe_release.py подменяют их на папку испытания
LIB = '/usr/local/lib/zavod/probes'
UNIT = '/etc/systemd/system/zprobe-run@.service'
DATA = '/var/lib/zavod/probes'
TESTS = '/var/lib/zavod/probes-tests'
REPORT_DIR = '/root'
JOURNAL_DIR = '/root'                     # дневники установки (REL3 C-01)
JOURNAL_PREFIX = 'zprobe-install-3.5.5-'
ROOT_UID = 0
ROOT_GID = 0
TRUST_FROM = '/'
TEST_USER = 'nobody'
SYSTEM_UID_MAX = 1000                     # учётная запись zprobe — системная (uid меньше)
LIB_FILES = {'pb1_session.py': 0o644, 'zprobe_rules.py': 0o644, 'zprobe_runner.py': 0o644,
             'zprobe_journal.py': 0o644, 'zprobe-start': 0o755}
UNIT_LINES = ('User=zprobe', 'ReadWritePaths=/var/lib/zavod/probes')
# установленные файлы клетки 3.5.2: путь на сервере → путь в пакете (сверка SHA-256 только чтением, R4 C-03)
CELL = {'/etc/zavod/zavod-egress.nft': 'server/cell/zavod-egress.nft',
        '/usr/local/lib/zavod/zavod-gate': 'server/cell/zavod-gate',
        '/usr/local/lib/zavod/zavod-proxy': 'server/cell/zavod-proxy',
        '/etc/systemd/system/zavod-gate.service': 'server/cell/zavod-gate.service',
        '/etc/systemd/system/zavod-proxy.service': 'server/cell/zavod-proxy.service',
        '/etc/systemd/system/zagent@.service': 'server/cell/zagent@.service'}
# ключ pins → файл пакета (как PIN_KEYS в build_release_3_5_5.py; равенство проверяет test_zprobe_release.py)
PIN_FILES = {'pb1_session.py': 'server/probes/pb1_session.py', 'zprobe_rules.py': 'server/probes/zprobe_rules.py',
             'zprobe_runner.py': 'server/probes/zprobe_runner.py', 'zprobe_journal.py': 'server/probes/zprobe_journal.py',
             'zprobe-start': 'server/probes/zprobe-start', 'zprobe-run@.service': 'server/probes/zprobe-run@.service',
             'zagent@.service': 'server/cell/zagent@.service', 'zavod-proxy': 'server/cell/zavod-proxy',
             'zavod-gate': 'server/cell/zavod-gate', 'zavod-egress.nft': 'server/cell/zavod-egress.nft',
             'phone_zprobe_verify.py': 'phone/zprobe_verify.py', 'phone_zprobe_rules.py': 'server/probes/zprobe_rules.py',
             'pc_zprobe_refs.sh': 'pc/zprobe_refs.sh', 'pc_zprobe_refs_check.py': 'pc/zprobe_refs_check.py',
             'pc_zprobe_rules.py': 'server/probes/zprobe_rules.py'}
PIN_KEYS_ALL = frozenset(PIN_FILES) | {'release_commit'}
EXPECTED_TESTS = 185
# M-03 (REL2): SHA-256 отсортированного списка имён испытаний test_zprobe.py на Linux (часть строки PASS до ' -> ',
# без 'PASS '; строки через \n, \n в конце). Источник: CI 43401514491 x64 и Arm64 (списки равны), 185 разных имён.
EXPECTED_TEST_NAMES_SHA256 = '206f3fc092bb5cf9026dd6b3fce49682fd9b837a1973af0effbbab3587868d36'
REQUIRED_LINUX = ('142', '143', '163', '164', '166', '169', '171', '179', '180')   # без пропуска на Linux
ALLOWED_SKIP = 'SKIP 174, 175 (Windows only)'
PSQL = ['runuser', '-u', 'postgres', '--', 'psql', '-X', '-A', '-t', '-q', '-v', 'ON_ERROR_STOP=1', '-d', 'bem']
DUMMY = 'zagent@' + '0' * 32 + '.service'
OPENED_BY_CHECK = "CHECK ((btrim(opened_by) <> ''::text))"


class Refused(Exception):
    pass


def sh(*args, timeout=60, inp=None, env=None):
    try:
        p = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout, input=inp, env=env)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as x:
        return 127, '', type(x).__name__


def sha_b(b):
    return hashlib.sha256(b).hexdigest()


def sha(path):
    with open(path, 'rb') as f:
        return sha_b(f.read())


def ver(text, word):
    m = re.search(re.escape(word) + r' (\d+)\.(\d+)', text or '')
    return (int(m.group(1)), int(m.group(2))) if m else None


def read_pins(path):
    """M-03: строгий разбор — каждая строка «ключ значение», ключ из PIN_KEYS_ALL, без повторов; все ключи есть."""
    pins, errs = {}, []
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8')
    for no, ln in enumerate(text.split('\n'), 1):
        if ln == '' or ln.startswith('#'):
            continue
        parts = ln.split(' ')
        if len(parts) != 2:
            errs.append(f'line {no} is not "key value"')
            continue
        k, v = parts
        if k not in PIN_KEYS_ALL:
            errs.append(f'unknown key {k}')
        elif k in pins:
            errs.append(f'repeated key {k}')
        elif not re.fullmatch(r'[0-9a-f]{40}' if k == 'release_commit' else r'[0-9a-f]{64}', v):
            errs.append(f'bad value for {k}')
        pins.setdefault(k, v)
    errs += [f'missing key {k}' for k in sorted(PIN_KEYS_ALL - set(pins))]
    return pins, errs


def read_release(path):
    with open(path, 'rb') as f:
        b = f.read()
    m = re.fullmatch(rb'commit=([0-9a-f]{40})\nversion=3\.5\.5\n', b)
    return m.group(1).decode() if m else None


class Report:
    def __init__(self):
        self.lines, self.fails, self.waits = [], 0, 0

    def add(self, cid, status, detail):
        detail = ' '.join(str(detail).split())[:300]
        self.lines.append(f'CHECK {cid} {status} {detail}')
        print(self.lines[-1], flush=True)
        self.fails += status == 'FAIL'
        self.waits += status == 'WAIT'

    def run(self, cid, fn):
        """L-02: исключение внутри одной проверки — строка FAIL с причиной, остальные проверки идут дальше."""
        try:
            status, detail = fn()
        except Exception as x:  # noqa: BLE001 — любая ошибка проверки = FAIL, не обрыв без итога
            status, detail = 'FAIL', f'error {type(x).__name__}: {x}'
        self.add(cid, status, detail)


def sql_body(sql_bytes, name):
    """Текст функции между AS $$ и $$; байт в байт (файл читается двоично) — то, что PostgreSQL хранит в prosrc."""
    m = re.search(rb'CREATE FUNCTION bem_control\.' + name.encode() + rb'\(.*?\bAS \$\$(.*?)\$\$;', sql_bytes, re.S)
    return m.group(1) if m else None


def prosrc_same(rc, out, body):
    """M-02: база отдаёт prosrc как hex (encode(convert_to(prosrc,'UTF8'),'hex')) — без потерь последнего перевода
    строки; снимается только перевод строки, который добавляет psql после значения."""
    if rc != 0 or body is None:
        return False
    h = out[:-1] if out.endswith('\n') else out
    return bool(re.fullmatch(r'(?:[0-9a-f]{2})+', h)) and bytes.fromhex(h) == body


def kernel_verdict(rc, out, err, probe_rc, probe_out):
    """M-05: WAIT только если журнал ядра прочитан успешно (rc=0, в нём есть записи ядра) и строк отказа нет."""
    if rc != 0:
        return 'FAIL', f'journalctl -k rc={rc} {err.strip()}'
    if probe_rc != 0 or len([ln for ln in probe_out.splitlines() if ln.strip()]) != 1:
        return 'FAIL', f'kernel journal unreadable or empty (probe rc={probe_rc})'
    try:
        json.loads(probe_out)
    except ValueError:
        return 'FAIL', 'kernel journal probe is not JSON'
    msgs = []
    for ln in out.splitlines():
        if not ln.strip():
            continue
        try:
            e = json.loads(ln)
        except ValueError:
            return 'FAIL', 'kernel journal line is not JSON'
        if not isinstance(e, dict):
            return 'FAIL', 'kernel journal line is not an object'
        m = e.get('MESSAGE')
        if isinstance(m, str) and m.startswith(R.KLOG_PREFIX):
            msgs.append(e)
    if not msgs:
        return 'WAIT', 'kernel journal read OK, no refused packet in 30 days; seen only after a trial refusal'
    k = R.parse_klog(msgs[-1]['MESSAGE'])
    ts = msgs[-1].get('__REALTIME_TIMESTAMP')
    ok = bool(k) and isinstance(ts, str) and ts.isdigit()
    return ('OK' if ok else 'FAIL'), f'lines={len(msgs)} last={k}'


def _int(v):
    return type(v) is int


def peer_ok(peer):
    """REL3 M-01: посредник слушает только IPv4 127.0.0.2 (cell/zavod-proxy, LISTEN) и пишет peer как
    «адрес:порт» клиента. Верно только: канонический IPv4-адрес петли 127.0.0.0/8 и порт 1–65535 без ведущих нулей."""
    if not isinstance(peer, str) or peer.count(':') != 1:
        return False
    a, p = peer.split(':')
    try:
        ip = ipaddress.IPv4Address(a)
    except ValueError:
        return False
    return str(ip) == a and ip.is_loopback and re.fullmatch(r'[1-9][0-9]{0,4}', p) is not None and int(p) <= 65535


PROXY_LISTEN = '127.0.0.2:3128'   # cell/zavod-proxy, LISTEN
# cell/zavod-proxy: HOST (имя в списке разрешённых), GITHUB (имена GitHub в списке запрещены), log() добавляет поле at.
PROXY_HOST = re.compile(r'\A(?=.{1,253}\Z)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z')
PROXY_GITHUB = ('github.com', 'githubusercontent.com', 'githubassets.com', 'github.io', 'githubapp.com', 'ghcr.io',
                'github.dev', 'githubcopilot.com')
PROXY_AT = re.compile(r'\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z')
# REL8 M-01: запись соединения — ровно поля handle() (cell/zavod-proxy). Обязательные есть всегда; необязательные —
# только те, что handle() ставит при этом decision (error — при любом: сбой отправки ответа).
PROXY_REC_REQUIRED = frozenset({'peer', 'uid', 'user', 'cgroup', 'lease', 'decision', 'ms', 'at'})
PROXY_DECISIONS = {   # decision: (обязательные дополнительные поля, допустимые дополнительные поля)
    'NOT_A_SESSION': (frozenset(), frozenset()),
    'BAD_REQUEST': (frozenset(), frozenset()),
    'METHOD_REFUSED': (frozenset({'method', 'target'}), frozenset({'method', 'target'})),
    'NOT_ALLOWED': (frozenset({'method', 'target'}), frozenset({'method', 'target'})),
    'DNS_FAILED': (frozenset({'method', 'target', 'group'}), frozenset({'method', 'target', 'group'})),
    'PRIVATE_ADDRESS': (frozenset({'method', 'target', 'group', 'resolved'}),
                        frozenset({'method', 'target', 'group', 'resolved'})),
    'CONNECT_FAILED': (frozenset({'method', 'target', 'group'}), frozenset({'method', 'target', 'group'})),
    'ALLOWED': (frozenset({'method', 'target', 'group', 'ip'}),
                frozenset({'method', 'target', 'group', 'ip', 'end', 'bytes_up', 'bytes_down'})),
    'ERROR': (frozenset({'error'}), frozenset({'method', 'target', 'group', 'resolved', 'ip'}))}
PROXY_END = ('CLOSED', 'IDLE_TIMEOUT')   # pump()
PROXY_ALLOW_GROUP = re.compile(r'\A[a-z][a-z0-9-]{0,31}\Z')   # load_allow(): имя группы
PROXY_LEASE = re.compile(r'\A[0-9a-f]{32}\Z')                 # SESSION_UNIT
PROXY_METHOD = re.compile(r'\A[A-Z]{1,16}\Z')                 # REQ
PROXY_ERROR = re.compile(r'\A[A-Za-z_][A-Za-z0-9_]{0,63}\Z')  # type(e).__name__


def proxy_at_ok(at):
    """REL8 L-01: at — время UTC по календарю (log(): time.strftime('%Y-%m-%dT%H:%M:%SZ')), не только по шаблону цифр."""
    if not isinstance(at, str) or not PROXY_AT.match(at):
        return False
    try:
        t = datetime.datetime.strptime(at, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        return False
    return t.strftime('%Y-%m-%dT%H:%M:%SZ') == at


def _ip_ok(x):
    if not isinstance(x, str):
        return False
    try:
        ipaddress.ip_address(x)
    except ValueError:
        return False
    return True


def proxy_record_problem(d):
    """REL8 M-01: запись соединения в точной форме log(**rec) из handle(). None — запись верна; иначе причина."""
    dec = d.get('decision')
    if not isinstance(dec, str) or dec not in PROXY_DECISIONS:
        return f'bad decision {dec!r}'
    need, may = PROXY_DECISIONS[dec]
    keys = set(d)
    if not PROXY_REC_REQUIRED <= keys:
        return f'missing fields {sorted(PROXY_REC_REQUIRED - keys)}'
    extra = keys - PROXY_REC_REQUIRED
    if not need <= extra:
        return f'{dec} without fields {sorted(need - extra)}'
    if extra - may - {'error'}:
        return f'{dec} with unexpected fields {sorted(extra - may - {"error"})}'
    if dec == 'ALLOWED':   # туннель закрылся сам (end и счётчики, без error) или оборвался (error, без end и счётчиков)
        tail = {'end', 'bytes_up', 'bytes_down'} & keys
        if not ((len(tail) == 3 and 'error' not in keys) or (not tail and 'error' in keys)):
            return 'ALLOWED with an impossible end/bytes/error set'
    if not peer_ok(d['peer']):
        return f'bad peer {d["peer"]!r}'
    uid, cg = d['uid'], d['cgroup']
    if not (uid is None or (_int(uid) and uid >= 0)):
        return f'bad uid {uid!r}'
    if not (cg is None or (_int(cg) and cg > 0)):
        return f'bad cgroup {cg!r}'
    if not (d['user'] is None or (isinstance(d['user'], str) and 0 < len(d['user']) <= 256)):
        return 'bad user'
    if not (d['lease'] is None or (isinstance(d['lease'], str) and PROXY_LEASE.match(d['lease']))):
        return 'bad lease'
    if not (_int(d['ms']) and d['ms'] >= 0):
        return f'bad ms {d["ms"]!r}'
    if not proxy_at_ok(d['at']):
        return f'bad at {d["at"]!r}'
    if 'method' in d:
        m = d['method']
        if not isinstance(m, str) or not PROXY_METHOD.match(m) or (m == 'CONNECT') == (dec == 'METHOD_REFUSED'):
            return f'bad method {m!r} for {dec}'
    if 'target' in d and not (isinstance(d['target'], str) and re.fullmatch(r'\S{1,300}', d['target'])):
        return 'bad target'
    if 'group' in d and not (isinstance(d['group'], str) and PROXY_ALLOW_GROUP.match(d['group'])):
        return 'bad group'
    if 'ip' in d and not _ip_ok(d['ip']):
        return 'bad ip'
    if 'resolved' in d and not (isinstance(d['resolved'], list) and len(d['resolved']) <= 4
                                and all(_ip_ok(x) for x in d['resolved'])):
        return 'bad resolved'
    if 'end' in d and d['end'] not in PROXY_END:
        return 'bad end'
    for k in ('bytes_up', 'bytes_down'):
        if k in d and not (_int(d[k]) and d[k] >= 0):
            return f'bad {k}'
    if 'error' in d and not (isinstance(d['error'], str) and PROXY_ERROR.match(d['error'])):
        return 'bad error'
    return None


def _no_dup_keys(pairs):
    """REL7 M-02: повтор ключа в объекте JSON — отказ (json.loads иначе молча берёт последнее значение)."""
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f'duplicate key {k!r}')
        d[k] = v
    return d


def proxy_allow_ok(allow):
    """REL7 M-02: allow строки READY — sorted(список разрешённых имён) посредника: список строк, каждое — имя по HOST,
    не имя GitHub, без повторов, по порядку. Пустой список допустим (посредник тогда отказывает всем)."""
    if not isinstance(allow, list) or not all(isinstance(h, str) for h in allow):
        return False
    if allow != sorted(set(allow)):
        return False
    return all(PROXY_HOST.match(h) and not any(h == g or h.endswith('.' + g) for g in PROXY_GITHUB) for h in allow)


def proxy_verdict(active, rc, out, active_rc=0):
    """M-05, REL2 M-02: systemctl is-active rc=0 и «active»; журнал прочитан (rc=0); каждая запись ZAVOD_PROXY —
    объект JSON с полями верного типа: peer — IPv4 петли и порт 1–65535 (peer_ok), uid — целое >= 0 или null, cgroup — целое > 0 или
    null (null пишет сам посредник, когда сокет собеседника не найден). Иной тип или значение — FAIL. Полная запись —
    uid и cgroup не null. Чтение удалось, полных записей нет — WAIT (видно только пробой)."""
    if active_rc != 0 or active != 'active':
        return 'FAIL', f'zavod-proxy active={active} rc={active_rc}'
    if rc != 0:
        return 'FAIL', f'journalctl -u zavod-proxy rc={rc}'
    recs = full = 0
    for ln in out.splitlines():
        # REL7 M-01: любая строка посредника (начало «ZAVOD_PROXY») — ровно «ZAVOD_PROXY » и объект JSON; иначе FAIL.
        # Чужие строки журнала (не с этого начала) пропускаются.
        if not ln.startswith('ZAVOD_PROXY'):
            continue
        if not ln.startswith('ZAVOD_PROXY {'):
            return 'FAIL', f'ZAVOD_PROXY line is not a JSON record: {ln[:120]!r}'
        try:
            d = json.loads(ln[len('ZAVOD_PROXY '):], object_pairs_hook=_no_dup_keys)
        except ValueError:
            return 'FAIL', 'ZAVOD_PROXY record is not JSON or repeats a key'
        if not isinstance(d, dict):
            return 'FAIL', 'ZAVOD_PROXY record is not an object'
        # CHECK-1 (сервер 2026-11-13): посредник пишет и служебные строки, не соединения (cell/zavod-proxy:304, 313);
        # log() добавляет к каждой строке поле at (время UTC).
        if d.get('decision') == 'READY':          # запуск службы: ровно allow, at, decision, listen
            if set(d) != {'allow', 'at', 'decision', 'listen'} or d['listen'] != PROXY_LISTEN \
                    or not proxy_at_ok(d['at']) or not proxy_allow_ok(d['allow']):
                return 'FAIL', f'ZAVOD_PROXY READY line has unexpected form: {sorted(d)}'
            continue
        if d.get('decision') == 'BUSY':           # отказ «занято»: ровно at, decision, peer; полной записью не считается
            if set(d) != {'at', 'decision', 'peer'} or not peer_ok(d['peer']) or not proxy_at_ok(d['at']):
                return 'FAIL', f'ZAVOD_PROXY BUSY line has unexpected form or peer: {d.get("peer")!r}'
            continue
        recs += 1
        why = proxy_record_problem(d)   # REL8 M-01: полная схема записи handle()
        if why:
            return 'FAIL', f'ZAVOD_PROXY record {recs}: {why}'
        full += d['uid'] is not None and d['cgroup'] is not None
    return ('OK' if full else 'WAIT'), f'active=active records={recs} with_peer_uid_cgroup={full}'


def tests_verdict(rc, out):
    """M-04: ровно EXPECTED_TESTS испытаний, все PASS, ни одного FAIL; пропуск — только 174–175 (Windows);
    обязательные Linux-испытания REQUIRED_LINUX выполнены по-настоящему. REL2 M-03: имена испытаний (строка PASS
    до ' -> ') все разные и их отсортированный список совпадает с закреплённым EXPECTED_TEST_NAMES_SHA256."""
    lines = out.splitlines()
    last = (out.strip().splitlines() or [''])[-1]
    m = re.fullmatch(r'ZPROBE_TESTS (\d+)/(\d+) PASS', last)
    passes = [ln for ln in lines if ln.startswith('PASS ')]
    fails = [ln for ln in lines if ln.startswith('FAIL ')]
    skips = [ln for ln in lines if ln.startswith('SKIP') and not ln.startswith(ALLOWED_SKIP)]
    skipped = {ln.split()[1] for ln in passes if 'SKIPPED' in ln}
    real = {ln.split()[1] for ln in passes if 'SKIPPED' not in ln}
    missing = [n for n in REQUIRED_LINUX if n not in real]
    names = [ln[5:].partition(' -> ')[0] for ln in passes]
    names_sha = sha_b(('\n'.join(sorted(names)) + '\n').encode('utf-8'))
    dup = len(names) - len(set(names))
    ok = (rc == 0 and dup == 0 and names_sha == EXPECTED_TEST_NAMES_SHA256 and m is not None and int(m.group(1)) == int(m.group(2)) == EXPECTED_TESTS
          and len(passes) == EXPECTED_TESTS and not fails and not skips and skipped <= {'174', '175'} and not missing)
    return ('OK' if ok else 'FAIL'), (f'rc={rc} {last} pass_lines={len(passes)} fail_lines={len(fails)} '
                                      f'unexpected_skips={len(skips)} skipped={sorted(skipped)} missing_required={missing} '
                                      f'duplicate_names={dup} names_sha={names_sha[:16]} '
                                      f'names_match={names_sha == EXPECTED_TEST_NAMES_SHA256}')


def new_dir(parent, stamp, mode):
    """L-02: новая папка <stamp>-NN (mkdir отказывает, если имя занято, — берётся следующее)."""
    for i in range(1, 100):
        p = os.path.join(parent, f'{stamp}-{i:02d}')
        try:
            os.mkdir(p, mode)
        except FileExistsError:
            continue
        os.chmod(p, mode)
        return p
    raise Refused(f'no free name for {stamp} in {parent}')


def new_file(path_fmt, stamp, data, mode=0o600):
    """L-02: новый файл (O_EXCL) с первым свободным именем path_fmt.format(stamp-NN)."""
    for i in range(1, 100):
        p = path_fmt.format(f'{stamp}-{i:02d}')
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        except FileExistsError:
            continue
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        return p
    raise Refused(f'no free name for {path_fmt}')


def ancestors(path):
    """M-07: каждый предок пути (до TRUST_FROM включительно) — обычный каталог, не ссылка, владелец ROOT_UID,
    без права записи группе и прочим. Возвращает список проблем."""
    probs, cur, base = [], os.path.dirname(os.path.abspath(path)), os.path.abspath(TRUST_FROM)
    chain = [cur]
    while cur != base and os.path.dirname(cur) != cur:
        cur = os.path.dirname(cur)
        chain.append(cur)
    if cur != base:
        return [f'{path} is not under {base}']
    for d in reversed(chain):
        try:
            st = os.lstat(d)
        except OSError as x:
            probs.append(f'{d} {type(x).__name__}')
            continue
        if not stat.S_ISDIR(st.st_mode):
            probs.append(f'{d} is not a plain folder')
        elif st.st_uid != ROOT_UID or st.st_mode & 0o022:
            probs.append(f'{d} owner={st.st_uid} mode={oct(stat.S_IMODE(st.st_mode))}')
    return probs


def state_dir(path, mode, uid, gid):
    """'absent' | 'same' | текст проблемы (не каталог, ссылка, чужой владелец или права)."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return 'absent'
    if not stat.S_ISDIR(st.st_mode):
        return f'{path} exists and is not a plain folder'
    if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (uid, gid, mode):
        return f'{path} owner={st.st_uid}:{st.st_gid} mode={oct(stat.S_IMODE(st.st_mode))}, want {uid}:{gid} {oct(mode)}'
    return 'same'


def state_file(path, data, mode, uid, gid):
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return 'absent'
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        return f'{path} exists and is not a plain single-link file'
    if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (uid, gid, mode):
        return f'{path} owner={st.st_uid}:{st.st_gid} mode={oct(stat.S_IMODE(st.st_mode))}, want {uid}:{gid} {oct(mode)}'
    if sha(path) != sha_b(data):
        return f'{path} exists and differs'
    return 'same'


def get_user(name):
    try:
        return pwd.getpwnam(name)
    except KeyError:
        return None


def get_group(name):
    try:
        return grp.getgrnam(name)
    except KeyError:
        return None


def read_journal():
    """REL3 C-01, REL4 M-01: события всех дневников установки по порядку (имя дневника начинается со времени UTC,
    внутри — порядок строк). Возвращает {путь: [(событие, данные), ...]}. Дневник — обычный файл root с одной ссылкой."""
    ev = {}
    try:
        names = sorted(os.listdir(JOURNAL_DIR))
    except FileNotFoundError:
        return ev
    for n in names:
        if not (n.startswith(JOURNAL_PREFIX) and n.endswith('.journal')):
            continue
        p = os.path.join(JOURNAL_DIR, n)
        st = os.lstat(p)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != ROOT_UID:
            continue
        with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
            text = f.read().decode('utf-8', 'replace')
        for ln in text.splitlines():
            kind, _, body = ln.partition(' ')
            if kind not in ('INTENT', 'CREATED', 'DONE'):
                continue
            try:
                d = json.loads(body)
            except ValueError:
                continue
            if isinstance(d, dict) and isinstance(d.get('path'), str):
                ev.setdefault(d['path'], []).append((kind, d))
    return ev


def own_unfinished(ev, path):
    """REL4 M-01: (намерение, личность), если последняя попытка по пути — INTENT, за ним CREATED (объект точно создан
    этим install) и нет DONE. Иначе None: INTENT без CREATED, завершённая (DONE) или ничего."""
    seq = ev.get(path, [])
    i = max((k for k, (e, _) in enumerate(seq) if e == 'INTENT'), default=None)
    if i is None:
        return None
    after = [e for e, _ in seq[i + 1:]]
    if after != ['CREATED']:
        return None
    return seq[i][1], seq[i + 1][1]


def own_group_gid(ev):
    """gid группы zprobe, которую создал этот выпуск (INTENT, затем CREATED с gid; DONE допустим), иначе None."""
    seq = ev.get('group:zprobe', [])
    i = max((k for k, (e, _) in enumerate(seq) if e == 'INTENT'), default=None)
    if i is None or len(seq) < i + 2 or seq[i + 1][0] != 'CREATED':
        return None
    gid = seq[i + 1][1].get('gid')
    return gid if type(gid) is int else None


def same_object(st, cr):
    return (st.st_dev, st.st_ino) == (cr.get('dev'), cr.get('ino'))


def resumable_dir(path, rec, mode, who, uid, gid):
    """REL3 C-01, REL4 M-01: свой недоделанный каталог — запись (INTENT, CREATED) с теми же правами и владельцем, тот
    же inode, обычный каталог (не ссылка), пустой, владелец root или целевой, права 0700 (как создан) или целевые."""
    if rec is None:
        return False
    it, cr = rec
    if (it.get('kind'), it.get('mode'), it.get('who')) != ('dir', mode, who):
        return False
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode) or not same_object(st, cr) or os.listdir(path):
        return False
    return st.st_uid in (ROOT_UID, uid) and st.st_gid in (ROOT_GID, gid) and stat.S_IMODE(st.st_mode) in (0o700, mode)


def resumable_file(path, rec, data, mode):
    """REL3 C-01, REL4 M-01: свой недоделанный файл — запись (INTENT, CREATED) с той же суммой, размером и правами,
    тот же inode, обычный файл root с одной ссылкой, права 0600 или целевые, его байты — начало байтов выпуска.
    Возвращает число уже записанных байтов или None."""
    if rec is None:
        return None
    it, cr = rec
    if (it.get('kind'), it.get('sha'), it.get('size'), it.get('mode')) != ('file', sha_b(data), len(data), mode):
        return None
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode) or not same_object(st, cr) or st.st_nlink != 1 \
            or (st.st_uid, st.st_gid) != (ROOT_UID, ROOT_GID):
        return None
    if stat.S_IMODE(st.st_mode) not in (0o600, mode) or st.st_size > len(data):
        return None
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        have = f.read(len(data) + 1)
    return len(have) if len(have) == st.st_size and data[:len(have)] == have else None


def plan(pkg, commit):
    """M-01, M-07: проход 1 — ничего не пишет. Возвращает (действия, проблемы); действия — создание нового или
    (REL3 C-01) достройка своего недоделанного объекта, начатого прежним install по дневнику."""
    ops = os.path.join(pkg, 'zavod', 'ops')
    acts, probs = [], []
    ev = read_journal()
    zp = get_user('zprobe')
    if zp is None:
        if (ev.get('user:zprobe') or [('', {})])[-1][0] == 'DONE':
            probs.append('user zprobe was created by an earlier install and is missing now')
        g = get_group('zprobe')
        if g is None:
            acts += [('group', 'zprobe'), ('user', 'zprobe')]
        elif own_group_gid(ev) == g.gr_gid and 0 < g.gr_gid < SYSTEM_UID_MAX and not g.gr_mem:
            acts.append(('user', 'zprobe'))
        else:
            probs.append('group zprobe exists without user zprobe (not created by this release)')
    elif not (0 < zp.pw_uid < SYSTEM_UID_MAX) or not zp.pw_shell.endswith('nologin'):
        probs.append('user zprobe exists but is not a system nologin account')
    with open(os.path.join(ops, 'server', 'probes', 'zprobe-run@.service'), 'rb') as f:
        unit = f.read()
    lines = unit.decode('utf-8').split('\n')
    probs += [f'package unit has no line {w}' for w in UNIT_LINES if lines.count(w) != 1]
    for p in (LIB, DATA, UNIT):
        probs += ancestors(p)
    s = state_dir(LIB, 0o755, ROOT_UID, ROOT_GID)
    if s == 'absent':
        acts.append(('dir', LIB, 0o755, 'root'))
    elif s != 'same':
        rec = own_unfinished(ev, LIB)
        if resumable_dir(LIB, rec, 0o755, 'root', ROOT_UID, ROOT_GID):
            acts.append(('finish_dir', LIB, 0o755, 'root', rec[1]))
        else:
            probs.append(s)
    if zp is None:
        s = 'absent' if not os.path.lexists(DATA) else f'{DATA} exists while user zprobe does not'
    else:
        s = state_dir(DATA, 0o750, zp.pw_uid, zp.pw_gid)
    if s == 'absent':
        acts.append(('dir', DATA, 0o750, 'zprobe'))
    elif s != 'same':
        rec = own_unfinished(ev, DATA)
        if zp is not None and resumable_dir(DATA, rec, 0o750, 'zprobe', zp.pw_uid, zp.pw_gid):
            acts.append(('finish_dir', DATA, 0o750, 'zprobe', rec[1]))
        else:
            probs.append(s)
    files = []
    for n, mode in LIB_FILES.items():
        with open(os.path.join(ops, 'server', 'probes', n), 'rb') as f:
            files.append((os.path.join(LIB, n), f.read(), mode))
    files.append((os.path.join(LIB, 'RELEASE'), f'commit={commit}\nversion=3.5.5\n'.encode(), 0o644))
    files.append((UNIT, unit, 0o644))
    for path, data, mode in files:
        s = state_file(path, data, mode, ROOT_UID, ROOT_GID)
        if s == 'absent':
            acts.append(('file', path, data, mode, 0))
        elif s != 'same':
            rec = own_unfinished(ev, path)
            have = resumable_file(path, rec, data, mode)
            if have is None:
                probs.append(s)
            else:
                acts.append(('finish_file', path, data, mode, have, rec[1]))
    return acts, probs


FAULT = None          # только для испытаний: функция (шаг, путь), вызывается перед каждым действием прохода 2


def _step(name, path):
    if FAULT is not None:
        FAULT(name, path)


class Journal:
    """REL3 C-01: дневник одного запуска install — НОВЫЙ файл (O_EXCL) /root/zprobe-install-3.5.5-<время>-NN.journal,
    создаётся только когда есть что делать; строки INTENT (до действия) и DONE (после), fsync каждой строки."""

    def __init__(self, stamp):
        self.stamp, self.fd, self.path = stamp, None, None

    def _line(self, text):
        if self.fd is None:
            for i in range(1, 100):
                p = os.path.join(JOURNAL_DIR, f'{JOURNAL_PREFIX}{self.stamp}-{i:02d}.journal')
                try:
                    self.fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_APPEND, 0o600)
                    self.path = p
                    break
                except FileExistsError:
                    continue
            else:
                raise Refused('no free install journal name')
        b = (text + '\n').encode('utf-8')
        while b:
            b = b[os.write(self.fd, b):]
        os.fsync(self.fd)

    def intent(self, **d):
        self._line('INTENT ' + json.dumps(d, sort_keys=True))

    def created(self, **d):
        _step('record', d['path'])
        self._line('CREATED ' + json.dumps(d, sort_keys=True))

    def done(self, path):
        self._line('DONE ' + json.dumps({'path': path}))

    def close(self):
        if self.fd is not None:
            os.close(self.fd)


def open_parent(path):
    """REL5 M-01: закреплённый дескриптор родительской папки — каталог root без записи для группы и прочих; объект
    дальше открывается только относительно него (имя не может уйти в другую папку между проверкой и действием)."""
    pfd = os.open(os.path.dirname(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    st = os.fstat(pfd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != ROOT_UID or st.st_mode & 0o022:
        os.close(pfd)
        raise Refused(f'parent of {path} is not a root folder closed for writing; untouched')
    return pfd, os.path.basename(path)


def fd_dir_ok(fd, cr, mode, uid, gid, fresh):
    """REL5 M-01: открытый каталог — тот самый (устройство и inode из CREATED), пустой; только что созданный —
    root, 0700; недоделанный — владелец root или целевой, права 0700 или целевые."""
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or not same_object(st, cr) or os.listdir(fd):
        return False
    if fresh:
        return (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) == (ROOT_UID, ROOT_GID, 0o700)
    return st.st_uid in (ROOT_UID, uid) and st.st_gid in (ROOT_GID, gid) and stat.S_IMODE(st.st_mode) in (0o700, mode)


def fd_file_ok(fd, cr, data, mode, have):
    """REL5 M-01: открытый файл — тот самый (устройство и inode из CREATED), обычный, одна ссылка, root, права 0600
    или целевые, размер ровно have, его байты (читаются через тот же дескриптор) — начало байтов выпуска."""
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or not same_object(st, cr) or st.st_nlink != 1 \
            or (st.st_uid, st.st_gid) != (ROOT_UID, ROOT_GID) or stat.S_IMODE(st.st_mode) not in (0o600, mode) \
            or st.st_size != have:
        return False
    got = b''
    while len(got) < have:
        b = os.pread(fd, have - len(got), len(got))
        if not b:
            break
        got += b
    return got == data[:have]


def apply(acts, done, j):
    """Проход 2 — создание нового под своим именем или достройка своего недоделанного (по дневнику); ничего не
    удаляется, не переименовывается и не перезаписывается. done пополняется по мере готовности (для PARTIAL)."""
    for a in acts:
        k = a[0]
        if k == 'group':
            j.intent(kind='group', path='group:zprobe')
            _step('groupadd', 'group:zprobe')
            rc, _, err = sh('groupadd', '--system', 'zprobe')
            if rc != 0:
                raise Refused(f'groupadd rc={rc} {err.strip()}')
            g = get_group('zprobe')
            if g is None:
                raise Refused('group zprobe is missing after groupadd')
            j.created(path='group:zprobe', gid=g.gr_gid)
            j.done('group:zprobe')
            done.append('group zprobe')
        elif k == 'user':
            j.intent(kind='user', path='user:zprobe')
            _step('useradd', 'user:zprobe')
            rc, _, err = sh('useradd', '--system', '--gid', 'zprobe', '--no-create-home', '--home-dir', '/nonexistent',
                            '--shell', '/usr/sbin/nologin', 'zprobe')
            if rc != 0:
                raise Refused(f'useradd rc={rc} {err.strip()}')
            j.done('user:zprobe')
            done.append('user zprobe')
        elif k in ('dir', 'finish_dir'):
            _, path, mode, who = a[:4]
            cr = a[4] if k == 'finish_dir' else None
            u = get_user('zprobe') if who == 'zprobe' else None
            if who == 'zprobe' and u is None:
                raise Refused('user zprobe is missing after useradd')
            uid, gid = (u.pw_uid, u.pw_gid) if u else (ROOT_UID, ROOT_GID)
            pfd, name = open_parent(path)
            try:
                if k == 'dir':
                    j.intent(kind='dir', path=path, mode=mode, who=who)
                    _step('mkdir', path)
                    os.mkdir(name, 0o700, dir_fd=pfd)
                else:
                    _step('reopen', path)
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=pfd)
            finally:
                os.close(pfd)
            try:
                if k == 'dir':
                    st = os.fstat(fd)
                    cr = {'dev': st.st_dev, 'ino': st.st_ino}
                    j.created(path=path, **cr)
                if not fd_dir_ok(fd, cr, mode, uid, gid, k == 'dir'):
                    raise Refused(f'{path}: the open folder is not the one this release created or it changed; '
                                  'untouched')
                _step('chown', path)
                os.fchown(fd, uid, gid)
                _step('chmod', path)
                os.fchmod(fd, mode)
                os.fsync(fd)
            finally:
                os.close(fd)
            j.done(path)
            done.append(path)
        else:
            _, path, data, mode, have = a[:5]
            cr = a[5] if k == 'finish_file' else None
            pfd, name = open_parent(path)
            try:
                _step('open', path)
                if k == 'file':
                    j.intent(kind='file', path=path, sha=sha_b(data), size=len(data), mode=mode)
                    fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_APPEND, 0o600,
                                 dir_fd=pfd)
                    try:
                        st = os.fstat(fd)
                        cr = {'dev': st.st_dev, 'ino': st.st_ino}
                        j.created(path=path, **cr)
                    except BaseException:
                        os.close(fd)
                        raise
                else:
                    _step('reopen', path)
                    fd = os.open(name, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW, dir_fd=pfd)
            finally:
                os.close(pfd)
            with os.fdopen(fd, 'wb') as f:
                if not fd_file_ok(f.fileno(), cr, data, mode, have):
                    raise Refused(f'{path}: the open file is not the one this release created or it changed; '
                                  'untouched')
                _step('write', path)
                f.write(data[have:])
                f.flush()
                _step('fchown', path)
                os.fchown(f.fileno(), ROOT_UID, ROOT_GID)
                _step('fchmod', path)
                os.fchmod(f.fileno(), mode)
                _step('fsync', path)
                os.fsync(f.fileno())
            j.done(path)
            done.append(path)


def unit_live_check():
    rc0, _, e0 = sh('systemctl', 'daemon-reload')
    rc, vout, verr = sh('systemd-analyze', 'verify', 'zprobe-run@check.service')
    _, rw, _ = sh('systemctl', 'show', 'zprobe-run@check.service', '-p', 'ReadWritePaths', '-p', 'User')
    got = rw.split('\n')
    ok = rc0 == 0 and rc == 0 and f'ReadWritePaths={DATA}' in got and 'User=zprobe' in got
    return ok, f'reload_rc={rc0} verify_rc={rc} {(vout + verr + e0).strip()[:200]} {" ".join(got)}'


def install_lock():
    """REL4 M-01: один install за раз — исключительная блокировка flock на папке дневников (новых файлов нет)."""
    fd = os.open(JOURNAL_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def install(pkg, commit):
    lock = install_lock()
    if lock is None:
        print('ZPROBE_355_INSTALL=REFUSED another install is running (lock on the journal folder); nothing changed')
        return 1
    try:
        return install_locked(pkg, commit)
    finally:
        os.close(lock)


def install_locked(pkg, commit):
    acts, probs = plan(pkg, commit)
    if probs:
        for p in probs:
            print('CONFLICT ' + p)
        print(f'ZPROBE_355_INSTALL=REFUSED conflicts={len(probs)}; checked before any change, nothing created')
        return 1
    done = []
    os.umask(0o077)
    j = Journal(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    try:
        apply(acts, done, j)
        acts2, probs2 = plan(pkg, commit)
        ok, detail = unit_live_check()
    except Exception as x:  # noqa: BLE001
        print(f'ZPROBE_355_INSTALL=PARTIAL created={done} journal={j.path} error={type(x).__name__}: {x}; '
              'nothing removed or renamed; run install again: it finishes only objects this release created '
              '(INTENT and CREATED with the same inode in the journal, no DONE), anything else is a conflict')
        return 1
    finally:
        j.close()
    print(f'INSTALLED_NEW={done or "nothing (already installed)"}')
    print(f'AFTER_PLAN actions={len(acts2)} conflicts={probs2} UNIT {detail}')
    if acts2 or probs2 or not ok:
        print('ZPROBE_355_INSTALL=REFUSED installed state or unit does not match the release; nothing removed')
        return 1
    print('ZPROBE_355_INSTALL=' + ('OK' if done else 'ALREADY') + f' release={commit}')
    return 0


def run_tests(test_py, stamp):
    """L-01: test_zprobe.py под nobody (setpriv) в новой папке; вывод — в ту же новую папку (L-02)."""
    nb = get_user(TEST_USER)
    if nb is None:
        raise Refused(f'user {TEST_USER} is missing')
    probs = ancestors(TESTS)
    if probs:
        raise Refused('tests folder: ' + '; '.join(probs))
    if not os.path.lexists(TESTS):
        os.mkdir(TESTS, 0o755)
        os.chmod(TESTS, 0o755)
    st = os.lstat(TESTS)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != ROOT_UID or st.st_mode & 0o022:
        raise Refused(f'{TESTS} is not a root-only plain folder')
    tdir = new_dir(TESTS, stamp, 0o755)
    work = os.path.join(tdir, 'work')
    os.mkdir(work, 0o700)
    os.chown(work, nb.pw_uid, nb.pw_gid)
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'HOME': work, 'ZPROBE_TEST_ROOT': work}
    rc, out, err = sh('setpriv', f'--reuid={nb.pw_uid}', f'--regid={nb.pw_gid}', '--clear-groups', '--',
                      'python3', '-I', '-B', test_py, timeout=900, env=env)
    new_file(os.path.join(tdir, 'tests{}.out'), '', (out + err).encode('utf-8'), 0o644)
    st, detail = tests_verdict(rc, out)
    return st, f'{detail} user={TEST_USER} dir={tdir}'


def check(pkg, rep, stamp):
    ops = os.path.join(pkg, 'zavod', 'ops')
    ctx = {'pins': {}, 'commit': None}

    def c01():
        pins, errs = read_pins(os.path.join(ops, 'zprobe_pins.txt'))
        ctx['pins'] = pins
        ctx['commit'] = read_release(os.path.join(pkg, 'RELEASE'))
        bad = [k for k, p in PIN_FILES.items() if pins.get(k) != sha(os.path.join(ops, p))]
        same = ctx['commit'] is not None and ctx['commit'] == pins.get('release_commit')
        return ('FAIL' if errs or bad or not same else 'OK'), \
            f"release_commit={pins.get('release_commit')} RELEASE={ctx['commit']} pins_errors={errs} differs={bad}"
    rep.run('01_package_pins', c01)

    def c02():
        rc, osr, _ = sh('cat', '/etc/os-release')
        pretty = re.search(r'PRETTY_NAME="([^"]*)"', osr)
        u = os.uname()
        return ('OK' if u.machine == 'aarch64' and rc == 0 else 'FAIL'), \
            f"{u.machine} kernel={u.release} os={pretty.group(1) if pretty else '?'}"
    rep.run('02_platform', c02)

    def c03():
        rg, gv, _ = sh('git', '--version')
        rs, _, sv = sh('ssh', '-V')
        g = ver(gv, 'git version')
        return ('OK' if rg == 0 and g and g >= (2, 37) and rs == 0 else 'FAIL'), f'{gv.strip()} | {sv.strip()}'
    rep.run('03_git_ssh', c03)

    def c04():
        rc, cv, _ = sh('curl', '--version')
        c = ver(cv, 'curl')
        rl, ld, _ = sh('ldd', '/usr/lib/git-core/git-remote-https')
        lib = re.search(r'(libcurl[^ ]*)', ld or '')
        return ('OK' if rc == 0 and c and c >= (7, 84) and rl == 0 and lib else 'FAIL'), \
            f"{(cv.splitlines() or ['absent'])[0]} | git-remote-https -> {lib.group(1) if lib else 'no libcurl'}"
    rep.run('04_curl', c04)

    def c05():
        rc, nft, err = sh('nft', 'list', 'table', 'inet', 'zavod')
        why = R.nft_problem(nft) if rc == 0 else f'nft_rc_{rc} {err.strip()}'
        return ('FAIL' if why else 'OK'), (why or 'chains output, egress_closed equal NFT_EXPECTED')
    rep.run('05_nft_table', c05)

    def c06():
        rc, kj, err = sh('journalctl', '-k', '-q', '--no-pager', '-o', 'json', '--output-fields=MESSAGE',
                         '--since', '-30d', timeout=180)
        prc, pout, _ = sh('journalctl', '-k', '-q', '--no-pager', '-o', 'json', '--output-fields=MESSAGE', '-n', '1')
        return kernel_verdict(rc, kj, err, prc, pout)
    rep.run('06_kernel_refused_line', c06)

    for path, rel_p in sorted(CELL.items()):
        def c07(path=path, rel_p=rel_p):
            want = sha(os.path.join(ops, rel_p))
            try:
                got = sha(path)
            except OSError as x:
                got = type(x).__name__
            key = os.path.basename(path)
            if key in PIN_FILES:          # M-03: закреплённый файл — pin обязателен и равен файлу пакета
                pin = ctx['pins'].get(key)
                ok, origin = got == want and pin == want, f'pin={(pin or "MISSING")[:16]}'
            else:                         # не закреплён — происхождение: файл пакета из release_commit (CI --verify)
                ok, origin = got == want, 'origin=release_commit file (not pinned)'
            return ('OK' if ok else 'FAIL'), f'installed={got[:16]} commit={want[:16]} {origin}'
        rep.run('07_cell_' + os.path.basename(path), c07)

    def c08():
        rc, ts, _ = sh('timedatectl', 'show', '-p', 'NTPSynchronized', '--value')
        return ('OK' if rc == 0 and ts.strip() == 'yes' else 'FAIL'), f'rc={rc} NTPSynchronized={ts.strip() or "?"}'
    rep.run('08_clock', c08)

    def c09a():
        with open(os.path.join(pkg, 'zavod', 'kernel', 'db', '06_zavod_ext_04.sql'), 'rb') as f:
            body = sql_body(f.read(), 'lease_reserve_start')
        rc, src, err = sh(*PSQL, inp="SELECT encode(convert_to(prosrc, 'UTF8'), 'hex') FROM pg_proc WHERE oid = "
                          "'bem_control.lease_reserve_start(uuid)'::regprocedure;")
        h = src[:-1] if src.endswith('\n') else src
        db = bytes.fromhex(h) if re.fullmatch(r'(?:[0-9a-f]{2})*', h) else b'?'
        return ('OK' if prosrc_same(rc, src, body) else 'FAIL'), \
            f'rc={rc} sql_sha={sha_b(body or b"")[:16]} db_sha={sha_b(db)[:16]} {err.strip()}'
    rep.run('09_lease_reserve_start', c09a)

    def c09b():
        rc, cdef, err = sh(*PSQL, inp="SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = "
                           "'bem_control.chat_lease'::regclass AND conname = 'chat_lease_opened_by_check';")
        return ('OK' if rc == 0 and cdef.strip() == OPENED_BY_CHECK else 'FAIL'), f'rc={rc} {cdef.strip()} {err.strip()}'
    rep.run('09_opened_by', c09b)

    def c10():
        with open('/proc/self/stat', encoding='ascii') as f:
            st = f.read()
        return 'OK', f'field22={int(st[st.rindex(")") + 2:].split()[19])}'
    rep.run('10_proc_start_time', c10)

    def c11():
        rc, dm, _ = sh('systemctl', 'show', DUMMY, '-p', 'LoadState', '-p', 'ActiveState', '-p', 'DropInPaths')
        return ('OK' if rc == 0 and 'LoadState=loaded' in dm.split('\n') else 'FAIL'), dm.replace('\n', ' ')
    rep.run('11_dummy_instance', c11)

    def c12():
        arc, pa, _ = sh('systemctl', 'is-active', 'zavod-proxy.service')
        rc, pj, _ = sh('journalctl', '-u', 'zavod-proxy.service', '-q', '--no-pager', '-o', 'cat', '-n', '500')
        return proxy_verdict(pa.strip(), rc, pj, arc)
    rep.run('12_proxy', c12)

    def c13():
        res = []
        for port in R.PORTS:
            try:
                with socket.create_connection(('github.com', port), timeout=8):
                    res.append(f'{port}=OK')
            except OSError as x:
                res.append(f'{port}={type(x).__name__}')
        return ('OK' if all(r.endswith('=OK') for r in res) else 'FAIL'), ' '.join(res)
    rep.run('13_host_to_github', c13)

    rep.run('14_tests', lambda: run_tests(os.path.join(ops, 'server', 'probes', 'test_zprobe.py'), stamp))

    def c15():
        with open(os.path.join(ops, 'server', 'probes', 'zprobe-run@.service'), 'rb') as f:
            lines = f.read().decode('utf-8').split('\n')
        miss = [w for w in UNIT_LINES if lines.count(w) != 1]
        return ('FAIL' if miss else 'OK'), f'package unit lines {list(UNIT_LINES)} missing_or_repeated={miss}'
    rep.run('15_unit_static', c15)

    def c16():
        if ctx['commit'] is None:
            return 'FAIL', 'RELEASE unreadable'
        acts, probs = plan(pkg, ctx['commit'])
        what = [a[1] for a in acts]
        return ('FAIL' if probs else 'OK'), f'install would create {len(acts)}: {what} conflicts={probs}'
    rep.run('16_install_plan', c16)
    return ctx['commit']


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('check', 'install') or os.geteuid() != 0:
        print('usage (root): zprobe_release.py check|install <package dir>')
        return 2
    mode, pkg = sys.argv[1], os.path.abspath(sys.argv[2])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    rep = Report()
    try:
        commit = check(pkg, rep, stamp)
        path = new_file(os.path.join(REPORT_DIR, 'zprobe-check-3.5.5-{}.txt'), stamp,
                        ('\n'.join(rep.lines) + '\n').encode('utf-8'))
        print(f'REPORT={path} SHA256={sha(path)}')
    except Exception as x:  # noqa: BLE001 — L-02: всегда явный итог
        print(f'ZPROBE_355_CHECK=FAIL error={type(x).__name__}: {x}')
        if mode == 'install':
            print('ZPROBE_355_INSTALL=REFUSED check did not finish; nothing installed')
        return 1
    print(f'ZPROBE_355_CHECK={"FAIL" if rep.fails else "OK"} fails={rep.fails} waits={rep.waits}')
    if mode == 'check':
        return 1 if rep.fails else 0
    if rep.fails:
        print('ZPROBE_355_INSTALL=REFUSED check has FAIL lines; nothing installed')
        return 1
    try:
        return install(pkg, commit)
    except Exception as x:  # noqa: BLE001
        print(f'ZPROBE_355_INSTALL=REFUSED error={type(x).__name__}: {x}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
