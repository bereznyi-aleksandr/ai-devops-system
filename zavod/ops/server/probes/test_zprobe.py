#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe.py
# ВЕРСИЯ: v0.8  СТАТУС: DRAFT
# v0.8 ред. R12 (2026-11-13 08:47 +02:00): M-R12-01 — 177–181 (179 = NEW_NEGATIVE_R12_N01, 180 = NEW_NEGATIVE_R12_N02; без права
#   на ссылки — SKIPPED; 177–178 внешний файл другой папки, 181 своя верная серия).
# v0.8 ред. R11 (2026-11-13 08:32 +02:00): M-R11-01, L-R11-01 — 171–176 (171 = NEW_NEGATIVE_R11_N01 относительным и полным путём;
#   174–175 короткое имя 8.3 и регистр на Windows, 176 папка в другом регистре).
# v0.8 ред. R10 (2026-11-13 08:17 +02:00): M-R10-01, M-R10-02, L-R10-01, L-R10-02 — 164–170 (164 = NEW_NEGATIVE_R10_N01 через
#   ссылку или junction, 166 = NEW_NEGATIVE_R10_N02; 170 — прогон не пишет кеш Python рядом с исходниками).
# v0.8 ред. R9 (2026-11-13 07:55 +02:00): M-R9-01, M-R9-02 — 159–163; 161–163 — настоящий main отдельным процессом
#   точной командой приёмки без -B (161 = NEW_NEGATIVE_R9_01, 163 = NEW_NEGATIVE_R9_02; без права на ссылки — SKIPPED).
# v0.8 ред. R8 (2026-11-13 07:38 +02:00): M-R8-01, M-R8-02 — 151–158 (152 = NEW_NEGATIVE_R8_N01, 154 = NEW_NEGATIVE_R8_N02);
#   144–150 вызывают accept_problem с настоящими суммами файлов programs/.
# v0.8 (2026-11-13 07:25 +02:00, аудит R7): верная модель — у соединения переходника клиент git (peer: PID, uid 61200,
#   цепочка git-remote-http → git до git_pid), в выводе git отказ SOCKS5 (2); C-R7-01 — 135–143 (136 =
#   NEW_NEGATIVE_R7_01-A, 142–143 = живой переходник по файлу-сокету: чужой клиент не обслуживается, только Linux);
#   M-R7-01 — 144–150 (приёмка на компьютере: fetch.txt и programs.sha256).
# v0.7 (2026-11-13 07:08 +02:00, аудит R6B): C-R6-02 испытания не удаляют ничего — папки только новые (fresh_dir: mkdir в
#   ZPROBE_TEST_ROOT или <временная папка>/zprobe_tests, остаются как след), файлы только новые (x, xb);
#   случай 130 — в программах пробы и тестах нет вызовов удаления, переименования и обрезки. C-R6-01 — 121–129
#   (121 = NEW_NEGATIVE_R6_N01), 16/48/50 переведены на переходник; M-R6-01 — 131–133; L-R6-01 — 134.
# v0.6 (2026-11-13 05:59 +02:00, аудит R5): верная модель — владелец сокета каждой записи посредника (uid 61200,
#   cgroup 777) равен экземпляру сеанса, адрес собеседника — адрес сеанса 127.0.0.1, окна и метки внутри run_utc,
#   отметки начала серий; отрицательные NEW_NEGATIVE_11–15 и случаи 99–120 на каждое замечание R5.
# v0.5 (2026-11-12 23:41 +02:00, аудит R4): верная модель — у каждой попытки окно [t0, t1] по меткам journald, у
#   записей посредника и строк ядра метка ts внутри окна своей попытки, строка ядра с адресом источника, run_utc;
#   журнал — папка сегментов. Отрицательные NEW_NEGATIVE_6–10 и случаи 69–95 на каждое замечание R4.
# v0.4 (2026-11-12 23:14 +02:00, аудит R3): верная модель — отказ tcp ECONNREFUSED со строкой ядра по порту
#   источника, номера строк сеанса, сырые IPAddressDeny/Allow и таблица nft из закреплённого zavod-egress.nft, итог
#   прогона RUN_DONE и уборка SAFE; отрицательные NEW_NEGATIVE_4/5 и случаи 48–64 на каждое замечание R3.
# ДАТА СОЗДАНИЯ: 2026-11-12 19:23 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-12 19:59 +02:00 (v0.3 по аудиту R2: отрицательные
#   модели ровно на контрпримеры NEGATIVE_1–3 — подмена порта, цели, пути, адресов git, cred_paths/gh_names = null;
#   неполная опись DNS, сбой DNS, ECONNREFUSED без признака стены, чужая цель в журнале посредника, недоверенная
#   программа телефона, факты не объект; верная модель — стена EPERM, DNS по всем именам)
# ИСПОЛНИТЕЛЬ: Claude (чаты 87eee078-952e-4855-8936-7f4d449aa9ac, c7307e9c-8e0e-4e24-997c-12d9fd3b0c71)
# НАЗНАЧЕНИЕ: проверки CI без сети, без ключей и без сервера (аудит ChatGPT STAGE355 R1, раздел 4): верная
#   подставная серия даёт «ВЕРНО», а каждая из отрицательных моделей — «НЕВЕРНО» с ожидаемой причиной: пустой
#   перечень, пропуск и повтор попытки, чужой вызов, отпечаток кода, таймаут, отказ без контроля снаружи, 403
#   NOT_A_SESSION, 403 без журнала посредника, нездоровый посредник, сбой подготовки git, git 128 без признака,
#   смена свойств службы, сбой остановки, ENOTDIR, порча и подмена журнала, якорь телефона, занятое имя серии.
#   Подставная серия «ВЕРНО» показывает только согласованность программ: подлинность даёт служба (DESIGN, раздел 2).
# ВЫЗОВ: python3 -I -B test_zprobe.py   (печатает строки PASS/FAIL и итог; код 0 — все прошли)
import copy
import hashlib
import json
import os
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True           # R10 L-01: проверка не пишет кеш Python рядом с исходниками
_PYC_DIRS = [os.path.join(HERE, '__pycache__')] + [os.path.join(HERE, '..', '..', d, '__pycache__') for d in ('phone', 'pc')]


def _pyc_state():
    out = {}
    for d in _PYC_DIRS:
        if os.path.isdir(d):
            for n in os.listdir(d):
                st = os.stat(os.path.join(d, n))
                out[os.path.join(d, n)] = (st.st_size, st.st_mtime_ns)
    return out


_PYC0 = _pyc_state()
TEST_ROOT = [os.environ.get('ZPROBE_TEST_ROOT') or os.path.join(tempfile.gettempdir(), 'zprobe_tests')]
sys.path[:0] = [HERE, os.path.join(HERE, '..', '..', 'phone')]
for mod, attrs in (('fcntl', {'LOCK_EX': 2, 'flock': lambda f, op: None}),
                   ('pwd', {'getpwuid': lambda u: types.SimpleNamespace(pw_name='zprobe')})):
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = types.SimpleNamespace(**attrs)
import zprobe_rules as R  # noqa: E402
import zprobe_journal as J  # noqa: E402
import zprobe_verify as V  # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..', '..', 'pc'))
import zprobe_refs_check as RC  # noqa: E402
# Время записи журнала в тестах постоянное: иначе две сборки по разные стороны секунды дают разные байты (тест 31).
J.time = types.SimpleNamespace(strftime=lambda fmt, t=None: '2026-11-12T00:00:00Z', gmtime=lambda: None)
import ipaddress  # noqa: E402
with open(os.path.join(HERE, '..', 'cell', 'zavod-egress.nft'), encoding='utf-8') as _f:
    NFT_GOOD = 'table inet zavod {' + _f.read().split('table inet zavod {', 1)[1]
CL = {'status': 'SAFE', 'unit_active_after': 'inactive', 'load_state': 'masked', 'session_state': 'INTERRUPTED',
      'kept_copy': '/var/lib/zavod/probes/archive/s1/50-zprobe.conf', 'lease': 'a' * 32}

L = 'a' * 32
C = '0123456789abcdef0123456789abcdef'
T = ['140.82.112.3', '2606:50c0:8000::153']
PINS = {'pb1_session.py': '1' * 64, 'zprobe_rules.py': '2' * 64, 'zprobe_runner.py': '3' * 64,
        'zprobe_journal.py': '4' * 64, 'zprobe-start': '5' * 64, 'zprobe-run@.service': '6' * 64,
        'zagent@.service': '7' * 64, 'zavod-proxy': '8' * 64, 'zavod-gate': '9' * 64, 'zavod-egress.nft': 'a' * 64,
        'release_commit': 'b' * 40}
for _k, _m in (('phone_zprobe_verify.py', V), ('phone_zprobe_rules.py', R)):
    with open(_m.__file__, 'rb') as _f:
        PINS[_k] = hashlib.sha256(_f.read()).hexdigest()


SRC = {'v4': '192.0.2.10', 'v6': '2001:db8::10'}


BASE = R.iso_us('2026-11-12T21:10:00Z') + 1_000_000   # R5 M-02: окна внутри run_utc


