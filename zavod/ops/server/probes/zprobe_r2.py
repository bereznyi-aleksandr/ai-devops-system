#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_r2.py
# ВЕРСИЯ: v0.7 (выпуск B11)  СТАТУС: DRAFT
# v0.7 (2026-11-17 18:22 +02:00, Claude, терминал zavod (58f8b71b); REL98 M-355-REL98-01): полный канонический JSON
#   наблюдений (C.obs_json, те же байты, что R2_OBS) сохраняется ДО проверок и печати отдельным файлом
#   /var/lib/zavod/r2obs/pb1trial2/obs-<SHA-256>.json (root:root 0600, O_EXCL|O_NOFOLLOW, fsync файла и папок; имя =
#   obs= в значениях H4/H5 proof, так proof связан с файлом). Запись — внутри сбора фактов: файл не записан (папка не
#   root, ссылка, нет места, файл с тем же именем и другими байтами) → сбор не удался → COLLECT, печати нет. Тот же файл
#   с теми же байтами — принимается (повтор). Ничего не удаляет, не переименовывает, не перезаписывает. Строка R2_OBS в
#   stdout остаётся копией; добавлена строка `R2_OBS_FILE <путь> sha=<SHA-256>`. CHECKS_VERSION не меняется.
# v0.6 (2026-11-17 17:33 +02:00, Claude, терминал zavod): CHECKS_VERSION = checks-0.6 (zprobe_checks.py v0.6: PIN_B9 со
#   значениями D14). Код R2 не менялся.
# v0.5 (2026-11-17 07:51 +02:00, Claude, терминал zavod, помощник; REL97 M-02): после строки R2= (и при отказе) печатается
#   отдельная строка `R2_OBS <json>` — полный канонический JSON наблюдений (C.obs_json: сводка seq, journald_restart,
#   старт journald, отсортированные other_ed, наблюдённые BD и SD, SHA-256 аренды, загрузка); его SHA-256 = obs= в значениях
#   H4/H5 proof, так оператор снимком строки доказывает, что именно было просканировано. CHECKS_VERSION = checks-0.5.
# v0.4 (2026-11-17 07:04 +02:00, Claude, терминал zavod (ee9861cd); REL96B PATH=A): выпуск B11 — только имя инструмента
#   и путь копии отпечатков B9: PATHS['pins_b9'] — своя копия в папке probes-b11 (установщик B11 кладёт её рядом и
#   проверяет, что B10 цел); TOOL — zprobe-r2-b11-0.1; в proof.tool_version добавлена версия проверок
#   (TOOL_VERSION = TOOL + '.checks-0.4': требование аудитора REL96B п. 3 «версии проверок в proof»). Остальное — как v0.3.
# v0.3 (2026-11-16 20:51, терминал zavod, сменщик после HANDOFF_20261116_1916; REL90 L-355-REL90-02): открытие
#   preserve/pb1trial2 (S.open_root) — внутри обработки: S.Refused и OSError → R2=REFUSED_INPUT preserve:…, код 2,
#   без трассировки; ничего не создано.
# v0.2 (2026-11-15 12:48, терминал zavod, сменщик 3a6de98b; REL69 M-02): до снимка, proof и вызова печати опись (A) и
#   настоящий набор файлов preserve сверяются с закрытой таблицей имён выгрузки (E.NAMES, B9R2, source):
#   имя вне таблицы, нет обязательного имени, файл без строки (A) или строка без файла →
#   R2=REFUSED_INPUT matrix:… / preserve_set:…, код 2. Ничего не создано, печати нет, preserve не тронут.
# ДАТА СОЗДАНИЯ: 2026-11-15 00:06 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 1.6 — шаг R2, печать аренды остатка pb1trial2 (`zprobe-start --seal-residue
#   pb1trial2`, от root, после установки B10 и «да» оператора). LID — из preserve/pb1trial2/state.json, сверка с
#   MANIFEST (A) и anchor.json R1; дальше — общий порядок печати 4.4 (zprobe_seal.seal, вид 'r2') через ту же
#   функцию, что уборка B10 (zprobe_unstarted.seal_unstarted): проверки H1-B9/H2-B9 и H3–H10 (zprobe_checks, вид
#   'b9'), снимок preserve/pb1trial2 (src = 0:0:0600, orig — из (A)), proof с preserve_manifest_sha256, вызов
#   функции 4.2; до и после — H8 и H10. Маску не снимает, ничего не удаляет.
# ВЫХОД: одна строка `R2=<ответ печати> status=<SAFE_PRE_START|BLOCKED_SESSION_UNKNOWN|BLOCKED_STOP_REVIEW> k=..
#   sha=.. failed=.. reason=..`; код 0 только при SAFE_PRE_START; `R2=REFUSED_<почему>` и код 2 — входы не сошлись.
# ДОПУЩЕНИЕ (на аудит, B11): копия отпечатков B9 — probes-b11/zprobe_pins_b9.txt (свой файл B11, равный файлу пакета и
#   B10); исходные показатели, основание исключения и хеш входных доказательств идут в proof без новых полей схемы:
#   значения H4/H5 (gap/verify/loss, n/u/oth, alt=R0V14, obs=<SHA-256 наблюдений = строка R2_OBS>, pin=<SHA-256
#   закреплённых значений>, bd=/sd= наблюдённые), preserve_manifest_sha256
#   (SHA-256 описи MANIFEST с суммами state/anchor/evidence), inventory_sha256, tool_version с версией проверок.
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
OBS_ROOT = '/var/lib/zavod/r2obs'       # REL98 M-01: папка файлов наблюдений (создаётся при первом R2, root 0700)
PATHS = {'preserve': '/var/lib/zavod/preserve', 'run': '/run/zprobe', 'seal': S.SEAL_ROOT,
         'pins_b9': '/usr/local/lib/zavod/probes-b11/zprobe_pins_b9.txt', 'obs': OBS_ROOT}
