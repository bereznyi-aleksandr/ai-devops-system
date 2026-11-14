#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_export.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-15 00:02 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проверки канала выгрузки раздела 5 (zprobe_export_rules.py, zprobe_export.py, zevidence_send.py,
#   zprobe_verify_export.py). Каждая проверка — одно нарушение. Печатает CASE <имя> PASS/FAIL/SKIP и итог
#   ZPROBE_EXPORT_TEST=PASS | PASS_NO_ROOT | FAIL.
#   R01–R20 — чистые правила, идут везде. X01–X18 — сборка, выдача и проверка ПК без печати: Linux (dir_fd),
#   root не нужен. Y01–Y06 — запечатанные серии B10 и B9 R2 (снимок seal/ root:root 0600): Linux от root (в CI —
#   sudo); без root — SKIP и итог PASS_NO_ROOT.
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_export_rules as E  # noqa: E402
import zprobe_seal as S  # noqa: E402

OK, SKIPPED = True, 0
BOOT = 'bc77431f' + '0' * 24
LID = '0123abcd-0000-4000-8000-00000000c0de'
L = LID.replace('-', '')
CUR1 = f's={"a" * 32};i=1f;b={BOOT};m=2a;t=5f1;x=9'
CUR2 = f's={"a" * 32};i=20;b={BOOT};m=2b;t=5f2;x=a'
DROP = f'/run/systemd/system/zagent@{L}.service.d/50-zprobe.conf'
LINUX = hasattr(os, 'O_NOFOLLOW') and sys.platform.startswith('linux')
ROOT = LINUX and os.geteuid() == 0


def case(name, cond):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL', flush=True)


def skip(name):
    global SKIPPED
    SKIPPED += 1
    print('CASE', name, 'SKIP', flush=True)


def refused(fn, *a, want=None):
    try:
        fn(*a)
    except E.Refused as e:
        return want is None or str(e).startswith(want)
    return False


def js(o):
    return json.dumps(o, sort_keys=True).encode()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def b10_files(s):
    return {
        'state.json': js({'series': s, 'runner': 'b10', 'lease': L, 'lease_id': LID, 'dropin': DROP}),
        'evidence.json': js({'series': s, 'status': 'RUNNING', 'step': 'anchor', 'lease': L, 'challenge': 'c' * 16,
                             'cred_paths': ['/x'], 'anchor_sha256': 'd' * 64}),
        'anchor_run.json': js({'series': s, 'lease': L, 'lease_id': LID, 'boot_id': BOOT, 'cursor': CUR1,
                               'cursor_us': 5, 'utc': '2026-11-14T08:00:01Z'}),
        'request.json': js({'challenge': 'c' * 16, 'probes': ['x']}),
    }


def cleanup_doc(s, status='SAFE_PRE_START'):
    return js({'series': s, 'found_by': 'state', 'lease': L, 'status': status, 'session_state': 'NONE',
               'pre_start': {'status': status, 'seal': 'SEALED_NOW', 'failed': [], 'reason': '-', 'k': 1,
                             'sha': 'e' * 64}})


def lease_row():
    return {'lease_id': LID, 'status': 'OPEN', 'holder_session': 'zprobe-pb1trial2', 'opened_by': 'zavod',
            'role_key': '08_zprobe', 'opened_at': '2026-11-14T08:00:00.123+00:00', 'closed_at': None,
            'tenant_id': 't', 'chat_number': 1, 'generation': 1, 'work_item_id': None, 'rules_commit': 'a',
            'code_commit': 'b', 'completion_evidence_id': None, 'result_evidence_id': None,
            'memory_evidence_id': None, 'next_evidence_id': None, 'report_id': None}


