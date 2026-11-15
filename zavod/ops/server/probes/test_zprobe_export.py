#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_export.py
# ВЕРСИЯ: v0.3 (выпуск B10)  СТАТУС: DRAFT
# v0.3 (2026-11-15, терминал zavod, сменщик cb6b67c5; REL66): L06–L09 — 2 МБ со всеми файлами, каталоги архива,
#   предел заголовков и потока (M-03, L-01); X28 — PASS-пакет + пустая/глубокая папка → FAIL; X29 — история ПК
#   через вызов программы (M-02); X30 — сервер считает MANIFEST в 2 МБ; Y15–Y17 — сумма печати с телефона (M-01).
#   REL66 L-02 (приоритетные CI): X31 (16, 109), X32 (17), X33 (42, 43, 93), X34 (95, 122), X35 (109, 123, 124),
#   X36 (115), Y18 (113). Далее по PARTIAL REL66: X37 (111), Y19 (45, 58, 112), Y20 (59), Y21 (73), Y22 (63, 64, 83),
#   Y23 (102), Y24 (106), Y25 (99). REL67: L10, X38 — только канонический архив (PAX, GNU, хвост, поля → FAIL);
#   X39 — journal_segments 0/1/MAX/MAX+1/10^9 и пустая цепочка; X40 — история пишется до итога; X41 — CI 16
#   (zprobe-export с серией ../x); X42 — CI 17 (две существующие серии). X43 (CI 47), Y26 (91), Y27 (81), Y28 (119).
#   R25 (CI 114), X44 (48), Y29 (105), Y30 (72), X45 (108), Y31 (42), Y32 (46), X46 (113), X47 (30, 90), Y33 (101), Y34 (78), Y35 (87).
# v0.2 (2026-11-15, терминал zavod, чат cb6b67c5): L01–L05 (ПК) и X19–X22 (send) — пределы архива до чтения;
#   X23–X25 — посторонний файл в исходной папке final (REL65 M-04); R21–R23 — метка-ловушка в тексте ALLOW (M-02);
#   REL65 M-05; R24, X26 — журнал без байтов, метка challenge во всём архиве (M-01, CI 31).
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


JCAN = '9e1d' * 8      # challenge журнала — метка-ловушка: в пакет не должна попасть (CI 31)


def segment(s, broken=False, gap=False):
    base = {'series': s, 'challenge': JCAN, 'probe': 'ПБ-1'}
    recs = [dict(base, kind='SERIES_START', probes=['x']),
            dict(base, kind='SERIES_END', records=1, status='INTERRUPTED', reason='r', cleanup=None)]
    prev, buf = '0' * 64, b''
    for i, r in enumerate(recs, 1):
        r = dict(r, seq=(i + 1 if gap and i == 2 else i), prev_sha256=('f' * 64 if broken and i == 2 else prev), time='2026-11-14T08:00:00Z')
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


def seal_attempt(P, s, fmt, files, k=1, inv_edit=None):
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
    if inv_edit:
        inv = inv_edit(inv)
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


def reproof(files, raw):
    """Подменить proof/proof.json и согласовать bundle.seal.proof_sha256 → (файлы, новая сумма для телефона)."""
    t = reseal(files, 'proof/proof.json', raw)
    b = json.loads(t['package/bundle.json'])
    b['seal'] = dict(b['seal'], proof_sha256=sha(raw))
    return reseal(t, 'package/bundle.json', S.canon(b)), sha(raw)


def with_row(files, key, data=None, mode='FULL_RAW', raw=None):
    """REL65 L-04: добавить (data не None) или убрать (data None) строку и файл; MANIFEST и READY пересчитаны.
    raw — подменить raw у существующей строки key (байты файла не меняются)."""
    files = dict(files)
    out = []
    for m, p, nm, r, rsz, o, osz in E.parse_manifest(files['MANIFEST.sha256']):
        k = f'{p}/{nm}'
        if k == key and data is None and raw is None:
            files.pop(k, None)
            continue
        if k == key and raw is not None:
            r = raw
        tail = 'out=-  out_size=-' if m == 'HASH_ONLY' else f'out={o}  out_size={osz}'
        out.append(f'{m}  {k}  raw={r}  raw_size={rsz}  {tail}')
    if data is not None:
        files[key] = data
        out.append(f'{mode}  {key}  raw={sha(data)}  raw_size={len(data)}  out={sha(data)}  out_size={len(data)}')
    files['MANIFEST.sha256'] = ('\n'.join(sorted(out, key=lambda x: tuple(x.split('  ')[1].rsplit('/', 1))))
                                + '\n').encode()
    files['READY'] = (sha(files['MANIFEST.sha256']) + '\n').encode()
    return files


def bump(v):
    return v[:-1] + ('0' if v[-1] != '0' else '1')


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
    case('R15_journal_chain_hash_only', E.journal_mode([('000001.jsonl', seg)]) == ('CHAIN_HASH_ONLY', 2, last))
    case('R16_journal_partial', E.journal_mode([('000001.jsonl', segment('s1', broken=True)[0])])[0]
         == 'PARTIAL_HASH_ONLY')
    case('R17_segments_gap', E.segments_problem(['000001.jsonl', '000003.jsonl', '.lock']) == 'journal:000003.jsonl')
    b = {'bundle_version': 2, 'manifest_schema_version': 2, 'matrix': 'B10.v2', 'allow_version': E.ALLOW_VERSION,
         'series': 's1', 'lease_id': LID, 'n': 1, 'b_probe': BOOT, 'boot_id': BOOT, 'journal_cursor': None,
         'journal_mode': 'CHAIN_HASH_ONLY', 'journal_segments': 1, 'journal_last_seq': 2, 'journal_last_sha256': last,
         'seal': None}
    case('R18_bundle_ok_and_extra', E.check_bundle(dict(b)) and refused(E.check_bundle, dict(b, x=1)))
    case('R19_bundle_v1_refused', refused(E.check_bundle, dict(b, matrix='B10.v1')))
    case('R24_journal_full_raw_forbidden', refused(E.check_bundle, dict(b, journal_mode='FULL_RAW'))
         and not E.place_mode_ok('B10', 'journal', '000001.jsonl', 'FULL_RAW', 'CHAIN_HASH_ONLY')
         and E.place_mode_ok('B10', 'journal', '000001.jsonl', 'HASH_ONLY', 'CHAIN_HASH_ONLY'))
    # REL65 M-02 (CI 31): выдуманная метка-ловушка в допустимых по виду текстовых полях не попадает в пакет
    can = 'CANARY0c4a1e5b7d9f2a6c8e0b3d5f7a9c1e2'
    ev2 = js({'series': 's1', 'status': 'ABORTED', 'step': 'anchor', 'reason': 'x ' + can,
              'env': {'kernel': can, 'systemd': can, 'python': '3', 'git': can}})
    d2, o2 = E.sanitize('B10', 'evidence.json', ev2)
    case('R21_canary_reason_env_not_in_out', can.encode() not in o2 and d2['reason'] == {'text_len': len('x ' + can)}
         and E.check_sanitized('B10', 'evidence.json', o2) == d2)
    cl = json.loads(cleanup_doc('s1'))
    cl['pre_start']['reason'] = can
    _, o3 = E.sanitize('B10', 'cleanup.json', js(cl))
    dc = js({'systemd': can, 'at': '2026-11-15T05:00:00Z', 'compared': 1, 'changed': ['Environment'],
             'values': {'Environment': {'redacted': True, 'len_before': 40, 'len_after': 40, 'before': 'K=' + can,
                                        'after': can, 'before_truncated': False, 'after_truncated': False}},
             'allowed': [], 'extra': [], 'complete': True, 'result': 'OK'})
    _, o4 = E.sanitize('B10', 'dropin_check.json', dc)
    case('R22_canary_cleanup_reason_dropin_before_after_not_in_out', can.encode() not in o3 and can.encode() not in o4
         and E.check_sanitized('B10', 'dropin_check.json', o4) is not None)
    raw_on_pc = S.canon(dict(json.loads(o2), reason=can))
    case('R23_pc_refuses_free_text_in_allow_field', refused(E.check_sanitized, 'B10', 'evidence.json', raw_on_pc,
                                                            want='evidence.json.reason'))
    m = manifest_a(b9_files())
    case('R20_manifest_a', len(E.parse_manifest_a(m, 'pb1trial2', L)) == 6
         and refused(E.parse_manifest_a, m.replace(b'/run/zprobe/pb1trial2/state.json',
                                                     b'/etc/zprobe/pb1trial2/state.json'), 'pb1trial2', L))


