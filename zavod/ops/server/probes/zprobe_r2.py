#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_r2.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-15 00:06 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 1.6 — шаг R2, печать аренды остатка pb1trial2 (`zprobe-start --seal-residue
#   pb1trial2`, от root, после установки B10 и «да» оператора). LID — из preserve/pb1trial2/state.json, сверка с
#   MANIFEST (A) и anchor.json R1; дальше — общий порядок печати 4.4 (zprobe_seal.seal, вид 'r2') через ту же
#   функцию, что уборка B10 (zprobe_unstarted.seal_unstarted): проверки H1-B9/H2-B9 и H3–H10 (zprobe_checks, вид
#   'b9'), снимок preserve/pb1trial2 (src = 0:0:0600, orig — из (A)), proof с preserve_manifest_sha256, вызов
#   функции 4.2; до и после — H8 и H10. Маску не снимает, ничего не удаляет.
# ВЫХОД: одна строка `R2=<ответ печати> status=<SAFE_PRE_START|BLOCKED_SESSION_UNKNOWN|BLOCKED_STOP_REVIEW> k=..
#   sha=.. failed=.. reason=..`; код 0 только при SAFE_PRE_START; `R2=REFUSED_<почему>` и код 2 — входы не сошлись.
# ДОПУЩЕНИЕ (на аудит): эталон файла службы B9 (1.3 А) — ключ `zprobe-run-b9@.service` копии отпечатков B9
#   LIB/zprobe_pins_b9.txt (её кладёт установщик B10 из пакета; так B9 хранил отпечатки B8), путь шаблона —
#   /etc/systemd/system/zprobe-run-b9@.service (UNIT_DIR B9).
import hashlib
import json
import os
import re
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_checks as C  # noqa: E402
import zprobe_export_rules as E  # noqa: E402
import zprobe_seal as S  # noqa: E402
import zprobe_unstarted as UN  # noqa: E402

SERIES = 'pb1trial2'
PATHS = {'preserve': '/var/lib/zavod/preserve', 'run': '/run/zprobe', 'seal': S.SEAL_ROOT,
         'pins_b9': '/usr/local/lib/zavod/probes-b10/zprobe_pins_b9.txt'}
B9_TEMPLATE = '/etc/systemd/system/zprobe-run-b9@.service'
TOOL = 'zprobe-r2-b10-0.1'
MAX_PINS = 64 * 1024


class Refused(Exception):
    pass


def pins_template(path):
    """{'path', 'sha'} шаблона B9 из копии отпечатков B9 (файл root, без записи группы и всех) или None."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022 or st.st_size > MAX_PINS:
            return None
        raw = os.read(fd, MAX_PINS + 1)
    finally:
        os.close(fd)
    hits = [ln.split(' ')[1] for ln in raw.decode('ascii', 'replace').split('\n')
            if ln.startswith('zprobe-run-b9@.service ') and len(ln.split(' ')) == 2]
    if len(hits) != 1 or not re.fullmatch(r'[0-9a-f]{64}', hits[0]):
        return None
    return {'path': B9_TEMPLATE, 'sha': hits[0]}


def inputs(P=PATHS):
    """1.6: LID из preserve/pb1trial2/state.json (ровно {lease, lease_id, dropin}), сверка с MANIFEST (A) и
    anchor.json. → (lid, сырые байты MANIFEST, entries для снимка {имя: (orig, orig_src)})."""
    home = os.path.join(P['preserve'], SERIES)
    fd = S.open_root(home)
    try:
        st_raw = S.read_small('state.json', fd)
        man_raw = S.read_small('MANIFEST.sha256', fd, S.MAX_SRC)
        anc_raw = S.read_small('anchor.json', fd)
    except (S.Refused, OSError) as e:
        raise Refused(f'preserve:{e}')
    finally:
        os.close(fd)
    try:
        st = json.loads(st_raw)
        anc = json.loads(anc_raw)
    except ValueError:
        raise Refused('json')
    if not isinstance(st, dict) or set(st) != {'lease', 'lease_id', 'dropin'} \
            or not isinstance(st['lease_id'], str) or not E.UUID.fullmatch(st['lease_id']):
        raise Refused('state_fields')
    lid = st['lease_id']
    L = lid.replace('-', '')
    if st['lease'] != L or st['dropin'] != f'/run/systemd/system/zagent@{L}.service.d/50-zprobe.conf':
        raise Refused('state_identity')
    try:
        man = E.parse_manifest_a(man_raw, SERIES, L)
    except E.Refused as e:
        raise Refused(f'manifest:{e}')
    if man.get('state.json', ('',))[0] != hashlib.sha256(st_raw).hexdigest() \
            or man['anchor.json'][0] != hashlib.sha256(anc_raw).hexdigest():
        raise Refused('manifest_sums')
    if not isinstance(anc, dict) or anc.get('series') != SERIES or anc.get('lease_id') != lid \
            or anc.get('lease') != L:
        raise Refused('anchor_identity')
    entries = {n: (v[2], v[3]) for n, v in man.items()}       # anchor.json: ('-', '-') — так в (B)
    return lid, man_raw, man, entries


def deps(lid, man_raw, man, entries, P=PATHS):
    L = lid.replace('-', '')
    home = os.path.join(P['preserve'], SERIES)
    src = {'state': os.path.join(P['run'], SERIES, 'state.json'), 'evidence': os.path.join(home, 'evidence.json'),
           'anchor': os.path.join(home, 'anchor.json'), 'manifest_state_sha': man['state.json'][0],
           'fragment_expected': pins_template(P['pins_b9'])}
    return {'exit_status': None, 'kind': 'r2', 'fixed_src': '0:0:0600',
            'preserve_manifest_sha256': hashlib.sha256(man_raw).hexdigest(),
            'collect': lambda: C.collect('b9', SERIES, lid, src),
            'recheck_facts': lambda: C.svc_mask(f'zagent@{L}.service'),
            'select_row': UN.select_seal, 'call_seal': UN.call_seal,
            'open_source': lambda: (S.open_root(home), f'/var/lib/zavod/preserve/{SERIES}', entries),
            'tool_version': TOOL, 'now_utc': UN.now_utc, 'root': P['seal']}


def line(r):
    return (f"R2={r.get('seal') or 'NONE'} status={r['status']} k={r.get('k') or '-'} sha={r.get('sha') or '-'} "
            f"failed={','.join(r.get('failed') or []) or '-'} reason={r.get('reason') or '-'}")[:400]


def main(argv, P=PATHS):
    if len(argv) != 2 or argv[1] != SERIES:
        print('usage: zprobe_r2.py pb1trial2')
        return 2
    if os.geteuid() != 0:
        print('R2=REFUSED_CALLER not_root')
        return 2
    try:
        lid, man_raw, man, entries = inputs(P)
    except Refused as e:
        print(f'R2=REFUSED_INPUT {e}'[:300])
        return 2
    r = UN.seal_unstarted(SERIES, lid, deps(lid, man_raw, man, entries, P))
    print(line(r))
    return 0 if r['status'] == 'SAFE_PRE_START' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
