#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_verify_export.py (программа ПК, версия 1)
# ВЕРСИЯ: v0.2 (выпуск B10)  СТАТУС: DRAFT
# v0.2 (2026-11-15, терминал zavod, чат cb6b67c5; REL65 M-05): архив читается потоком, пределы числа файлов,
#   размера каждого, суммы и глубины проверяются до чтения файла.
# ДАТА СОЗДАНИЯ: 2026-11-15 00:00 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 5 п.5 — проверка очищенного пакета на ПК (архив tar от zevidence-send).
#   Инварианты а–е; итог — первый подходящий из FAIL > INCOMPLETE > UNSEALED > PASS_SANITIZED. Таблицы и
#   разборщики — те же, что у сервера (zprobe_export_rules.py, zprobe_seal.py, zprobe_rules.py).
# ВЫЗОВ: python -I zprobe_verify_export.py <архив.tar> <серия> [--seal-sha <hex строки lease_seal с телефона>]
#        [--state <файл истории ПК>]
#   Файл истории — JSON {серия: {"n": .., "journal_last_seq": ..}}; меньшее значение → FAIL (откат). Обновляется
#   только при итоге не FAIL.
# ЧЕСТНАЯ ГРАНИЦА (пишется в отчёт): PASS_SANITIZED — полная внутренняя согласованность описи, proof и выгрузки;
#   что опись перечисляет всё, что было в папке сервера, ПК доказать не может (это утверждение root). Суммы HASH_ONLY
#   и строка телефона приходят от того же сервера.
import hashlib
import json
import os
import re
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_export_rules as E  # noqa: E402
import zprobe_seal as S  # noqa: E402

BOUNDARY = ('Честная граница: PASS_SANITIZED — полная внутренняя согласованность описи и выгрузки, '
            'а не независимое чтение папки сервера; суммы HASH_ONLY и строка телефона — от того же сервера.')
RANK = ('FAIL', 'INCOMPLETE', 'UNSEALED', 'PASS_SANITIZED')


class Fail(Exception):
    pass


def limit_of(rel):
    """Предел одного файла пакета: MANIFEST — 1 МБ, READY — 128 байт, остальные — E.MAX_FILE (256 КБ)."""
    return {'MANIFEST.sha256': 1 << 20, 'READY': 128}.get(rel, E.MAX_FILE)


TOTAL_CAP = E.MAX_TOTAL                       # сумма файлов пакета кроме MANIFEST и READY ≤ 2 МБ
MAX_DEPTH = 3                                 # sealed/source/<имя> — глубже в пакете ничего нет


def read_tar(path, series):
    """а) архив: только папки и обычные файлы под <серия>/<n>/, без «..», ссылок и повторов. → (n, {путь: байты}).
    Пределы (REL65 M-05) — ДО чтения каждого файла и потоком, без getmembers целиком: ≤ E.MAX_FILES файлов,
    каждый ≤ своего предела, сумма ≤ TOTAL_CAP, глубина ≤ MAX_DEPTH; иначе FAIL."""
    files, n, total = {}, None, 0
    with tarfile.open(path, mode='r:') as tf:
        for m in tf:
            parts = m.name.split('/')
            if len(parts) < 2 or parts[0] != series or not re.fullmatch(r'[1-9][0-9]{0,3}', parts[1]) \
                    or any(p in ('', '.', '..') for p in parts):
                raise Fail(f'tar:name:{m.name}')
            if n is None:
                n = int(parts[1])
            elif int(parts[1]) != n:
                raise Fail('tar:two_roots')
            if m.isdir():
                continue
            if not m.isreg():
                raise Fail(f'tar:type:{m.name}')
            rel = '/'.join(parts[2:])
            if rel in files:
                raise Fail(f'tar:duplicate:{rel}')
            total += 0 if rel in ('MANIFEST.sha256', 'READY') else m.size
            if len(parts) - 2 > MAX_DEPTH or len(files) + 1 > E.MAX_FILES or m.size > limit_of(rel) \
                    or total > TOTAL_CAP:
                raise Fail(f'tar:limits:{rel}')
            data = tf.extractfile(m).read(m.size + 1)
            if len(data) != m.size:
                raise Fail(f'tar:size:{rel}')
            files[rel] = data
    if n is None:
        raise Fail('tar:empty')
    return n, files