def rules_cases_rel67():
    """CI 114: разрыв seq или prev → журнал не цепочка (PARTIAL_HASH_ONLY), без last_seq."""
    good, *_ = segment('s1')
    gap, *_ = segment('s1', gap=True)
    brk, *_ = segment('s1', broken=True)
    case('R25_ci114_seq_gap_or_prev_break_partial',
         E.journal_mode([('000001.jsonl', good)])[0] == 'CHAIN_HASH_ONLY'
         and E.journal_mode([('000001.jsonl', gap)]) == ('PARTIAL_HASH_ONLY', None, None)
         and E.journal_mode([('000001.jsonl', brk)]) == ('PARTIAL_HASH_ONLY', None, None))


def tar_with_dirs(s, n, files, extra_dirs=()):
    """REL66 M-03: архив как у zevidence-send плюс лишние записи-каталоги."""
    import tarfile
    import zevidence_send as Z
    buf = io.BytesIO(Z.tar_bytes(s, n, files))
    out = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='r:') as src, tarfile.open(fileobj=out, mode='w', format=tarfile.USTAR_FORMAT) as tf:
        for m in src:
            tf.addfile(m, src.extractfile(m) if m.isreg() else None)
        for d in extra_dirs:
            ti = tarfile.TarInfo(f'{s}/{n}/{d}')
            ti.type, ti.mode = tarfile.DIRTYPE, 0o755
            tf.addfile(ti)
    path = os.path.join(tempfile.mkdtemp(), 'x.tar')
    with open(path, 'wb') as f:
        f.write(out.getvalue())
    return path


def raw_path(base, name, data):
    pth = os.path.join(base, name)
    with open(pth, 'wb') as f:
        f.write(data)
    return pth


def fails_v(V, pth, series):
    try:
        V.read_tar(pth, series)
    except V.Fail:
        return True
    return False


