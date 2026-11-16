#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_r2.py
# ВЕРСИЯ: v0.2 (выпуск B10)  СТАТУС: DRAFT
# v0.2 (2026-11-16 20:51, терминал zavod; REL90 L-355-REL90-02): T14 — preserve/pb1trial2 нет, ссылка, не root, 0777 →
#   R2=REFUSED_INPUT preserve:…, код 2, без трассировки, печать не вызвана.
# ДАТА СОЗДАНИЯ: 2026-11-15 00:07 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проверки zprobe_r2.py (проект B10 v0.18 1.6). T01–T02 — без root. T03–T12 — Linux от root (в CI —
#   sudo): входы preserve, настоящая печать вида r2 (снимок, опись B с orig из (A), proof с
#   preserve_manifest_sha256; проверки H и SQL — подставные), повтор ALREADY_SEALED, тревога после печати и сквозная
#   выгрузка B9 R2 этой печати → ПК PASS_SANITIZED. Итог ZPROBE_R2_TEST=PASS | PASS_NO_ROOT | FAIL.
import hashlib
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_zprobe_export as TX  # noqa: E402
import zprobe_checks as C  # noqa: E402
import zprobe_r2 as R2  # noqa: E402
import zprobe_unstarted as UN  # noqa: E402

OK, SKIPPED = True, 0
ROOT = TX.ROOT


def case(name, cond):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL', flush=True)


def good_eval(_facts):
    ch = {f'H{i}': {'ok': True, 'value': f'n={i} OK'} for i in range(1, 11)}
    ch['H9'] = {'ok': True, 'value': 'OK', 'src': 'r1'}
    return {'ok': True, 'failed': [], 'checks': ch, 'boot_id': TX.BOOT, 't0_utc': '2026-11-14T08:00:00Z',
            'journal_from_cursor': TX.CUR1, 'journal_to_cursor': TX.CUR2}


def mk(base, files=None, man_files=None):
    P = {'preserve': os.path.join(base, 'preserve'), 'run': os.path.join(base, 'run'),
         'seal': os.path.join(base, 'seal'), 'pins_b9': os.path.join(base, 'pins_b9.txt')}
    home = os.path.join(P['preserve'], R2.SERIES)
    os.makedirs(home, mode=0o700)
    os.makedirs(P['seal'], mode=0o755)
    files = files or TX.b9_files()
    for n, d in files.items():
        TX.put0600(home, n, d)
    TX.put0600(home, 'MANIFEST.sha256', TX.manifest_a(man_files or files))
    with open(P['pins_b9'], 'w') as f:
        f.write('# pins\nzprobe-run-b9@.service ' + 'a' * 64 + '\n')
    os.chmod(P['pins_b9'], 0o644)
    return P, files


def run(P, db, ans='SEALED_NOW', recheck=True):
    lid, man_raw, man, entries = R2.inputs(P)
    d = R2.deps(lid, man_raw, man, entries, P)
    d['collect'] = lambda: {}
    d['recheck_facts'] = lambda: {'svc': recheck, 'mask': recheck}
    d['select_row'] = lambda _lid: db.get('row')
    d['call_seal'] = lambda s, l_, sha: (db.__setitem__('row', {'series': s, 'proof_sha256': sha}), ans)[1]
    return UN.seal_unstarted(R2.SERIES, lid, d)


