#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_r2_b11.py
# ВЕРСИЯ: v0.1 (выпуск B11)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-17 07:04 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-17 07:04 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат zavod (ee9861cd)
# НАЗНАЧЕНИЕ: требование аудитора REL96B (раздел 4): шаг R2 из B11 на синтетике, с НАСТОЯЩЕЙ функцией проверок (не
#   подставной, как в test_zprobe_r2.py). Одни и те же факты (остаток b9/pb1trial2: перезапуск journald после T0 и
#   ровно шесть закреплённых записей R1; пробный PIN построен так же, как закрепление R0 v14 — как в test_zprobe_checks.py):
#   - zprobe_checks B10 (настоящий файл из коммита выпуска B10, сумма сверена с отпечатками B10) → BLOCKED H4,H5, печати нет;
#   - zprobe_checks B11 (дерево) → H1–H10 OK, печать, proof с показателями, основанием исключения, версиями и хешами;
#   - повтор — тот же результат, один каталог попытки, proof не изменён; пустая корневая папка seal root:root 0700
#     принимается; отрицательные проверки (дыра в журнале, седьмая запись, служба работает) — BLOCKED без печати и без строки в БД.
#   Часть проверок — чистые (без root, любая ОС), печать — только Linux root (в CI sudo).
#   Строки: CASE <Rnn_имя> PASS|FAIL|SKIP. Итог: ZPROBE_R2_B11_TEST=PASS | PASS_NO_ROOT | FAIL.
# ОГРАНИЧЕНИЯ: пишет только во временные папки; ничего не удаляет; PIN подменяется только внутри процесса теста.
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import types

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, HERE)
import test_zprobe_export as TX  # noqa: E402
import test_zprobe_r2 as T2  # noqa: E402
import zprobe_checks as C  # noqa: E402
import zprobe_r2 as R2  # noqa: E402
import zprobe_unstarted as UN  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()) as _quiet:       # фикстуры и эталонные случаи test_zprobe_checks.py
    import test_zprobe_checks as TC  # noqa: E402

OK, SKIPPED = True, 0
ROOT = TX.ROOT
TEST_PIN, TEST_PIN_SHA = TC.TP, TC.H('test-pin')
H4H5 = ['H4', 'H5']


def case(name, cond, detail=''):
    global OK
    OK &= bool(cond)
    print('CASE', name, 'PASS' if cond else 'FAIL ' + f'-> {detail}'[:300], flush=True)


def skip(name):
    global SKIPPED
    SKIPPED += 1
    print('CASE', name, 'SKIP (needs Linux root)', flush=True)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def b10_checks():
    """Настоящий zprobe_checks.py выпуска B10 из коммита выпуска (git show); сумма — по отпечаткам B10."""
    pins = dict(ln.split(' ', 1) for ln in open(os.path.join(REPO, 'zavod', 'ops', 'zprobe_pins_b10.txt'),
                                                encoding='utf-8').read().split('\n') if ln and not ln.startswith('#'))
    raw = subprocess.run(['git', '-C', REPO, 'show', f'{pins["release_commit"]}:zavod/ops/server/probes/zprobe_checks.py'],
                         capture_output=True, check=True).stdout
    m = types.ModuleType('zprobe_checks_b10')
    m.__file__ = 'zprobe_checks_b10.py'
    exec(compile(raw, 'zprobe_checks_b10.py', 'exec'), m.__dict__)
    return m, sha(raw) == pins['zprobe_checks.py']


def pinned_facts(**kw):
    """Факты остатка b9/pb1trial2 с перезапуском journald после T0 и шестью закреплёнными записями (как B03)."""
    f = TC.facts('b9')
    TC.alt(f, **kw)
    return f


class Pin:
    """Пробный PIN внутри блока: настоящего журнала сервера здесь нет (как в test_zprobe_checks.py)."""
    def __enter__(self):
        self.keep = (C.PIN_B9, C.PIN_SHA)
        C.PIN_B9, C.PIN_SHA = TEST_PIN, TEST_PIN_SHA

    def __exit__(self, *a):
        C.PIN_B9, C.PIN_SHA = self.keep