def cli(V, argv):
    """Вызов main программы ПК → (код, вывод)."""
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = V.main(['zprobe_verify_export.py'] + argv)
    return rc, buf.getvalue()


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
        # CI 30, 90: предел числа файлов пакета (32) на стороне zprobe-export — сверх предела пакета нет
        rows30, _ = X.assemble(s, None, BOOT, 9, P)
        nphys = len([r for r in rows30 if r[0] != 'HASH_ONLY'])
        keep, ok30 = E.MAX_FILES, False
        try:
            E.MAX_FILES = nphys + 1
            r30 = refused(X.assemble, s, None, BOOT, 9, P, want='limits:package')
            E.MAX_FILES = nphys + 2
            ok30 = len(X.assemble(s, None, BOOT, 9, P)[0]) == len(rows30)
        finally:
            E.MAX_FILES = keep
        case('X47_ci30_ci90_export_over_file_limit_refused', r30 and ok30 and keep == 32 and nphys + 2 <= 32)
        n1, files = fetch(P, s)
        n_t, files_t = tar_roundtrip(s, n1, files, base)
        res = V.verify(n_t, files_t, s, first=True)
        case('X02_pc_unsealed', res[0] == 'UNSEALED' and files_t == files and 'final/evidence.json' in files
             and b'cred_paths' in files['final/evidence.json'] and b'/x' not in files['final/evidence.json'])
        whole = Z.tar_bytes(s, n1, files)        # REL65 M-01, CI 31: метка во ВСЁМ готовом архиве, включая журнал
        case('X26_journal_challenge_canary_absent_in_whole_archive',
             JCAN.encode() not in whole and not any(JCAN.encode() in v for v in files.values())
             and not any(k.startswith('journal/') for k in files) and 'journal_chain_root_claim' in res[2])
        case('X03_hash_only_no_file', 'final/request.json' not in files and any('final/request.json' in h for h in res[3]))
        run(P, s)
        _, files2 = fetch(P, s)
        case('X04_second_package_n2', json.loads(files2['package/bundle.json'])['n'] == 2)
        case('X05_rollback_fail', V.verify(1, files, s, history={'n': 2})[0] == 'FAIL')
        b2 = json.loads(files2['package/bundle.json'])     # REL65 L-04, CI 121: n растёт, journal_last_seq меньше принятого
        ls2 = b2['journal_last_seq']
        case('X27_journal_last_seq_rollback_fail_n_grows',
             type(ls2) is int and V.verify(2, files2, s, history={'n': 1, 'journal_last_seq': ls2 + 1})[0] == 'FAIL'
             and V.verify(2, files2, s, history={'n': 1, 'journal_last_seq': ls2})[0] != 'FAIL')
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
        # REL65 M-04 (CI 109/123/124): посторонний файл в исходной папке final — отказ, а не пропуск
        P23, _ = mkenv(os.path.join(base, 'm23'), s, 'B10')
        put(os.path.join(P23['run'], s, 'notes.json'), b'{}')
        case('X23_final_foreign_notes_refused', refused(run, P23, s, want='final/notes.json:unknown'))
        P24, _ = mkenv(os.path.join(base, 'm24'), s, 'B10')
        os.unlink(os.path.join(P24['run'], s, 'state.json'))
        put(os.path.join(P24['run'], s, 'notes.json'), b'{}')
        case('X24_no_state_plus_foreign_notes_fail_first', refused(run, P24, s))
        P25, _ = mkenv(os.path.join(base, 'm25'), 'pb1trial2', 'B9R2')
        put(os.path.join(P25['preserve'], 'pb1trial2', 'extra.txt'), b'x')
        case('X25_b9_preserve_foreign_refused_manifest_allowed',
             refused(run, P25, 'pb1trial2', want='final/extra.txt:unknown'))
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
        # REL66 M-03: ранее принятый пакет + пустая папка / глубокая папка / повтор папки → FAIL
        pt = os.path.join(base, 'canon.tar')
        with open(pt, 'wb') as f:
            f.write(Z.tar_bytes(s, n1, files))
        ok = V.verify(*V.read_tar(pt, s), s, first=True)[0] == 'UNSEALED'
        bad = []
        for extra in (['final/notes_empty_dir'], ['suspicious/nested/too'], ['final'], ['package/x']):
            try:
                V.read_tar(tar_with_dirs(s, n1, files, extra), s)
                bad.append(extra[0])
            except V.Fail as e:
                if not str(e).startswith('tar:dir:'):
                    bad.append(extra[0])
        case('X28_pc_pass_package_plus_extra_or_deep_dir_fail', ok and not bad)
        # REL66 M-02 (CI 121): история ПК через вызов программы — файл, --init, откат, без --state
        st = os.path.join(base, 'pc_state.json')
        t1 = os.path.join(base, 'p1.tar')
        t2 = os.path.join(base, 'p2.tar')
        with open(t1, 'wb') as f:
            f.write(Z.tar_bytes(s, 1, files))
        with open(t2, 'wb') as f:
            f.write(Z.tar_bytes(s, 2, files2))
        steps = []
        steps.append(cli(V, [t1, s, '--state', st])[0] == 1 and not os.path.exists(st))           # нет файла
        rc, out = cli(V, [t1, s, '--state', st, '--init'])
        steps.append(rc == 10 and 'FIRST_RECEIPT' in out and json.load(open(st))[s]['n'] == 1)    # первый приём
        steps.append(cli(V, [t1, s, '--state', st, '--init'])[0] == 2)                            # --init повторно
        rc, out = cli(V, [t2, s, '--state', st])
        steps.append(rc == 10 and json.load(open(st))[s]['n'] == 2)                               # n=2 принят
        rc, out = cli(V, [t1, s, '--state', st])
        steps.append(rc == 1 and 'REASON v:rollback' in out and json.load(open(st))[s]['n'] == 2)  # старый n
        with open(st, 'w') as f:
            json.dump({s: {'n': 1, 'journal_last_seq': (ls2 or 0) + 1}}, f)
        rc, out = cli(V, [t2, s, '--state', st])
        steps.append(rc == 1 and 'REASON v:rollback' in out)                                      # меньший last_seq
        steps.append(cli(V, [t2, s])[0] == 2)                                                     # без --state
        with open(st, 'w') as f:
            f.write('{broken')
        rc, out = cli(V, [t2, s, '--state', st])
        steps.append(rc == 1 and 'state:corrupt' in out)                                          # битый файл
        with open(st, 'w') as f:
            json.dump({'other1': {'n': 1, 'journal_last_seq': 0}}, f)
        steps.append(cli(V, [t2, s, '--state', st])[0] == 1)                                      # нет записи серии
        r = V.verify(1, files, s)
        steps.append(r[0] == 'INCOMPLETE' and 'history_absent' in r[1])                          # API без истории
        case('X29_pc_cli_history_required_rollback_fail', all(steps))
        # REL66 L-02, CI 16 и 109: имя с «..» в архиве ПК — FAIL; подпапка в папке источника — отказ сервера
        import tarfile
        tb = io.BytesIO()
        with tarfile.open(fileobj=tb, mode='w', format=tarfile.USTAR_FORMAT) as tf:
            ti = tarfile.TarInfo(f'{s}/1/final/../x.json')
            ti.size = 2
            tf.addfile(ti, io.BytesIO(b'{}'))
        tdot = os.path.join(base, 'dot.tar')
        with open(tdot, 'wb') as f:
            f.write(tb.getvalue())
        try:
            V.read_tar(tdot, s)
            r1 = False
        except V.Fail as e:
            r1 = str(e).startswith('tar:name:')
        P31, _ = mkenv(os.path.join(base, 'm31'), s, 'B10')
        put(os.path.join(P31['run'], s, 'a', 'b.json'), b'{}')
        try:
            run(P31, s)
            r2 = False
        except (E.Refused, OSError):
            r2 = True
        case('X31_ci16_ci109_dotdot_name_and_source_subdir_refused', r1 and r2)
        # CI 17: лишний аргумент, путь вместо серии, чужая (несуществующая) серия — отказ без вывода
        out = io.BytesIO()
        r1 = all(Z.main({'SSH_ORIGINAL_COMMAND': c}, out) == 2 for c in
                 ('send b10ci1 x', 'send ../b10ci1', 'send /var/lib/zavod', 'send', '')) and out.getvalue() == b''
        try:
            Z.pick('b10zz9', P['export'], None)
            r2 = False
        except (Z.Bad, OSError):
            r2 = True
        case('X32_ci17_send_extra_arg_path_foreign_series_refused', r1 and r2)
        # CI 42, 43, 93: нет READY, READY с чужой суммой (ПК и send), файл у строки HASH_ONLY, out у HASH_ONLY
        t_noready = dict(files)
        t_noready.pop('READY')
        t_badready = dict(files, READY=(sha(b'other') + '\n').encode())
        hkey = next(f'{p_}/{nm}' for m, p_, nm, *_ in E.parse_manifest(files['MANIFEST.sha256']) if m == 'HASH_ONLY')
        t_hfile = dict(files, **{hkey: b'{}'})
        mline = files['MANIFEST.sha256'].decode().replace(f'{hkey}  ', f'{hkey}  ', 1)
        rows_txt = []
        for ln in mline.splitlines():
            if f'  {hkey}  ' in ln:
                ln = ln.replace('out=-  out_size=-', f'out={sha(b"{}")}  out_size=2')
            rows_txt.append(ln)
        man_h = ('\n'.join(rows_txt) + '\n').encode()
        t_hout = dict(files, **{'MANIFEST.sha256': man_h, 'READY': (sha(man_h) + '\n').encode(), hkey: b'{}'})
        r_pc = [V.verify(1, t, s, first=True) for t in (t_noready, t_badready, t_hfile, t_hout)]
        P33, _ = mkenv(os.path.join(base, 'm33'), s, 'B10')
        run(P33, s)
        rp = os.path.join(P33['export'], s, '1', 'READY')
        os.chmod(rp, 0o640)
        with open(rp, 'wb') as f:
            f.write((sha(b'other') + '\n').encode())
        try:
            Z.pick(s, P33['export'], None)
            r_send = False
        except Z.Bad as e:
            r_send = str(e) == 'no_ready_package'
        case('X33_ci42_ci43_ci93_ready_and_hash_only_fail',
             r_pc[0][1] == ['a:READY'] and r_pc[1][1] == ['a:READY'] and r_pc[2][1] == ['a:set']
             and r_pc[3][0] == 'FAIL' and r_send)
        # CI 95 и 122: пропуск каждого обязательного final/* по одному → INCOMPLETE с причиной этого имени
        bad = []
        for nm in E.required('B10', 'final'):
            r = V.verify(1, with_row(files, f'final/{nm}'), s, first=True)
            if r[0] != 'INCOMPLETE' or f'final_required_absent:{nm}' not in r[1]:
                bad.append((nm, r[0], r[1][:2]))
        case('X34_ci95_ci122_each_required_final_absent_incomplete', not bad and 'state.json' in E.required('B10', 'final'))
        if bad:
            print('X34_DETAIL', bad)
        # CI 109, 123, 124 на ПК: лишний final/notes.json (без строки и со строкой), .01, подпапка; нет state + notes
        t1 = dict(files, **{'final/notes.json': b'{}'})
        cand = [t1, with_row(files, 'final/notes.json', b'{}', mode='ALLOW'),
                with_row(files, 'final/state.json.01', b'{}', mode='ALLOW'),
                with_row(files, 'final/a/b.json', b'{}', mode='ALLOW'),
                with_row(with_row(files, 'final/state.json'), 'final/notes.json', b'{}', mode='ALLOW')]
        res35 = []
        for t in cand:
            try:
                res35.append(V.verify(1, t, s, first=True)[0])
            except E.Refused:
                res35.append('FAIL')
        case('X35_ci109_ci123_ci124_pc_foreign_final_fail', res35 == ['FAIL'] * 5)
        # CI 115: файлы journal/ в архиве ПК — FAIL (журнал только HASH_ONLY)
        seg, *_ = segment(s)
        res36 = []
        for mode in ('FULL_RAW', 'ALLOW'):
            try:
                res36.append(V.verify(1, with_row(files, 'journal/000001.jsonl', seg, mode=mode), s, first=True)[0])
            except E.Refused:
                res36.append('FAIL')
        res36.append(V.verify(1, dict(files, **{'journal/000001.jsonl': seg}), s, first=True)[0])
        case('X36_ci115_pc_journal_files_fail', res36 == ['FAIL'] * 3)
        # CI 111: пакет без печати (seal=null) со строкой proof/ или sealed/ → FAIL
        res37 = []
        for key in ('proof/proof.json', 'sealed/meta/INVENTORY.sha256', 'sealed/source/state.json'):
            try:
                res37.append(V.verify(1, with_row(files, key, b'{}'), s, first=True)[0])
            except E.Refused:
                res37.append('FAIL')
        case('X37_ci111_unsealed_with_proof_or_sealed_row_fail', res37 == ['FAIL'] * 3)
        # REL67 M-02: канонический архив ПК = байты zevidence-send; к PASS-пакету PAX-метка или хвост → FAIL
        whole = Z.tar_bytes(s, n1, files)
        bad38 = []
        for extra in (b'X' * 36, b'\0' * 1024):
            pth = os.path.join(base, f'tail{len(extra)}.tar')
            with open(pth, 'wb') as f:
                f.write(whole + extra)
            try:
                V.read_tar(pth, s)
                bad38.append(len(extra))
            except V.Fail as e:
                if str(e) != 'tar:not_canonical':
                    bad38.append(str(e))
        case('X38_pc_canonical_equals_send_and_tail_fail', V.canonical_tar(s, n1, files) == whole and not bad38)
        # REL67 M-01: journal_segments с пределом до перебора; пустая цепочка не CHAIN
        import time
        bj = json.loads(files['package/bundle.json'])
        okv = []
        for v_, want in ((1, True), (E.MAX_LINES, True), (E.MAX_LINES + 1, False), (10 ** 9, False), (-1, False)):
            okv.append(refused(E.check_bundle, dict(bj, journal_segments=v_)) != want)
        t0 = time.monotonic()
        r39 = V.verify(1, reseal(files, 'package/bundle.json', S.canon(dict(bj, journal_segments=10 ** 9))), s, first=True)
        r39b = V.verify(1, reseal(files, 'package/bundle.json', S.canon(dict(bj, journal_segments=E.MAX_LINES))), s,
                        first=True)
        fast = time.monotonic() - t0 < 5
        chain0 = refused(E.check_bundle, dict(bj, journal_mode='CHAIN_HASH_ONLY', journal_segments=0)) and \
            refused(E.check_bundle, dict(bj, journal_mode='CHAIN_HASH_ONLY', journal_last_seq=0))
        case('X39_journal_segments_bounded_and_empty_chain_refused',
             all(okv) and r39[0] == 'FAIL' and r39b[0] == 'FAIL' and r39b[1] == ['g:segments'] and fast and chain0
             and E.journal_mode([])[0] == 'PARTIAL_HASH_ONLY')
        # REL67 M-03: история пишется до итога; сбой записи → FAIL state_persist без PASS, история прежняя
        st40 = os.path.join(base, 'st40.json')
        with open(st40 + '.tmp', 'w') as f:
            f.write('foreign')
        p40a = raw_path(base, 'p40a.tar', Z.tar_bytes(s, 1, files))
        p40b = raw_path(base, 'p40b.tar', Z.tar_bytes(s, 2, files2))
        rc, out = cli(V, [p40a, s, '--state', st40, '--init'])
        r40 = [rc == 10 and open(st40 + '.tmp').read() == 'foreign' and json.load(open(st40))[s]['n'] == 1]
        before = open(st40, 'rb').read()
        saved = (V.os.replace, V.os.fsync)
        for kind in ('replace', 'fsync', 'enospc'):
            def boom(*a, **k):
                raise OSError(28, 'No space left on device')
            if kind == 'fsync':
                V.os.fsync = boom
            else:
                V.os.replace = boom
            try:
                rc, out = cli(V, [p40b, s, '--state', st40])
            finally:
                V.os.replace, V.os.fsync = saved
            r40.append(rc == 1 and 'REASON state_persist:OSError' in out and 'UNSEALED' not in out
                       and 'PASS' not in out.replace('PASS_SANITIZED —', '') and open(st40, 'rb').read() == before
                       and not [x for x in os.listdir(base) if x.startswith('.zprobe_state_')])
        case('X40_state_written_before_result_persist_fail_no_pass', all(r40))
        if not all(r40):
            print('X40_DETAIL', r40)
        # REL67 L-01, CI 16: серия с «..», путём, пустая, лишний аргумент — zprobe-export отказывает кодом 2
        case('X41_ci16_export_main_bad_series_code2',
             all(X.main(a) == 2 for a in (['zprobe-export', '../x'], ['zprobe-export', 'a/b'], ['zprobe-export', ''],
                                           ['zprobe-export', s, 'x'], ['zprobe-export'])))
        # REL67 L-02, CI 17: две существующие серии с готовыми пакетами — выдаётся пакет ТОЛЬКО названной серии
        s2 = 'b10ci9'
        P42, _ = mkenv(os.path.join(base, 'm42'), s, 'B10')
        P42b, _ = mkenv(os.path.join(base, 'm42b'), s2, 'B10')
        P42b['export'] = P42['export']
        run(P42, s)
        run(P42b, s2)
        na, fa = Z.pick(s, P42['export'], None)
        nb, fb = Z.pick(s2, P42['export'], None)
        ta, tb_ = Z.tar_bytes(s, na, fa), Z.tar_bytes(s2, nb, fb)
        # CI 47: n=1 без READY пропускается, n=2 с READY выдаётся; байты папки n=1 до и после выдачи те же
        P43, _ = mkenv(os.path.join(base, 'm43'), s, 'B10')
        run(P43, s)
        run(P43, s)
        d1 = os.path.join(P43['export'], s, '1')
        os.chmod(os.path.join(d1, 'READY'), 0o640)
        os.rename(os.path.join(d1, 'READY'), os.path.join(base, 'ready43.moved'))

        def snap(d):
            out = {}
            for root_, _, fs in os.walk(d):
                for f_ in fs:
                    out[os.path.relpath(os.path.join(root_, f_), d)] = sha(open(os.path.join(root_, f_), 'rb').read())
            return out
        b43 = snap(d1)
        n43, f43 = Z.pick(s, P43['export'], None)
        case('X43_ci47_unready_n1_skipped_n2_sent_n1_unchanged',
             n43 == 2 and json.loads(f43['package/bundle.json'])['n'] == 2 and snap(d1) == b43 and 'READY' not in b43)
        # CI 48: send — номер или путь вместо серии → код 2; ПК — корень архива n не равен bundle.n → FAIL
        out48 = io.BytesIO()
        r48 = all(Z.main({'SSH_ORIGINAL_COMMAND': c}, out48) == 2 for c in
                  (f'send {s} 1', 'send 1', f'send {s}/1', f'get {s}')) and out48.getvalue() == b''
        p48 = raw_path(base, 'p48.tar', Z.tar_bytes(s, 3, files))
        n48, f48 = V.read_tar(p48, s)
        r48b = n48 == 3 and V.verify(n48, f48, s, first=True)[1] == ['v:bundle_n_series']
        case('X44_ci48_send_number_or_path_code2_pc_root_n_mismatch_fail', r48 and r48b)
        # CI 108: журнал — сегментов в bundle больше, чем строк (нет 000002); лишняя строка 000002 при segments=1
        bj45 = json.loads(files['package/bundle.json'])
        r45a = V.verify(1, reseal(files, 'package/bundle.json', S.canon(dict(bj45, journal_segments=2))), s, first=True)
        m45 = files['MANIFEST.sha256'] + ('HASH_ONLY  journal/000002.jsonl  raw=' + sha(b'x') +
                                          '  raw_size=1  out=-  out_size=-\n').encode()
        r45b = V.verify(1, dict(files, **{'MANIFEST.sha256': m45, 'READY': (sha(m45) + '\n').encode()}), s, first=True)
        case('X45_ci108_journal_segment_missing_or_extra_fail', r45a[1] == ['g:segments'] and r45b[0] == 'FAIL')
        # CI 113 (сторона zprobe-export): чужой курсор proof или якоря → отказ сервера до выдачи пакета
        cp = E.cursors_problem
        pf = {'journal_from_cursor': CUR1, 'journal_to_cursor': CUR2}
        cs = CUR2.replace('s=' + 'a' * 32, 's=' + 'c' * 32)
        cb = CUR2.replace('b=' + BOOT, 'b=' + 'd' * 32)
        ca = CUR2.replace('i=20', 'i=21')
        r46 = [cp(pf, [CUR2], BOOT), cp(dict(pf, journal_to_cursor=cs), [], BOOT),
               cp({'journal_from_cursor': CUR2, 'journal_to_cursor': CUR1}, [], BOOT),
               cp(dict(pf, journal_to_cursor=cb), [], BOOT), cp(pf, [], 'd' * 32), cp(pf, [ca], BOOT),
               cp(pf, [cs.replace('i=20', 'i=1f')], BOOT), cp(dict(pf, journal_to_cursor='junk'), [], BOOT)]
        case('X46_ci113_export_foreign_cursor_refused',
             r46 == [None, 'cursor:proof', 'cursor:proof', 'cursor:proof', 'cursor:proof', 'cursor:anchor',
                     'cursor:anchor', 'cursor:form'])
        if r46[0] is not None or r46[-1] != 'cursor:form':
            print('X46_DETAIL', r46)
        case('X42_ci17_two_existing_series_each_gets_only_own',
             json.loads(fa['package/bundle.json'])['series'] == s and json.loads(fb['package/bundle.json'])['series'] == s2
             and s2.encode() not in ta and V.read_tar(raw_path(base, 'a42.tar', ta), s)[1] == fa
             and V.read_tar(raw_path(base, 'b42.tar', tb_), s2)[1] == fb and fails_v(V, raw_path(base, 'c42.tar', ta), s2))
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
        r = V.verify(n, got, s, seal_sha=row['proof_sha256'], first=True)
        case('Y01_b10_sealed_pass', r[0] == 'PASS_SANITIZED' and b['journal_cursor'] == CUR2
             and 'sealed/source/request.json' not in got and 'sealed/source/state.json' in got)
        case('Y02_phone_sha_mismatch_fail', V.verify(n, got, s, seal_sha='0' * 64)[0] == 'FAIL')
        s9 = 'pb1trial2'
        P9, f9 = mkenv(os.path.join(base, 'b'), s9, 'B9R2')
        row9 = seal_attempt(P9, s9, 'B9R2', f9)
        n9, _, _ = X.write_package(s9, row9, BOOT, P9, gid)
        _, got9 = Z.pick(s9, P9['export'], None)
        r9 = V.verify(n9, got9, s9, seal_sha=row9['proof_sha256'], first=True)
        case('Y03_b9r2_sealed_pass', r9[0] == 'PASS_SANITIZED' and 'sealed/meta/MANIFEST.sha256' in got9, )
        # CI 46: сбой вызова до COMMIT — попытка k=1 без строки, печать взяла k=2; выгрузка берёт только k=2
        s46 = 'b10ci46'
        P46, f46 = mkenv(os.path.join(base, 'k2'), s46, 'B10')
        lost = dict(f46)
        lost['state.json'] = f46['state.json'] + b' '
        seal_attempt(P46, s46, 'B10', lost, k=1)
        row46 = seal_attempt(P46, s46, 'B10', f46, k=2)
        n46, _, _ = X.write_package(s46, row46, BOOT, P46, gid)
        _, got46 = Z.pick(s46, P46['export'], None)
        r46 = V.verify(n46, got46, s46, seal_sha=row46['proof_sha256'], first=True)
        case('Y32_ci46_lost_k1_export_takes_k2', r46[0] == 'PASS_SANITIZED'
             and sha(got46.get('proof/proof.json', b'')) == row46['proof_sha256']
             and got46.get('sealed/source/state.json') is not None)
        # CI 101: final/cleanup.json записан ПОСЛЕ печати (COMMIT) → выгрузка PASS_SANITIZED; подмена final/ на ПК → FAIL
        s101 = 'b10ci101'
        P101, f101 = mkenv(os.path.join(base, 'late'), s101, 'B10', final=False)
        row101 = seal_attempt(P101, s101, 'B10', f101)
        put(os.path.join(P101['run'], s101, 'cleanup.json'), cleanup_doc(s101))
        n101, _, _ = X.write_package(s101, row101, BOOT, P101, gid)
        _, got101 = Z.pick(s101, P101['export'], None)
        r101 = V.verify(n101, got101, s101, seal_sha=row101['proof_sha256'], first=True)
        bad101 = dict(got101, **{'final/cleanup.json': got101.get('final/cleanup.json', b'') + b' '})
        r101b = V.verify(n101, bad101, s101, seal_sha=row101['proof_sha256'], first=True)
        case('Y33_ci101_late_final_pass_pc_swap_fail', r101[0] == 'PASS_SANITIZED' and 'final/cleanup.json' in got101
             and r101b[0] == 'FAIL')
        if r101[0] != 'PASS_SANITIZED' or r101b[0] != 'FAIL':
            print('Y33_DETAIL', r101[:2], r101b[:2])
        # CI 78, 87: опись (B) B9 R2 с испорченным полем строки (не anchor.json) — сумма proof верна, выгрузка отказывает
        def inv_field(idx, val):
            def ed(inv):
                out = []
                done = False
                for ln in inv.decode().splitlines(keepends=True):
                    f = ln.rstrip('\n').split('  ')
                    if not done and f[2] != 'anchor.json':
                        f[idx] = val(f[idx]) if callable(val) else val
                        if idx == 4 and val == '-':
                            f[6] = '-'
                        done = True
                    out.append('  '.join(f) + '\n')
                return ''.join(out).encode()
            return ed
        bad78 = [(3, lambda p: p.replace('/var/lib/zavod/preserve/', '/var/tmp/')), (4, lambda p: p + 'x'), (4, '-')]
        bad87 = [(5, '0:0:0644'), (6, '0:0:0644')]
        res = []
        for j, (idx, val) in enumerate(bad78 + bad87):
            Pj, fj = mkenv(os.path.join(base, f'inv{j}'), s9, 'B9R2')
            rowj = seal_attempt(Pj, s9, 'B9R2', fj, inv_edit=inv_field(idx, val))
            try:
                X.write_package(s9, rowj, BOOT, Pj, gid)
                res.append('accepted')
            except E.Refused as e:
                res.append(str(e).split(':')[0])
        case('Y34_ci78_b9_inventory_phys_orig_refused', 'accepted' not in res[:3] and len(res) == 5)
        case('Y35_ci87_b9_inventory_src_orig_src_refused', 'accepted' not in res[3:] and len(res) == 5)
        print('Y34_DETAIL', res)
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
        # REL65 L-04: проверки CI без теста по карте CI_MATRIX_B10_REL66 (ПК — FAIL, root — отказ).
        pv = row['proof_sha256']
        case('Y07_ci96_optional_dropin_check_absent_warns',
             r[0] == 'PASS_SANITIZED' and 'FINAL_OPTIONAL_ABSENT dropin_check.json' in r[2])
        bad = []
        for key, field in (('final/state.json', 'lease_id'), ('final/evidence.json', 'lease'),
                           ('sealed/source/anchor.json', 'series'), ('package/bundle.json', 'lease_id')):
            d = json.loads(got9[key])
            t = reseal(got9, key, S.canon(dict(d, **{field: bump(d[field])})))
            if V.verify(n9, t, s9, seal_sha=row9['proof_sha256'])[0] != 'FAIL':
                bad.append(key)
        case('Y08_ci77_b9r2_link_swap_fail', not bad)
        t = dict(got)
        t['sealed/source/request.json'] = b'{}'
        case('Y09_ci98_file_without_row_fail', V.verify(n, t, s, seal_sha=pv)[0] == 'FAIL')
        case('Y10_ci100_place_outside_table_fail',
             V.verify(n, with_row(got, 'root/x', b'{}'), s, seal_sha=pv)[0] == 'FAIL'
             and V.verify(n, with_row(got, 'sealed/source/proof.json', got['proof/proof.json']), s,
                          seal_sha=pv)[0] == 'FAIL')
        case('Y11_ci86_sealed_meta_extra_or_missing_fail',
             V.verify(n, with_row(got, 'sealed/meta/extra.sha256', b'x\n'), s, seal_sha=pv)[0] == 'FAIL'
             and V.verify(n, with_row(got, 'sealed/source/INVENTORY.sha256', got['sealed/meta/INVENTORY.sha256']),
                          s, seal_sha=pv)[0] == 'FAIL'
             and V.verify(n, with_row(got, 'sealed/meta/INVENTORY.sha256'), s, seal_sha=pv)[0] == 'FAIL')
        case('Y12_ci120_sealed_raw_not_from_snapshot_fail',
             V.verify(n, with_row(got, 'sealed/source/state.json', raw=sha(b'other')), s, seal_sha=pv)[0] == 'FAIL')
        sd = 'b10ci3'
        Pd, fd_ = mkenv(os.path.join(base, 'd'), sd, 'B10')
        arch = {'50-zprobe.conf': b'[Service]\nA=1\n', '50-zprobe.conf.1': b'[Service]\nA=0\n'}
        for nm, dt in arch.items():
            put(os.path.join(Pd['archive'], sd, nm), dt)
        put(os.path.join(Pd['started'], sd), b'started ' + sd.encode() + b'\n')
        rowd = seal_attempt(Pd, sd, 'B10', fd_)
        nd, _, _ = X.write_package(sd, rowd, BOOT, Pd, gid)
        _, gotd = Z.pick(sd, Pd['export'], None)
        rows_d = {f'{p}/{nm}': (m, r) for m, p, nm, r, *_ in E.parse_manifest(gotd['MANIFEST.sha256'])}
        want = {'final/archive.' + k: ('HASH_ONLY', sha(v)) for k, v in arch.items()}
        want['final/started.marker'] = ('HASH_ONLY', sha(b'started ' + sd.encode() + b'\n'))
        case('Y13_ci116_archive_and_started_hash_only',
             all(rows_d.get(k) == v for k, v in want.items()) and not any(k in gotd for k in want)
             and V.verify(nd, gotd, sd, seal_sha=rowd['proof_sha256'], first=True)[0] == 'PASS_SANITIZED')
        put(os.path.join(Pd['archive'], sd, 'notes.txt'), b'x')
        r1 = refused(X.write_package, sd, rowd, BOOT, Pd, gid, want='archive/notes.txt')
        os.remove(os.path.join(Pd['archive'], sd, 'notes.txt'))
        os.rename(os.path.join(Pd['archive'], sd), os.path.join(Pd['archive'], sd + '.real'))
        os.symlink(sd + '.real', os.path.join(Pd['archive'], sd))
        try:
            X.write_package(sd, rowd, BOOT, Pd, gid)
            r2 = False
        except (E.Refused, OSError):
            r2 = True
        case('Y14_ci117_archive_foreign_name_or_link_refused', r1 and r2)
        # REL66 M-01: сумма печати с телефона обязательна для PASS
        r = V.verify(n, got, s, first=True)
        r9 = V.verify(n9, got9, s9, first=True)
        case('Y15_no_phone_seal_sha_not_pass', r[0] == 'INCOMPLETE' and 'phone_seal_sha_absent' in r[1]
             and r9[0] == 'INCOMPLETE' and 'phone_seal_sha_absent' in r9[1])
        case('Y16_phone_seal_sha_bad_format_fail',
             all(V.verify(n, got, s, seal_sha=x, first=True)[1] == ['e:phone_seal_sha_format']
                 for x in ('', pv[:63], pv + '0', pv.upper(), 'g' * 64))
             and V.verify(n, got, s, seal_sha=pv, first=True)[0] == 'PASS_SANITIZED')
        st = os.path.join(base, 'pc_state.json')
        tp = os.path.join(base, 'sealed.tar')
        with open(tp, 'wb') as f:
            f.write(Z.tar_bytes(s, n, got))
        rc1, out1 = cli(V, [tp, s, '--state', st, '--init'])
        rc2, out2 = cli(V, [tp, s, '--state', st, '--init', '--seal-sha', '0' * 64])
        rc3, out3 = cli(V, [tp, s, '--state', st, '--init', '--seal-sha', pv.upper()])
        case('Y17_cli_phone_sha_absent_incomplete_no_state_write',
             rc1 == 11 and 'REASON phone_seal_sha_absent' in out1 and rc2 == 1
             and rc3 == 0 and 'ZPROBE_VERIFY_EXPORT=PASS_SANITIZED' in out3 and json.load(open(st))[s]['n'] == n)
        # REL66 L-02, CI 113 на ПК: journal_cursor пакета ≠ proof, другой b_probe/boot_id → FAIL
        bj = json.loads(got['package/bundle.json'])
        t_c = reseal(got, 'package/bundle.json', S.canon(dict(bj, journal_cursor=CUR1)))
        t_b = reseal(got, 'package/bundle.json', S.canon(dict(bj, b_probe='0' * 32)))
        r_c = V.verify(n, t_c, s, seal_sha=pv, first=True)
        r_b = V.verify(n, t_b, s, seal_sha=pv, first=True)
        case('Y18_ci113_pc_journal_cursor_or_boot_mismatch_fail', r_c[0] == 'FAIL' and r_b[0] == 'FAIL')
        if r_c[0] != 'FAIL' or r_b[0] != 'FAIL':
            print('Y18_DETAIL', r_c[:2], r_b[:2])
        def vf(t, sh=pv):
            try:
                return V.verify(n, t, s, seal_sha=sh, first=True)[0]
            except E.Refused:
                return 'FAIL'
        pj = json.loads(got['proof/proof.json'])
        # CI 45, 58, 112: нет proof, proof изменён (сумма телефона прежняя), лишнее поле, нет INVENTORY
        t_extra, sh_extra = reproof(got, S.canon(dict(pj, extra=1)))
        r19 = [vf(with_row(got, 'proof/proof.json')), vf(reproof(got, S.canon(dict(pj, tool_version='x')))[0]),
               vf(t_extra, sh_extra), vf(with_row(got, 'sealed/meta/INVENTORY.sha256'))]
        case('Y19_ci45_ci58_ci112_proof_absent_changed_extra_inventory_absent_fail', r19 == ['FAIL'] * 4)
        # CI 59: proof.sources без одного источника / с лишним (сумма телефона согласована)
        src = pj['sources']
        r20 = [vf(*reproof(got, S.canon(dict(pj, sources=src[1:])))),
               vf(*reproof(got, S.canon(dict(pj, sources=src + [{'name': 'x.json', 'sha256': sha(b'x'), 'size': 1}]))))]
        case('Y20_ci59_proof_sources_missing_or_extra_fail', r20 == ['FAIL'] * 2)
        # CI 73: proof.json не в каноническом виде (пробелы, перевод строки, порядок ключей)
        canon = S.canon(pj)
        r21 = [vf(*reproof(got, json.dumps(pj, sort_keys=True, indent=1).encode())),
               vf(*reproof(got, canon + b'\n')),
               vf(*reproof(got, json.dumps(dict(reversed(list(pj.items()))), separators=(',', ':')).encode()))]
        case('Y21_ci73_proof_not_canonical_fail', r21 == ['FAIL'] * 3)
        # CI 63, 64, 83: опись с лишней строкой / без строки / изменённой суммой; proof и печать согласованы
        inv = got['sealed/meta/INVENTORY.sha256']
        lines = inv.splitlines(keepends=True)
        r22 = []
        for new in (inv + lines[0], b''.join(lines[1:]), inv.replace(lines[0][:64], sha(b'other').encode(), 1)):
            t = reseal(got, 'sealed/meta/INVENTORY.sha256', new)
            r22.append(vf(*reproof(t, S.canon(dict(pj, inventory_sha256=sha(new))))))
        case('Y22_ci63_ci64_ci83_inventory_line_extra_missing_sum_fail', r22 == ['FAIL'] * 3)
        # CI 102: bundle без matrix, matrix чужого формата, лишнее поле
        bj = json.loads(got['package/bundle.json'])
        nomatrix = {k: v for k, v in bj.items() if k != 'matrix'}
        r23 = [vf(reseal(got, 'package/bundle.json', S.canon(nomatrix))),
               vf(reseal(got, 'package/bundle.json', S.canon(dict(bj, matrix='B11.v1')))),
               vf(reseal(got, 'package/bundle.json', S.canon(dict(bj, matrix='B9R2.v2')))),
               vf(reseal(got, 'package/bundle.json', S.canon(dict(bj, extra=1))))]
        case('Y23_ci102_bundle_matrix_absent_foreign_extra_field_fail', r23 == ['FAIL'] * 4)
        # CI 106: у HASH_ONLY archive.* и started.marker появился файл → FAIL
        r24 = []
        for key in ('final/archive.50-zprobe.conf', 'final/started.marker'):
            try:
                r24.append(V.verify(nd, dict(gotd, **{key: b'x'}), sd, seal_sha=rowd['proof_sha256'], first=True)[0])
            except E.Refused:
                r24.append('FAIL')
        case('Y24_ci106_hash_only_archive_started_with_file_fail', r24 == ['FAIL'] * 2)
        # CI 99: места пакета с печатью — ровно proof/, sealed/source, sealed/meta, final, package; журнал только HASH_ONLY
        places = {k.rsplit('/', 1)[0] for k in got if '/' in k}
        jrows = [m for m, p_, *_ in E.parse_manifest(got['MANIFEST.sha256']) if p_ == 'journal']
        case('Y25_ci99_sealed_package_places_and_journal_hash_only',
             places == {'proof', 'sealed/source', 'sealed/meta', 'final', 'package'}
             and jrows and set(jrows) == {'HASH_ONLY'} and set(got) >= {'proof/proof.json', 'package/bundle.json'})
        # CI 91: B9 R2 — нет final/cleanup.json → INCOMPLETE; нет cleanup.json в sealed/source → FAIL
        r26a = V.verify(n9, with_row(got9, 'final/cleanup.json'), s9, seal_sha=row9['proof_sha256'], first=True)
        r26b = V.verify(n9, with_row(got9, 'sealed/source/cleanup.json'), s9, seal_sha=row9['proof_sha256'], first=True)
        case('Y26_ci91_b9r2_final_cleanup_absent_incomplete_source_cleanup_absent_fail',
             r26a[0] == 'INCOMPLETE' and 'final_required_absent:cleanup.json' in r26a[1] and r26b[0] == 'FAIL')
        # CI 81: B10 — имя вне матрицы в sealed/source (cleanup.json, notes.json) → FAIL
        r27 = []
        for key in ('sealed/source/cleanup.json', 'sealed/source/notes.json'):
            try:
                r27.append(V.verify(n, with_row(got, key, b'{}', mode='ALLOW'), s, seal_sha=pv, first=True)[0])
            except E.Refused:
                r27.append('FAIL')
        case('Y27_ci81_b10_source_name_outside_matrix_fail', r27 == ['FAIL'] * 2)
        # CI 119: подмена файла ДАННЫХ в seal/<S>/<k>/src/ (не описи) → отказ root
        Pe, fe = mkenv(os.path.join(base, 'e'), s, 'B10')
        rowe = seal_attempt(Pe, s, 'B10', fe)
        dpath = os.path.join(Pe['seal'], s, '1', 'src', 'state.json')
        with open(dpath, 'ab') as f:
            f.write(b' ')
        case('Y28_ci119_seal_src_data_file_tamper_refused', refused(X.write_package, s, rowe, BOOT, Pe, gid))
        # CI 105: опись, proof или bundle в режиме ALLOW → FAIL; FULL_RAW с out≠raw → FAIL
        r29 = []
        for key in ('proof/proof.json', 'package/bundle.json', 'sealed/meta/INVENTORY.sha256'):
            try:
                r29.append(V.verify(n, reseal(got, key, got[key], mode='ALLOW'), s, seal_sha=pv, first=True)[0])
            except E.Refused:
                r29.append('FAIL')
        man = got['MANIFEST.sha256'].decode().splitlines()
        fr = next(i for i, ln in enumerate(man) if ln.startswith('FULL_RAW  package/bundle.json'))
        cols = man[fr].split('  ')
        cols[2] = 'raw=' + sha(b'x')
        man[fr] = '  '.join(cols)
        mraw = ('\n'.join(man) + '\n').encode()
        t29 = dict(got, **{'MANIFEST.sha256': mraw, 'READY': (sha(mraw) + '\n').encode()})
        r29.append(V.verify(n, t29, s, seal_sha=pv, first=True)[0])
        case('Y29_ci105_meta_proof_bundle_allow_or_full_raw_out_ne_raw_fail', r29 == ['FAIL'] * 4)
        # CI 72: sealed/source берётся из снимка seal/, а не из /run: после печати файл в /run изменён
        Pf, ff = mkenv(os.path.join(base, 'f'), s, 'B10')
        rowf = seal_attempt(Pf, s, 'B10', ff)
        snap_sha = sha(ff['evidence.json'])
        runp = os.path.join(Pf['run'], s, 'evidence.json')
        with open(runp, 'ab') as f:
            f.write(b' ')
        try:
            nf, _, _ = X.write_package(s, rowf, BOOT, Pf, gid)
            _, gotf = Z.pick(s, Pf['export'], None)
            rawf = {f'{p_}/{nm}': r for m, p_, nm, r, *_ in E.parse_manifest(gotf['MANIFEST.sha256'])}
            r30 = rawf['sealed/source/evidence.json'] == snap_sha and rawf.get('final/evidence.json') != snap_sha
        except E.Refused:
            r30 = True                                   # отказ тоже безопасен: /run не подменяет снимок
        case('Y30_ci72_sealed_source_from_snapshot_not_run', r30)
        # CI 42: bundle с чужой версией ALLOW → FAIL
        bj31 = json.loads(got['package/bundle.json'])
        r31 = [V.verify(n, reseal(got, 'package/bundle.json', S.canon(dict(bj31, allow_version=v_))), s, seal_sha=pv,
                        first=True)[0] for v_ in ('allow.v2', 'allow.v0', 1)]
        case('Y31_ci42_bundle_foreign_allow_version_fail', r31 == ['FAIL'] * 3)
        rc4, _ = cli(V, [tp, s, '--state', st, '--seal-sha', pv])
        if rc4 != 0:
            case('Y17_repeat_same_n_pass', False)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def limit_cases():
    """REL65 M-05 (CI 16/17): ПК отказывает по числу, размеру, сумме и глубине ДО чтения файлов архива."""
    import tarfile
    import zprobe_verify_export as V

    def raw_tar(data):
        p = os.path.join(tempfile.mkdtemp(), 'a.tar')
        with open(p, 'wb') as f:
            f.write(data)
        return p

    def tar_of(entries, s='s1'):
        """REL67 M-02: канонический архив (как у zevidence-send) — пределы проверяются раньше сверки байтов."""
        return raw_tar(V.canonical_tar(s, 1, {rel: b'x' * size for rel, size in entries}))

    def fails(p, want):
        try:
            V.read_tar(p, 's1')
        except V.Fail as e:
            return str(e).startswith(want)
        return False
    case('L01_pc_33_files_refused', fails(tar_of([(f'final/f{i}.json', 10) for i in range(33)]), 'tar:limits'))
    case('L02_pc_total_over_2mb_small_files_refused',
         fails(tar_of([(f'final/f{i}.json', 256 * 1024) for i in range(8)] + [('final/z.json', 1)]), 'tar:limits'))
    case('L03_pc_one_file_over_256kb_refused', fails(tar_of([('final/big.json', 256 * 1024 + 1)]), 'tar:limits'))
    case('L04_pc_depth_4_refused', fails(tar_of([('sealed/source/x/y.json', 10)]), 'tar:dir:sealed/source/x'))
    n, files = V.read_tar(tar_of([('MANIFEST.sha256', 300 * 1024), ('READY', 65), ('final/a.json', 10)]), 's1')
    case('L05_pc_within_limits_read_manifest_up_to_1mb', n == 1 and len(files) == 3)
    q = 256 * 1024                           # REL66 L-01: граница 2 МБ вместе с MANIFEST и READY
    exact = [('MANIFEST.sha256', E.MAX_TOTAL - 4 * q - 65), ('READY', 65)] + [(f'final/f{i}', q) for i in range(4)]
    over = [('MANIFEST.sha256', E.MAX_TOTAL - 4 * q - 64), ('READY', 65)] + [(f'final/f{i}', q) for i in range(4)]
    case('L06_pc_total_2mb_counts_manifest_and_ready',
         len(V.read_tar(tar_of(exact), 's1')[1]) == 6 and fails(tar_of(over), 'tar:limits'))

    def tar_dirs(dirs, files_=(('final/a.json', 10),)):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:') as tf:
            for d in dirs:
                ti = tarfile.TarInfo(f's1/1/{d}' if d else 's1/1')
                ti.type = tarfile.DIRTYPE
                tf.addfile(ti)
            for rel, size in files_:
                ti = tarfile.TarInfo(f's1/1/{rel}')
                ti.size = size
                tf.addfile(ti, io.BytesIO(b'x' * size))
        p = os.path.join(tempfile.mkdtemp(), 'd.tar')
        with open(p, 'wb') as f:
            f.write(buf.getvalue())
        return p
    case('L07_pc_dirs_only_root_and_file_parents',
         len(V.read_tar(tar_of([('final/a.json', 10)]), 's1')[1]) == 1
         and fails(tar_dirs(['', 'final', 'final/notes_empty_dir']), 'tar:dir:final/notes_empty_dir')
         and fails(tar_dirs(['sealed/source/deep']), 'tar:dir:sealed/source/deep')
         and fails(tar_dirs(['final', 'final']), 'tar:dir:final')
         and fails(tar_dirs(['proof']), 'tar:dir:proof'))
    case('L08_pc_header_count_limit', fails(tar_dirs([f'd{i}' for i in range(V.MAX_HEADERS)]), 'tar:headers')
         and fails(tar_dirs([f'd{i}' for i in range(V.MAX_HEADERS - 1)]), 'tar:dir:'))
    big = os.path.join(tempfile.mkdtemp(), 'big.tar')
    with open(big, 'wb') as f:
        f.write(b'\0' * (V.MAX_TAR_BYTES + 1))
    case('L09_pc_stream_size_limit_before_open', fails(big, 'tar:stream_size'))
    # REL67 M-02: тот же состав, но PAX-заголовок с меткой, GNU-формат, другое поле или хвост → FAIL
    good = {'final/a.json': b'{}', 'MANIFEST.sha256': b'm', 'READY': b'r'}
    canon = V.canonical_tar('s1', 1, good)
    canary = 'SYNTHETIC_CANARY_DO_NOT_EXPORT_77991'

    def variant(fmt, pax=None, mtime=0, tail=b''):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w', format=fmt, pax_headers=pax or {}) as tf:
            src = tarfile.open(fileobj=io.BytesIO(canon), mode='r:')
            for m in src:
                m.mtime = mtime
                tf.addfile(m, src.extractfile(m) if m.isreg() else None)
        return raw_tar(buf.getvalue() + tail)
    v = [variant(tarfile.PAX_FORMAT, pax={'note': canary}), variant(tarfile.GNU_FORMAT), variant(tarfile.USTAR_FORMAT, mtime=1),
         raw_tar(canon + b'X' * 36), raw_tar(canon + b'\0' * 512)]
    case('L10_pc_only_canonical_tar_pax_gnu_field_tail_fail',
         V.read_tar(raw_tar(canon), 's1')[1] == good and all(fails(x, 'tar:not_canonical') for x in v))