def b9_files():
    s = 'pb1trial2'
    f = {'state.json': js({'lease': L, 'lease_id': LID, 'dropin': DROP}),
         'evidence.json': js({'series': s, 'status': 'RUN_DONE', 'step': 'done', 'lease': L, 'challenge': 'c' * 8}),
         'cleanup.json': js({'series': s, 'found_by': 'state', 'lease': L, 'status': 'SAFE'}),
         'request.json': js({'challenge': 'c' * 8}), 'dropin_50-zprobe.conf': b'[Service]\nX=1\n'}
    names = sorted(f)
    f['anchor.json'] = js({'series': s, 'lease': L, 'lease_id': LID, 'boot_id': BOOT, 'utc': '2026-11-14T08:00:00Z',
                           'cursor_before': CUR1, 'cursor_before_us': 1, 'cursor_after': CUR2, 'cursor_after_us': 2,
                           'source_names': names, 'source_modes': {n: '0:1001:0640' for n in names},
                           'mask_link': '/dev/null', 'lease_row': lease_row()})
    return f


def manifest_a(files):
    out = []
    for n in sorted(files):
        d = files[n]
        if n == 'anchor.json':
            out.append(f'{sha(d)}  {len(d)}  anchor.json  -')
        elif n == 'dropin_50-zprobe.conf':
            out.append(f'{sha(d)}  {len(d)}  {n}  {DROP}  src=0:0:0644')
        else:
            out.append(f'{sha(d)}  {len(d)}  {n}  /run/zprobe/pb1trial2/{n}  src=0:1001:0640')
    return ('\n'.join(out) + '\n').encode()


def segment(s, broken=False):
    base = {'series': s, 'challenge': 'c' * 16, 'probe': 'ПБ-1'}
    recs = [dict(base, kind='SERIES_START', probes=['x']),
            dict(base, kind='SERIES_END', records=1, status='INTERRUPTED', reason='r', cleanup=None)]
    prev, buf = '0' * 64, b''
    for i, r in enumerate(recs, 1):
        r = dict(r, seq=i, prev_sha256=('f' * 64 if broken and i == 2 else prev), time='2026-11-14T08:00:00Z')
        if i == 1:
            r['skipped_segments'] = []
        line = json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        buf += line + b'\n'
        prev = sha(line)
    return buf, 2, prev


def put(path, data, mode=0o640):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    os.chmod(path, mode)


def mkenv(base, s, fmt, final=True, journal='full'):
    P = {k: os.path.join(base, k) for k in ('run', 'preserve', 'seal', 'export', 'archive', 'started', 'journal')}
    for k in ('export', 'journal'):
        os.makedirs(P[k], exist_ok=True)
    home = os.path.join(P['preserve'] if fmt == 'B9R2' else P['run'], s)
    files = b9_files() if fmt == 'B9R2' else b10_files(s)
    for n, d in files.items():
        put(os.path.join(home, n), d)
    if fmt == 'B9R2':
        put(os.path.join(home, 'MANIFEST.sha256'), manifest_a(files))
    elif final:
        put(os.path.join(home, 'cleanup.json'), cleanup_doc(s))
    if journal:
        seg, *_ = segment(s, broken=(journal == 'broken'))
        put(os.path.join(P['journal'], '000001.jsonl'), seg)
        put(os.path.join(P['journal'], '.lock'), b'')
    return P, files