def run(P, db, facts, calls, ans='SEALED_NOW'):
    lid, man_raw, man, entries = R2.inputs(P)
    d = R2.deps(lid, man_raw, man, entries, P)
    d['collect'] = lambda: facts
    d['recheck_facts'] = lambda: {'svc': facts['svc'], 'mask': facts['mask']}
    d['select_row'] = lambda _lid: db.get('row')

    def call_seal(s, _l, h):
        calls.append(h)
        db['row'] = {'series': s, 'proof_sha256': h}
        return ans
    d['call_seal'] = call_seal
    return UN.seal_unstarted(R2.SERIES, lid, d)


def tree_listing(path):
    out = []
    for dp, dn, fn in sorted(os.walk(path)):
        out += [os.path.join(dp, n) for n in sorted(dn + fn)]
    return out


def main():
    b10, b10_sha_ok = b10_checks()
    case('R01_fixtures_and_b10_checks_are_the_real_files', TC.OK and b10_sha_ok and not hasattr(b10, 'PIN_B9')
         and R2.TOOL_VERSION == 'zprobe-r2-b11-0.1.checks-0.4' and len(R2.TOOL_VERSION) <= 40, (TC.OK, b10_sha_ok))
    with Pin():
        f = pinned_facts()
        r10, r11 = b10.evaluate(f), C.evaluate(f)
        v4, v5 = r11['checks']['H4']['value'], r11['checks']['H5']['value']
        case('R02_same_input_b10_blocked_h4_h5_b11_ok', r10['ok'] is False and r10['failed'] == H4H5
             and r11['ok'] is True and r11['failed'] == [] and sorted(r11['checks']) == sorted(C.CHECKS)
             and f'alt=R0V14 pin={TEST_PIN_SHA}' in v4 and f'al=6 un=0 alt=R0V14 pin={TEST_PIN_SHA}' in v5, (r10, v4, v5))
        fb = TC.facts('b10')
        TC.alt(fb)
        case('R03_other_formats_and_series_get_no_exception', C.evaluate(fb)['failed'] != []
             and C.evaluate(dict(pinned_facts(), series='pb1trial3'))['ok'] is False
             and C.evaluate(dict(pinned_facts(), fmt='b10'))['ok'] is False)
        case('R04_proof_values_carry_source_figures', all(k in v4 for k in ('gap=', 'verify=', 'loss=')) and all(
            k in v5 for k in ('n=', 'u=', 'st=', 'oth=6', 'al=6')), (v4, v5))
    if not ROOT:
        for n in ('R05_b10_blocked_nothing_written', 'R06_b11_seals_proof_with_basis_versions_hashes',
                  'R07_repeat_idempotent', 'R08_negative_blocked_without_seal', 'R09_service_active_blocked'):
            skip(n)
        print('ZPROBE_R2_B11_TEST=' + ('PASS_NO_ROOT' if OK else 'FAIL'))
        return 0 if OK else 1
    base = tempfile.mkdtemp(dir='/var/lib')
    os.chmod(base, 0o755)
    try:
        # --- B10 на тех же фактах: BLOCKED H4,H5, ничего не создано и не записано
        P, files = T2.mk(os.path.join(base, 'a'))
        os.chmod(P['seal'], 0o700)                  # пустая корневая папка seal root:root 0700 (как на сервере)
        home = os.path.join(P['preserve'], R2.SERIES)
        before_pres, db, calls = tree_listing(home), {}, []
        keep = (C.evaluate, C.h8_ok, C.h10_ok)
        with Pin():
            try:
                C.evaluate, C.h8_ok, C.h10_ok = b10.evaluate, b10.h8_ok, b10.h10_ok
                rb = run(P, db, pinned_facts(), calls)
            finally:
                C.evaluate, C.h8_ok, C.h10_ok = keep
        case('R05_b10_blocked_nothing_written', rb['status'] == 'BLOCKED_SESSION_UNKNOWN' and rb['failed'] == H4H5
             and rb['reason'] == 'checks' and rb['seal'] is None and calls == [] and db == {}
             and os.listdir(P['seal']) == [] and tree_listing(home) == before_pres, rb)
        # --- B11: печать, proof, повтор
        lid, man_raw, _man, _e = R2.inputs(P)
        with Pin():
            r1 = run(P, db, pinned_facts(), calls)
            a = os.path.join(P['seal'], R2.SERIES, '1')
            raw = open(os.path.join(a, 'proof.json'), 'rb').read()
            proof = json.loads(raw)
            srcs = {s['name']: s['sha256'] for s in proof['sources']}
            ck = proof['checks']
            case('R06_b11_seals_proof_with_basis_versions_hashes', r1['status'] == 'SAFE_PRE_START'
                 and r1['seal'] == 'SEALED_NOW' and r1['failed'] == []
                 and oct(os.stat(P['seal']).st_mode & 0o777) == '0o700'
                 and sorted(ck) == sorted(C.CHECKS) and all(ck[k]['ok'] is True for k in ck)
                 and f'alt=R0V14 pin={TEST_PIN_SHA}' in ck['H4']['value'] and 'alt=R0V14' in ck['H5']['value']
                 and proof['tool_version'] == R2.TOOL_VERSION
                 and proof['preserve_manifest_sha256'] == sha(man_raw)
                 and srcs['evidence.json'] == sha(files['evidence.json']) and srcs['state.json'] == sha(files['state.json'])
                 and srcs['anchor.json'] == sha(files['anchor.json']) and len(proof['inventory_sha256']) == 64
                 and calls == [sha(raw)] and db['row']['proof_sha256'] == sha(raw), (r1, ck['H4'], proof['tool_version']))
            snap = (raw, sorted(os.listdir(os.path.join(P['seal'], R2.SERIES))))
            r2 = run(P, db, pinned_facts(), calls, ans='ALREADY_SEALED')
            case('R07_repeat_idempotent', r2['status'] == 'SAFE_PRE_START' and r2['seal'] == 'ALREADY_SEALED'
                 and snap == (open(os.path.join(a, 'proof.json'), 'rb').read(), ['1'])
                 and sorted(os.listdir(os.path.join(P['seal'], R2.SERIES))) == ['1'] and calls == [sha(raw), sha(raw)],
                 (r2, calls))
        # --- отрицательные: BLOCKED без печати, без строки в БД, папка seal пуста
        neg, why = [], []
        gap = [e for e in TC.ENT if int(e['__SEQNUM']) != 1003]
        muts = (('journal_gap', lambda: pinned_facts(ents=gap)),
                ('seventh_record', lambda: pinned_facts(oe=TC.OED + [TC.oed(dict(TC.SELF[0], MESSAGE='x'))], other=7)),
                ('missing_record', lambda: pinned_facts(oe=TC.OED[:5], other=5)),
                ('foreign_uid', lambda: pinned_facts(oe=TC.OED[:2] + [TC.oed(dict(TC.SELF[2], _UID='1000'))] + TC.OED[3:])))
        for i, (tag, mk_facts) in enumerate(muts):
            Pn, _f = T2.mk(os.path.join(base, f'n{i}'))
            os.chmod(Pn['seal'], 0o700)
            dbn, cn = {}, []
            with Pin():
                rn = run(Pn, dbn, mk_facts(), cn)
            neg.append(rn['status'] == 'BLOCKED_SESSION_UNKNOWN' and rn['reason'] == 'checks' and rn['seal'] is None
                       and cn == [] and dbn == {} and os.listdir(Pn['seal']) == [])
            why.append((tag, rn['failed']))
        case('R08_negative_blocked_without_seal', all(neg), (neg, why))
        Ps, _f = T2.mk(os.path.join(base, 'svc'))
        os.chmod(Ps['seal'], 0o700)
        fs = None
        with Pin():
            fs = pinned_facts()
            fs['svc']['ActiveState'] = 'active'
            ds, cs = {}, []
            rs = run(Ps, ds, fs, cs)
        case('R09_service_active_blocked', rs['status'] == 'BLOCKED_SESSION_UNKNOWN' and 'H8' in rs['failed'] and cs == []
             and ds == {} and os.listdir(Ps['seal']) == [], rs)
    finally:
        pass
    print('ZPROBE_R2_B11_TEST=' + ('PASS' if OK else 'FAIL'))
    return 0 if OK else 1


if __name__ == '__main__':
    sys.exit(main())
