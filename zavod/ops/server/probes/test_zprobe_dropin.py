#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_dropin.py
# ВЕРСИЯ: v0.5 (B15)  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 14:32 +02:00
# v0.5 (Claude, терминал zavod; выпуск B15): D21 — бегунок B15 первой записью пишет запись старта S (startrec);
#   в D21 задан INVOCATION_ID (как у службы systemd) и папка startrec/<серия> во временной папке, и проверено, что
#   S записана до отказа диска на dropin_check.json и evidence.json.
# v0.4 (Claude, терминал zavod; REL124 AGREED 0/0/1, L-355-REL124-01): D46–D48 — схема выгрузки evidence.json
#   (EVIDENCE.cage_partial): настоящий cage_partial из dropin_verdict с raw_changed_props проходит sanitize и
#   check_sanitized ПК; формат v0.1 (без raw_changed_props) проходит; плохое имя, не список, лишнее поле — отказ.
#   D49 — release.version «3.5.5-b10»/«3.5.5-b13» (как в RELEASE сборщика) проходит выгрузку, «3.5.5-x» и «-b100» — нет.
# v0.3 (Claude, терминал zavod; B13, REL123 M-355-REL123-01 и L-355-REL123-01): D07 — новая строка журнала; D22–D45 —
#   смысловое сравнение: перестановка наборов и замер MemoryAvailable проходят (значения из CI 44282558463), любое
#   изменение состава, охранных свойств (MemoryMax, ProtectSystem, IPAddressDeny, ExecStartPre, User, Slice), новое
#   неизвестное свойство, дубликат, чужие знаки, обрезка и потеря dropin_check.json — отказ до start; бегунок
#   dropin_verdict: proceed и cage.props_ok всегда совпадают; документ v0.2 и cage_partial проходят схему выгрузки.
# v0.2 (2026-11-15 12:11, терминал zavod, сменщик 3a6de98b; REL68 L-01): D21 — CI 28, один запуск zprobe_runner.main,
#   где не записались и dropin_check.json, и evidence.json → одна строка diag=INCOMPLETE, итог INTERRUPTED.
# ДАТА СОЗДАНИЯ: 2026-11-14 23:00 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 09» (3037f186)
# НАЗНАЧЕНИЕ: проверки zprobe_dropin.py (проект B10 v0.18 раздел 2). Каждая проверка — одно нарушение.
#   Печатает CASE <имя> PASS/FAIL и итог ZPROBE_DROPIN_TEST=PASS/FAIL. Запуск: python3 -I test_zprobe_dropin.py
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_dropin as D  # noqa: E402

ALLOWED = {'ExecStart', 'ExecStartEx', 'DropInPaths'}
BASE = {'ExecStart': 'old', 'DropInPaths': '', 'User': 'zagent', 'MemoryMax': '3221225472'}
OK = True
ROOT = os.environ.get('ZPROBE_TEST_ROOT') or None


def case(name, cond):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL')


def after(**kw):
    a = dict(BASE)
    a.update(kw)
    return a


def run(a, writer=None, logger=None, before=BASE):
    d = tempfile.mkdtemp(prefix='zdrop-', dir=ROOT)
    lines = []
    lg = logger or (lambda s: lines.append(s) or True)
    r = D.decide(before, a, ALLOWED, 'systemd 255', '2026-11-14T21:00:00Z', os.path.join(d, 'dropin_check.json'),
                 **({'writer': writer} if writer else {}), logger=lg)
    return r, lines, d


r, lines, d = run(after(ExecStart='new', DropInPaths='/run/x.conf'))
case('D01 only allowed keys -> OK, proceed', r['proceed'] and r['doc']['result'] == 'OK' and r['abort'] is None)
with open(os.path.join(d, 'dropin_check.json'), encoding='ascii') as f:
    disk = json.load(f)
case('D02 file written equals document', disk == r['doc'] and r['code'] == '-')
case('D03 file mode 0600', os.stat(os.path.join(d, 'dropin_check.json')).st_mode & 0o777 == 0o600
     or os.name != 'posix')