def put0600(dir_, name, data):
    fd = os.open(os.path.join(dir_, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, data)
    os.close(fd)


def seal_attempt(P, s, fmt, files, k=1):
    """Снимок seal/<S>/<k>/src/ + INVENTORY (B) + proof.json, как пишет zprobe_seal (root:root 0600)."""
    a = os.path.join(P['seal'], s, str(k))
    os.makedirs(os.path.join(a, 'src'), mode=0o700)
    names = sorted(files)
    lines, sources = [], []
    man = None
    if fmt == 'B9R2':
        man = manifest_a(files)
        ma = E.parse_manifest_a(man, s, L)
    for n in names:
        d = files[n]
        put0600(os.path.join(a, 'src'), n, d)
        if fmt == 'B10':
            phys = f'/run/zprobe/{s}/{n}'
            lines.append(S.inventory_line(sha(d), len(d), n, phys, phys, '0:1001:0640', '0:1001:0640'))
        else:
            phys = f'/var/lib/zavod/preserve/{s}/{n}'
            lines.append(S.inventory_line(sha(d), len(d), n, phys, ma[n][2], '0:0:0600', ma[n][3]))
        sources.append({'name': n, 'sha256': sha(d), 'size': len(d)})
    inv = ''.join(lines).encode()
    put0600(os.path.join(a, 'src'), 'INVENTORY.sha256', inv)
    p = {'version': 1, 'series': s, 'lease_id': LID, 'boot_id': BOOT, 't0_utc': '2026-11-14T08:00:00Z',
         'checks': {f'H{i}': {'ok': True, 'value': f'n={i} OK'} for i in range(1, 11)},
         'journal_from_cursor': CUR1, 'journal_to_cursor': CUR2, 'sources': sources, 'inventory_sha256': sha(inv),
         'preserve_manifest_sha256': sha(man) if man else None, 'tool_version': 'b10-0.1',
         'created_utc': '2026-11-14T21:00:00Z'}
    p['checks']['H9'] = {'ok': True, 'value': 'OK', 'src': 'run' if fmt == 'B10' else 'r1'}
    raw = S.canon(p)
    put0600(a, 'proof.json', raw)
    return {'series': s, 'proof_sha256': sha(raw), 'sealed_at': '2026-11-14T21:00:01Z'}


def reseal(files, path=None, data=None, mode=None):
    """Подмена файла/режима в архиве с пересчётом MANIFEST и READY (проверяем ПК, а не READY)."""
    files = dict(files)
    rows = E.parse_manifest(files['MANIFEST.sha256'])
    out = []
    for m, p, nm, r, rsz, o, osz in rows:
        key = f'{p}/{nm}'
        if key == path:
            files[key] = data
            m = mode or m
        if m == 'HASH_ONLY':
            out.append(f'{m}  {key}  raw={r}  raw_size={rsz}  out=-  out_size=-')
        else:
            d = files[key]
            rr, rs = (sha(d), len(d)) if m == 'FULL_RAW' else (r, rsz)
            out.append(f'{m}  {key}  raw={rr}  raw_size={rs}  out={sha(d)}  out_size={len(d)}')
    files['MANIFEST.sha256'] = ('\n'.join(out) + '\n').encode()
    files['READY'] = (sha(files['MANIFEST.sha256']) + '\n').encode()
    return files


def rules_cases():
    ev = js({'series': 's1', 'status': 'RUNNING', 'step': 'anchor', 'challenge': 'zz', 'cred_paths': ['/a', '/b'],
             'env': {'kernel': '6.8', 'host': 'secret-host'}})
    doc, out = E.sanitize('B10', 'evidence.json', ev)
    case('R01_known_deny_becomes_count', doc['challenge'] == {'known_deny_count': 2}
         and doc['cred_paths'] == {'known_deny_count': 2} and doc['env']['host'] == {'known_deny_count': 11})
    case('R02_no_secret_bytes_in_out', b'secret-host' not in out and b'/a' not in out and b'zz' not in out)
    case('R03_pc_accepts_sanitized', E.check_sanitized('B10', 'evidence.json', out) == doc)
    bad = js(dict(json.loads(out), challenge={'known_deny_count': 2, 'v': 'x'}))
    case('R04_pc_refuses_deny_with_content', refused(E.check_sanitized, 'B10', 'evidence.json', S.canon(json.loads(bad))))
    case('R05_unknown_field_refused', refused(E.sanitize, 'B10', 'evidence.json', js({'plan_x': 1}),
                                              want='evidence.json.plan_x'))
    case('R06_bad_format_refused', refused(E.sanitize, 'B10', 'evidence.json', js({'lease': 'XYZ'}),
                                           want='evidence.json.lease'))
    ar = json.loads(b10_files('s1')['anchor_run.json'])
    case('R07_anchor_run_ok', E.sanitize('B10', 'anchor_run.json', js(ar))[0] == ar)
    case('R08_anchor_run_extra_field', refused(E.sanitize, 'B10', 'anchor_run.json', js(dict(ar, x=1))))
    case('R09_anchor_run_cursor_boot', refused(E.sanitize, 'B10', 'anchor_run.json',
                                               js(dict(ar, boot_id='1' * 32)), want='anchor_run.json:cursor_boot'))
    a9 = E.sanitize('B9R2', 'anchor.json', b9_files()['anchor.json'])[0]
    case('R10_lease_row_deny', a9['lease_row']['tenant_id'] == {'known_deny_count': 1}
         and a9['lease_row']['status'] == 'OPEN')
    ln = E.manifest_line('HASH_ONLY', 'final', 'request.json', b'abc', None)
    rows = E.parse_manifest((ln + '\n').encode())
    case('R11_manifest_line_hash_only', rows[0][5] is None and rows[0][4] == 3 and ln.endswith('out=-  out_size=-'))
    l2 = E.manifest_line('ALLOW', 'final', 'state.json', b'{}', b'{}')
    case('R12_manifest_order', refused(E.parse_manifest, (l2 + '\n' + ln + '\n').encode(), want='MANIFEST:order')
         and len(E.parse_manifest((ln + '\n' + l2 + '\n').encode())) == 2)
    case('R13_manifest_full_word_refused', refused(E.parse_manifest, (ln.replace('HASH_ONLY', 'FULL') + '\n').encode()))
    case('R14_full_raw_json_mode_bad', not E.place_mode_ok('B10', 'final', 'evidence.json', 'FULL_RAW')
         and E.place_mode_ok('B10', 'final', 'evidence.json', 'ALLOW')
         and not E.place_mode_ok('B10', 'sealed/source', 'cleanup.json', 'ALLOW'))
    seg, last_seq, last = segment('s1')
    case('R15_journal_full', E.journal_mode([('000001.jsonl', seg)]) == ('FULL_RAW', 2, last))
    case('R16_journal_partial', E.journal_mode([('000001.jsonl', segment('s1', broken=True)[0])])[0]
         == 'PARTIAL_HASH_ONLY')
    case('R17_segments_gap', E.segments_problem(['000001.jsonl', '000003.jsonl', '.lock']) == 'journal:000003.jsonl')
    b = {'bundle_version': 2, 'manifest_schema_version': 2, 'matrix': 'B10.v2', 'allow_version': E.ALLOW_VERSION,
         'series': 's1', 'lease_id': LID, 'n': 1, 'b_probe': BOOT, 'boot_id': BOOT, 'journal_cursor': None,
         'journal_mode': 'FULL_RAW', 'journal_segments': 1, 'journal_last_seq': 2, 'journal_last_sha256': last,
         'seal': None}
    case('R18_bundle_ok_and_extra', E.check_bundle(dict(b)) and refused(E.check_bundle, dict(b, x=1)))
    case('R19_bundle_v1_refused', refused(E.check_bundle, dict(b, matrix='B10.v1')))
    m = manifest_a(b9_files())
    case('R20_manifest_a', len(E.parse_manifest_a(m, 'pb1trial2', L)) == 6
         and refused(E.parse_manifest_a, m.replace(b'/run/zprobe/pb1trial2/state.json',
                                                     b'/etc/zprobe/pb1trial2/state.json'), 'pb1trial2', L))


def export_cases():
    import zevidence_send as Z
    import zprobe_export as X
    import zprobe_verify_export as V
    gid = os.getgid()

    def run(P, s, seal=None, boot=BOOT):
        return X.write_package(s, seal, boot, P, gid)

    def fetch(P, s):
        n, files = Z.pick(s, P['export'], None)
        return n, files

    def tar_roundtrip(s, n, files, base):
        p = os.path.join(base, f'pkg_{n}_{len(files)}.tar')
        with open(p, 'wb') as f:
            f.write(Z.tar_bytes(s, n, files))
        return V.read_tar(p, s)

    base = tempfile.mkdtemp()
    try:
        s = 'b10ci1'
        P, _ = mkenv(os.path.join(base, 'a'), s, 'B10')
        n, man_sha, b = run(P, s)
        pdir = os.path.join(P['export'], s, '1')
        listing = sorted(os.listdir(pdir))
        case('X01_export_unsealed', n == 1 and b['seal'] is None and 'READY' in listing and 'sealed' not in listing
             and open(os.path.join(pdir, 'READY'), 'rb').read() == (man_sha + '\n').encode())
        n1, files = fetch(P, s)
        n_t, files_t = tar_roundtrip(s, n1, files, base)
        res = V.verify(n_t, files_t, s)
        case('X02_pc_unsealed', res[0] == 'UNSEALED' and files_t == files and 'final/evidence.json' in files
             and b'cred_paths' in files['final/evidence.json'] and b'/x' not in files['final/evidence.json'])
        case('X03_hash_only_no_file', 'final/request.json' not in files and any('final/request.json' in h for h in res[3]))
        run(P, s)
        _, files2 = fetch(P, s)
        case('X04_second_package_n2', json.loads(files2['package/bundle.json'])['n'] == 2)
        case('X05_rollback_fail', V.verify(1, files, s, history={'n': 2})[0] == 'FAIL')
        t = reseal(files, 'final/evidence.json', S.canon(dict(json.loads(files['final/evidence.json']),
                                                              cred_paths=['/leak'])))
        case('X06_pc_deny_content_fail', V.verify(1, t, s)[0] == 'FAIL')
        t = reseal(files, 'final/state.json', b10_files(s)['state.json'], mode='FULL_RAW')
        r = V.verify(1, t, s)
        case('X07_pc_full_raw_json_fail', r[0] == 'FAIL' and r[1][0].startswith('d:mode'))
        t = dict(files)
        t['final/state.json'] = t['final/state.json'].replace(b'b10', b'b11')
        case('X08_pc_byte_tamper_fail', V.verify(1, t, s)[1][0].startswith('a:out'))
        t = reseal(files, 'package/bundle.json', S.canon(dict(json.loads(files['package/bundle.json']), n=7)))
        case('X09_pc_bundle_n_fail', V.verify(1, t, s)[0] == 'FAIL')
        # выдача: подмена байта в папке пакета, лишний файл, папка без READY
        p2 = os.path.join(P['export'], s, '2')
        with open(os.path.join(p2, 'final', 'state.json'), 'ab') as f:
            f.write(b' ')
        try:
            Z.pick(s, P['export'], None)
            r = False
        except Z.Bad as e:
            r = str(e).startswith('package:')
        case('X10_send_tamper_refused', r)
        os.makedirs(os.path.join(P['export'], s, '3'))
        os.chmod(os.path.join(P['export'], s, '3'), 0o750)
        P3, _ = mkenv(os.path.join(base, 'c'), s, 'B10')
        n3, _, _ = run(P3, s)
        put(os.path.join(P3['export'], s, '1', 'extra.txt'), b'x')
        try:
            Z.pick(s, P3['export'], None)
            r = False
        except Z.Bad as e:
            r = str(e) == 'package:set'
        case('X11_send_extra_file_refused', r)
        try:
            Z.pick(s, P['export'], None)
            r = False
        except Z.Bad as e:
            r = str(e).startswith('package:')   # n=3 без READY пропущена, n=2 испорчена
        case('X12_send_skips_unready', r)
        P4, _ = mkenv(os.path.join(base, 'd'), s, 'B10', journal='broken')
        run(P4, s)
        _, f4 = fetch(P4, s)
        r = V.verify(1, f4, s)
        case('X13_journal_partial_incomplete', r[0] == 'INCOMPLETE' and not any(k.startswith('journal/') for k in f4))
        P5, _ = mkenv(os.path.join(base, 'e'), s, 'B10')
        put(os.path.join(P5['journal'], 'x.txt'), b'')
        case('X14_journal_extra_refused', refused(run, P5, s, want='journal:x.txt'))
        P6, _ = mkenv(os.path.join(base, 'f'), s, 'B10')
        put(os.path.join(P6['archive'], s, 'other.conf'), b'')
        case('X15_archive_bad_name_refused', refused(run, P6, s, want='archive/other.conf'))
        P7, _ = mkenv(os.path.join(base, 'g'), s, 'B10', final=False)
        run(P7, s)
        _, f7 = fetch(P7, s)
        r = V.verify(1, f7, s)
        case('X16_final_required_absent_incomplete', r[0] == 'INCOMPLETE' and 'final_required_absent:cleanup.json'
             in r[1])
        P8, _ = mkenv(os.path.join(base, 'h'), s, 'B10')
        os.unlink(os.path.join(P8['run'], s, 'state.json'))
        os.symlink('/etc/hostname', os.path.join(P8['run'], s, 'state.json'))
        case('X17_symlink_refused', refused(run, P8, s, want='state.json'))
        P9, _ = mkenv(os.path.join(base, 'i'), s, 'B10')
        put(os.path.join(P9['run'], s, 'request.json'), b'{' + b' ' * (E.MAX_FILE + 10) + b'}')
        ok1 = refused(run, P9, s, want='final/request.json')
        out = io.BytesIO()
        ok2 = Z.main({'SSH_ORIGINAL_COMMAND': 'send b10ci1 2'}, out) == 2 and \
            Z.main({'SSH_ORIGINAL_COMMAND': 'get b10ci1'}, out) == 2 and out.getvalue() == b''
        fz = files
        ok3 = Z.tar_bytes(s, 1, fz) == Z.tar_bytes(s, 1, fz)
        case('X18_limits_command_tar', ok1 and ok2 and ok3)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def sealed_cases():
    import zevidence_send as Z
    import zprobe_export as X
    import zprobe_verify_export as V
    base = tempfile.mkdtemp(dir='/var/lib')
    os.chmod(base, 0o755)
    gid = os.getgid()
    try:
        s = 'b10ci2'
        P, files = mkenv(os.path.join(base, 'a'), s, 'B10')
        row = seal_attempt(P, s, 'B10', files)
        n, _, b = X.write_package(s, row, BOOT, P, gid)
        _, got = Z.pick(s, P['export'], None)
        r = V.verify(n, got, s, seal_sha=row['proof_sha256'])
        case('Y01_b10_sealed_pass', r[0] == 'PASS_SANITIZED' and b['journal_cursor'] == CUR2
             and 'sealed/source/request.json' not in got and 'sealed/source/state.json' in got)
        case('Y02_phone_sha_mismatch_fail', V.verify(n, got, s, seal_sha='0' * 64)[0] == 'FAIL')
        s9 = 'pb1trial2'
        P9, f9 = mkenv(os.path.join(base, 'b'), s9, 'B9R2')
        row9 = seal_attempt(P9, s9, 'B9R2', f9)
        n9, _, _ = X.write_package(s9, row9, BOOT, P9, gid)
        _, got9 = Z.pick(s9, P9['export'], None)
        r9 = V.verify(n9, got9, s9, seal_sha=row9['proof_sha256'])
        case('Y03_b9r2_sealed_pass', r9[0] == 'PASS_SANITIZED' and 'sealed/meta/MANIFEST.sha256' in got9, )
        shutil.copytree(os.path.join(P['seal'], s, '1'), os.path.join(P['seal'], s, '2'))
        case('Y04_two_attempts_refused', refused(X.write_package, s, row, BOOT, P, gid, want='proof:attempt'))
        Pc, fc = mkenv(os.path.join(base, 'c'), s, 'B10')
        rowc = seal_attempt(Pc, s, 'B10', fc)
        inv = os.path.join(Pc['seal'], s, '1', 'src', 'INVENTORY.sha256')
        os.chmod(inv, 0o600)
        with open(inv, 'ab') as f:
            f.write(b'x')
        case('Y05_inventory_tamper_refused', refused(X.write_package, s, rowc, BOOT, Pc, gid, want='proof:'))
        with open(os.path.join(P9['preserve'], s9, 'MANIFEST.sha256'), 'ab') as f:
            f.write(b'\n')
        case('Y06_b9_manifest_changed_refused', refused(X.write_package, s9, row9, BOOT, P9, gid,
                                                        want='MANIFEST.sha256:sha256'))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main():
    rules_cases()
    if LINUX:
        export_cases()
    else:
        for i in range(1, 19):
            skip(f'X{i:02d}')
    if ROOT:
        sealed_cases()
    else:
        for i in range(1, 7):
            skip(f'Y{i:02d}')
    if not OK:
        print('ZPROBE_EXPORT_TEST=FAIL')
        return 1
    print('ZPROBE_EXPORT_TEST=' + ('PASS_NO_ROOT' if SKIPPED else 'PASS'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