def verify(n, files, series, seal_sha=None, history=None):
    """→ (итог, причины, предупреждения, HASH_ONLY-строки)."""
    warn, why = [], []
    try:
        man, ready = files.get('MANIFEST.sha256'), files.get('READY')
        if man is None or ready != (hashlib.sha256(man).hexdigest() + '\n').encode('ascii'):
            raise Fail('a:READY')
        rows = E.parse_manifest(man)
        phys = {f'{p}/{nm}': (o, osz) for m, p, nm, r, rsz, o, osz in rows if m != 'HASH_ONLY'}
        if set(files) != set(phys) | {'MANIFEST.sha256', 'READY'}:
            raise Fail('a:set')
        for path, (o, osz) in phys.items():
            if len(files[path]) != osz or hashlib.sha256(files[path]).hexdigest() != o:
                raise Fail(f'a:out:{path}')
        braw = files.get('package/bundle.json')
        if braw is None:
            raise Fail('e:bundle')
        try:
            b = json.loads(braw)
        except ValueError:
            raise Fail('e:bundle_json')
        if S.canon(b) != braw:
            raise Fail('e:bundle_canon')
        E.check_bundle(b)
        fmt = E.fmt_of(b['matrix'])
        if b['n'] != n or b['series'] != series:
            raise Fail('v:bundle_n_series')
        if history and (n < history.get('n', 0) or (b['journal_last_seq'] is not None and
                                                     b['journal_last_seq'] < history.get('journal_last_seq', 0))):
            raise Fail('v:rollback')
        lid = b['lease_id']
        for m, p, nm, *_ in rows:
            if not E.place_mode_ok(fmt, p, nm, m, b['journal_mode']):
                raise Fail(f'd:mode:{p}/{nm}')
        docs = {'sealed/source': {}, 'final': {}}
        for m, p, nm, *_ in rows:
            if m == 'ALLOW':
                docs[p][nm] = E.check_sanitized(fmt, nm, files[f'{p}/{nm}'])
        names = {p: {nm for m, pp, nm, *_ in rows if pp == p} for p in E.PLACES}
        result = 'PASS_SANITIZED'
        for nm in E.required(fmt, 'final'):
            if nm not in names['final']:
                why.append(f'final_required_absent:{nm}')
                result = 'INCOMPLETE'
        for nm, row in E.NAMES.items():
            if row[1] == 'ALLOW' and E.need(fmt, 'final', nm) == 'opt' and nm not in names['final']:
                warn.append(f'FINAL_OPTIONAL_ABSENT {nm}')
        for place in ('sealed/source', 'final'):
            bad = E.links_problem(fmt, series, lid, docs[place], b)
            if bad:
                raise Fail(f'v:link:{place}:{bad}')
        seal = b['seal']
        proof = None
        if seal is None:
            if names['sealed/source'] or names['sealed/meta'] or names['proof']:
                raise Fail('e:unsealed_has_sealed')
            if result == 'PASS_SANITIZED':
                result = 'UNSEALED'
        else:
            if seal_sha is not None and seal_sha != seal['proof_sha256']:
                raise Fail('e:phone_seal_sha')
            raw = files.get('proof/proof.json')
            if raw is None or hashlib.sha256(raw).hexdigest() != seal['proof_sha256']:
                raise Fail('e:proof')
            logical = sorted(names['sealed/source'])
            try:
                proof = S.check_proof(raw, series, lid, logical)
            except S.Refused as e:
                raise Fail(f'v:proof:{e}')
            want_meta = {'INVENTORY.sha256', 'MANIFEST.sha256'} if fmt == 'B9R2' else {'INVENTORY.sha256'}
            if names['sealed/meta'] != want_meta:
                raise Fail('e:meta')
            for nm in E.required(fmt, 'source'):
                if nm not in names['sealed/source']:
                    raise Fail(f'e:source_required:{nm}')
            inv_raw = files['sealed/meta/INVENTORY.sha256']
            if hashlib.sha256(inv_raw).hexdigest() != proof['inventory_sha256']:
                raise Fail('v:inventory_sha')
            try:
                inv = S.parse_inventory(inv_raw)
            except S.Refused as e:
                raise Fail(f'v:inventory:{e}')
            man_a = None
            if fmt == 'B9R2':
                mraw = files['sealed/meta/MANIFEST.sha256']
                if hashlib.sha256(mraw).hexdigest() != proof['preserve_manifest_sha256']:
                    raise Fail('v:manifest_a_sha')
                man_a = E.parse_manifest_a(mraw, series, lid.replace('-', ''))
                if sorted(man_a) != logical:
                    raise Fail('v:manifest_a_names')
            if sorted(inv) != logical:
                raise Fail('v:inventory_names')
            bad = E.inventory_b_problem(fmt, series, inv_raw, man_a)
            if bad:
                raise Fail(f'v:{bad}')
            raw_of = {nm: (r, rsz) for m, p, nm, r, rsz, *_ in rows if p == 'sealed/source'}
            for s in proof['sources']:
                if inv[s['name']] != (s['sha256'], s['size']) or raw_of[s['name']] != (s['sha256'], s['size']):
                    raise Fail(f'v:source:{s["name"]}')
            if b['journal_cursor'] != proof['journal_to_cursor']:
                raise Fail('v:journal_cursor')
        anc = docs['sealed/source'].get('anchor_run.json' if fmt == 'B10' else 'anchor.json') \
            or docs['final'].get('anchor_run.json')
        if anc is not None:
            if not (anc['boot_id'] == b['b_probe'] == b['boot_id']):
                raise Fail('v:boot_id')
            curs = [anc['cursor']] if fmt == 'B10' else [anc['cursor_before'], anc['cursor_after']]
            if proof is not None:
                bad = E.cursors_problem(proof, curs, b['b_probe'])
                if bad:
                    raise Fail(f'v:{bad}')
        elif proof is not None and proof['boot_id'] != b['b_probe']:
            raise Fail('v:b_probe')
        segs = sorted(nm for nm in names['journal'])
        if segs != ['%06d.jsonl' % i for i in range(1, b['journal_segments'] + 1)]:
            raise Fail('g:segments')
        if b['journal_mode'] == 'FULL_RAW':
            got = E.journal_mode([(nm, files[f'journal/{nm}']) for nm in segs])
            if got != ('FULL_RAW', b['journal_last_seq'], b['journal_last_sha256']):
                raise Fail('g:chain')
        else:
            why.append('journal_partial_hash_only')
            if result in ('PASS_SANITIZED', 'UNSEALED'):
                result = 'INCOMPLETE'
    except Fail as e:
        return 'FAIL', [str(e)], warn, []
    except E.Refused as e:
        return 'FAIL', [f'refused:{e}'], warn, []
    except (KeyError, TypeError, ValueError) as e:
        return 'FAIL', [f'{type(e).__name__}:{e}'], warn, []
    hashes = [f'{p}/{nm} {r} {rsz}' for m, p, nm, r, rsz, *_ in rows if m == 'HASH_ONLY']
    return result, why, warn, hashes