def send_limit_cases():
    """REL65 M-05 на сервере: zevidence_send._tree отказывает до чтения (Linux, dir_fd)."""
    import zevidence_send as Z
    base = tempfile.mkdtemp()
    try:
        def tree(entries):
            d = tempfile.mkdtemp(dir=base)
            os.chmod(d, 0o750)
            for rel, size in entries:
                parts = rel.split('/')
                for i in range(1, len(parts)):          # подпапки 0750, файлы 0640 — как у создателя пакета
                    sub = os.path.join(d, *parts[:i])
                    os.makedirs(sub, exist_ok=True)
                    os.chmod(sub, 0o750)
                with open(os.path.join(d, rel), 'wb') as f:
                    f.write(b'x' * size)
                os.chmod(os.path.join(d, rel), 0o640)
            fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
            try:
                Z._tree(fd, '', None, {})
                return 'OK'
            except Z.Bad as e:
                return str(e)
            finally:
                os.close(fd)
        case('X19_send_33_files_refused', tree([(f'final/f{i}', 10) for i in range(33)]).startswith('package:limits'))
        case('X20_send_sum_over_2mb_refused',
             tree([(f'final/f{i}', 250 * 1024) for i in range(9)]).startswith('package:limits'))
        case('X21_send_file_over_256kb_refused', tree([('final/big', 256 * 1024 + 1)]).startswith('package:limits'))
        case('X22_send_depth_4_refused', tree([('sealed/source/x/y', 10)]).startswith('package:depth'))
        q = 256 * 1024                       # REL66 L-01: MANIFEST и READY входят в 2 МБ
        exact = [('MANIFEST.sha256', E.MAX_TOTAL - 4 * q - 65), ('READY', 65)] + [(f'final/f{i}', q) for i in range(4)]
        over = [('MANIFEST.sha256', E.MAX_TOTAL - 4 * q - 64), ('READY', 65)] + [(f'final/f{i}', q) for i in range(4)]
        case('X30_send_total_counts_manifest_and_ready', tree(exact) == 'OK'
             and tree(over).startswith('package:limits'))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main():
    rules_cases()
    rules_cases_rel67()
    limit_cases()
    if LINUX:
        export_cases()
        send_limit_cases()
    else:
        for i in range(1, 46):
            skip(f'X{i:02d}')
    if ROOT:
        sealed_cases()
    else:
        for i in range(1, 32):
            skip(f'Y{i:02d}')
    if not OK:
        print('ZPROBE_EXPORT_TEST=FAIL')
        return 1
    print('ZPROBE_EXPORT_TEST=' + ('PASS_NO_ROOT' if SKIPPED else 'PASS'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