case('D04 Exec value redacted, no value and no hash', disk['values']['ExecStart'] == {
    'redacted': True, 'len_before': 3, 'len_after': 3} and 'new' not in json.dumps(disk))

r, lines, d = run(after(ExecStart='new', User='root'))
case('D05 extra key -> REFUSED, abort dropin_changed_other_props',
     not r['proceed'] and r['doc']['result'] == 'REFUSED' and r['abort'] == 'dropin_changed_other_props'
     and r['doc']['extra'] == ['User'])
case('D06 non-sensitive values kept before/after', r['doc']['values']['User'] == {'before': 'zagent', 'after': 'root'})
case('D07 log line: result, names, no values',
     lines == ['ZPROBE_DROPIN_CHECK result=REFUSED diag=OK code=- n=2 changed=ExecStart,User raw=2 reordered=- '
               'runtime=- unparsed=-'])

r, lines, d = run(after(Environment='TOKEN=abc', ExecStart='new'))
case('D08 Environment redacted and secret not in log or file',
     r['doc']['values']['Environment'].get('redacted') is True and 'abc' not in json.dumps(r['doc'])
     and 'abc' not in lines[0])

r, lines, d = run(after(Description='x' * 600))
case('D09 value over 512 -> truncated, complete=false, STOP diag_overflow',
     r['doc']['values']['Description']['after_truncated'] is True and len(r['doc']['values']['Description']['after'])
     == 512 and not r['doc']['complete'] and r['doc']['result'] == 'STOP' and r['abort'] == 'diag_overflow'
     and not r['proceed'])
case('D10 log diag=INCOMPLETE when comparison incomplete', 'diag=INCOMPLETE' in lines[0])

many = {f'P{i}': str(i) for i in range(201)}
r, lines, d = run(dict(BASE, **many))
case('D11 over 200 changed names -> STOP diag_overflow', r['doc']['result'] == 'STOP' and not r['doc']['complete']
     and len(r['doc']['values']) == 200 and r['abort'] == 'diag_overflow')
case('D12 log line holds at most 40 names', len(lines[0].split('changed=')[1].split(',')) == 40)

r, lines, d = run(after(ExecStart='new', User='root'), writer=lambda p, b: 'ENOSPC')
case('D13 write fails on refusal -> still refusal, diag INCOMPLETE, code in log',
     r['abort'] == 'dropin_changed_other_props' and r['diag_status'] == 'DIAGNOSTICS_INCOMPLETE'
     and 'diag=INCOMPLETE code=ENOSPC' in lines[0] and r['exit_code'] is None)

r, lines, d = run(after(ExecStart='new'), writer=lambda p, b: 'sha_mismatch')
case('D14 OK comparison but file not written -> no start (dropin_check_unwritten)',
     not r['proceed'] and r['abort'] == 'dropin_check_unwritten')

r, lines, d = run(after(ExecStart='new', User='root'), writer=lambda p, b: 'EIO', logger=lambda s: False)
case('D15 file and log both lost -> exit code 75', r['exit_code'] == 75 and not r['proceed'])

r, lines, d = run(after(ExecStart='new', User='root'), logger=lambda s: False)
case('D16 log lost but file written -> no exit 75, still refusal', r['exit_code'] is None
     and r['abort'] == 'dropin_changed_other_props' and not r['logged'])

p = os.path.join(tempfile.mkdtemp(prefix='zdrop-', dir=ROOT), 'dropin_check.json')
open(p, 'w').close()
case('D17 existing file -> EEXIST, not overwritten', D.write_check(p, b'{}') == 'EEXIST' and os.path.getsize(p) == 0)

if os.name == 'posix':
    q = os.path.join(tempfile.mkdtemp(prefix='zdrop-', dir=ROOT), 'dropin_check.json')
    os.symlink('/dev/null', q)
    case('D18 symlink in place -> refused (EEXIST), target untouched', D.write_check(q, b'{}') == 'EEXIST')
else:
    case('D18 symlink in place -> refused (skipped: not posix)', True)

r, lines, d = run(after(**{'Bad Name;rm': '1', 'ExecStart': 'new'}))
case('D19 unsafe property name shown as ? in log', 'changed=?,ExecStart' in lines[0])

