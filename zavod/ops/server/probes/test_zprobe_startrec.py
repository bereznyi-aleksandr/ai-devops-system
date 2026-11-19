#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_startrec.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 14:08 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 14:08 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: офлайн-тесты встраивания записей старта B15 (DECISION_B15 v0.2 часть B, v0.5 часть C; REL155 AGREED,
#   L-355-REL155-02: сквозные отрицательные тесты): zprobe_journal v0.14 (startrec I|Q, status, SERIES_END с
#   invocation_id), zprobe_runner v0.20 (запись S), zprobe-start v0.15 (порядок I → systemctl --no-block → Q, --status
#   только читает). Сквозной путь: настоящие файлы записей во временной папке, поддельный systemctl.
# ОГРАНИЧЕНИЯ: на Windows fsync папки недоступен — тест подменяет Ops.fsync_dir пустым шагом (только не на Linux);
#   на Linux CI всё по-настоящему. Временные папки — tempfile.TemporaryDirectory (P4.718: в OS temp, в пределах вызова,
#   итог — строки CASE и итоговая строка).
import json
import os
import re
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for mod, attrs in (('fcntl', {'LOCK_EX': 2, 'flock': lambda f, op: None}),
                   ('pwd', {'getpwuid': lambda u: types.SimpleNamespace(pw_name='zprobe')})):
    try:
        __import__(mod)
    except ImportError:
        sys.modules[mod] = types.SimpleNamespace(**attrs)
import zprobe_recstore as RS  # noqa: E402
import zprobe_start_status as ST  # noqa: E402
import zprobe_journal as J  # noqa: E402
import zprobe_runner as N  # noqa: E402

PLATFORM_STUB = os.name != 'posix'
if PLATFORM_STUB:
    RS.Ops.fsync_dir = lambda self, d: None

    def _fsync(self, fd):
        try:
            os.fsync(fd)
        except OSError:
            pass
    RS.Ops.fsync = _fsync

OK, BAD = [], []
C = 'c' * 32
INV = '1' * 32
INV2 = '2' * 32


def case(name, cond, info=''):
    (OK if cond else BAD).append(name)
    print(f'CASE {name} {"PASS" if cond else "FAIL"}' + ('' if cond else f' :: {str(info)[:300]}'), flush=True)


def env(root):
    J.JDIR, J.SDIR, J.RUN, J.SRDIR = (os.path.join(root, x) for x in ('journal', 'started', 'run', 'startrec'))
    N.SRDIR = J.SRDIR
    os.makedirs(J.SRDIR)
    os.makedirs(J.RUN)


def call(fn, *a, **k):
    import io
    import contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            r = fn(*a, **k)
        return r, buf.getvalue().strip()
    except (J.Refused, J.Bad) as e:
        return None, f'REFUSED {getattr(e, "kind", "BAD")}: {e}'
    except N.Abort as e:
        return None, f'ABORT {e}'


def unit_run(run='inactive', inv='', jrn='inactive', jobs='', fail=None):
    """Поддельный systemctl: list-jobs и show двух служб."""
    def r(a):
        if fail and fail in a:
            return types.SimpleNamespace(returncode=1, stdout='')
        if a[1] == 'list-jobs':
            return types.SimpleNamespace(returncode=0, stdout=jobs)
        if a[-1].startswith('zprobe-run-b15@'):
            return types.SimpleNamespace(returncode=0, stdout=f'ActiveState={run}\nInvocationID={inv}\n')
        return types.SimpleNamespace(returncode=0, stdout=f'ActiveState={jrn}\nInvocationID=\n')
    return r


def commit(series, ev, cl=None):
    d = os.path.join(J.RUN, series)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'request.json'), 'w', encoding='utf-8') as f:
        json.dump({'challenge': C, 'probes': ['ПБ-1'], 'series': series}, f)
    if ev is not None:
        with open(os.path.join(d, 'evidence.json'), 'w', encoding='utf-8') as f:
            json.dump(ev, f)
    return call(J.do_commit, series)