def ts_of(i):
    """Метка journald (мкс) середины окна i-й попытки; окно i — [BASE + 10000*i, BASE + 10000*i + 5000]."""
    return BASE + 10000 * i + 2500


def good():
    plog, atts, port = [], [], [41000]

    def lp(decision, target):
        port[0] += 1
        plog.append({'peer': f'127.0.0.1:{port[0]}', 'lease': L, 'decision': decision, 'target': target, 'uid': 61200,
                     'cgroup': 777, 'ts': ts_of(len(atts))})
        return port[0]
    cage = {k: True for k in ('unit_ok', 'uid_ok', 'cgroup_ok', 'invocation_ok', 'mounts_ok', 'dropin_ok',
                              'props_ok', 'isolated_ok')}
    cage['changed_props'] = ['DropInPaths', 'ExecStart', 'ExecStartEx']
    cage['ipacl'] = ['0.0.0.0/0 ::/0', '127.0.0.2/32']
    cage['nft_table'] = NFT_GOOD
    cage['uid'], cage['cgroup_id'] = 61200, 777
    klog, sport = [], [50000]
    atts.append({'name': 'cage', 'kind': 'cage', 'facts': cage})
    atts.append({'name': 'cred_env', 'kind': 'cred_env', 'facts': {'found': []}})
    for p in R.CRED_PATHS:
        atts.append({'name': 'cred_path_' + p.strip('/').replace('/', '_'), 'kind': 'cred_path',
                     'facts': {'path': p, 'errno': 'EACCES'}})
    for ip in T:
        for port_ in R.PORTS:
            sport[0] += 1
            src = SRC[R.fam(ip)]
            klog.append({'src': src, 'dst': str(ipaddress.ip_address(ip)), 'proto': 'TCP', 'spt': sport[0],
                         'dpt': port_, 'ts': ts_of(len(atts))})
            atts.append({'name': f'tcp_{port_}_{R.ip_tag(ip)}', 'kind': 'tcp',
                         'facts': {'ip': ip, 'port': port_, 'errno': 'ECONNREFUSED', 'ms': 1, 'lport': sport[0],
                                   'src': src}})
    atts.append({'name': 'git_prep', 'kind': 'git_prep', 'facts': {'init': 0, 'add': 0, 'commit': 0, 'rev_parse': 0,
                                                                   'head': 'c' * 40, 'config_list': ''}})
    gp = lp('NOT_ALLOWED', 'github.com:443')
    atts.append({'name': 'push_https_proxy', 'kind': 'git_push', 'facts': {
        'via': 'proxy', 'rc': 128, 'absent': False,
        'stderr_tail': "fatal: unable to access: Can't complete SOCKS5 connection to github.com. (2)",
        'git_pid': 4242,
        'relay': {'conns': [{'target': 'github.com:443', 'src': '127.0.0.1', 'lport': gp, 'status': 403,
                             'err': None, 'peer': {'pid': 4243, 'uid': 61200, 'chain_ok': True,
                                                   'chain': [[4243, 'git-remote-http'], [4242, 'git']]}}],
                  'err': None, 'alive': False}}})
    atts.append({'name': 'push_https_direct', 'kind': 'git_push', 'facts': {
        'via': 'direct', 'rc': 128, 'absent': False, 'resolve': T, 'stderr_tail':
        '* Immediate connect fail for 140.82.112.3: Connection refused\n'
        '* Immediate connect fail for 2606:50c0:8000::153: Connection refused\nfatal: unable to access'}})
    atts.append({'name': 'push_ssh', 'kind': 'git_push', 'facts': {
        'via': 'ssh', 'rc': 128, 'absent': False, 'ip': T[0],
        'stderr_tail': 'ssh: connect to host 140.82.112.3 port 22: Connection refused'}})
    for n in R.GH_NAMES:
        atts.append({'name': 'connect_' + n, 'kind': 'proxy', 'facts': {
            'mode': 'connect', 'target': n + ':443', 'lport': lp('NOT_ALLOWED', n + ':443'), 'status': 403, 'err': None,
            'src': '127.0.0.1'}})
    for ip in R.first_per_family(T):
        tg = (f'[{ip}]' if ':' in ip else ip) + ':443'
        atts.append({'name': 'connect_ip_' + R.ip_tag(ip), 'kind': 'proxy', 'facts': {
            'mode': 'connect', 'target': tg, 'lport': lp('NOT_ALLOWED', tg), 'status': 403, 'err': None, 'src': '127.0.0.1'}})
    atts.append({'name': 'plain_get', 'kind': 'proxy', 'facts': {
        'mode': 'plain', 'target': 'api.github.com', 'lport': lp('METHOD_REFUSED', 'http://api.github.com/'),
        'status': 405, 'err': None, 'src': '127.0.0.1'}})
    for i, a in enumerate(atts[1:], 1):
        a['seq'] = i
        a['window'] = [BASE + 10000 * i, BASE + 10000 * i + 5000]
    req = {'series': 's1', 'challenge': C, 'probes': ['ПБ-1']}
    ev = {'series': 's1', 'challenge': C, 'probes': ['ПБ-1'], 'status': 'RUN_DONE', 'step': 'done',
          'kernel_log': klog, 'run_utc': ['2026-11-12T21:10:00Z', '2026-11-12T21:20:00Z'],
          'targets': T, 'gh_names': list(R.GH_NAMES), 'cred_paths': list(R.CRED_PATHS), 'meta_sha256': 'd' * 64,
          'dns': {n: list(T) for n in R.GH_NAMES},
          'code_sha256': {k: v for k, v in PINS.items() if k != 'release_commit' and not k.startswith('phone_')},
          'env': {'kernel': 'k'}, 'release': {'commit': 'b' * 40}, 'lease': L, 'lease_state': 'INTERRUPTED',
          'control': {'tcp': {f'{ip}|{p}': 'OPEN' for ip in T for p in R.PORTS}, 'host_v6': True,
                      'proxy_health': 'OK'},
          'proxy_log': plog, 'attempts': atts}
    return req, ev


def att(ev, name):
    return next(a for a in ev['attempts'] if a['name'] == name)


RUN_N = [0]


def fresh_dir():
    """R6 C-R6-02: новая папка испытания — только создаётся (mkdir без exist_ok), никогда не удаляется, не
    переименовывается и не перезаписывается; остаётся на диске как след прогона. Корень — ZPROBE_TEST_ROOT или
    <системная временная папка>/zprobe_tests."""
    root = TEST_ROOT[0]
    if not os.path.isdir(root):
        os.makedirs(root)
    RUN_N[0] += 1
    d = os.path.join(root, f'run-{time.strftime("%Y%m%dT%H%M%S", time.gmtime())}-{os.getpid()}-{RUN_N[0]:03d}')
    os.mkdir(d)
    return d


def journal_bytes(recs_list):
    """Сегменты журнала [(имя, байты)] после записи серий настоящим J.append во временную папку."""
    d = fresh_dir()
    if True:
        J.JDIR, J.SDIR = os.path.join(d, 'journal'), os.path.join(d, 'started')
        for series, recs in recs_list:
            J.reserve(series, recs[0]['challenge'])   # R5 M-03: как zprobe-start до запуска службы
            J.append(series, recs)
        return J.read_segments(J.JDIR)


def rechain(segs, edit):
    parts = [[json.loads(x) for x in d.split(b'\n')[:-1]] for _, d in segs]
    edit([r for p in parts for r in p])
    out, prev = [], '0' * 64
    for (name, _), p in zip(segs, parts):
        b = b''
        for r in p:
            r['prev_sha256'] = prev
            line = json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
            b += line + b'\n'
            prev = hashlib.sha256(line).hexdigest()
        out.append((name, b))
    return out


def check(series, req, ev, challenge=C, pins=PINS, anchor=None, data=None, cl=None, markers=None, refs=None):
    if data is None:
        data = journal_bytes([(series, J.build(series, req, ev, 'commit', CL if cl is None else cl))])
    return V.verdict(data, series, challenge, pins, anchor, markers, refs)[0]


def mk(*names, ch=C):
    return {n: J.marker(n, ch) for n in names}


def with_segments(segs, fn, reserved=('s1', 's2')):
    """fn() над папкой журнала с данными сегментами (для проверки J.append поверх обрыва); серии reserved уже
    отмечены (R5 M-03)."""
    d = fresh_dir()
    if True:
        J.JDIR, J.SDIR = os.path.join(d, 'journal'), os.path.join(d, 'started')
        os.mkdir(J.JDIR)
        for n in reserved:
            J.reserve(n, C)
        for n, b in segs:
            with open(os.path.join(J.JDIR, n), 'xb') as f:   # только новый файл
                f.write(b)
        try:
            fn()
            got = None
        except J.Bad as e:
            got = f'Bad({e.code}) {e}'
        try:
            segs = J.read_segments(J.JDIR)
        except J.Bad:
            segs = None
        return got, segs


RESULTS = []


def _try(fn):
    """R10: исключение → его текст (для отрицательных случаев)."""
    try:
        fn()
    except (OSError, ValueError) as x:
        return str(x)
    return None