B9_TEMPLATE = '/etc/systemd/system/zprobe-run-b9@.service'
TOOL = 'zprobe-r2-b11-0.2'             # v0.7: 0.2 — файл наблюдений до печати (REL98 M-01)
CHECKS_VERSION = 'checks-0.6'          # версия zprobe_checks.py (его паспорт: v0.6); сверяет test_zprobe_r2_b11.py
TOOL_VERSION = TOOL + '.' + CHECKS_VERSION   # proof.tool_version: [0-9A-Za-z._-]{1,40}
MAX_PINS = 64 * 1024
MAX_OBS = 1 << 20


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
    try:                                   # REL90 L-02: нет папки, ссылка, не root, запись группы/всех → отказ, код 2
        fd = S.open_root(home)
    except (S.Refused, OSError) as e:
        raise Refused(f'preserve:{e}')
    try:
        st_raw = S.read_small('state.json', fd)
        man_raw = S.read_small('MANIFEST.sha256', fd, S.MAX_SRC)
        anc_raw = S.read_small('anchor.json', fd)
        present = set(os.listdir(fd))
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
    # REL69 M-02: печать необратима, а выгрузка берёт только имена закрытой таблицы — сверка ДО печати
    for n in sorted(man):
        if E.need('B9R2', 'source', n) is None:
            raise Refused(f'matrix:{n}')
    for n in E.required('B9R2', 'source'):
        if n not in man:
            raise Refused(f'matrix_required:{n}')
    if present != set(man) | {'MANIFEST.sha256'}:
        odd = sorted(present ^ (set(man) | {'MANIFEST.sha256'}))
        raise Refused(f'preserve_set:{odd[0]}')
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
            'tool_version': TOOL_VERSION, 'now_utc': UN.now_utc, 'root': P['seal']}


def line(r):
    return (f"R2={r.get('seal') or 'NONE'} status={r['status']} k={r.get('k') or '-'} sha={r.get('sha') or '-'} "
            f"failed={','.join(r.get('failed') or []) or '-'} reason={r.get('reason') or '-'}")[:400]


def obs_line(facts):
    """Строка `R2_OBS <json>`: каноническая запись наблюдений; SHA-256 её json-части = obs= в proof (REL97 M-02)."""
    return 'R2_OBS ' + (C.obs_json(facts) if isinstance(facts, dict) else 'null')


def _sub_dir(name, parent_fd):
    """Подпапка root 0700: создаётся, если её нет; открывается без ссылок, root:root, без записи группы и всех."""
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
        os.fsync(parent_fd)
    except FileExistsError:
        pass
    return S.open_dir(name, dir_fd=parent_fd)


def keep_obs(facts, root):
    """REL98 M-01: канонический JSON наблюдений → <root>/pb1trial2/obs-<sha>.json до печати. Возвращает (путь, sha).
    Новый файл — O_EXCL, root:root 0600, fsync файла и папки. Файл с этим именем уже есть: те же байты — принят (повтор),
    другие — S.Refused (ничего не перезаписывается). Любой сбой — исключение: сбор фактов не удаётся, печати нет."""
    raw = C.obs_json(facts).encode('ascii')
    h = hashlib.sha256(raw).hexdigest()
    name = f'obs-{h}.json'
    parent, base = os.path.split(root.rstrip('/'))
    pfd = S.open_root(parent)
    try:
        rfd = _sub_dir(base, pfd)
    finally:
        os.close(pfd)
    try:
        sfd = _sub_dir(SERIES, rfd)
    finally:
        os.close(rfd)
    try:
        try:
            S.put_excl(name, raw, sfd)
            os.fsync(sfd)
        except FileExistsError:
            if S.read_small(name, sfd, MAX_OBS) != raw:
                raise S.Refused(f'obs_differs:{name}')
    finally:
        os.close(sfd)
    return os.path.join(root, SERIES, name), h


def obs_file_line(kept):
    """Строка `R2_OBS_FILE <путь> sha=<SHA-256>` — где лежит сохранённая до печати копия наблюдений."""
    return f'R2_OBS_FILE {kept[0]} sha={kept[1]}' if kept else 'R2_OBS_FILE - sha=-'


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
    d = deps(lid, man_raw, man, entries, P)
    box = {}
    collect = d['collect']

    def collect_keep():                    # те же факты, что видит проверка, остаются для строки R2_OBS
        box['facts'] = collect()
        box['kept'] = keep_obs(box['facts'], P['obs'])   # REL98 M-01: файл наблюдений ДО проверок и печати; сбой → COLLECT
        return box['facts']
    d['collect'] = collect_keep
    r = UN.seal_unstarted(SERIES, lid, d)
    print(line(r))
    print(obs_line(box.get('facts')))      # и при отказе: что именно просканировано (копия; основной носитель — файл)
    print(obs_file_line(box.get('kept')))
    return 0 if r['status'] == 'SAFE_PRE_START' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
