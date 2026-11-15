#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_export.py
# ВЕРСИЯ: v0.2 (выпуск B10)  СТАТУС: DRAFT
# v0.2 (2026-11-15, терминал zavod, чат cb6b67c5; REL65 M-04): перед сборкой final/ папка источника серии
#   перечисляется целиком; имя вне таблицы своего формата (кроме MANIFEST.sha256 у B9 preserve) или не обычный
#   файл → EXPORT_REFUSED final/<имя>:unknown (на ПК — FAIL).
# ДАТА СОЗДАНИЯ: 2026-11-14 23:59 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 5 п.1 — `zprobe-export <серия>` (от root): новая папка
#   /var/lib/zavod/export/<серия>/<n>/ эксклюзивно (n = наибольший + 1; занято — STOP, ничего не заменяется),
#   пакет строится заново по таблицам zprobe_export_rules.py; всё нераспознанное — EXPORT_REFUSED <файл>:<поле>
#   и частичного пакета нет (сбой после mkdir оставляет папку без READY, как есть; повтор — новой папкой n+1).
#   Порядок сборки п.1е: sealed/source и sealed/meta (снимок выбранной попытки) → final/ → proof/ → journal/ →
#   package/bundle.json → MANIFEST.sha256 → fsync → READY (SHA-256 MANIFEST) последним. Права: папки root:zevid
#   0750, файлы root:zevid 0640. Сырого systemctl show нет.
# ВЫХОД: 0 и строка `ZPROBE_EXPORT_OK series=<S> n=<n> manifest_sha256=<hex> seal=<yes|no> journal=<режим>`;
#   2 и `EXPORT_REFUSED <файл>:<поле>`; 3 — `EXPORT_STOP <причина>` (папка занята, сбой записи).
# ДОПУЩЕНИЯ (на аудит): 1) серия pb1trial2 — формат B9R2, иная — B10; 2) lease_id берётся из state.json места
#   «файл серии» (B9R2 — preserve/pb1trial2, B10 — /run/zprobe/<S>) и проверяется связями; 3) b_probe без печати —
#   boot_id якоря (B10 — final anchor_run.json, B9R2 — preserve anchor.json); 4) обязательная строка sealed/source,
#   которой нет при печати, — EXPORT_REFUSED (на ПК это FAIL); 5) final/ читается по имени из таблицы (папка серии
#   не перечисляется), archive/<S> перечисляется целиком.

import hashlib
import json
import os
import re
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_export_rules as E  # noqa: E402
import zprobe_seal as S  # noqa: E402

PATHS = {'run': '/run/zprobe', 'preserve': '/var/lib/zavod/preserve', 'seal': '/var/lib/zavod/seal',
         'export': '/var/lib/zavod/export', 'archive': '/var/lib/zavod/probes/archive',
         'started': '/var/lib/zavod/probes/started', 'journal': '/var/lib/zavod/probes/journal'}
N_RE = re.compile(r'[1-9][0-9]{0,3}')
Refused = E.Refused


class Stop(Exception):
    pass


def fmt_for(series):
    return 'B9R2' if series == 'pb1trial2' else 'B10'