r, lines, d = run(dict(BASE))
case('D20 nothing changed -> OK with empty changed, log changed=-', r['proceed'] and r['doc']['changed'] == []
     and lines[0].endswith('n=0 changed=- raw=0 reordered=- runtime=- unparsed=-'))

# --- B13: смысловое сравнение (значения — из CI 44282558463, x64, повтор 1) ---
A1 = ('zavod-nft.service basic.target systemd-tmpfiles-setup.service -.mount systemd-remount-fs.service zagent.slice '
      'network.target systemd-journald.socket tmp.mount sysinit.target')
A2 = ('basic.target -.mount network.target systemd-tmpfiles-setup.service zagent.slice tmp.mount sysinit.target '
      'systemd-journald.socket zavod-nft.service systemd-remount-fs.service')
RQ1, RQ2 = '-.mount zavod-nft.service sysinit.target zagent.slice', 'zagent.slice -.mount sysinit.target zavod-nft.service'
RM1 = '/var/tmp /var/lib/private/zagent /var/lib/zagent/aaaaaaaaaaaaaaaaaaaaaaaaaaabc001'
RM2 = '/var/lib/zagent/aaaaaaaaaaaaaaaaaaaaaaaaaaabc001 /var/lib/private/zagent /var/tmp'
B2 = dict(BASE, After=A1, Requires=RQ1, RequiresMountsFor=RM1, MemoryAvailable='15801966592', ProtectSystem='strict',
          IPAddressDeny='any', Slice='zagent.slice', ExecStartPre='{ path=/bin/true ; argv[]=/bin/true }')
CI = dict(After=A2, Requires=RQ2, RequiresMountsFor=RM2, MemoryAvailable='15796998144')


def after2(**kw):
    a = dict(B2, ExecStart='new', DropInPaths='/run/x.conf')
    a.update(kw)
    return a


def refused(r, key):
    return (not r['proceed'] and r['doc']['result'] == 'REFUSED' and r['abort'] == 'dropin_changed_other_props'
            and key in r['doc']['extra'])


r, lines, d = run(after2(**CI), before=B2)
doc = r['doc']
case('D22 CI pattern: After/Requires/RequiresMountsFor reordered + MemoryAvailable -> OK, proceed',
     r['proceed'] and doc['result'] == 'OK' and doc['extra'] == [] and r['abort'] is None)
case('D23 classes: reordered 3, runtime 1, changed only dropin keys, raw keeps all 6',
     doc['reordered'] == ['After', 'Requires', 'RequiresMountsFor'] and doc['runtime'] == ['MemoryAvailable']
     and doc['changed'] == ['DropInPaths', 'ExecStart'] and len(doc['raw_changed']) == 6 and doc['unparsed'] == [])
case('D24 file: rule B13.v0.2 and before/after values of reordered and runtime kept',
     doc['rule'] == 'B13.v0.2' and doc['values']['After'] == {'before': A1, 'after': A2}
     and doc['values']['MemoryAvailable'] == {'before': '15801966592', 'after': '15796998144'}
     and doc['stop_reason'] is None and doc['complete'])
case('D25 log line: semantic changed + raw count + reordered/runtime names',
     lines == ['ZPROBE_DROPIN_CHECK result=OK diag=OK code=- n=2 changed=DropInPaths,ExecStart raw=6 '
               'reordered=After,Requires,RequiresMountsFor runtime=MemoryAvailable unparsed=-'])
r, _, _ = run(after2(After=A2 + ' evil.service'), before=B2)
case('D26 After gains a unit -> REFUSED (After)', refused(r, 'After'))
r, _, _ = run(after2(Requires='zagent.slice sysinit.target zavod-nft.service'), before=B2)
case('D27 Requires loses a unit -> REFUSED (Requires)', refused(r, 'Requires'))
r, _, _ = run(after2(RequiresMountsFor=RM2 + ' /home'), before=B2)
case('D28 RequiresMountsFor gains a path -> REFUSED', refused(r, 'RequiresMountsFor'))
r, _, _ = run(after2(Wants='x.service'), before=dict(B2, Wants=''))
case('D29 empty set becomes non-empty -> REFUSED (Wants)', refused(r, 'Wants'))
r, _, _ = run(after2(Requires=RQ2 + ' zagent.slice'), before=B2)
case('D30 duplicate element in a set -> STOP dropin_props_unparsed, no start',
     not r['proceed'] and r['doc']['result'] == 'STOP' and r['abort'] == 'dropin_props_unparsed'
     and r['doc']['unparsed'] == ['Requires'] and r['doc']['stop_reason'] == 'unparsed')