def main():
    global SKIPPED
    case('T01_usage', R2.main(['x', 'pb1trial3']) == 2)
    case('T02_line', R2.line({'seal': 'SEALED_NOW', 'status': 'SAFE_PRE_START', 'k': 1, 'sha': 'f' * 64,
                              'failed': [], 'reason': 'first'}).startswith('R2=SEALED_NOW status=SAFE_PRE_START k=1'))
    if not ROOT:
        for i in range(3, 15):
            SKIPPED += 1
            print(f'CASE T{i:02d} SKIP', flush=True)
        print('ZPROBE_R2_TEST=' + ('PASS_NO_ROOT' if OK else 'FAIL'))
        return 0 if OK else 1
    saved = (C.evaluate, C.h8_ok, C.h10_ok)
    C.evaluate, C.h8_ok, C.h10_ok = good_eval, (lambda v: v is True), (lambda v: v is True)
    base = tempfile.mkdtemp(dir='/var/lib')
    os.chmod(base, 0o755)
    try:
        P, files = mk(os.path.join(base, 'a'))
        lid, man_raw, man, entries = R2.inputs(P)
        case('T03_inputs', lid == TX.LID and entries['anchor.json'] == ('-', '-')
             and entries['state.json'][0] == '/run/zprobe/pb1trial2/state.json')
        case('T04_pins_template', R2.pins_template(P['pins_b9']) == {'path': R2.B9_TEMPLATE, 'sha': 'a' * 64})
        f2 = dict(files, **{'state.json': TX.js({'lease': TX.L, 'lease_id': TX.LID, 'dropin': TX.DROP, 'x': 1})})
        P2, _ = mk(os.path.join(base, 'b'), f2)
        try:
            R2.inputs(P2)
            r = False
        except R2.Refused as e:
            r = str(e) == 'state_fields'
        case('T05_state_extra_field', r)
        P3, _ = mk(os.path.join(base, 'c'), files, dict(files, **{'state.json': b'{}'}))
        try:
            R2.inputs(P3)
            r = False
        except R2.Refused as e:
            r = str(e) == 'manifest_sums'
        case('T06_manifest_sum_mismatch', r)
        db = {}
        r1 = run(P, db)
        a = os.path.join(P['seal'], R2.SERIES, '1')
        proof = json.load(open(os.path.join(a, 'proof.json')))
        inv = open(os.path.join(a, 'src', 'INVENTORY.sha256')).read()
        case('T07_first_seal_safe', r1['status'] == 'SAFE_PRE_START' and r1['seal'] == 'SEALED_NOW'
             and proof['preserve_manifest_sha256'] == hashlib.sha256(man_raw).hexdigest())
        case('T08_inventory_orig_from_a', 'anchor.json  phys=/var/lib/zavod/preserve/pb1trial2/anchor.json  orig=-  '
             'src=0:0:0600  orig_src=-' in inv and 'orig=/run/zprobe/pb1trial2/state.json' in inv
             and 'MANIFEST.sha256' not in [s['name'] for s in proof['sources']])
        r2 = run(P, db, ans='ALREADY_SEALED')
        case('T09_retry_already_sealed', r2['seal'] == 'ALREADY_SEALED' and r2['status'] == 'SAFE_PRE_START'
             and sorted(os.listdir(os.path.join(P['seal'], R2.SERIES))) == ['1'])
        P4, _ = mk(os.path.join(base, 'd'))
        r4 = run(P4, {}, recheck=False)
        case('T10_recheck_fail_no_safe', r4['status'] != 'SAFE_PRE_START' and r4['reason'] == 'recheck')
        import zevidence_send as Z
        import zprobe_export as X
        import zprobe_verify_export as V
        XP = {'run': P['run'], 'preserve': P['preserve'], 'seal': P['seal'], 'export': os.path.join(base, 'export'),
              'archive': os.path.join(base, 'archive'), 'started': os.path.join(base, 'started'),
              'journal': os.path.join(base, 'journal')}
        os.makedirs(XP['export'])
        os.makedirs(XP['journal'])
        seg, *_ = TX.segment(R2.SERIES)
        TX.put(os.path.join(XP['journal'], '000001.jsonl'), seg)
        row = dict(db['row'], sealed_at='2026-11-14T21:00:01Z')
        n, _, b = X.write_package(R2.SERIES, row, TX.BOOT, XP, os.getgid())
        _, got = Z.pick(R2.SERIES, XP['export'], None)
        res = V.verify(n, got, R2.SERIES, seal_sha=row['proof_sha256'], first=True)
        case('T11_r2_then_export_pass', res[0] == 'PASS_SANITIZED' and b['matrix'] == 'B9R2.v2')
        case('T12_r2_hash_only_no_bytes', 'sealed/source/request.json' not in got
             and 'sealed/source/dropin_50-zprobe.conf' not in got and any('dropin_50-zprobe.conf' in h for h in res[3]))
        # REL69 M-02, CI 90: preserve с 33 и 64 файлами (верный MANIFEST), одно чужое имя, файл без строки (A),
        # строка без файла — R2 отказывает ДО печати: call_seal и seal_unstarted не вызваны, папка seal пуста,
        # preserve тот же. Отказ выгрузки на таком же наборе — X51 (test_zprobe_export.py).
        import contextlib
        import io
        calls = []
        keep_un = (UN.seal_unstarted, UN.call_seal)
        UN.seal_unstarted = lambda *a, **k: calls.append('seal_unstarted') or {'status': 'SAFE_PRE_START'}
        UN.call_seal = lambda *a, **k: calls.append('call_seal') or 'SEALED_NOW'
        r13 = []
        try:
            for tag, total, extra_dir, drop_file in (('33', 33, None, None), ('64', 64, None, None),  # noqa
                                                     ('one', len(files) + 1, None, None), ('dir', len(files), 'note.txt', None),
                                                     ('gone', len(files), None, 'request.json')):
                fx = dict(files)
                for i in range(total - len(files)):
                    fx[f'extra{i:02d}.json'] = b'{}'
                Px, _ = mk(os.path.join(base, 't13' + tag), fx)
                home = os.path.join(Px['preserve'], R2.SERIES)
                if extra_dir:
                    TX.put0600(home, extra_dir, b'x')
                if drop_file:
                    os.unlink(os.path.join(home, drop_file))
                before = sorted(os.listdir(home))
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = R2.main(['zprobe_r2.py', R2.SERIES], Px)
                want = ('R2=REFUSED_INPUT preserve_set:' + (extra_dir or drop_file)) if (extra_dir or drop_file) \
                    else 'R2=REFUSED_INPUT matrix:extra00.json'
                r13.append(rc == 2 and buf.getvalue().strip() == want and os.listdir(Px['seal']) == []
                           and sorted(os.listdir(home)) == before and len(before) == total + 1
                           + (1 if extra_dir else 0) - (1 if drop_file else 0))
            r13.append(calls == [])
            buf = io.StringIO()
            Pg, _ = mk(os.path.join(base, 't13good'))
            with contextlib.redirect_stdout(buf):
                R2.main(['zprobe_r2.py', R2.SERIES], Pg)
            r13.append(calls == ['seal_unstarted'])              # верная опись проходит сверку и идёт к печати
        finally:
            UN.seal_unstarted, UN.call_seal = keep_un
        case('T13_ci90_r2_33_64_foreign_refused_before_seal', all(r13))
        if not all(r13):
            print('T13_DETAIL', r13, calls, buf.getvalue()[:200])
        # REL90 L-355-REL90-02: preserve/pb1trial2 нет, это ссылка, папка не root или с записью для всех —
        # R2=REFUSED_INPUT preserve:…, код 2, без трассировки; печать не вызвана, папка seal пуста.
        calls.clear()
        UN.seal_unstarted = lambda *a, **k: calls.append('seal_unstarted') or {'status': 'SAFE_PRE_START'}
        r14 = []
        try:
            for tag in ('none', 'link', 'owner', 'mode'):
                Px, _ = mk(os.path.join(base, 't14' + tag))
                home = os.path.join(Px['preserve'], R2.SERIES)
                if tag in ('none', 'link'):
                    os.rename(home, home + '.away')
                if tag == 'link':
                    os.symlink(home + '.away', home)
                if tag == 'owner':
                    os.chown(home, 65534, 65534)
                if tag == 'mode':
                    os.chmod(home, 0o777)
                buf = io.StringIO()
                try:
                    with contextlib.redirect_stdout(buf):
                        rc = R2.main(['zprobe_r2.py', R2.SERIES], Px)
                except Exception as e:  # noqa: BLE001 — трассировка и есть дефект L-02
                    rc = f'exc:{type(e).__name__}'
                out = buf.getvalue().strip()
                r14.append((tag, rc == 2 and out.startswith('R2=REFUSED_INPUT preserve:') and '\n' not in out
                            and os.listdir(Px['seal']) == []))
            r14.append(('calls', calls == []))
        finally:
            UN.seal_unstarted, UN.call_seal = keep_un
        case('T14_rel90_l02_preserve_open_refused', all(ok for _, ok in r14))
        if not all(ok for _, ok in r14):
            print('T14_DETAIL', r14, buf.getvalue()[:200])
    finally:
        C.evaluate, C.h8_ok, C.h10_ok = saved
        shutil.rmtree(base, ignore_errors=True)
    print('ZPROBE_R2_TEST=' + ('PASS' if OK else 'FAIL'))
    return 0 if OK else 1


if __name__ == '__main__':
    sys.exit(main())
