#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_r2_b11.py
# ВЕРСИЯ: v0.5 (выпуск B11)  СТАТУС: DRAFT
# v0.5 (2026-11-17 18:59 +02:00, Claude, терминал zavod; REL99 M-355-REL99-01): R01 — TOOL zprobe-r2-b11-0.3; R13 —
#   четвёртая строка R2_OBS_CHECK; R19–R23 — R2.main при УЖЕ существующей строке БД и proof (ветка повтора общего S.seal,
#   где сбор фактов не вызывается): R19 файл наблюдений на месте → ALREADY_SEALED и ровно один новый вызов печати; R20 файла
#   нет; R21 другие байты; R22 права 0644; R23 старый proof без obs= (файл на месте) — во всех четырёх REFUSED_INCONSISTENT /
#   BLOCKED_STOP_REVIEW, ни одного нового вызова печати, папка seal и файлы испытания не тронуты. Каждый случай — в новой
#   папке наблюдений (подстановка пути P['obs']); ничего не удаляется, не переименовывается и не перезаписывается.
# v0.4 (2026-11-17 18:22 +02:00, Claude, терминал zavod (58f8b71b); REL98 M-355-REL98-01): R01 — TOOL zprobe-r2-b11-0.2;
#   R13 — третья строка R2_OBS_FILE; R14 (файл наблюдений есть уже в момент вызова печати, байты = R2_OBS, имя и сумма = obs=
#   в proof, root 0600; и при отказе), R15 (stdout оборван после печати — proof, строка БД и файл наблюдений целы и связаны),
#   R16 (папка наблюдений небезопасна — COLLECT, печати нет), R17 (файл с тем же именем и другими байтами — COLLECT, байты
#   не тронуты, печати нет), R18 (тот же файл с теми же байтами — принят, печать есть). Папки — только новые; ничего не
#   удаляется, не переименовывается и не перезаписывается.
# v0.3 (2026-11-17 17:33 +02:00, Claude, терминал zavod): R-проверки под checks-0.6 (PIN_B9 со значениями D14).
# v0.2 (2026-11-17 07:51 +02:00, Claude, терминал zavod, помощник; REL97): R01–R04 под checks-0.5 и раскладку obs/pin/bd/sd;
#   R10 (obs в proof = SHA-256 строки R2_OBS, pin от наблюдений не зависит), R11 (другая аренда при том же T0 — BLOCKED без
#   печати), R12 (other=0 при H4 alt — BLOCKED H5 без печати), R13 (main(): строка R2_OBS и при отказе, и после печати).
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
         and R2.TOOL_VERSION == 'zprobe-r2-b11-0.3.checks-0.6' and len(R2.TOOL_VERSION) <= 40, (TC.OK, b10_sha_ok))
    with Pin():
        f = pinned_facts()
        r10, r11 = b10.evaluate(f), C.evaluate(f)
        v4, v5 = r11['checks']['H4']['value'], r11['checks']['H5']['value']
        case('R02_same_input_b10_blocked_h4_h5_b11_ok', r10['ok'] is False and r10['failed'] == H4H5
             and r11['ok'] is True and r11['failed'] == [] and sorted(r11['checks']) == sorted(C.CHECKS)
             and f' alt=R0V14 obs={C.obs_sha(f)} pin={TEST_PIN_SHA} bd=' in v4
             and f' OK alt=R0V14 obs={C.obs_sha(f)} pin={TEST_PIN_SHA} sd=' in v5, (r10, v4, v5))
        fb = TC.facts('b10')
        TC.alt(fb)
        case('R03_other_formats_and_series_get_no_exception', C.evaluate(fb)['failed'] != []
             and C.evaluate(dict(pinned_facts(), series='pb1trial3'))['ok'] is False
             and C.evaluate(dict(pinned_facts(), fmt='b10'))['ok'] is False)
        case('R04_proof_values_carry_source_figures', all(k in v4 for k in ('gap=', 'verify=', 'loss=')) and all(
            k in v5 for k in ('n=', 'u=', 'oth=6', 'obs=', 'sd=')), (v4, v5))
        ol = R2.obs_line(f)
        oj = ol.split(' ', 1)[1]
        kv = dict(x.split('=', 1) for x in v4.split(' ') if '=' in x)
        f2 = pinned_facts()
        f2['scan']['n'] += 1
        f3 = pinned_facts()
        f3['journald_restart']['rx'] = 2
        case('R10_obs_in_proof_value_is_sha256_of_r2_obs_line_pin_independent',
             ol.startswith('R2_OBS {') and '\n' not in ol and kv['obs'] == sha(oj.encode()) != kv['pin'] == TEST_PIN_SHA
             and json.loads(oj)['seq'] == f['scan']['seq'] and json.loads(oj)['jd']['main_pid'] == '4242'
             and json.loads(oj)['bd'] == TEST_PIN['bd'] and json.loads(oj)['sd'] == TEST_PIN['sd']
             and sha(R2.obs_line(f2).split(' ', 1)[1].encode()) != kv['obs'] and R2.obs_line(f3) != ol
             and C.evaluate(f2)['checks']['H4']['value'].split(' pin=')[1][:64] == TEST_PIN_SHA
             and R2.obs_line(None) == 'R2_OBS null', (ol[:80], kv))
    if not ROOT:
        for n in ('R05_b10_blocked_nothing_written', 'R06_b11_seals_proof_with_basis_versions_hashes',
                  'R07_repeat_idempotent', 'R08_negative_blocked_without_seal', 'R09_service_active_blocked',
                  'R11_other_lease_same_t0_blocked_nothing_written', 'R12_other_zero_with_h4_alt_blocked_nothing_written',
                  'R13_main_prints_r2_obs_after_seal_and_on_refusal', 'R14_obs_file_written_before_seal_and_linked',
                  'R15_stdout_broken_after_seal_evidence_kept', 'R16_unsafe_obs_dir_blocks_seal',
                  'R17_obs_name_with_other_bytes_blocks_seal_not_overwritten', 'R18_same_obs_file_accepted',
                  'R19_retry_with_obs_file_already_sealed', 'R20_retry_obs_file_missing_no_seal_call',
                  'R21_retry_obs_other_bytes_no_seal_call', 'R22_retry_obs_wrong_mode_no_seal_call',
                  'R23_retry_old_proof_without_obs_no_seal_call'):
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
             and rb['reason'] == 'checks' and rb['seal'] == 'BLOCKED_SESSION_UNKNOWN' and rb.get('k') is None and rb.get('sha') is None and calls == [] and db == {}
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
                 and f' pin={TEST_PIN_SHA} ' in ck['H4']['value'] and 'alt=R0V14' in ck['H5']['value']
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
            neg.append(rn['status'] == 'BLOCKED_SESSION_UNKNOWN' and rn['reason'] == 'checks' and rn['seal'] == 'BLOCKED_SESSION_UNKNOWN' and rn.get('sha') is None
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
        # --- REL97: другая аренда при том же T0 и other=0 при H4 alt — BLOCKED, ничего не записано
        def blocked_case(tag, mk_facts):
            Pn, _f = T2.mk(os.path.join(base, tag))
            os.chmod(Pn['seal'], 0o700)
            homen = os.path.join(Pn['preserve'], R2.SERIES)
            before, dbn, cn = tree_listing(homen), {}, []
            with Pin():
                rn = run(Pn, dbn, mk_facts(), cn)
            return rn, (cn == [] and dbn == {} and os.listdir(Pn['seal']) == [] and tree_listing(homen) == before)
        lid2 = '11111111-1111-4111-8111-111111111111'
        rl, okl = blocked_case('lid2', lambda: json.loads(json.dumps(pinned_facts()).replace(TC.LID, lid2).replace(
            TC.L, lid2.replace('-', ''))))
        case('R11_other_lease_same_t0_blocked_nothing_written', rl['status'] == 'BLOCKED_SESSION_UNKNOWN'
             and rl['failed'] == H4H5 and rl['reason'] == 'checks' and rl.get('sha') is None and okl, (rl, okl))
        rz, okz = blocked_case('zero', lambda: pinned_facts(oe=[], other=0))
        case('R12_other_zero_with_h4_alt_blocked_nothing_written', rz['status'] == 'BLOCKED_SESSION_UNKNOWN'
             and rz['failed'] == ['H5'] and rz['reason'] == 'checks' and rz.get('sha') is None and okz, (rz, okz))

        # --- main(): строка R2_OBS после печати и при отказе; obs в proof = SHA-256 её json
        def obs_dir(Px):
            return os.path.join(Px['obs'], R2.SERIES)

        def obs_now(Px):
            return sorted(os.listdir(obs_dir(Px))) if os.path.isdir(obs_dir(Px)) else None

        def main_r2(Pm, facts, dbm, cm, seen=None, out=None, ans='SEALED_NOW'):
            keep = (C.collect, C.svc_mask, UN.select_seal, UN.call_seal)

            def cs(series, _lid, h, *a, **k):
                if seen is not None:
                    seen.append(obs_now(Pm))       # что лежит в папке наблюдений в момент вызова печати
                cm.append(h)
                dbm['row'] = {'series': series, 'proof_sha256': h}
                return ans
            C.collect = lambda fmt, series, lid, src: facts
            C.svc_mask = lambda unit: {'svc': facts['svc'], 'mask': facts['mask']}
            UN.select_seal, UN.call_seal = (lambda _lid: dbm.get('row')), cs
            buf = out if out is not None else io.StringIO()
            try:
                with Pin(), contextlib.redirect_stdout(buf):
                    rc = R2.main(['zprobe_r2.py', R2.SERIES], Pm)
            finally:
                C.collect, C.svc_mask, UN.select_seal, UN.call_seal = keep
            return rc, (buf.getvalue().split('\n') if out is None else [])

        def mk_obs(tag):
            Px, _fx = T2.mk(os.path.join(base, tag))
            os.chmod(Px['seal'], 0o700)
            Px['obs'] = os.path.join(base, tag, 'r2obs')      # новая папка испытания; R2 создаёт её сам
            return Px
        Pm = mk_obs('m1')
        fm = pinned_facts()
        dm, cm = {}, []
        seen1 = []
        rc1, out1 = main_r2(Pm, fm, dm, cm, seen1)
        pm = json.loads(open(os.path.join(Pm['seal'], R2.SERIES, '1', 'proof.json'), 'rb').read())
        Pr = mk_obs('m2')
        fr_ = pinned_facts(oe=[], other=0)
        rc2, out2 = main_r2(Pr, fr_, {}, [])
        obs_m = pm['checks']['H4']['value'].split(' obs=')[1][:64]
        with Pin():                         # bd/sd наблюдений считаются по действующему PIN, как внутри main()
            ol1, ol2 = R2.obs_line(fm), R2.obs_line(fr_)
        parts = (rc1 == 0, out1[0].startswith('R2=SEALED_NOW status=SAFE_PRE_START'), out1[1].startswith('R2_OBS {'),
                 sha(out1[1].split(' ', 1)[1].encode()) == obs_m,
                 obs_m == pm['checks']['H5']['value'].split(' obs=')[1][:64], out1[1] == ol1,
                 rc2 == 1, out2[0].startswith('R2=BLOCKED_SESSION_UNKNOWN'), out2[1] == ol2,
                 os.listdir(Pr['seal']) == [], json.loads(out2[1].split(' ', 1)[1])['other_n'] == 0,
                 out1[3] == f'R2_OBS_CHECK ok {obs_m}', out2[3] == 'R2_OBS_CHECK -')
        case('R13_main_prints_r2_obs_after_seal_and_on_refusal', all(parts), (parts, rc2, out2[0][:120]))

        # --- REL98 M-01: файл наблюдений до печати, связь с proof, обрыв stdout, отказы записи
        def obs_file_ok(Px, line_obs, line_file, h):
            p = os.path.join(obs_dir(Px), f'obs-{h}.json')
            st = os.lstat(p)
            raw_o = open(p, 'rb').read()
            return (line_file == f'R2_OBS_FILE {p} sha={h}' and raw_o == line_obs.split(' ', 1)[1].encode()
                    and sha(raw_o) == h and (st.st_uid, st.st_gid, st.st_mode & 0o777) == (0, 0, 0o600)
                    and os.listdir(obs_dir(Px)) == [f'obs-{h}.json']
                    and (os.stat(obs_dir(Px)).st_mode & 0o777, os.stat(Px['obs']).st_mode & 0o777) == (0o700, 0o700))
        h2 = sha(out2[1].split(' ', 1)[1].encode())
        parts14 = (seen1 == [[f'obs-{obs_m}.json']], obs_file_ok(Pm, out1[1], out1[2], obs_m),
                   obs_file_ok(Pr, out2[1], out2[2], h2), h2 != obs_m)
        case('R14_obs_file_written_before_seal_and_linked', all(parts14), (parts14, seen1, out1[2:3], out2[2:3]))

        class Broken(io.StringIO):
            def write(self, _s):
                raise BrokenPipeError(32, 'stdout closed')
        Pb = mk_obs('m3')
        db_b, c_b, seen_b, exc = {}, [], [], None
        try:
            main_r2(Pb, pinned_facts(), db_b, c_b, seen_b, Broken())
        except BrokenPipeError as e:
            exc = e
        pb_raw = open(os.path.join(Pb['seal'], R2.SERIES, '1', 'proof.json'), 'rb').read()
        obs_b = json.loads(pb_raw)['checks']['H4']['value'].split(' obs=')[1][:64]
        fb_path = os.path.join(obs_dir(Pb), f'obs-{obs_b}.json')
        parts15 = (exc is not None, c_b == [sha(pb_raw)], db_b.get('row', {}).get('proof_sha256') == sha(pb_raw),
                   seen_b == [[f'obs-{obs_b}.json']], os.path.isfile(fb_path) and sha(open(fb_path, 'rb').read()) == obs_b)
        case('R15_stdout_broken_after_seal_evidence_kept', all(parts15), parts15)

        Pu = mk_obs('m4')
        loose = os.path.join(base, 'm4', 'loose')
        os.mkdir(loose)
        os.chmod(loose, 0o777)                              # группа и все могут писать — небезопасно
        Pu['obs'] = os.path.join(loose, 'r2obs')
        du, cu = {}, []
        rcu, outu = main_r2(Pu, pinned_facts(), du, cu)
        case('R16_unsafe_obs_dir_blocks_seal', rcu == 1 and outu[0].startswith('R2=BLOCKED_SESSION_UNKNOWN')
             and 'failed=COLLECT' in outu[0] and outu[2] == 'R2_OBS_FILE - sha=-' and cu == [] and du == {}
             and os.listdir(Pu['seal']) == [] and os.listdir(loose) == [], (rcu, outu[:3]))

        def pre_obs(Px, data, h):
            os.mkdir(Px['obs'], 0o700)
            os.mkdir(obs_dir(Px), 0o700)
            fd = os.open(os.path.join(obs_dir(Px), f'obs-{h}.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.write(fd, data)
            os.close(fd)
            return os.path.join(obs_dir(Px), f'obs-{h}.json')
        with Pin():
            oj7 = R2.obs_line(pinned_facts()).split(' ', 1)[1].encode()
        P7 = mk_obs('m5')
        f7 = pre_obs(P7, b'{"other":1}', sha(oj7))
        st7 = os.lstat(f7)
        d7, c7 = {}, []
        rc7, out7 = main_r2(P7, pinned_facts(), d7, c7)
        st7b = os.lstat(f7)
        case('R17_obs_name_with_other_bytes_blocks_seal_not_overwritten', rc7 == 1 and 'failed=COLLECT' in out7[0]
             and open(f7, 'rb').read() == b'{"other":1}' and (st7.st_ino, st7.st_mtime_ns) == (st7b.st_ino, st7b.st_mtime_ns)
             and c7 == [] and d7 == {} and os.listdir(P7['seal']) == [], (rc7, out7[:3]))
        P8 = mk_obs('m6')
        f8 = pre_obs(P8, oj7, sha(oj7))
        st8 = os.lstat(f8)
        d8, c8 = {}, []
        rc8, out8 = main_r2(P8, pinned_facts(), d8, c8)
        st8b = os.lstat(f8)
        case('R18_same_obs_file_accepted', rc8 == 0 and out8[0].startswith('R2=SEALED_NOW status=SAFE_PRE_START')
             and out8[2] == f'R2_OBS_FILE {f8} sha={sha(oj7)}'
             and (st8.st_ino, st8.st_mtime_ns) == (st8b.st_ino, st8b.st_mtime_ns) and len(c8) == 1, (rc8, out8[:3]))

        # --- REL99 M-01: повтор при уже существующей строке БД и proof — файл наблюдений проверяется ДО вызова печати
        def state(Px, paths):
            seal_tree = [(q, open(q, 'rb').read() if os.path.isfile(q) else None) for q in tree_listing(Px['seal'])]
            files_ = [(q, os.lstat(q).st_ino, os.lstat(q).st_mtime_ns, os.lstat(q).st_mode, open(q, 'rb').read())
                      for q in paths]
            return seal_tree, files_
        Pa = mk_obs('r1')
        da, ca = {}, []
        rca0, outa0 = main_r2(Pa, pinned_facts(), da, ca)
        ha = outa0[2].split(' sha=')[1]
        good_a = os.path.join(obs_dir(Pa), f'obs-{ha}.json')

        def retry_refused(Px, dbx, cx, paths):
            n0, st0 = len(cx), state(Px, paths)
            rcx, outx = main_r2(Px, pinned_facts(), dbx, cx, ans='ALREADY_SEALED')
            return (rcx == 1, outx[0].startswith('R2=REFUSED_INCONSISTENT status=BLOCKED_STOP_REVIEW'),
                    ' reason=obs:' in outx[0], outx[1] == 'R2_OBS null', outx[3].startswith('R2_OBS_CHECK refused:'),
                    len(cx) == n0, state(Px, paths) == st0), outx[:4]

        def other_obs(tag):
            Px = dict(Pa)
            Px['obs'] = os.path.join(base, tag)          # новая папка наблюдений, старая (с верным файлом) не трогается
            return Px
        Pb2 = other_obs('r2obs_missing')
        os.mkdir(Pb2['obs'], 0o700)
        os.mkdir(obs_dir(Pb2), 0o700)
        p20, o20 = retry_refused(Pb2, da, ca, [good_a])
        case('R20_retry_obs_file_missing_no_seal_call', all(p20) and 'missing:' in o20[0]
             and os.listdir(obs_dir(Pb2)) == [], (p20, o20))
        Pc2 = other_obs('r2obs_bytes')
        fc2 = pre_obs(Pc2, b'{"other":2}', ha)
        p21, o21 = retry_refused(Pc2, da, ca, [good_a, fc2])
        case('R21_retry_obs_other_bytes_no_seal_call', all(p21) and 'obs_sha' in o21[0], (p21, o21))
        with open(good_a, 'rb') as fh:
            good_bytes = fh.read()
        Pd2 = other_obs('r2obs_mode')
        fd2 = pre_obs(Pd2, good_bytes, ha)
        os.chmod(fd2, 0o644)
        p22, o22 = retry_refused(Pd2, da, ca, [good_a, fd2])
        case('R22_retry_obs_wrong_mode_no_seal_call', all(p22) and 'file_mode' in o22[0], (p22, o22))
        n19 = len(ca)
        rc19, out19 = main_r2(Pa, pinned_facts(), da, ca, ans='ALREADY_SEALED')
        case('R19_retry_with_obs_file_already_sealed', rca0 == 0 and rc19 == 0
             and out19[0].startswith('R2=ALREADY_SEALED status=SAFE_PRE_START') and ' reason=retry' in out19[0]
             and out19[1] == 'R2_OBS null' and out19[2] == f'R2_OBS_FILE {good_a} sha={ha}'
             and out19[3] == f'R2_OBS_CHECK ok {ha}' and len(ca) == n19 + 1 == 2 and ca[0] == ca[1]
             and sorted(os.listdir(os.path.join(Pa['seal'], R2.SERIES))) == ['1'], (rc19, out19[:4], ca))
        Pe = mk_obs('r5')
        de, ce = {}, []
        ev_keep = C.evaluate

        def ev_old(f):                                     # proof прежнего вида: в H4/H5 нет токена obs=
            res = ev_keep(f)
            for k in ('H4', 'H5'):
                if k in res.get('checks', {}):
                    res['checks'][k]['value'] = R2.OBS_TOKEN.sub('', res['checks'][k]['value'])
            return res
        with Pin():
            try:
                C.evaluate = ev_old
                re0 = run(Pe, de, pinned_facts(), ce)
            finally:
                C.evaluate = ev_keep
        pe_raw = open(os.path.join(Pe['seal'], R2.SERIES, '1', 'proof.json'), 'rb').read()
        fe = pre_obs(Pe, oj7, sha(oj7))                     # верный файл наблюдений на месте — не хватает только токена
        p23, o23 = retry_refused(Pe, de, ce, [fe])
        case('R23_retry_old_proof_without_obs_no_seal_call', re0['status'] == 'SAFE_PRE_START'
             and ce[:1] == [sha(pe_raw)] and b'obs=' not in pe_raw and all(p23) and 'obs_token' in o23[0],
             (re0.get('status'), p23, o23))
    finally:
        pass
    print('ZPROBE_R2_B11_TEST=' + ('PASS' if OK else 'FAIL'))
    return 0 if OK else 1


if __name__ == '__main__':
    sys.exit(main())