r, _, _ = run(after2(After='basic.target;rm -.mount'), before=dict(B2, After='-.mount basic.target;rm'))
case('D31 foreign characters in a set element -> STOP unparsed', r['abort'] == 'dropin_props_unparsed'
     and not r['proceed'])
r, _, _ = run(after2(MemoryAvailable='[not set]'), before=B2)
case('D32 MemoryAvailable not a number -> REFUSED', refused(r, 'MemoryAvailable'))
r, _, _ = run(after2(MemoryAvailable='infinity'), before=B2)
case('D33 MemoryAvailable number -> infinity is still a measurement -> OK', r['proceed']
     and r['doc']['runtime'] == ['MemoryAvailable'])
for i, (k, v) in enumerate((('MemoryMax', '1'), ('ProtectSystem', 'no'), ('IPAddressDeny', ''), ('User', 'root'),
                            ('Slice', '-.slice'))):
    r, _, _ = run(after2(**{k: v}), before=B2)
    case('D%d guard property %s changed -> REFUSED' % (34 + i, k), refused(r, k))
r, _, _ = run(after2(ExecStartPre='{ argv[]=/bin/true ; path=/bin/true }'), before=B2)
case('D39 ExecStartPre same parts other order -> REFUSED (commands are never normalised), value redacted',
     refused(r, 'ExecStartPre') and r['doc']['values']['ExecStartPre'].get('redacted') is True)
r, _, _ = run(after2(NewProp='1'), before=B2)
case('D40 unknown property appears -> REFUSED', refused(r, 'NewProp'))
a = after2(**CI)
del a['After']
r, _, _ = run(a, before=B2)
case('D41 set property disappears -> REFUSED (After)', refused(r, 'After'))
long1 = ' '.join('u%03d.service' % i for i in range(60))
long2 = ' '.join(reversed(long1.split()))
r, _, _ = run(after2(After=long2), before=dict(B2, After=long1))
case('D42 reordered set longer than 512 -> value truncated -> STOP diag_overflow, no start',
     not r['proceed'] and r['doc']['result'] == 'STOP' and r['abort'] == 'diag_overflow'
     and r['doc']['reordered'] == ['After'])
r, _, _ = run(after2(**CI), before=B2, writer=lambda p, b: 'ENOSPC')
case('D43 only harmless differences but dropin_check.json lost -> no start (dropin_check_unwritten)',
     not r['proceed'] and r['abort'] == 'dropin_check_unwritten')


def export_ok():
    import zprobe_export_rules as X
    r, _, _ = run(after2(**CI), before=B2)
    r2, _, _ = run(after2(After=A2 + ' evil.service'), before=B2)
    try:
        X.DROPIN_CHECK(json.loads(json.dumps(r['doc'])), 'dropin_check')
        X.DROPIN_CHECK(json.loads(json.dumps(r2['doc'])), 'dropin_check')
    except X.Refused as e:
        print('D44_DETAIL', e)
        return False
    return True


case('D44 dropin_check v0.2 (OK and REFUSED) passes the export schema', export_ok())


