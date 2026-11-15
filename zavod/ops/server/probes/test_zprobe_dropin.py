#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_dropin.py
# ВЕРСИЯ: v0.2 (выпуск B10)  СТАТУС: DRAFT
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
     lines == ['ZPROBE_DROPIN_CHECK result=REFUSED diag=OK code=- n=2 changed=ExecStart,User'])

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
     and lines[0].endswith('n=0 changed=-'))


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
        (sys, 'argv'))]
    cap = os.path.join(top, 'stdout.txt')
    sys.stdout.flush()
    fd_keep, fd_cap = os.dup(1), real_open(cap, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    err = None
    try:
        N.RUN, N.LIB = os.path.join(top, 'run'), lib
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
            and end['reason'].startswith('runner_missing|cleanup:'))
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