def walk_dir(path):
    """Каталог по дескриптору: каждый шаг от / без ссылок (O_NOFOLLOW). Нет — None."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in [p for p in path.split('/') if p]:
            nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = nfd
    except FileNotFoundError:
        os.close(fd)
        return None
    except OSError:
        os.close(fd)
        raise Refused(f'{path}:dir')
    return fd


def read_at(dir_fd, name, limit=E.MAX_FILE, label=None):
    """Обычный файл без ссылок, не больше limit. Нет — None; иное — Refused."""
    label = label or name
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=dir_fd)
    except FileNotFoundError:
        return None
    except OSError:
        raise Refused(f'{label}:open')
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            raise Refused(f'{label}:file')
        got = b''
        while len(got) <= limit:
            part = os.read(fd, 65536)
            if not part:
                break
            got += part
    finally:
        os.close(fd)
    if len(got) > limit:
        raise Refused(f'{label}:size')
    return got


def read_path(dirpath, name, limit=E.MAX_FILE, label=None):
    fd = walk_dir(dirpath)
    if fd is None:
        return None
    try:
        return read_at(fd, name, limit, label)
    finally:
        os.close(fd)


def add(rows, mode, place, name, raw, out=None):
    rows.append((mode, place, name, raw, out if mode == 'ALLOW' else (raw if mode == 'FULL_RAW' else None)))


def sealed_part(fmt, series, lid, seal_row, P, rows):
    """п.1 (1), п.1е: попытка k по proof_sha256 (ровно одна), proof и снимок — через S.verify_attempt; источники
    только из seal/<S>/<k>/src/. → (proof, пересобранные JSON sealed/source)."""
    sfd = walk_dir(os.path.join(P['seal'], series))
    if sfd is None:
        raise Refused('proof:seal_dir')
    try:
        hits = S.find_retry(sfd, seal_row['proof_sha256'])
        if len(hits) != 1:
            raise Refused('proof:attempt')
        afd = S.open_dir(str(hits[0]), dir_fd=sfd)
    finally:
        os.close(sfd)
    try:
        raw_proof = S.read_small('proof.json', afd)
        kind = 'r2' if fmt == 'B9R2' else 'cleanup'
        try:
            proof = S.verify_attempt(afd, raw_proof, series, lid, kind)
        except S.Refused as e:
            raise Refused(f'proof:{e}')
        src = S.open_dir('src', dir_fd=afd)
        try:
            inv_raw = S.read_small('INVENTORY.sha256', src, S.MAX_SRC)
            data = {s['name']: S.read_small(s['name'], src, S.MAX_SRC) for s in proof['sources']}
        finally:
            os.close(src)
    finally:
        os.close(afd)
    man_a = man_raw = None
    if fmt == 'B9R2':
        man_raw = read_path(os.path.join(P['preserve'], series), 'MANIFEST.sha256', label='MANIFEST.sha256')
        if man_raw is None or hashlib.sha256(man_raw).hexdigest() != proof['preserve_manifest_sha256']:
            raise Refused('MANIFEST.sha256:sha256')
        man_a = E.parse_manifest_a(man_raw, series, lid.replace('-', ''))
        if sorted(man_a) != sorted(data):
            raise Refused('MANIFEST.sha256:names')
    bad = E.inventory_b_problem(fmt, series, inv_raw, man_a)
    if bad:
        raise Refused(bad)
    docs = {}
    for name in sorted(data):
        row = E.name_row(name)
        if row is None or E.need(fmt, 'source', name) is None:
            raise Refused(f'sealed/source/{name}:name')
        if row[1] == 'ALLOW':
            docs[name], out = E.sanitize(fmt, name, data[name])
            add(rows, 'ALLOW', 'sealed/source', name, data[name], out)
        else:
            add(rows, 'HASH_ONLY', 'sealed/source', name, data[name])
    for name in E.required(fmt, 'source'):
        if name not in data:
            raise Refused(f'sealed/source/{name}:missing')
    add(rows, 'FULL_RAW', 'sealed/meta', 'INVENTORY.sha256', inv_raw)
    if man_raw is not None:
        add(rows, 'FULL_RAW', 'sealed/meta', 'MANIFEST.sha256', man_raw)
    add(rows, 'FULL_RAW', 'proof', 'proof.json', raw_proof)
    return proof, docs


def final_part(fmt, series, P, rows):
    """п.1 (2): текущие файлы по имени и формату из «Откуда»; archive/<S> перечисляется целиком."""
    home = os.path.join(P['preserve'] if fmt == 'B9R2' else P['run'], series)
    known = {n for n in E.NAMES if n != 'started.marker'
             and (E.need(fmt, 'final', n) is not None or E.need(fmt, 'source', n) is not None)}
    if fmt == 'B9R2':
        known.add('MANIFEST.sha256')      # служебная опись B9 preserve (раздел 5 п.1, сверяется в sealed/meta)
    hfd = walk_dir(home)
    if hfd is not None:                   # REL65 M-04: посторонний файл в папке источника — отказ, не пропуск
        try:
            for ent in sorted(os.listdir(hfd)):
                st = os.stat(ent, dir_fd=hfd, follow_symlinks=False)
                if ent not in known or not stat.S_ISREG(st.st_mode):
                    raise Refused(f'final/{ent}:unknown')
        finally:
            os.close(hfd)
    docs = {}
    for name in sorted(E.NAMES):
        if E.need(fmt, 'final', name) is None or name == 'started.marker':
            continue
        data = read_path(home, name, label=f'final/{name}')
        if data is None:
            continue
        mode = E.NAMES[name][1]
        if mode == 'ALLOW':
            docs[name], out = E.sanitize(fmt, name, data)
            add(rows, 'ALLOW', 'final', name, data, out)
        else:
            add(rows, 'HASH_ONLY', 'final', name, data)
    afd = walk_dir(os.path.join(P['archive'], series))
    if afd is not None:
        try:
            for ent in sorted(os.listdir(afd)):
                m = E.ARCH_FILE.fullmatch(ent)
                if not m:
                    raise Refused(f'archive/{ent}:name')
                data = read_at(afd, ent, label=f'archive/{ent}')
                add(rows, 'HASH_ONLY', 'final', 'archive.' + ent, data)
        finally:
            os.close(afd)
    mk = read_path(P['started'], series, label='started.marker')
    if mk is not None:
        add(rows, 'HASH_ONLY', 'final', 'started.marker', mk)
    return docs


def journal_part(P, rows):
    jfd = walk_dir(P['journal'])
    segs = []
    if jfd is not None:
        try:
            names = os.listdir(jfd)
            bad = E.segments_problem(names)
            if bad:
                raise Refused(bad)
            for n in sorted(x for x in names if x != '.lock'):
                segs.append((n, read_at(jfd, n, label=f'journal/{n}')))
        finally:
            os.close(jfd)
    mode, last_seq, last_sha = E.journal_mode(segs)
    for n, data in segs:
        add(rows, 'FULL_RAW' if mode == 'FULL_RAW' else 'HASH_ONLY', 'journal', n, data)
    return mode, len(segs), last_seq, last_sha


def assemble(series, seal_row, boot_now, n, P=PATHS):
    """Чистая сборка строк пакета (без записи). → (строки, bundle)."""
    if not E.SERIES.fullmatch(series):
        raise Refused('series:name')
    fmt = fmt_for(series)
    home = os.path.join(P['preserve'] if fmt == 'B9R2' else P['run'], series)
    lid = lease_of(series, P)
    rows, proof, src_docs = [], None, {}
    if seal_row is not None:
        if seal_row.get('series') != series:
            raise Refused('seal:series')
        proof, src_docs = sealed_part(fmt, series, lid, seal_row, P, rows)
    fin_docs = final_part(fmt, series, P, rows)
    jmode, nseg, last_seq, last_sha = journal_part(P, rows)
    for docs in (src_docs, fin_docs):
        bad = E.links_problem(fmt, series, lid, docs)
        if bad:
            raise Refused(f'link:{bad}')
    if fmt == 'B10':
        anc = src_docs.get('anchor_run.json') or fin_docs.get('anchor_run.json')
        curs = [anc['cursor']] if anc else []
    else:
        anc = src_docs.get('anchor.json')
        if anc is None:
            a_raw = read_path(home, 'anchor.json', label='anchor.json')
            anc = E.sanitize(fmt, 'anchor.json', a_raw)[0] if a_raw else None
        curs = [anc['cursor_before'], anc['cursor_after']] if anc else []
        if anc and anc['cursor_before_us'] > anc['cursor_after_us']:
            raise Refused('anchor.json:cursor_order')
    if proof is not None:
        b_probe = proof['boot_id']
        bad = E.cursors_problem(proof, curs, b_probe)
        if bad:
            raise Refused(bad)
    elif anc is not None:
        b_probe = anc['boot_id']
    else:
        raise Refused('b_probe:anchor')
    if anc is not None and anc['boot_id'] != b_probe:
        raise Refused('anchor:boot_id')
    bundle = {'bundle_version': 2, 'manifest_schema_version': 2, 'matrix': f'{fmt}.v2',
              'allow_version': E.ALLOW_VERSION, 'series': series, 'lease_id': lid, 'n': n, 'b_probe': b_probe,
              'boot_id': boot_now, 'journal_cursor': proof['journal_to_cursor'] if proof else None,
              'journal_mode': jmode, 'journal_segments': nseg, 'journal_last_seq': last_seq,
              'journal_last_sha256': last_sha,
              'seal': None if seal_row is None else {'series': series, 'proof_sha256': seal_row['proof_sha256'],
                                                     'sealed_at': seal_row['sealed_at']}}
    E.check_bundle(bundle)
    add(rows, 'FULL_RAW', 'package', 'bundle.json', S.canon(bundle))
    rows.sort(key=lambda r: (r[1], r[2]))
    keys = [(r[1], r[2]) for r in rows]
    if len(set(keys)) != len(keys):
        raise Refused('manifest:duplicate')
    for r in rows:
        if not E.place_mode_ok(fmt, r[1], r[2], r[0], jmode):
            raise Refused(f'{r[1]}/{r[2]}:mode')
    phys = [r for r in rows if r[0] != 'HASH_ONLY']
    if len(phys) + 2 > E.MAX_FILES or len(rows) > E.MAX_LINES or any(len(r[4]) > E.MAX_FILE for r in phys) \
            or sum(len(r[4]) for r in phys) > E.MAX_TOTAL:
        raise Refused('limits:package')
    return rows, bundle


def manifest(rows):
    return ''.join(E.manifest_line(m, p, n, raw, out) + '\n' for m, p, n, raw, out in rows).encode('ascii')


def _mkdir_sync(name, dir_fd, gid, mode=0o750):
    os.mkdir(name, mode, dir_fd=dir_fd)
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    os.fchown(fd, 0 if os.geteuid() == 0 else -1, gid)
    os.fchmod(fd, mode)
    os.fsync(dir_fd)          # L-02: новая запись каталога надёжна — fsync родителя после mkdir
    return fd


def _put(name, data, dir_fd, gid):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dir_fd)
    try:
        os.fchown(fd, 0 if os.geteuid() == 0 else -1, gid)
        os.fchmod(fd, 0o640)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def next_n(series_fd):
    ns = []
    for ent in os.listdir(series_fd):
        if not N_RE.fullmatch(ent):
            raise Stop(f'export_entry:{ent}')
        ns.append(int(ent))
    return max(ns, default=0) + 1


def open_series(series, P, gid):
    """export/<S>: папка root:zevid 0750 (создаётся при первом пакете), не ссылка."""
    efd = walk_dir(P['export'])
    if efd is None:
        raise Stop('export_root')
    try:
        try:
            fd = os.open(series, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=efd)
        except FileNotFoundError:
            fd = _mkdir_sync(series, efd, gid)
        st = os.fstat(fd)
        if st.st_gid != gid or stat.S_IMODE(st.st_mode) != 0o750 or (os.geteuid() == 0 and st.st_uid != 0):
            os.close(fd)
            raise Stop('export_series_owner')
        return fd
    finally:
        os.close(efd)


def write_package(series, seal_row, boot_now, P=PATHS, gid=None):
    """Полная выгрузка. → (n, sha MANIFEST, bundle)."""
    if gid is None:
        import grp
        gid = grp.getgrnam('zevid').gr_gid
    sfd = open_series(series, P, gid)
    try:
        n = next_n(sfd)
        rows, bundle = assemble(series, seal_row, boot_now, n, P)
        try:
            nfd = _mkdir_sync(str(n), sfd, gid)
        except FileExistsError:
            raise Stop('export_busy')
    finally:
        os.close(sfd)
    try:
        dirs = {}
        for _, place, name, raw, out in rows:
            if out is None:
                continue
            top, _, sub = place.partition('/')
            if top not in dirs:
                dirs[top] = _mkdir_sync(top, nfd, gid)
            if sub and place not in dirs:
                dirs[place] = _mkdir_sync(sub, dirs[top], gid)
            _put(name, out, dirs[place], gid)
        for fd in dirs.values():
            os.fsync(fd)
        man = manifest(rows)
        _put('MANIFEST.sha256', man, nfd, gid)
        os.fsync(nfd)
        sha = hashlib.sha256(man).hexdigest()
        _put('READY', (sha + '\n').encode('ascii'), nfd, gid)
        os.fsync(nfd)
    finally:
        for fd in locals().get('dirs', {}).values():
            os.close(fd)
        os.close(nfd)
    return n, sha, bundle


def lease_of(series, P=PATHS):
    fmt = fmt_for(series)
    raw = read_path(os.path.join(P['preserve'] if fmt == 'B9R2' else P['run'], series), 'state.json',
                    label='state.json')
    if raw is None:
        raise Refused('state.json:missing')
    return E.sanitize(fmt, 'state.json', raw)[0]['lease_id']


def seal_row_db(lid, psql):
    """Строка lease_seal по аренде (первичный ключ — lease_id; серия сверяется в assemble)."""
    out = psql("SELECT coalesce((SELECT json_build_object('series', series, 'proof_sha256', proof_sha256, "
               "'sealed_at', to_char(sealed_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'))::text "
               "FROM bem_control.lease_seal WHERE lease_id = :'id'::uuid), 'none')", id=lid)
    if out == 'none':
        return None
    row = json.loads(out)
    if not isinstance(row, dict) or set(row) != {'series', 'proof_sha256', 'sealed_at'}:
        raise Refused('seal:row')
    return row


def main(argv):
    if len(argv) != 2 or not E.SERIES.fullmatch(argv[1]):
        print('usage: zprobe-export <series>', file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        print('EXPORT_STOP not_root')
        return 3
    import zprobe_checks as C
    series = argv[1]
    try:
        with open('/proc/sys/kernel/random/boot_id', encoding='ascii') as f:
            boot = f.read().strip().replace('-', '')
        row = seal_row_db(lease_of(series), C.psql_stdin)
        n, sha, b = write_package(series, row, boot)
    except Refused as e:
        print(f'EXPORT_REFUSED {e}')
        return 2
    except (Stop, OSError, RuntimeError, ValueError) as e:
        print(f'EXPORT_STOP {type(e).__name__}:{e}'[:300])
        return 3
    print(f"ZPROBE_EXPORT_OK series={series} n={n} manifest_sha256={sha} seal={'yes' if row else 'no'} "
          f"journal={b['journal_mode']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