def runner_verdict():
    """M-355-REL123-01: один источник решения. proceed и cage.props_ok совпадают во всех случаях."""
    import zprobe_runner as N
    keep = N.DROP.decide
    res = []
    dmy = {'ExecStart': 'dummy', 'DropInPaths': ''}
    try:
        for name, a, want in (('ci', after2(**CI), True), ('after+', after2(After=A2 + ' evil.service'), False),
                              ('memmax', after2(MemoryMax='1', **CI), False),
                              ('dup', after2(Requires=RQ2 + ' zagent.slice'), False)):
            dd = tempfile.mkdtemp(prefix='zdrop-', dir=ROOT)
            N.DROP.decide = lambda *x, **k: keep(*x, **dict(k, logger=lambda s: True))
            dec, cage = N.dropin_verdict(B2, a, dmy, dict(dmy), 'text', 'systemd 255', '2026-11-18T10:00:00Z',
                                         os.path.join(dd, 'dropin_check.json'))
            ok = (dec['proceed'] is want and cage['props_ok'] is want
                  and cage['changed_props'] == dec['doc']['changed']
                  and cage['raw_changed_props'] == dec['doc']['raw_changed']
                  and (not want or not set(cage['changed_props']) - N.R.DROPIN_KEYS))
            if not ok:
                print('D45_DETAIL', name, dec['proceed'], cage['props_ok'], dec['doc']['result'])
            res.append(ok)
    finally:
        N.DROP.decide = keep
    return all(res) and len(res) == 4


case('D45 runner dropin_verdict: proceed == cage.props_ok (CI pattern true; After+, MemoryMax, duplicate false)',
     runner_verdict())


def evidence_docs():
    """L-355-REL124-01: evidence.json с НАСТОЯЩИМ cage_partial шага отказа (как пишет бегунок v0.14)."""
    import zprobe_runner as N
    keep = N.DROP.decide
    dmy = {'ExecStart': 'dummy', 'DropInPaths': ''}
    dd = tempfile.mkdtemp(prefix='zdrop-', dir=ROOT)
    try:
        N.DROP.decide = lambda *x, **k: keep(*x, **dict(k, logger=lambda s: True))
        dec, cage = N.dropin_verdict(B2, after2(After=A2 + ' evil.service', **{k: v for k, v in CI.items() if k != 'After'}),
                                     dmy, dict(dmy), 'text', 'systemd 255', '2026-11-18T11:00:00Z',
                                     os.path.join(dd, 'dropin_check.json'))
    finally:
        N.DROP.decide = keep
    ev = {'series': 's1', 'status': 'ABORTED', 'step': 'dropin', 'reason': 'Abort:' + dec['abort'],
          'dropin_check': {'result': dec['doc']['result'], 'code': dec['code'], 'diag_status': dec['diag_status'],
                           'logged': dec['logged']}, 'diag_status': dec['diag_status'], 'cage_partial': cage}
    return ev, cage


def export_evidence():
    import zprobe_export_rules as X
    ev, cage = evidence_docs()
    try:
        doc, out = X.sanitize('B10', 'evidence.json', json.dumps(ev, sort_keys=True).encode())
        pc = X.check_sanitized('B10', 'evidence.json', out)
    except X.Refused as e:
        print('D46_DETAIL', e)
        return False, False, []
    good = (doc['cage_partial'] == cage and pc == doc and cage['raw_changed_props'] != cage['changed_props']
            and 'After' in cage['changed_props'] and 'MemoryAvailable' in cage['raw_changed_props']
            and cage['props_ok'] is False)
    old = dict(ev, cage_partial={k: v for k, v in cage.items() if k != 'raw_changed_props'})
    try:
        v01 = X.sanitize('B10', 'evidence.json', json.dumps(old, sort_keys=True).encode())[0]['cage_partial']
        v01_ok = 'raw_changed_props' not in v01 and v01['changed_props'] == cage['changed_props']
    except X.Refused as e:
        print('D47_DETAIL', e)
        v01_ok = False
    bad = []
    for name, cp in (('bad_name', dict(cage, raw_changed_props=['Bad Name'])),
                     ('not_list', dict(cage, raw_changed_props='After')),
                     ('extra_field', dict(cage, raw_x=['After']))):
        try:
            X.sanitize('B10', 'evidence.json', json.dumps(dict(ev, cage_partial=cp), sort_keys=True).encode())
            bad.append(name + ':accepted')
        except X.Refused as e:
            bad.append(name + ':' + ('ok' if str(e).startswith('evidence.json.cage_partial') else 'path=' + str(e)))
    return good, v01_ok, bad