def main(argv):
    args, opts = [], {}
    it = iter(argv[1:])
    for a in it:
        if a in ('--seal-sha', '--state'):
            opts[a] = next(it, None)
        else:
            args.append(a)
    if len(args) != 2 or not E.SERIES.fullmatch(args[1]) or None in opts.values():
        print('usage: zprobe_verify_export.py <archive.tar> <series> [--seal-sha HEX] [--state FILE]')
        return 2
    series = args[1]
    hist_all = {}
    if '--state' in opts and os.path.exists(opts['--state']):
        with open(opts['--state'], encoding='utf-8') as f:
            hist_all = json.load(f)
    try:
        n, files = read_tar(args[0], series)
        res, why, warn, hashes = verify(n, files, series, opts.get('--seal-sha'), hist_all.get(series))
    except (Fail, tarfile.TarError, OSError) as e:
        n, res, why, warn, hashes = None, 'FAIL', [str(e)], [], []
    print(f'ZPROBE_VERIFY_EXPORT={res} series={series} n={n}')
    for w in why:
        print(f'REASON {w}')
    for w in warn:
        print(w)
    for h in hashes:
        print(f'HASH_ONLY {h}')
    print(BOUNDARY)
    if res != 'FAIL' and '--state' in opts:
        b = json.loads(files['package/bundle.json'])
        hist_all[series] = {'n': n, 'journal_last_seq': b['journal_last_seq'] or
                            hist_all.get(series, {}).get('journal_last_seq', 0)}
        tmp = opts['--state'] + '.tmp'
        with open(tmp, 'x', encoding='utf-8') as f:
            json.dump(hist_all, f, sort_keys=True)
        os.replace(tmp, opts['--state'])
    return {'PASS_SANITIZED': 0, 'UNSEALED': 10, 'INCOMPLETE': 11}.get(res, 1)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