def main():
    # ---- J: SERIES_END несёт invocation_id ----
    req = {'challenge': C, 'probes': ['ПБ-1']}
    end = J.build('s1', req, {'status': 'ABORTED', 'series': 's1', 'challenge': C, 'invocation_id': INV}, 'commit')[-1]
    case('J01 END from evidence: invocation_id and src evidence',
         end['invocation_id'] == INV and end['invocation_src'] == 'evidence', end)
    end = J.build('s1', req, None, 'commit', ev_state='missing', s_rec={'invocation_id': INV2})[-1]
    case('J02 END without evidence: invocation_id from record S', end['invocation_id'] == INV2
         and end['invocation_src'] == 'S' and end['status'] == 'INTERRUPTED', end)
    end = J.build('s1', req, None, 'commit', ev_state='missing')[-1]
    case('J03 END without evidence and S: "-" and src none', end['invocation_id'] == '-'
         and end['invocation_src'] == 'none', end)
    end = J.build('s1', req, {'status': 'ABORTED', 'invocation_id': 'xyz'}, 'commit', s_rec={'invocation_id': INV2})[-1]
    case('J04 malformed evidence invocation_id -> record S', end['invocation_id'] == INV2, end)

    # ---- K: startrec I и Q ----
    with tempfile.TemporaryDirectory() as root:
        env(root)
        _, out = call(J.do_startrec, 'I', 'k1', C)
        case('K01 startrec I without folder -> DENIED', out.startswith('REFUSED DENIED') and 'folder' in out, out)
        os.makedirs(os.path.join(J.SRDIR, 'k1'))
        _, out = call(J.do_startrec, 'I', 'k1', C)
        case('K02 startrec I of an unreserved series -> DENIED', out.startswith('REFUSED DENIED') and 'reserved' in out, out)
        _, out = call(J.do_reserve, 'k1', C)
        _, out = call(J.do_startrec, 'I', 'k1', 'd' * 32)
        case('K03 startrec I with another challenge -> DENIED', out.startswith('REFUSED DENIED'), out)
        _, out = call(J.do_startrec, 'Q', 'k1', '7')
        case('K04 startrec Q before I -> DENIED, no Q', out.startswith('REFUSED DENIED')
             and not os.path.exists(os.path.join(J.SRDIR, 'k1', 'Q')), out)
        _, out = call(J.do_startrec, 'I', 'k1', C)
        rec = RS.read_record(os.path.join(J.SRDIR, 'k1'), 'I', 'I')
        case('K05 startrec I -> STARTREC line and whole record I', out.startswith('ZPROBE_JOURNAL STARTREC I series=k1 ')
             and rec == {'series': 'k1', 'challenge': C}, (out, rec))
        _, out = call(J.do_startrec, 'I', 'k1', C)
        case('K06 second startrec I -> refused (FSYNC), no repeat', out.startswith('REFUSED FSYNC'), out)
        _, out = call(J.do_startrec, 'Q', 'k1', 'x1')
        case('K07 startrec Q with a bad job -> DENIED', out.startswith('REFUSED DENIED') and 'job' in out, out)
        _, out = call(J.do_startrec, 'Q', 'k1', '0')
        case('K08 startrec Q 0 after I -> written', out.startswith('ZPROBE_JOURNAL STARTREC Q series=k1 ')
             and RS.read_record(os.path.join(J.SRDIR, 'k1'), 'Q', 'Q') == {'series': 'k1', 'job': '0'}, out)

    # ---- R: бегунок пишет S ----
    with tempfile.TemporaryDirectory() as root:
        env(root)
        ev = {}
        _, out = call(N.write_start_record, 'r1', C, ev, env={})
        case('R01 runner without INVOCATION_ID -> Abort, no S', out == 'ABORT startrec_no_invocation_id', out)
        _, out = call(N.write_start_record, 'r1', C, ev, env={'INVOCATION_ID': INV})
        case('R02 runner without startrec folder -> Abort startrec_no_folder', out == 'ABORT startrec_no_folder', out)
        os.makedirs(os.path.join(J.SRDIR, 'r1'))
        _, out = call(N.write_start_record, 'r1', C, ev, env={'INVOCATION_ID': INV})
        rec = RS.read_record(os.path.join(J.SRDIR, 'r1'), 'S', 'S')
        case('R03 runner writes S {series, challenge, invocation_id}; ev invocation_id',
             rec == {'series': 'r1', 'challenge': C, 'invocation_id': INV} and ev.get('invocation_id') == INV
             and re.fullmatch(r'[0-9a-f]{64}', ev.get('startrec_S_sha256', '')), (out, rec, ev))
        _, out = call(N.write_start_record, 'r1', C, {}, env={'INVOCATION_ID': INV})
        case('R04 second S -> Abort startrec_S_FileExistsError (no replacement)',
             out == 'ABORT startrec_S_FileExistsError', out)

    # ---- S: сквозной путь status ----
    with tempfile.TemporaryDirectory() as root:
        env(root)
        r, out = call(J.do_status, 'e1', unit_run())
        case('S01 nothing at all -> UNKNOWN no_R, code 4, retry=NO', r == 4 and out ==
             'ZPROBE_STATUS UNKNOWN series=e1 reason=no_R retry=NO', out)
        call(J.do_reserve, 'e1', C)
        r, out = call(J.do_status, 'e1', unit_run())
        case('S02 R only, units inactive -> DEAD R_only_not_started', ' DEAD ' in out and 'R_only_not_started' in out, out)
        os.makedirs(os.path.join(J.SRDIR, 'e1'))
        call(J.do_startrec, 'I', 'e1', C)
        r, out = call(J.do_status, 'e1', unit_run(jobs=' 41 zprobe-run-b15@e1.service start waiting\n'))
        case('S03 I and job queued -> QUEUED', ' QUEUED ' in out, out)
        r, out = call(J.do_status, 'e1', unit_run())
        case('S04 I, no S, units dead -> DEAD I_without_S_unit_dead', ' DEAD ' in out and 'I_without_S' in out, out)
        call(J.do_startrec, 'Q', 'e1', '41')
        call(N.write_start_record, 'e1', C, {}, env={'INVOCATION_ID': INV})
        r, out = call(J.do_status, 'e1', unit_run('active', INV))
        case('S05 S and runner active with same InvocationID -> STARTED', ' STARTED ' in out and 'S_unit_alive' in out, out)
        r, out = call(J.do_status, 'e1', unit_run('active', INV2))
        case('S06 S and runner active with another InvocationID -> UNKNOWN', ' UNKNOWN ' in out
             and 'S_invocation_differs_from_unit' in out, out)
        r, out = call(J.do_status, 'e1', unit_run('inactive', '', 'deactivating'))
        case('S07 runner done, journal unit still deactivating -> STARTED (not FAILED_AFTER_START)',
             ' STARTED ' in out and 'journal_pending' in out, out)
        r, out = call(J.do_status, 'e1', unit_run('failed'))
        case('S08 S without E, both units dead -> FAILED_AFTER_START', ' FAILED_AFTER_START ' in out and r == 4, out)
        r, out = call(J.do_status, 'e1', unit_run(fail='list-jobs'))
        case('S09 systemctl list-jobs fails -> UNKNOWN systemctl_no_answer', 'systemctl_no_answer' in out, out)
        r, out = call(J.do_status, 'e1', unit_run(fail='zprobe-journal-b15@e1.service'))
        case('S10 systemctl show of the journal unit fails -> UNKNOWN', 'systemctl_no_answer' in out, out)
        commit('e1', {'status': 'ABORTED', 'series': 'e1', 'challenge': C, 'invocation_id': INV})
        r, out = call(J.do_status, 'e1', unit_run())
        case('S11 S and SERIES_END with the same invocation_id -> TERMINAL, code 0', r == 0
             and out == 'ZPROBE_STATUS TERMINAL series=e1 reason=S_and_E retry=NO', out)
        before = sorted(os.listdir(os.path.join(J.SRDIR, 'e1')))
        call(J.do_status, 'e1', unit_run())
        case('S12 status writes nothing (startrec folder unchanged)',
             sorted(os.listdir(os.path.join(J.SRDIR, 'e1'))) == before, before)

    with tempfile.TemporaryDirectory() as root:
        env(root)
        call(J.do_reserve, 'e2', C)
        os.makedirs(os.path.join(J.SRDIR, 'e2'))
        call(J.do_startrec, 'I', 'e2', C)
        call(N.write_start_record, 'e2', C, {}, env={'INVOCATION_ID': INV})
        commit('e2', {'status': 'ABORTED', 'series': 'e2', 'challenge': C, 'invocation_id': INV2})
        r, out = call(J.do_status, 'e2', unit_run())
        case('S13 SERIES_END invocation differs from S (evidence of another run) -> UNKNOWN E_differs_from_S',
             'E_differs_from_S' in out and r == 4, out)

    with tempfile.TemporaryDirectory() as root:
        env(root)
        call(J.do_reserve, 'e3', C)
        os.makedirs(os.path.join(J.SRDIR, 'e3'))
        call(J.do_startrec, 'I', 'e3', C)
        call(N.write_start_record, 'e3', C, {}, env={'INVOCATION_ID': INV})
        commit('e3', None)
        segs = J.read_segments(J.JDIR)
        endrec = json.loads(segs[0][1].split(b'\n')[-2])
        r, out = call(J.do_status, 'e3', unit_run())
        case('S14 runner left no evidence: END INTERRUPTED takes invocation from S -> TERMINAL (not PASS)',
             endrec['status'] == 'INTERRUPTED' and endrec['invocation_src'] == 'S' and ' TERMINAL ' in out, (endrec, out))
        p = os.path.join(J.SRDIR, 'e3', 'S')
        os.chmod(p, 0o644)
        with open(p, 'ab') as f:
            f.write(b'x')
        r, out = call(J.do_status, 'e3', unit_run())
        case('S15 record S damaged after .ok -> UNKNOWN S_or_E_corrupt', 'S_or_E_corrupt' in out, out)

    with tempfile.TemporaryDirectory() as root:
        env(root)
        call(J.do_reserve, 'e4', C)
        os.makedirs(os.path.join(J.SRDIR, 'e4'))
        call(J.do_startrec, 'I', 'e4', C)
        os.makedirs(J.JDIR, exist_ok=True)
        with open(os.path.join(J.JDIR, '000001.jsonl'), 'wb') as f:
            f.write(b'{"broken')
        r, out = call(J.do_status, 'e4', unit_run())
        case('S16 broken journal -> UNKNOWN (E corrupt), never a start', ' UNKNOWN ' in out, out)
        with open(os.path.join(J.SDIR, 'e5'), 'wb') as f:
            f.write(b'ZPROBE_STARTED series=e5 challenge=zz\n')
        rec = J.status_records('e5', [], J.read_markers())
        case('S17 malformed start mark -> R CORRUPT', rec['R'] == ST.CORRUPT, rec)
        rec = J.status_records('e4', [('000001.jsonl', json.dumps({'kind': 'SERIES_START', 'series': 'e4'}).encode()
                                       + b'\n' + json.dumps({'kind': 'SERIES_END', 'series': 'e4', 'challenge': C,
                                                             'records': 1}).encode() + b'\n')], J.read_markers())
        case('S18 SERIES_END without invocation_id -> E CORRUPT', rec['E'] in ([ST.CORRUPT],), rec)
        if not PLATFORM_STUB:
            os.symlink(os.path.join(root, 'elsewhere'), os.path.join(J.SRDIR, 'e6'))
            rec = J.status_records('e6', [], {})
            case('S19 startrec folder is a symlink -> I/Q/S CORRUPT', rec['I'] == ST.CORRUPT, rec)
        else:
            print('SKIP S19 (symlink on this platform) counted as PASS only here')
            OK.append('S19')

    # ---- U: разбор systemctl ----
    u = J.unit_state('u1', unit_run('active', INV, 'inactive', ' 5 zprobe-journal-b15@u1.service start waiting\n'))
    case('U01 unit_state: runner active, journal job queued', u == {'active': 'active', 'invocation': INV, 'job': False,
                                                                    'journal': {'active': 'inactive', 'job': True}}, u)
    case('U02 parse_show without ActiveState -> None', J.parse_show('InvocationID=x\n') is None)

    # ---- T: тексты пускателя и подключение модулей ----
    with open(os.path.join(HERE, 'zprobe-start'), encoding='utf-8') as f:
        sh = f.read()
    main_part = sh[sh.index('S=$1; C=$2; P=$3'):]
    i_pos = main_part.find('startrec I "$S" "$C"')
    s_pos = main_part.find('systemctl start --no-block "$U"')
    q_pos = main_part.find('startrec Q "$S" "$JOB"')
    case('T01 zprobe-start: I before systemctl start --no-block, Q after it and only at rc 0',
         0 < i_pos < s_pos < q_pos and 'if [ "$URC" = 0 ]; then' in main_part[s_pos:q_pos], (i_pos, s_pos, q_pos))
    st_part = sh[sh.index('if [ "${1:-}" = "--status" ]; then'):]
    st_part = st_part[:st_part.index('\nfi\n')]
    case('T02 zprobe-start --status only reads (exec status, no systemctl start, no mkdir)',
         'zprobe_journal.py" status "$2"' in st_part and 'systemctl' not in st_part and 'mkdir' not in st_part, st_part)
    case('T03 zprobe-start: no blocking start of the runner and B15 names only',
         'systemctl start "zprobe-run' not in sh and 'probes-b14' not in sh.split('set -euo pipefail', 1)[1]
         and 'b14@' not in sh.split('set -euo pipefail', 1)[1], '')
    case('T04 zprobe-start: startrec folder must be new (no mkdir -p), parent root:zprobe 0750',
         'mkdir -m 0750 "$SR/$S"' in sh and 'mkdir -p' not in sh and 'root:zprobe:750:directory' in sh)
    case('T05 runner and journal import zprobe_recstore and zprobe_start_status; runner pins both',
         J.RS is RS and J.ST is ST and N.RS is RS and 'zprobe_recstore.py' in N.PINNED
         and 'zprobe_start_status.py' in N.PINNED and N.LIB.endswith('probes-b15'))

    total = len(OK) + len(BAD)
    print(f'ZPROBE_STARTREC_TESTS {len(OK)}/{total} {"PASS" if not BAD else "FAIL"}'
          + (' PLATFORM_STUB=fsync_dir' if PLATFORM_STUB else ''), flush=True)
    sys.exit(0 if not BAD else 1)


if __name__ == '__main__':
    main()