def case(name, want, got):
    ok = (got is None) if want is None else (got is not None and want in got)
    RESULTS.append(ok)
    print(('PASS ' if ok else 'FAIL ') + name + ' -> ' + str(got))


def mut(name, want, f, **kw):
    req, ev = good()
    f(req, ev)
    case(name, want, check('s1', req, ev, **kw))


def main():
    req, ev = good()
    case('01 good synthetic series', None, check('s1', req, ev))
    mut('02 empty probe list', 'probe list', lambda r, e: r.update(probes=[]))
    mut('03 missing attempt', 'missing', lambda r, e: e['attempts'].pop())
    mut('04 duplicate attempt', 'duplicate', lambda r, e: e['attempts'].append(copy.deepcopy(e['attempts'][1])))
    mut('05 attempt outside matrix', 'outside the matrix',
        lambda r, e: e['attempts'].append({'name': 'tcp_80_x', 'kind': 'tcp', 'facts': {}}))
    case('06 foreign challenge', 'foreign challenge', check('s1', req, ev, challenge='f' * 32))
    case('07 code fingerprint vs pins', 'fingerprints', check('s1', req, ev, pins=dict(PINS, **{'zprobe_rules.py': '0' * 64})))
    mut('08 tcp timeout', 'NOT_PROVEN', lambda r, e: att(e, 'tcp_22_140.82.112.3')['facts'].update(errno='timeout'))
    mut('09 refusal without outside control', 'no_outside_control',
        lambda r, e: e['control']['tcp'].update({'140.82.112.3|22': 'CLOSED'}))
    mut('10 slow refusal', 'NOT_PROVEN', lambda r, e: att(e, 'tcp_443_140.82.112.3')['facts'].update(ms=3000))
    mut('11 403 NOT_A_SESSION', 'NOT_PROVEN', lambda r, e: [x.update(decision='NOT_A_SESSION') for x in e['proxy_log']
                                                            if x['target'] == 'api.github.com:443'])
    mut('12 403 without proxy log', 'log_0', lambda r, e: e['proxy_log'].remove(
        next(x for x in e['proxy_log'] if x['target'] == 'uploads.github.com:443')))
    mut('13 CONNECT answered 405', 'NOT_PROVEN', lambda r, e: att(e, 'connect_ghcr.io')['facts'].update(status=405))
    mut('14 proxy not healthy', 'proxy health', lambda r, e: e['control'].update(proxy_health='FAILED'))
    mut('15 git commit failed', 'git_prep', lambda r, e: att(e, 'git_prep')['facts'].update(commit=1))
    mut('16 R6 git relay: proxy answer not 403', 'relay_not_403',
        lambda r, e: att(e, 'push_https_proxy')['facts']['relay']['conns'][0].update(status=502))
    mut('17 direct push connected', 'direct_unconfirmed', lambda r, e: att(e, 'push_https_direct')['facts'].update(
        stderr_tail=att(e, 'push_https_direct')['facts']['stderr_tail'] + '\n* Connected to github.com (140.82.112.3)'))
    mut('18 extra unit property changed', 'extra_props',
        lambda r, e: att(e, 'cage')['facts']['changed_props'].append('IPAddressDeny'))
    mut('19 cage mounts not proven', 'cage_mounts_ok', lambda r, e: att(e, 'cage')['facts'].update(mounts_ok=False))
    mut('20 runner aborted (stop failed)', 'INTERRUPTED',
        lambda r, e: e.update(status='ABORTED', step='stop', reason='Abort:session_not_stopped'))
    mut('21 ENOTDIR on key path', 'NOT_PROVEN', lambda r, e: att(e, 'cred_path_root')['facts'].update(errno='ENOTDIR'))
    mut('22 token name in environment', 'OPEN', lambda r, e: att(e, 'cred_env')['facts'].update(found=['GH_TOKEN']))
    mut('23 IPv6 unreachable while host has IPv6', 'NOT_PROVEN', lambda r, e: (
        att(e, 'tcp_443_2606-50c0-8000--153')['facts'].update(errno='ENETUNREACH'),
        e['control']['tcp'].update({'2606:50c0:8000::153|443': 'CLOSED'})))

    def no_v6(r, e):
        e['control']['host_v6'] = False
        for p in R.PORTS:
            att(e, f'tcp_{p}_2606-50c0-8000--153')['facts'].update(errno='ENETUNREACH')
            e['control']['tcp'][f'2606:50c0:8000::153|{p}'] = 'CLOSED'
        att(e, 'push_https_direct')['facts'].update(stderr_tail=
                                                     '* Immediate connect fail for 140.82.112.3: Connection refused')
    mut('24 IPv6 absent on host is accepted', None, no_v6)
    mut('25 lease not INTERRUPTED', 'lease state', lambda r, e: e.update(lease_state='RUNNING'))
    # Аудит R2: контрпримеры ChatGPT и новые требования — каждый обязан дать «НЕВЕРНО».
    mut('34 R2 NEGATIVE_1 port swapped', 'binding_port',
        lambda r, e: att(e, 'tcp_443_140.82.112.3')['facts'].update(port=22))
    mut('35 R2 NEGATIVE_2 connect target swapped', 'binding_target',
        lambda r, e: att(e, 'connect_api.github.com')['facts'].update(target='github.com:443'))
    mut('36 R2 NEGATIVE_2 key path swapped', 'binding_path',
        lambda r, e: att(e, 'cred_path_etc_zavod')['facts'].update(path='/tmp'))
    mut('37 R2 NEGATIVE_3 cred_paths null', 'cred_paths differ', lambda r, e: e.update(cred_paths=None))
    mut('38 R2 NEGATIVE_3 gh_names null', 'gh_names differ', lambda r, e: e.update(gh_names=None))
    mut('39 R2 C-02 targets truncated', 'full DNS inventory', lambda r, e: e.update(targets=T[:1]))
    mut('40 R2 C-02 DNS failure for one name', 'failed or malformed',
        lambda r, e: e['dns'].update({'ghcr.io': ['error_OSError']}))
    mut('41 R2 M-07 EHOSTUNREACH is not a proven wall', 'NOT_PROVEN',
        lambda r, e: att(e, 'tcp_22_140.82.112.3')['facts'].update(errno='EHOSTUNREACH'))
    mut('42 R2 C-01 git resolve swapped', 'binding_resolve',
        lambda r, e: att(e, 'push_https_direct')['facts'].update(resolve=T[:1]))
    mut('43 R2 C-01 proxy log for another target', 'log_0', lambda r, e: [
        x.update(target='gist.github.com:443') for x in e['proxy_log'] if x['target'] == 'api.github.com:443'])
    mut('44 R2 L-08 facts not an object', 'facts_not_object', lambda r, e: att(e, 'cred_env').update(facts=None))
    mut('45 R2 L-08 control malformed', 'control malformed', lambda r, e: e.update(control={'proxy_health': 'OK', 'tcp': None}))
    case('46 R2 L-09 phone program not trusted', 'phone program not trusted',
         check('s1', req, ev, pins=dict(PINS, **{'phone_zprobe_rules.py': '0' * 64})))
    mut('47 R2 C-01 kind swapped', 'kind_mismatch', lambda r, e: att(e, 'plain_get').update(kind='tcp'))
    # Аудит R3: контрпримеры ChatGPT и новые требования — каждый обязан дать «НЕВЕРНО».
    mut('48 R3 NEW_NEGATIVE_4 git proxy record removed, CONNECT kept', 'relay_log_0',
        lambda r, e: e['proxy_log'].pop(0))
    mut('49 R3 C-01 second proxy record in the git window', 'proxy_unconfirmed_2', lambda r, e: e['proxy_log'].append(
        {'peer': '127.0.0.1:49999', 'lease': L, 'decision': 'NOT_ALLOWED', 'target': 'github.com:443', 'uid': 61200,
         'cgroup': 777, 'ts': att(e, 'push_https_proxy')['window'][0] + 1}))
    mut('50 R3 C-01 git record ALLOWED', 'relay_log_1', lambda r, e: e['proxy_log'][0].update(decision='ALLOWED'))
    mut('51 R3 M-04 kernel refusal line missing', 'kernel_log_0', lambda r, e: e['kernel_log'].pop(0))
    mut('52 R3 M-04 kernel line for another source port', 'kernel_log_0',
        lambda r, e: e['kernel_log'][0].update(spt=1))
    mut('53 R3 M-04 tcp without own port', 'no_lport',
        lambda r, e: att(e, 'tcp_22_140.82.112.3')['facts'].update(lport=None))
    mut('54 R3 M-04 session line numbers broken', 'session_seq_broken',
        lambda r, e: att(e, 'cred_env').update(seq=99))
    mut('55 R3 M-02 deny is partial', 'ipacl_deny_not_any',
        lambda r, e: att(e, 'cage')['facts'].update(ipacl=['0.0.0.0/0', '127.0.0.2/32']))
    mut('56 R3 M-02 extra allowed address', 'ipacl_allow_not_exact',
        lambda r, e: att(e, 'cage')['facts'].update(ipacl=['0.0.0.0/0 ::/0', '127.0.0.2/32 10.0.0.0/8']))
    mut('57 R3 M-02 accept before session jump', 'nft_chain_differs_output', lambda r, e: att(e, 'cage')['facts'].update(
        nft_table=NFT_GOOD.replace('\t\tmeta skuid 61184-65519 jump', '\t\tmeta skuid 61184-65519 accept\n\t\tmeta skuid 61184-65519 jump', 1)))
    mut('58 R3 M-02 output chain not hooked', 'nft_chain_differs_output', lambda r, e: att(e, 'cage')['facts'].update(
        nft_table=NFT_GOOD.replace('hook output', 'hook prerouting', 1)))
    mut('59 R3 M-02 nft string present but chain missing', 'nft_table_count',
        lambda r, e: att(e, 'cage')['facts'].update(nft_table='meta skuid 61184-65519 jump egress_closed'))
    mut('60 R3 C-02 template touched', 'cage_isolated_ok',
        lambda r, e: att(e, 'cage')['facts'].update(isolated_ok=False))
    req, ev = good()
    case('61 R3 M-03 cleanup failed -> INTERRUPTED', 'cleanup_BLOCKED_STOP_FAILED',
         check('s1', req, ev, cl=dict(CL, status='BLOCKED_STOP_FAILED')))
    case('62 R3 M-03 cleanup missing -> INTERRUPTED', 'cleanup_missing', check('s1', req, ev, cl='missing'))
    case('63 R3 M-03 unit not masked', 'cleanup_not_sealed', check('s1', req, ev, cl=dict(CL, load_state='loaded')))
    pc = {'pc_zprobe_refs.sh': 'e' * 64, 'pc_zprobe_refs_check.py': 'f' * 64}
    rb = ('ZPROBE_REFS v2\nwhen=before\nseries=s1\nrepo=%s\nprefix=%s\ntool_sha256=%s\ntime_utc=2026-11-12T21:05:00Z\n'
          'rc=0\n---\n') % (R.REFS_REPO, R.REFS_PREFIX, 'e' * 64)
    ra = rb.replace('when=before', 'when=after').replace('21:05:00', '21:25:00')
    tl = f'ZPROBE_TIMES series=s1 challenge={C} run_start=2026-11-12T21:10:00Z run_end=2026-11-12T21:20:00Z ' \
         f'pins_sha256={"9" * 64}'

    def rp(b=rb, a=ra, t=tl, p=pc, ps='9' * 64, me='f' * 64):
        return RC.problem(b, a, t, p, ps, me)
    case('64 R3 M-01 refs before/after unchanged around the run', None, rp())
    case('65 R3 NEW_NEGATIVE_5 no refs documents', 'malformed', rp('', ''))
    case('66 R3 M-01 read error', 'read failed', rp(a=ra.replace('rc=0', 'rc=128')))
    case('67 R3 M-01 probe branch on GitHub', 'probe branch exists',
         rp(a=ra + 'e' * 40 + '\trefs/heads/zprobe/pb1-' + C[:8] + '\n'))
    case('68 R3 M-01 after earlier than the run end', 'do not bracket', rp(a=ra.replace('21:25:00', '21:15:00')))
    # Аудит R4: контрпримеры ChatGPT NEW_NEGATIVE_6–10 и новые требования — каждый обязан дать «НЕВЕРНО».
    mut('69 R4 NEW_NEGATIVE_6 git record replaced by a foreign record outside windows', 'proxy_unexplained_1',
        lambda r, e: (e['proxy_log'].pop(0), e['proxy_log'].append(
            {'peer': '127.0.0.1:49998', 'lease': L, 'decision': 'NOT_ALLOWED', 'target': 'github.com:443',
             'uid': 61200, 'cgroup': 777, 'ts': att(e, 'git_prep')['window'][0] + 1})))
    mut('70 R4 C-01 foreign record between two windows', 'proxy_unexplained_1', lambda r, e: e['proxy_log'].append(
        {'peer': '127.0.0.1:49997', 'lease': L, 'decision': 'NOT_ALLOWED', 'target': 'github.com:443', 'uid': 61200,
         'cgroup': 777, 'ts': att(e, 'push_https_proxy')['window'][1] + 100}))
    mut('71 R4 C-01 proxy record without journal time', 'no journal time',
        lambda r, e: e['proxy_log'][0].pop('ts'))
    mut('72 R4 C-01 CONNECT record in another attempt window', 'log_0', lambda r, e: next(
        x for x in e['proxy_log'] if x['target'] == 'api.github.com:443').update(
        ts=att(e, 'connect_gist.github.com')['window'][0] + 1))
    mut('73 R4 NEW_NEGATIVE_7 return in egress_closed', 'nft_chain_differs_egress_closed',
        lambda r, e: att(e, 'cage')['facts'].update(nft_table=NFT_GOOD.replace(
            '\t\tmeta l4proto tcp reject', '\t\tip daddr 140.82.112.3 return\n\t\tmeta l4proto tcp reject', 1)))
    mut('74 R4 C-02 goto in output', 'nft_chain_differs_output',
        lambda r, e: att(e, 'cage')['facts'].update(nft_table=NFT_GOOD.replace(
            '\t\tct state established,related accept', '\t\tct state established,related accept\n\t\tgoto input', 1)))
    mut('75 R4 C-02 second table inet zavod', 'nft_table_count',
        lambda r, e: att(e, 'cage')['facts'].update(nft_table=NFT_GOOD + '\n' + NFT_GOOD))
    ch = R._nft_chains(NFT_GOOD)
    case('76 R4 C-02 pinned rule list equals cell/zavod-egress.nft', None,
         None if all(ch.get(k) == v for k, v in R.NFT_EXPECTED.items()) else 'NFT_EXPECTED differs from the file')
    case('77 R4 NEW_NEGATIVE_8 both snapshots after the run', 'do not bracket',
         rp(b=rb.replace('21:05:00', '21:21:00'), a=ra.replace('21:25:00', '21:22:00')))
    case('78 R4 M-01 snapshot for another series', 'another series', rp(b=rb.replace('series=s1', 'series=s9')))
    case('79 R4 M-01 snapshot too far from the run', 'too far', rp(b=rb.replace('21:05:00', '20:00:00')))
    case('80 R4 L-02 snapshot by a program not in pins', 'not in pins',
         rp(a=ra.replace('tool_sha256=' + 'e' * 64, 'tool_sha256=' + '0' * 64)))
    case('81 R4 L-02 PC check program not in pins', 'differs from pins', rp(me='0' * 64))
    case('82 R4 L-02 pins differ from the phone manifest', 'pins file differs', rp(ps='0' * 64))
    case('83 R4 M-01 times line forged or malformed', 'malformed', rp(t=tl.replace('series=s1', 'series=')))
    req, ev = good()
    case('84 R4 NEW_NEGATIVE_9 cleanup with no session_start row', 'cleanup_not_sealed',
         check('s1', req, ev, cl=dict(CL, session_state='NONE')))
    mut('85 R4 NEW_NEGATIVE_10 kernel line from another source address', 'kernel_log_0',
        lambda r, e: e['kernel_log'][0].update(src='192.0.2.99'))
    mut('86 R4 M-03 kernel line outside the attempt window', 'kernel_log_0',
        lambda r, e: e['kernel_log'][0].update(ts=att(e, 'tcp_22_140.82.112.3')['window'][0] - 1))
    mut('87 R4 M-03 tcp without source address', 'no_src',
        lambda r, e: att(e, 'tcp_22_140.82.112.3')['facts'].update(src=None))
    mut('88 R4 windows overlap', 'session_window_broken',
        lambda r, e: att(e, 'cred_env')['window'].__setitem__(1, att(e, 'cred_env')['window'][1] + 20000))
    mut('89 R4 window missing (no PB1_BEGIN)', 'session_window_broken', lambda r, e: att(e, 'git_prep').update(window=None))
    mut('90 R4 M-01 run times missing', 'run_utc malformed', lambda r, e: e.update(run_utc=None))
    req, ev = good()
    s1 = journal_bytes([('s1', J.build('s1', req, ev, 'commit', CL))])
    req2, ev2 = good()
    req2['series'] = ev2['series'] = 's2'
    cut = [(s1[0][0], s1[0][1][:-30])]           # обрыв записи: последняя строка не дописана
    got, segs = with_segments(cut, lambda: J.append('s2', J.build('s2', req2, ev2, 'commit', CL)))
    case('91 R4 M-04 new series after a torn segment is written', None, got)
    case('92 R4 M-04 series after a torn segment verifies', None, check('s2', req2, ev2, data=segs))
    case('93 R4 M-04 torn series reported as interrupted', 'series interrupted', check('s1', req, ev, data=segs))
    case('94 R4 M-04 torn segment kept byte for byte', None, None if segs[0] == cut[0] else 'torn segment changed')
    case('95 R4 M-04 torn segment not declared by the next one', 'not declared',
         check('s2', req2, ev2, data=rechain(segs, lambda rs: next(x for x in rs if x.get('series') == 's2').update(skipped_segments=[]))))
    segs_cut = segs

    # Аудит R5: контрпримеры ChatGPT NEW_NEGATIVE_11–15 и новые требования — каждый обязан дать «НЕВЕРНО».
    def foreign_git(r, e, **kw):
        g = e['proxy_log'][0]
        g.update(kw)
    mut('99 R5 NEW_NEGATIVE_11 git record of another owner in the same window', 'proxy_foreign_owner',
        lambda r, e: foreign_git(r, e, peer='127.0.0.3:49998', uid=65000))
    mut('100 R5 C-01 git record from another cgroup', 'proxy_foreign_owner', lambda r, e: foreign_git(r, e, cgroup=778))
    mut('101 R5 C-01 CONNECT record from another address, same port', 'proxy_foreign_owner', lambda r, e: next(
        x for x in e['proxy_log'] if x['target'] == 'api.github.com:443').update(
        peer='127.0.0.3:' + str(att(e, 'connect_api.github.com')['facts']['lport'])))
    mut('102 R5 C-01 proxy attempt without own address', 'proxy_src_unknown',
        lambda r, e: att(e, 'connect_api.github.com')['facts'].update(src=None))
    mut('103 R5 C-01 git record port equals a CONNECT port', 'proxy_port_reused', lambda r, e: foreign_git(
        r, e, peer='127.0.0.1:' + str(att(e, 'connect_github.com')['facts']['lport'])))
    mut('104 R5 C-01 session cgroup unknown', 'proxy_owner_unknown', lambda r, e: att(e, 'cage')['facts'].pop('cgroup_id'))
    forged = tl.replace('21:10:00', '21:22:00').replace('21:20:00', '21:26:00')
    b2, a2 = rb.replace('21:05:00', '21:21:00'), ra.replace('21:25:00', '21:28:00')
    case('105a R5 NEW_NEGATIVE_12 forged typed line passes only the preliminary check', None, rp(b=b2, a=a2, t=forged))
    pins_pc = dict(PINS, **pc)
    req, ev = good()
    case('105 R5 NEW_NEGATIVE_12 step check uses run times from the journal', 'do not bracket',
         check('s1', req, ev, pins=pins_pc, refs=(b2, a2)))
    case('106 R5 M-01 step check with snapshots around the journal run', None, check('s1', req, ev, pins=pins_pc,
                                                                                    refs=(rb, ra)))
    mut('107 R5 NEW_NEGATIVE_13 run_utc shifted by two days', 'session_outside_run_time',
        lambda r, e: e.update(run_utc=['2026-11-14T21:10:00Z', '2026-11-14T21:20:00Z']))
    mut('108 R5 M-02 proxy record time outside the run', 'session_outside_run_time',
        lambda r, e: e['proxy_log'][-1].update(ts=BASE + 4_000_000_000))
    req, ev = good()
    case('111 R5 M-03 phone: series without its start mark', 'not reserved', check('s1', req, ev, markers=mk('s2')))
    case('112 R5 M-03 phone: torn segment matched to no reserved series', 'torn segment not matched',
         check('s2', req2, ev2, data=segs_cut, markers=mk('s2')))
    case('112a R5 M-03 phone: torn reserved series is interrupted', 'series interrupted',
         check('s1', req, ev, data=segs_cut, markers=mk('s1', 's2')))
    case('112b R5 M-03 phone: series after torn reserved one verifies', None,
         check('s2', req2, ev2, data=segs_cut, markers=mk('s1', 's2')))
    case('113 R5 M-03 phone: start mark with another challenge', 'not reserved with this challenge',
         check('s1', req, ev, markers=mk('s1', ch='f' * 32)))
    B = 'PB1_BEGIN {"name": "cred_env", "seq": 1}'
    A = 'PB1 {"facts": {"found": []}, "kind": "cred_env", "name": "cred_env", "seq": 1}'
    good_msgs = [(B, 10), (A, 20), ('PB1_DONE', 30)]
    got = R.collect_session(good_msgs)
    case('114a R5 M-05 strict session lines give windows', None,
         got[1] or (None if got[0][0]['window'] == [10, 20] else 'window wrong'))
    case('114 R5 NEW_NEGATIVE_15 duplicate PB1_BEGIN refused', 'begin_out_of_order',
         R.collect_session([(B, 5), (B, 10), (A, 20), ('PB1_DONE', 30)])[1])
    case('115 R5 M-05 begin without result refused', 'begin_without_result',
         R.collect_session([(B, 10), ('PB1_DONE', 30)])[1])
    case('116 R5 M-05 result without begin refused', 'result_without_begin', R.collect_session([(A, 20), ('PB1_DONE', 30)])[1])
    case('117 R5 M-05 unknown session line refused', 'line_unknown',
         R.collect_session([('PB1_PLAN_BAD ValueError', 1), ('PB1_DONE', 2)])[1])
    with open(os.path.join(HERE, 'pb1_session.py'), encoding='utf-8') as f:
        src = f.read()
    case('119 R5 M-04 session work folder and file only new', None,
         None if 'exist_ok=True' not in src and 'os.O_EXCL' in src and "open(os.path.join(repo, 'pb1.txt'), 'w'" not in src
         else 'session may replace files')
    case('120 R5 M-01 PC rules module not in pins', 'zprobe_rules.py differs',
         RC.problem(rb, ra, tl, dict(pc, pc_zprobe_rules_py=None), '9' * 64, 'f' * 64, '0' * 64))
    # R6 (аудит ChatGPT R6B): C-R6-01 точный порт соединения git через переходник; C-R6-02 испытания без удаления.
    mut('121 R6 NEW_NEGATIVE_R6_N01 git record with another port of the same owner', 'relay_log_0',
        lambda r, e: e['proxy_log'][0].update(peer='127.0.0.1:49998'))

    def relay(e):
        return att(e, 'push_https_proxy')['facts']['relay']
    mut('122 R6 C-01 relay saw no connection', 'proxy_src_unknown', lambda r, e: relay(e).update(conns=[]))
    mut('123 R6 C-01 relay thread not stopped', 'proxy_src_unknown', lambda r, e: relay(e).update(alive=True))
    mut('124 R6 C-01 relay error', 'proxy_src_unknown', lambda r, e: relay(e).update(err='EADDRINUSE'))
    mut('125 R6 C-01 relay connection without own port', 'proxy_src_unknown',
        lambda r, e: relay(e)['conns'][0].update(lport=None))
    mut('126 R6 C-01 second relay connection without proxy record', 'relay_log_0',
        lambda r, e: relay(e)['conns'].append(dict(relay(e)['conns'][0], lport=49996)))
    mut('127 R6 C-01 relay target is not github.com:443', 'relay_not_403',
        lambda r, e: relay(e)['conns'][0].update(target='api.github.com:443'))
    mut('128 R6 C-01 extra owner record in the git window', 'proxy_unconfirmed_2',
        lambda r, e: e['proxy_log'].append(dict(e['proxy_log'][0], peer='127.0.0.1:49995')))
    case('129 R6 C-01 session sends git only through its relay', None,
         None if "'socks5h://localhost' + sock" in src and 'http://127.0.0.2:3128' not in src
         and 'f[\'src\'], f[\'lport\'] = u.getsockname()[:2]' in src
         and 'relay.set_git(p.pid)' in src and 'SO_PEERCRED' in src else 'git not bound to relay port')
    # R7 C-R7-01: клиент переходника — именно git этой попытки, и git сам сообщил отказ SOCKS5.
    def peer(e):
        return relay(e)['conns'][0]['peer']
    mut('135 R7 C-01 relay client is not git (chain not reaching git)', 'relay_peer_not_git',
        lambda r, e: peer(e).update(chain_ok=False, chain=[[5000, 'python3']]))
    mut('136 R7 NEW_NEGATIVE_R7_01-A git rc 128 without SOCKS refusal', 'git_no_socks_refusal',
        lambda r, e: att(e, 'push_https_proxy')['facts'].update(
            stderr_tail='fatal: unsupported proxy scheme, git did not reach relay'))
    mut('137 R7 C-01 relay client uid is not the session uid', 'relay_peer_not_git',
        lambda r, e: peer(e).update(uid=0))
    mut('138 R7 C-01 chain ends at another process', 'relay_peer_not_git',
        lambda r, e: peer(e).update(chain=[[4243, 'git-remote-http'], [4100, 'git']]))
    mut('139 R7 C-01 git pid unknown', 'relay_peer_not_git',
        lambda r, e: att(e, 'push_https_proxy')['facts'].update(git_pid=None))
    mut('140 R7 C-01 non-git name inside the chain', 'relay_peer_not_git',
        lambda r, e: peer(e).update(chain=[[4243, 'python3'], [4242, 'git']], pid=4243))
    mut('141 R7 C-01 relay connection without peer facts', 'relay_peer_not_git',
        lambda r, e: relay(e)['conns'][0].update(peer=None))
    import socket as _so
    import pb1_session as PS
    if hasattr(_so, 'AF_UNIX') and hasattr(_so, 'SO_PEERCRED') and os.path.isdir('/proc/self'):
        import subprocess as _sp
        d = fresh_dir()
        other = _sp.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        rl = PS.Relay(os.path.join(d, 'r1'))
        rl.set_git(other.pid)                # git — другой процесс; клиент — сам тест (не потомок git)
        with _so.socket(_so.AF_UNIX, _so.SOCK_STREAM) as cl:
            cl.connect(os.path.join(d, 'r1'))
            cl.sendall(b'\x05\x01\x00')
            cl.settimeout(10)
            try:
                got_b = cl.recv(16)
            except ConnectionResetError:     # переходник закрыл соединение, не прочитав приветствие
                got_b = b''
        rep = rl.close()
        other.kill()
        other.wait()
        c0 = (rep['conns'] or [{}])[0]
        case('142 R7 NEW_NEGATIVE_R7_01-B live relay refuses a SOCKS client that is not git', None,
             None if c0.get('err') == 'peer_not_git' and got_b == b'' and c0.get('target') is None
             else f'served foreign client: {c0} {got_b!r}')
        rl = PS.Relay(os.path.join(d, 'r2'))
        rl.set_git(os.getpid())              # «git» — сам тест: цепочка из одного звена дошла
        with _so.socket(_so.AF_UNIX, _so.SOCK_STREAM) as cl:
            cl.connect(os.path.join(d, 'r2'))
            cl.sendall(b'\x05\x01\x00')
            cl.settimeout(10)
            got_b = cl.recv(16)
        rep = rl.close()
        c0 = (rep['conns'] or [{}])[0]
        pr = c0.get('peer') or {}
        case('143 R7 C-01 live relay records peer pid, uid and chain of its own client', None,
             None if pr.get('chain_ok') is True and pr.get('pid') == os.getpid() and pr.get('uid') == os.getuid()
             and got_b[:2] == b'\x05\x00' else f'peer not recorded: {c0} {got_b!r}')
    else:
        print('SKIP 142, 143 (live relay over AF_UNIX needs Linux) — counted as PASS only on this platform')
        case('142 R7 NEW_NEGATIVE_R7_01-B live relay (SKIPPED: not Linux)', None, None)
        case('143 R7 C-01 live relay peer facts (SKIPPED: not Linux)', None, None)
    # R7 M-R7-01: приёмка на компьютере сама требует fetch.txt с тремя нулями и programs.sha256 = манифест.
    msha = '7' * 64
    real = {'zprobe_verify.py': PINS['phone_zprobe_verify.py'], 'zprobe_rules.py': PINS['phone_zprobe_rules.py'],
            'zprobe_pins.txt': msha}
    good_prog = (f"{PINS['phone_zprobe_verify.py']}  zprobe_verify.py\n{PINS['phone_zprobe_rules.py']}  zprobe_rules.py\n"
                 f"{msha}  zprobe_pins.txt\n")
    case('144 R7 M-01 acceptance with fetch codes 0 and programs from manifest', None,
         V.accept_problem(V.FETCH_OK + '\n', good_prog, PINS, msha, real))
    case('145 R7 NEW_NEGATIVE_R7_02 ssh_rc=255 in fetch.txt -> not accepted', 'fetch.txt',
         V.accept_problem('ZPROBE_FETCH ssh_rc=255 started_rc=0 journal_rc=0\n', good_prog, PINS, msha, real))
    case('146 R7 M-01 fetch.txt missing -> not accepted', 'fetch.txt', V.accept_problem(None, good_prog, PINS, msha, real))
    case('147 R7 M-01 journal scp failed -> not accepted', 'fetch.txt',
         V.accept_problem('ZPROBE_FETCH ssh_rc=0 started_rc=0 journal_rc=1\n', good_prog, PINS, msha, real))
    case('148 R7 M-01 series pins differ from release manifest', 'differs',
         V.accept_problem(V.FETCH_OK, good_prog, PINS, '8' * 64, real))
    case('149 R7 M-01 series rules program differs', 'differs',
         V.accept_problem(V.FETCH_OK, good_prog.replace(PINS['phone_zprobe_rules.py'], 'e' * 64), PINS, msha, real))
    case('150 R7 M-01 programs.sha256 missing or with an extra line', 'programs.sha256',
         V.accept_problem(V.FETCH_OK, None, PINS, msha, real) or V.accept_problem(V.FETCH_OK, good_prog + 'f' * 64 + '  x\n',
                                                                         PINS, msha, real))
    bad = ['shutil.' + 'rmtree', 'os.' + 'remove(', 'os.' + 'unlink(', 'os.' + 'rmdir(', 'os.' + 'rename(',
           'os.' + 'replace(', 'Temporary' + 'Directory', 'O_' + 'TRUNC', '.un' + 'link(', 'remove' + 'dirs']
    found = []
    for fn in ('pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py', 'test_zprobe.py',
               'zprobe-start', '../../phone/zprobe_verify.py', '../../pc/zprobe_refs_check.py'):
        with open(os.path.join(HERE, *fn.split('/')), encoding='utf-8') as f:
            text = f.read()
        found += [fn + ':' + b for b in bad if b in text]
    case('130 R6 C-02 probe programs and tests contain no delete, rename or truncate call', None,
         ', '.join(found) or None)
    # R6 M-R6-01: служба упала до SERIES_END, на сервере нет ни одного сегмента — телефон всё равно проверяет.
    case('131 R6 M-01 reserved series, journal folder empty -> interrupted', 'series interrupted',
         V.verdict([], 's9', C, PINS, None, mk('s9'))[0])
    case('132 R6 M-01 empty journal and no start mark fetched -> refused', 'not',
         V.verdict([], 's9', C, PINS, None, {})[0])
    with open(os.path.join(HERE, '..', '..', 'phone', 'zprobe_series.sh'), encoding='utf-8') as f:
        ph = f.read()
    tail_ = ph.split('set +e', 1)[-1]
    case('133 R6 M-01 phone keeps going after ssh failure and fetches started and journal', None,
         None if ('SRC=${PIPESTATUS[0]}' in tail_ and 'mkdir "$W/$S/journal"' in tail_
                  and tail_.index('started"; MRC') < tail_.index('zprobe_verify.py" "$W/$S/journal"')
                  and 'exit 3' in tail_) else 'phone may stop before verification')
    case('134 R6 L-01 phone copies pinned programs into the series folder', None,
         None if 'programs.sha256' in ph and '"$W/$S/programs/$f"' in ph else 'programs not in series folder')

    # R8 M-R8-01, M-R8-02: входы приёмки — только из папки серии, файлы programs/ — по настоящим байтам.
    def series_dir(fetch_line='ZPROBE_FETCH ssh_rc=0 started_rc=0 journal_rc=0', files=None, drop=None, extra=None):
        root = os.path.join(fresh_dir(), 's1')     # R9 M-02: имя корня = имя серии
        os.mkdir(root)
        os.mkdir(os.path.join(root, 'journal'))
        os.mkdir(os.path.join(root, 'programs'))
        body = files or {'zprobe_verify.py': b'v', 'zprobe_rules.py': b'r', 'zprobe_pins.txt': b'p'}
        for nme, b in body.items():
            if nme != drop:
                with open(os.path.join(root, 'programs', nme), 'xb') as f:
                    f.write(b)
        if extra:
            with open(os.path.join(root, 'programs', extra), 'xb') as f:
                f.write(b'x')
        with open(os.path.join(root, 'programs.sha256'), 'x', encoding='utf-8') as f:
            for nme, b in body.items():
                f.write(hashlib.sha256(b).hexdigest() + '  ' + nme + '\n')
        with open(os.path.join(root, 'fetch.txt'), 'x', encoding='utf-8') as f:
            f.write(fetch_line + '\n')
        return root
    hv = {nme: hashlib.sha256(b).hexdigest() for nme, b in (('zprobe_verify.py', b'v'), ('zprobe_rules.py', b'r'))}
    pins8 = dict(PINS, **{'phone_zprobe_verify.py': hv['zprobe_verify.py'], 'phone_zprobe_rules.py': hv['zprobe_rules.py']})
    m8 = hashlib.sha256(b'p').hexdigest()

    def accept(root, fetch=None):
        why, ft, pt, act = V.series_inputs(os.path.join(root, 'journal'), fetch or os.path.join(root, 'fetch.txt'), 's1')
        return why or V.accept_problem(ft, pt, pins8, m8, act)
    ok_dir = series_dir()
    case('151 R8 acceptance inputs from the series folder, real bytes match', None, accept(ok_dir))
    bad_dir = series_dir('ZPROBE_FETCH ssh_rc=255 started_rc=0 journal_rc=0')
    case('152 R8 NEW_NEGATIVE_R8_N01 foreign fetch.txt with three zeros for a series with ssh_rc=255', 'not the one',
         accept(bad_dir, os.path.join(ok_dir, 'fetch.txt')))
    case('153 R8 M-01 own fetch.txt with ssh_rc=255 -> not accepted', 'fetch.txt', accept(bad_dir))
    case('154 R8 NEW_NEGATIVE_R8_N02 programs/zprobe_pins.txt missing, list still right', 'exactly the three',
         accept(series_dir(drop='zprobe_pins.txt')))
    d8 = series_dir()
    with open(os.path.join(d8, 'programs', 'zprobe_pins.txt'), 'ab') as f:
        f.write(b'changed')
    case('155 R8 M-02 pins copy byte changed, old list kept', 'bytes differ', accept(d8))
    case('156 R8 M-02 program copy missing', 'exactly the three', accept(series_dir(drop='zprobe_rules.py')))
    case('157 R8 M-02 extra file in programs/', 'exactly the three', accept(series_dir(extra='notes.txt')))
    case('158 R8 M-01 main reads fetch and programs only through series_inputs', None,
         None if 'series_inputs(path, a[9], series, oth)' in open(V.__file__, encoding='utf-8').read()
         else 'main bypasses series_inputs')
    case('159 R9 M-02 series folder name differs from series', 'name differs',
         V.series_inputs(os.path.join(ok_dir, 'journal'), os.path.join(ok_dir, 'fetch.txt'), 's2')[0])
    case('160 R9 M-02 journal argument not <series folder>/journal', 'must be',
         V.series_inputs(os.path.join(ok_dir, 'started'), os.path.join(ok_dir, 'fetch.txt'), 's1')[0])
    # R9: полная команда приёмки — настоящий main в отдельном процессе, точная команда без -B, новая папка.
    import subprocess as _sp2
    req9, ev9 = good()
    seg9 = journal_bytes([('s1', J.build('s1', req9, ev9, 'commit', CL))])
    pins9 = dict(PINS, **pc)
    man9 = ''.join(f'{k} {v}\n' for k, v in sorted(pins9.items())).encode('ascii')

    def full_series(fetch_line=V.FETCH_OK, journal_link=None, programs=True, seg_link=None, link_files=None):
        top = fresh_dir()
        root = os.path.join(top, 's1')
        os.mkdir(root)
        if journal_link:
            os.symlink(journal_link, os.path.join(root, 'journal'), target_is_directory=True)
        else:
            os.mkdir(os.path.join(root, 'journal'))
            if seg_link:
                os.symlink(seg_link, os.path.join(root, 'journal', seg9[0][0]))
            for nme, b in ([] if seg_link else seg9):
                with open(os.path.join(root, 'journal', nme), 'xb') as f:
                    f.write(b)
        os.mkdir(os.path.join(root, 'started'))
        with open(os.path.join(root, 'started', 's1'), 'xb') as f:
            f.write(J.marker('s1', C))
        files = {'zprobe_verify.py': open(V.__file__, 'rb').read(), 'zprobe_rules.py': open(R.__file__, 'rb').read(),
                 'zprobe_pins.txt': man9}
        if programs:
            os.mkdir(os.path.join(root, 'programs'))
            for nme, b in files.items():
                with open(os.path.join(root, 'programs', nme), 'xb') as f:
                    f.write(b)
        for nme, b in (('programs.sha256', ''.join(hashlib.sha256(b).hexdigest() + '  ' + nme + '\n'
                                                   for nme, b in files.items()).encode('ascii')),
                       ('fetch.txt', (fetch_line + '\n').encode('ascii')), ('manifest.txt', man9),
                       ('refs_before.txt', rb.encode('utf-8')), ('refs_after.txt', ra.encode('utf-8'))):
            if nme in (link_files or {}):    # R12: файл корня — ссылка на чужой файл
                os.symlink(link_files[nme], os.path.join(root, nme))
                continue
            with open(os.path.join(root, nme), 'xb') as f:
                f.write(b)
        return root

    def run_main(root, prog=None, fetch='fetch.txt', journal='journal', manifest='manifest.txt', after='refs_after.txt'):
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        env.pop('PYTHONDONTWRITEBYTECODE', None)
        p = _sp2.run([sys.executable, '-I', prog or os.path.join('programs', 'zprobe_verify.py'), journal, 's1', C,
                      manifest, '-', '--refs', 'refs_before.txt', after, '--fetch', fetch],
                     cwd=root, env=env, capture_output=True, timeout=120)
        b = p.stdout + p.stderr        # -I не читает PYTHONIOENCODING: на Windows вывод в кодировке системы
        try:
            t = b.decode('utf-8')
        except UnicodeDecodeError:
            import locale
            t = b.decode(locale.getpreferredencoding(False), 'replace')
        return p.returncode, t.strip().splitlines()[:1]
    g9 = full_series()
    rc9, out9 = run_main(g9)
    case('161 R9 NEW_NEGATIVE_R9_01 exact acceptance command without -B accepts a true series, no __pycache__', None,
         None if rc9 == 0 and out9 and out9[0].startswith('ВЕРНО (журнал и ветки')
         and not os.path.exists(os.path.join(g9, 'programs', '__pycache__')) else f'rc={rc9} {out9}')
    b9 = full_series('ZPROBE_FETCH ssh_rc=255 started_rc=0 journal_rc=0')
    rc9, out9 = run_main(b9, fetch=os.path.join(g9, 'fetch.txt'))
    case('162 R9 main: foreign fetch.txt for a series with ssh_rc=255 refused', None,
         None if rc9 == 1 and out9 and 'not the one' in out9[0] else f'rc={rc9} {out9}')
    try:
        l9 = full_series('ZPROBE_FETCH ssh_rc=255 started_rc=0 journal_rc=0', journal_link=os.path.join(g9, 'journal'),
                         programs=False)
    except (OSError, NotImplementedError) as x:
        l9 = None
        print('SKIP 163 body (symlink not allowed here: ' + type(x).__name__ + ') — counted as PASS only on this platform')
    if l9:
        rc9, out9 = run_main(l9, prog=os.path.join(g9, 'programs', 'zprobe_verify.py'), fetch=os.path.join(g9, 'fetch.txt'))
        case('163 R9 NEW_NEGATIVE_R9_02 journal is a link to another true series -> refused', None,
             None if rc9 == 1 and out9 and 'link' in out9[0] else f'rc={rc9} {out9}')
    else:
        case('163 R9 NEW_NEGATIVE_R9_02 journal link (SKIPPED: no symlink right)', None, None)
    # R10 M-R10-01: корень серии — ссылка (или junction Windows) на исправную серию; полные пути через ссылку.
    top10 = fresh_dir()
    lk10 = os.path.join(top10, 's1')
    try:
        os.symlink(g9, lk10, target_is_directory=True)
    except (OSError, NotImplementedError):
        if os.name == 'nt':
            _sp2.run(['cmd', '/c', 'mklink', '/J', os.path.normpath(lk10), os.path.normpath(g9)], capture_output=True)
    if os.path.isdir(lk10):
        rc10, out10 = run_main(lk10, prog=os.path.join(g9, 'programs', 'zprobe_verify.py'),
                               fetch=os.path.join(lk10, 'fetch.txt'), journal=os.path.join(lk10, 'journal'))
        case('164 R10 NEW_NEGATIVE_R10_N01 series root is a link/junction to a true series -> refused', None,
             None if rc10 == 1 and out10 and 'through a link' in out10[0] else f'rc={rc10} {out10}')
    else:
        print('SKIP 164 body (neither symlink nor junction allowed here) — counted as PASS only on this platform')
        case('164 R10 NEW_NEGATIVE_R10_N01 root link (SKIPPED)', None, None)
    case('165 R10 M-01 real series folder (no links on the path) still accepted', None,
         None if V.ancestor_problem(g9) is None else V.ancestor_problem(g9))
    # R10 M-R10-02: файл журнала — ссылка на внешний открытый файл: отказ ДО чтения, его отпечаток не печатается.
    dummy = os.path.join(fresh_dir(), 'public_dummy.bin')
    with open(dummy, 'xb') as f:
        f.write(b'public dummy bytes, not a journal\n')
    dsum = R.segments_digest([(seg9[0][0], open(dummy, 'rb').read())])[1]
    try:
        n10 = full_series(seg_link=dummy)
    except (OSError, NotImplementedError) as x:
        n10 = None
        print('SKIP 166 body (file symlink not allowed here: ' + type(x).__name__ + ') — counted as PASS only on this platform')
    if n10:
        rc10, out10 = run_main(n10)
        case('166 R10 NEW_NEGATIVE_R10_N02 journal file is a link: refused, foreign bytes not read', None,
             None if rc10 == 1 and out10 and 'link' in out10[0] and dsum not in out10[0] else f'rc={rc10} {out10}')
    else:
        case('166 R10 NEW_NEGATIVE_R10_N02 journal file link (SKIPPED: no symlink right)', None, None)
    case('167 R10 M-02 read_plain refuses a non-plain file (folder)', None,
         None if _try(lambda: V.read_plain(fresh_dir())) else 'folder read as a file')
    psrc = open(os.path.join(HERE, 'pb1_session.py'), encoding='utf-8').read()
    case('168 R10 L-02 relay checks process start time of client (before/after) and git', None,
         None if 'gen_ok' in psrc and 'self.git_start == self.start_time(top)' in psrc and
         's0 == self.start_time(pid)' in psrc else 'no process generation check')
    if os.path.isdir('/proc/self'):
        import pb1_session as _P
        st10 = _P.Relay.start_time(os.getpid())
        case('169 R10 L-02 start_time of a live process is a number, of an absent one None', None,
             None if isinstance(st10, int) and _P.Relay.start_time(2 ** 22 + 7) is None else f'{st10}')
    else:
        print('SKIP 169 (needs /proc, Linux) — counted as PASS only on this platform')
        case('169 R10 L-02 start_time (SKIPPED: no /proc)', None, None)
    # R11 M-R11-01: hop/../journal, где hop — ссылка (junction) в исправную серию A: отказ до чтения.
    b11 = full_series()
    hop = os.path.join(b11, 'hop')
    os.mkdir(os.path.join(g9, 'bridge11')) if not os.path.exists(os.path.join(g9, 'bridge11')) else None
    try:
        os.symlink(os.path.join(g9, 'bridge11'), hop, target_is_directory=True)
    except (OSError, NotImplementedError):
        if os.name == 'nt':
            _sp2.run(['cmd', '/c', 'mklink', '/J', os.path.normpath(hop), os.path.normpath(os.path.join(g9, 'bridge11'))],
                     capture_output=True)
    if os.path.isdir(hop):
        for jarg in (os.path.join('hop', '..', 'journal'), os.path.join(b11, 'hop', '..', 'journal')):
            rc11, out11 = run_main(b11, journal=jarg)
            case('171 R11 NEW_NEGATIVE_R11_N01 journal argument ' + ('relative' if jarg.startswith('hop') else 'absolute')
                 + ' hop/../journal -> refused', None,
                 None if rc11 == 1 and out11 and "'..'" in out11[0] else f'rc={rc11} {out11}')
    else:
        print('SKIP 171 body (neither symlink nor junction allowed here) — counted as PASS only on this platform')
        case('171 R11 NEW_NEGATIVE_R11_N01 (SKIPPED)', None, None)
    case('172 R11 M-01 raw_problem: .. refused, plain journal path accepted', None,
         None if V.raw_problem('a/../journal') and V.raw_problem('a\\..\\journal') and V.raw_problem('journal') is None
         and V.raw_problem(os.path.join(g9, 'journal')) is None else 'raw_problem wrong')
    src11 = open(V.__file__, encoding='utf-8').read()
    case('173 R11 M-01 main reads the journal only at <root>/journal after the checks', None,
         None if "read_segments(os.path.join(series_root(path), 'journal') if len(a) == 10 else path)" in src11
         else 'main reads the raw journal argument')
    if os.name == 'nt':                   # R11 L-01: короткое имя 8.3 и другой регистр папки-предка не мешают
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        n11 = ctypes.windll.kernel32.GetShortPathNameW(os.path.normpath(g9), buf, 1024)
        short = buf.value if n11 else ''
        up11 = os.path.dirname(os.path.normpath(g9))
        alt = os.path.join(up11.swapcase() if up11[:1].isalpha() else up11, 's1')
        case('174 R11 L-01 real series folder via other-case parent path accepted', None, V.link_problem(alt, 's1'))
        if short and os.path.normcase(short) != os.path.normcase(os.path.normpath(g9)):
            case('175 R11 L-01 real series folder via 8.3 short path: ancestors not a link', None, V.ancestor_problem(short))
        else:
            print('SKIP 175 (8.3 short names off on this volume) — counted as PASS only on this platform')
            case('175 R11 L-01 8.3 short path (SKIPPED: no short names)', None, None)
    else:
        print('SKIP 174, 175 (Windows only) — counted as PASS only on this platform')
        case('174 R11 L-01 other case (SKIPPED: not Windows)', None, None)
        case('175 R11 L-01 8.3 short path (SKIPPED: not Windows)', None, None)
    case('176 R11 L-01 series folder named in other case than series -> refused', 'name differs',
         V.link_problem(os.path.join(os.path.dirname(g9), 'S1'), 's1'))
    # R12 M-R12-01: манифест и снимки — только файлы корня серии, не ссылки.
    for no12, kw12, nm12 in (('177', {'after': os.path.join(g9, 'refs_after.txt')}, 'refs_after.txt'),
                             ('178', {'manifest': os.path.join(g9, 'manifest.txt')}, 'manifest.txt')):
        rc12, out12 = run_main(full_series(), **kw12)
        case(no12 + ' R12 M-01 ' + nm12 + ' of another series folder -> refused', None,
             None if rc12 == 1 and out12 and nm12 in out12[0] else f'rc={rc12} {out12}')
    for no12, nm12, tag12 in (('179', 'refs_after.txt', 'NEW_NEGATIVE_R12_N01'), ('180', 'manifest.txt', 'NEW_NEGATIVE_R12_N02')):
        try:
            l12 = full_series(link_files={nm12: os.path.join(g9, nm12)})
        except (OSError, NotImplementedError) as x:
            l12 = None
            print(f'SKIP {no12} body (file symlink not allowed here: ' + type(x).__name__ + ') — counted as PASS only on this platform')
        if l12:
            rc12, out12 = run_main(l12)
            case(f'{no12} R12 {tag12} {nm12} is a link to another series -> refused', None,
                 None if rc12 == 1 and out12 and nm12 in out12[0] else f'rc={rc12} {out12}')
        else:
            case(f'{no12} R12 {tag12} {nm12} link (SKIPPED: no symlink right)', None, None)
    rc12, out12 = run_main(full_series())
    case('181 R12 own plain manifest and snapshots in the series folder still accepted', None,
         None if rc12 == 0 and out12 and out12[0].startswith('ВЕРНО (журнал и ветки') else f'rc={rc12} {out12}')
    case('170 R10 L-01 this run wrote no Python cache next to the sources', None,
         None if _pyc_state() == _PYC0 else 'cache changed: ' + ', '.join(sorted(set(_pyc_state()) ^ set(_PYC0)))[:300])

    req, ev = good()
    data = journal_bytes([('s1', J.build('s1', req, ev, 'commit', CL))])
    nm, raw = data[0]
    case('26 byte changed in journal', 'chain broken',
         check('s1', req, ev, data=[(nm, raw.replace(b'"ECONNREFUSED"', b'"ECONNREFUSEX"', 1))]))
    case('27 bad JSON line', 'bad JSON', check('s1', req, ev, data=[(nm, raw[:40] + b'\n' + raw[41:])]))

    def flip(recs):
        recs[3]['outcome'] = 'DENIED_POLICY'
        recs[3]['facts']['errno'] = 'ENOTDIR'
    case('28 outcome forged and re-chained', 'rules give', check('s1', req, ev, data=rechain(data, flip)))
    case('29 step forged and re-chained', 'mismatch',
         check('s1', req, ev, data=rechain(data, lambda rs: rs[3].update(step='3.5.5.2'))))
    other = rechain(data, lambda rs: rs[0].update(time='2000-01-01T00:00:00Z'))
    case('30 phone anchor: history rewritten', 'phone anchor',
         check('s1', req, ev, data=data, anchor=R.segments_digest(other)))
    req2, ev2 = good()
    req2['series'] = ev2['series'] = 's2'
    data2 = journal_bytes([('s1', J.build('s1', req, ev, 'commit', CL)), ('s2', J.build('s2', req2, ev2, 'commit', CL))])
    case('31 anchor of first series holds after second', None,
         check('s2', req2, ev2, data=data2, anchor=R.segments_digest(data)))
    got, _ = with_segments([], lambda: (J.append('s1', J.build('s1', req, ev, 'abort')[:1]),
                                        J.append('s1', J.build('s1', req, ev, 'commit', CL))))
    case('32 series name reuse refused', 'Bad(3)', got)
    got, _ = with_segments([], lambda: J.reserve('s1', C))
    case('109 R5 NEW_NEGATIVE_14 second start mark for the same series name refused', 'already used', got)
    got, _ = with_segments([], lambda: J.append('s3', J.build('s3', dict(req, series='s3'), dict(ev, series='s3'),
                                                                'commit', CL)))
    case('110 R5 M-03 series without a start mark is not written', 'not reserved', got)
    got, segs = with_segments([('000001.jsonl', b'{not json}\n')],
                              lambda: J.append('s1', J.build('s1', req, ev, 'commit', CL)))
    case('33 damaged journal refused without write', 'Bad(3)', got if len(segs) == 1 else 'written anyway')
    got, _ = with_segments([('000002.jsonl', data[0][1])], lambda: J.append('s1', J.build('s1', req, ev, 'commit', CL)))
    case('96 R4 M-04 segment numbers with a gap refused', 'not contiguous', got)
    got, _ = with_segments([('notes.txt', b'x')], lambda: J.append('s1', J.build('s1', req, ev, 'commit', CL)))
    case('97 R4 M-04 foreign file in journal folder refused', 'foreign file', got)
    d = fresh_dir()
    if True:
        pp = os.path.join(d, 'pins.txt')
        with open(pp, 'x', encoding='utf-8') as f:
            f.write('release_commit ' + 'b' * 40 + '\n')
        start = next(r for r in V.R.journal_chain(data)[0] if r['kind'] == 'SERIES_START')
        line = V.times_line('s1', C, start, pp)
    case('98 R4 M-01 phone times line is what the PC check reads', None,
         None if RC.TIMES.match(line) else 'times line format differs: ' + line)
    n = sum(RESULTS)
    print(f'ZPROBE_TESTS {n}/{len(RESULTS)} PASS')
    sys.exit(0 if n == len(RESULTS) else 1)


if __name__ == '__main__':
    main()