g46, g47, b48 = export_evidence()
case('D46 evidence.json with real cage_partial (raw_changed_props) passes export and PC check unchanged', g46)
case('D47 evidence.json cage_partial of format v0.1 (no raw_changed_props) still passes', g47)
case('D48 cage_partial: bad name, not a list, unknown field -> refused at cage_partial',
     b48 == ['bad_name:ok', 'not_list:ok', 'extra_field:ok'] or print('D48_DETAIL', b48))


def release_version():
    import zprobe_export_rules as X
    res = []
    for v, want in (('3.5.5-b10', True), ('3.5.5-b13', True), ('3.5.5', True), ('3.5.5-x', False),
                    ('3.5.5-b100', False), ('-b10', False)):
        ev = {'series': 's1', 'release': {'commit': 'a' * 40, 'version': v}}
        try:
            X.sanitize('B10', 'evidence.json', json.dumps(ev).encode())
            res.append(want)
        except X.Refused:
            res.append(not want)
    return all(res) or print('D49_DETAIL', res)


case('D49 evidence release.version of the builder form 3.5.5-bNN passes export; other forms refused', release_version())


def ci28_both_writes_fail():
    """REL68 L-01, CI 28: ОДИН запуск zprobe_runner.main, в котором не записались и dropin_check.json, и
    evidence.json (диск полон: os.open с O_CREAT на эти два имени → ENOSPC). Настоящие run(), DROP.decide,
    write_check, emit и put_new; подменены только внешние команды (systemctl, psql, nft, сеть) и якорь.
    Ждём: ровно одна строка ZPROBE_DROPIN_CHECK … diag=INCOMPLETE code=ENOSPC в выводе службы, строки
    ZPROBE_RUNNER нет, файлов нет, а zprobe_journal.build по этой папке даёт INTERRUPTED runner_missing."""
    import errno
    import zprobe_journal as J
    import zprobe_runner as N
    s, ch = 'ci28s', '0123456789abcdef0123456789abcdef'
    top = tempfile.mkdtemp(prefix='zdrop-', dir=ROOT)
    d = os.path.join(top, 'run', s)
    os.makedirs(d)
    req = {'series': s, 'probes': N.R.PROBES, 'challenge': ch}
    with open(os.path.join(d, 'request.json'), 'w', encoding='utf-8') as f:
        json.dump(req, f)
    lib = os.path.join(top, 'lib')
    os.makedirs(lib)
    with open(os.path.join(lib, 'RELEASE'), 'w', encoding='ascii') as f:
        f.write('commit=' + 'b' * 40 + '\n')
    shows = [dict(BASE), {'ExecStart': 'dummy', 'DropInPaths': ''}, after(ExecStart='new', User='root'),
             {'ExecStart': 'dummy', 'DropInPaths': ''}]
    hits = []
    real_open, real_put = os.open, N.put_new

    def fake_sh(*args, **kw):
        if args[:2] == ('id', '-g'):
            return '0\n'
        if args[:2] == ('systemctl', '--version'):
            return 'systemd 255 (test)\n'
        if args[0] == 'cat':
            return '12345678-1234-1234-1234-123456789abc\n'
        return ''

    def full_disk(path, flags, *a, **k):
        name = os.path.basename(str(path))
        if name in ('dropin_check.json', 'evidence.json') and flags & os.O_CREAT:
            hits.append(name)
            raise OSError(errno.ENOSPC, 'No space left on device')
        return real_open(path, flags, *a, **k)

    def fake_put(path, data, mode, gid=0):
        if os.path.basename(path) == 'evidence.json':
            return real_put(path, data, mode, gid)        # настоящая запись свидетельства
        if path.startswith(top):
            with open(path, 'x', encoding='utf-8') as f:
                f.write(data)

    keep = [(m, k, getattr(m, k)) for m, k in (
        (N, 'RUN'), (N, 'LIB'), (N, 'sh'), (N, 'show'), (N, 'pg'), (N, 'sha_file'), (N, 'snapshot_targets'),
        (N, 'proxy_probe_from_host'), (N, 'mkdirs_sync'), (N, 'put_new'), (N.UN, 'series_taken'),
        (N.UN, 'take_anchor'), (N.UN, 'open_src'), (N.UN, 'write_anchor'), (os, 'open'), (os, 'geteuid'),
        (sys, 'argv'), (N, 'SRDIR'))]
    srd = os.path.join(top, 'startrec')            # B15: папку серии создаёт zprobe-start до systemctl
    os.makedirs(os.path.join(srd, s))
    inv_keep = os.environ.get('INVOCATION_ID')
    cap = os.path.join(top, 'stdout.txt')
    sys.stdout.flush()
    fd_keep, fd_cap = os.dup(1), real_open(cap, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    err = None
    try:
        N.RUN, N.LIB, N.SRDIR = os.path.join(top, 'run'), lib, srd
        os.environ['INVOCATION_ID'] = 'ab' * 16
        N.sh, N.pg, N.sha_file = fake_sh, (lambda q, **v: ''), (lambda p: 'a' * 64)
        N.show = lambda unit, *props: shows.pop(0)
        N.snapshot_targets = lambda: ([], {}, 'c' * 64)
        N.proxy_probe_from_host = lambda: (0, 'none')
        N.mkdirs_sync, N.put_new = (lambda path, mode: None), fake_put
        N.UN.series_taken = lambda series, places: False
        N.UN.take_anchor = lambda *a, **k: {}
        N.UN.open_src = lambda path: real_open(path, os.O_RDONLY)
        N.UN.write_anchor = lambda dir_fd, doc: 'd' * 64
        os.geteuid = lambda: 0
        sys.argv = ['zprobe_runner.py', 'run', s]
        os.dup2(fd_cap, 1)
        os.open = full_disk
        try:
            N.main()
        except BaseException as e:  # noqa: BLE001 — ждём OSError(ENOSPC) от записи evidence; SystemExit тоже видим
            err = e
    finally:
        sys.stdout.flush()
        os.dup2(fd_keep, 1)
        os.close(fd_keep)
        os.close(fd_cap)
        for m, k, v in keep:
            setattr(m, k, v)
        if inv_keep is None:
            os.environ.pop('INVOCATION_ID', None)
        else:
            os.environ['INVOCATION_ID'] = inv_keep
    with open(cap, encoding='ascii', errors='replace') as f:
        out = f.read().splitlines()
    diag = [ln for ln in out if ln.startswith('ZPROBE_DROPIN_CHECK ')]
    es, ev = J.load3(os.path.join(d, 'evidence.json'))
    cl = {'status': 'SAFE', 'unit_active_after': 'inactive', 'load_state': 'masked',
          'session_state': 'INTERRUPTED', 'kept_copy': '/var/lib/zavod/probes/archive/s1/50-zprobe.conf',
          'lease': 'a' * 32}
    end = J.build(s, req, ev, 'commit', cl, es, 'ok')[-1]
    good = (isinstance(err, OSError) and err.errno == errno.ENOSPC and hits == ['dropin_check.json', 'evidence.json']
            and len(diag) == 1 and ' result=REFUSED diag=INCOMPLETE code=ENOSPC ' in diag[0]
            and not [ln for ln in out if ln.startswith('ZPROBE_RUNNER ')]
            and not os.path.lexists(os.path.join(d, 'dropin_check.json'))
            and not os.path.lexists(os.path.join(d, 'evidence.json')) and not shows and es == 'missing'
            and end['kind'] == 'SERIES_END' and end['status'] == 'INTERRUPTED'
            and end['reason'].startswith('runner_missing|cleanup:')
            and os.path.isfile(os.path.join(srd, s, 'S')) and os.path.isfile(os.path.join(srd, s, 'S.ok')))
    if not good:
        print('D21_DETAIL', repr(err), hits, out, es, end, len(shows))
    return good


if sys.platform.startswith('linux'):
    case('D21 CI28 one runner run: dropin_check and evidence both unwritten -> one diag line, INTERRUPTED',
         ci28_both_writes_fail())
else:
    case('D21 CI28 one runner run with both writes failing (skipped: not Linux)', True)

print('ZPROBE_DROPIN_TEST=' + ('PASS' if OK else 'FAIL'))
sys.exit(0 if OK else 1)
