#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_r2.py
# ВЕРСИЯ: v0.9 (выпуск B12)  СТАТУС: DRAFT
# v0.9 (2026-11-17 22:07 +02:00, Claude, терминал zavod; проект DESIGN_B12_H4_DIAG v0.3, REL109 AGREED 0/0/2): после
#   четырёх строк B11 — пятая строка `R2_DIAG <json>` (закрытая схема, sort_keys, ensure_ascii): состояние ветки
#   DIAG_STATE (PRIMARY_CHECKS | MISMATCH | FACTS_UNHASHABLE | COLLECT_ERROR | RETRY_NOT_EVALUATED | OTHER | DIAG_ERROR),
#   части H4 (повторный C.evaluate на сохранённых фактах — только в PRIMARY_CHECKS, после сверки obs_sha с файлом
#   keep_obs и отпечатка всех фактов facts_sha), jdiag (коды и длительности проходов), derived_eval_sha с
#   origin=recomputed_on_kept_facts. Ни номера аренды, ни путей, ни сырого текста. Строка R2=, статус, вызов печати и код
#   возврата вычисляются до диагностики и от неё не зависят; сбой диагностики — DIAG_ERROR с кодом из закрытого списка;
#   сбой записи в stdout (BrokenPipe, в т.ч. при сбросе буфера) ловится: повторной печати нет, код — запомненный.
#   Ранний отказ (usage, not_root, REFUSED_INPUT) — одна строка, как в B11, R2_DIAG нет. TOOL zprobe-r2-b12-0.1,
#   отпечатки B9 — своя копия probes-b12.
# v0.8 (2026-11-17 18:59 +02:00, Claude, терминал zavod; REL99 M-355-REL99-01): перед КАЖДЫМ вызовом функции печати
#   (первичная печать и ветка повтора, где общий S.seal не вызывает сбор фактов) R2 только чтением проверяет файл
#   наблюдений: попытка с этим proof ровно одна (S.find_retry), proof.json root:root 0600 и его SHA-256 = переданной;
#   в значениях H4 и H5 ровно по одному токену obs=<SHA-256>, оба равны; файл <obs>/pb1trial2/obs-<sha>.json — обычный,
#   root:root 0600, путь без ссылок и без записи группы и всех (S.open_root, S.read_small), SHA-256 полных байтов = sha;
#   на первичной печати ещё и sha = сумме файла, записанного до проверок. Нет токена (старый proof без obs), токены разные,
#   нет файла, права не те, байты не те → функция печати НЕ вызывается: R2=REFUSED_INCONSISTENT status=BLOCKED_STOP_REVIEW
#   reason=obs:<почему>, код 1. Общий zprobe_seal.py не менялся. Строка R2_OBS_FILE на повторе показывает проверенный файл;
#   новая четвёртая строка `R2_OBS_CHECK ok <sha> | refused:<почему> | -` (до печати не дошли). TOOL zprobe-r2-b11-0.3.
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
#   После неё (v0.5–v0.8): `R2_OBS <json|null>`, `R2_OBS_FILE <путь|-> sha=<SHA-256|->`, `R2_OBS_CHECK ok <sha>|refused:..|-`.
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
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zprobe_checks as C  # noqa: E402
import zprobe_export_rules as E  # noqa: E402
import zprobe_seal as S  # noqa: E402
import zprobe_unstarted as UN  # noqa: E402

SERIES = 'pb1trial2'
OBS_ROOT = '/var/lib/zavod/r2obs'       # REL98 M-01: папка файлов наблюдений (создаётся при первом R2, root 0700)
PATHS = {'preserve': '/var/lib/zavod/preserve', 'run': '/run/zprobe', 'seal': S.SEAL_ROOT,
         'pins_b9': '/usr/local/lib/zavod/probes-b12/zprobe_pins_b9.txt', 'obs': OBS_ROOT}
B9_TEMPLATE = '/etc/systemd/system/zprobe-run-b9@.service'
TOOL = 'zprobe-r2-b12-0.1'             # v0.9: B12 — строка R2_DIAG (части H4 при отказе)
CHECKS_VERSION = 'checks-0.7'          # версия zprobe_checks.py (его паспорт: v0.7); сверяет test_zprobe_r2_b12.py
TOOL_VERSION = TOOL + '.' + CHECKS_VERSION   # proof.tool_version: [0-9A-Za-z._-]{1,40}
MAX_PINS = 64 * 1024
MAX_OBS = 1 << 20


class Refused(Exception):
    pass


class ObsRefused(Exception):
    """REL99 M-01: файл наблюдений для proof не доказан — функция печати не вызывается."""


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


OBS_TOKEN = re.compile(r'(?:^| )obs=([0-9a-f]{64})(?= |$)')


def proof_obs(proof_sha, P=PATHS):
    """REL99 M-01, только чтение: proof с SHA-256 proof_sha в seal/pb1trial2 (ровно одна попытка) → obs из H4/H5 (по одному
    токену, равны) → файл <obs>/pb1trial2/obs-<sha>.json (root:root 0600, путь root без ссылок), SHA-256 полных байтов = obs.
    Возвращает (путь, obs); любое несоответствие — ObsRefused(почему). Ничего не создаёт и не меняет."""
    try:
        rfd = S.open_root(P['seal'])
        try:
            sfd = S.open_dir(SERIES, dir_fd=rfd)
        finally:
            os.close(rfd)
        try:
            hits = S.find_retry(sfd, proof_sha)
            if len(hits) != 1:
                raise ObsRefused(f'proof_hits:{len(hits)}')
            afd = S.open_dir(str(hits[0]), dir_fd=sfd)
            try:
                raw = S.read_small('proof.json', afd)
            finally:
                os.close(afd)
        finally:
            os.close(sfd)
        if hashlib.sha256(raw).hexdigest() != proof_sha:
            raise ObsRefused('proof_sha')
        checks = json.loads(raw)['checks']
        toks = [OBS_TOKEN.findall(checks[k]['value']) for k in ('H4', 'H5')]
        if any(len(t) != 1 for t in toks):
            raise ObsRefused('obs_token')          # старый proof без obs= или два токена — не доказано
        if toks[0][0] != toks[1][0]:
            raise ObsRefused('obs_token_differs')
        h = toks[0][0]
        name = f'obs-{h}.json'
        ofd = S.open_root(os.path.join(P['obs'], SERIES))
        try:
            data = S.read_small(name, ofd, MAX_OBS)
        finally:
            os.close(ofd)
        if hashlib.sha256(data).hexdigest() != h:
            raise ObsRefused('obs_sha')
        return os.path.join(P['obs'], SERIES, name), h
    except ObsRefused:
        raise
    except FileNotFoundError as e:
        raise ObsRefused(f'missing:{os.path.basename(str(e.filename or "-"))}'[:100])
    except (S.Refused, OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise ObsRefused(f'{type(e).__name__}:{e}'[:100])


def obs_file_line(kept):
    """Строка `R2_OBS_FILE <путь> sha=<SHA-256>` — где лежит сохранённая до печати копия наблюдений."""
    return f'R2_OBS_FILE {kept[0]} sha={kept[1]}' if kept else 'R2_OBS_FILE - sha=-'


EXC_CODES = ('TimeoutExpired', 'Refused', 'OSError', 'ValueError', 'KeyError', 'TypeError', 'OTHER')
DIAG_STATES = ('PRIMARY_CHECKS', 'MISMATCH', 'FACTS_UNHASHABLE', 'COLLECT_ERROR', 'RETRY_NOT_EVALUATED', 'OTHER',
               'DIAG_ERROR')
DIAG_CODES = EXC_CODES + ('EVALUATE_UNKNOWN', 'FACTS_SHA', 'OBS_SHA', 'EVAL_MUTATED')
DIAG_KEYS = ('v', 'state', 'code', 'origin', 'failed', 'ok', 'H4', 'jdiag', 'obs_sha', 'facts_sha', 'derived_eval_sha')
FAILED_NAMES = tuple(C.CHECKS) + ('ARGS', 'COLLECT')
ORIGIN = 'recomputed_on_kept_facts'
DIAG_MAX = 1500


def exc_code(e):
    """Класс исключения из закрытого списка (B12): без текста исключения."""
    if isinstance(e, subprocess.TimeoutExpired):
        return 'TimeoutExpired'
    if isinstance(e, (S.Refused, Refused, ObsRefused)):
        return 'Refused'
    for t in (OSError, ValueError, KeyError, TypeError):
        if isinstance(e, t):
            return t.__name__
    return 'OTHER'


def _set_default(o):
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=repr)
    raise TypeError('unserializable')


def canon(x):
    """Канонический JSON (sort_keys, ensure_ascii, без пробелов); множества — отсортированные списки."""
    return json.dumps(x, sort_keys=True, ensure_ascii=True, separators=(',', ':'), default=_set_default)


def facts_sha(facts):
    """REL108 L-03: SHA-256 канонического JSON ВСЕГО словаря фактов или None (не сериализуется)."""
    try:
        return hashlib.sha256(canon(facts).encode('ascii')).hexdigest()
    except Exception:  # noqa: BLE001 — любой сбой сериализации = FACTS_UNHASHABLE
        return None


def _typed(d, keys, ints=(), strs=None):
    """Только значения закрытых типов: bool (по умолчанию) или int (ключи ints), строки — из strs; иначе null."""
    d = d if isinstance(d, dict) else {}
    out = {}
    for k in keys:
        v = d.get(k)
        if strs and k in strs:
            out[k] = v if isinstance(v, str) and v in strs[k] else None
        elif k in ints:
            out[k] = v if type(v) is int else None
        else:
            out[k] = v if type(v) is bool else None
    return out


def diag_obj(r, box):
    """Объект строки R2_DIAG (2.2 а–в проекта B12). Состояние — по тому, что реально произошло; части H4 — только в
    PRIMARY_CHECKS, на тех же фактах, что записаны keep_obs (повторный C.evaluate — чистая функция фактов)."""
    fl = r.get('failed')
    failed = [x if x in FAILED_NAMES else 'OTHER' for x in fl if isinstance(x, str)] if isinstance(fl, list) else []
    fs0 = box.get('facts_sha')
    base = dict.fromkeys(DIAG_KEYS)
    base.update(v=1, failed=failed, facts_sha=fs0 if isinstance(fs0, str) else None)
    if 'kept' in box:
        if failed == ['COLLECT']:                 # бросил evaluate внутри UN.run_checks — тип R2 не видел (REL108 L-01)
            return dict(base, state='COLLECT_ERROR', code='EVALUATE_UNKNOWN')
        facts = box['facts']
        fs1 = facts_sha(facts)
        if fs0 is None or fs1 is None:
            return dict(base, state='FACTS_UNHASHABLE')
        if fs1 != fs0:
            return dict(base, state='MISMATCH', code='FACTS_SHA')
        osha = hashlib.sha256(C.obs_json(facts).encode('ascii')).hexdigest()
        if osha != box['kept'][1]:
            return dict(base, state='MISMATCH', code='OBS_SHA')
        ev2 = C.evaluate(facts)
        if facts_sha(facts) != fs0:               # evaluate не должен менять факты (R09)
            return dict(base, state='MISMATCH', code='EVAL_MUTATED')
        ck = ev2.get('checks') if isinstance(ev2.get('checks'), dict) else {}
        try:
            dsha = hashlib.sha256(canon({k: v for k, v in ev2.items() if k != 'diag'}).encode('ascii')).hexdigest()
        except Exception:  # noqa: BLE001
            dsha = None
        dg = ev2.get('diag')
        h4 = dg.get('H4') if isinstance(dg, dict) else None
        jg = facts.get('jdiag')
        return dict(base, state='PRIMARY_CHECKS', origin=ORIGIN,
                    ok={k: (ck[k].get('ok') is True if isinstance(ck.get(k), dict) else None) for k in C.CHECKS},
                    H4=_typed(h4, C.H4_PARTS, ints=C.H4_INTS) if isinstance(h4, dict) else None,
                    jdiag=_typed(jg, C.JDIAG_KEYS, ints=tuple(k for k in C.JDIAG_KEYS if k != 'verify_class'),
                                 strs={'verify_class': C.VERIFY_CLASSES}) if isinstance(jg, dict) else None,
                    obs_sha=osha, derived_eval_sha=dsha)
    if failed == ['COLLECT'] or 'facts' in box or 'collect_exc' in box:
        code = box.get('collect_exc')
        return dict(base, state='COLLECT_ERROR', code=code if code in EXC_CODES else 'OTHER')
    if r.get('reason') == 'retry' or r.get('seal') == 'REFUSED_INCONSISTENT':
        return dict(base, state='RETRY_NOT_EVALUATED')
    return dict(base, state='OTHER')


def diag_error(e):
    return json.dumps({'v': 1, 'state': 'DIAG_ERROR', 'code': exc_code(e)}, sort_keys=True, separators=(',', ':'))


def diag_line(r, box):
    """Строка `R2_DIAG <json>`: всегда правильный JSON; сбой — DIAG_ERROR; длиннее DIAG_MAX — OVERSIZE (без обрезки)."""
    try:
        obj = diag_obj(r, box)
        s = json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)
        if len(s) > DIAG_MAX:
            s = json.dumps({'v': 1, 'state': obj['state'], 'error': 'OVERSIZE', 'len': len(s)}, sort_keys=True,
                           separators=(',', ':'))
    except Exception as e:  # noqa: BLE001 — диагностика не влияет на решение, статус и код возврата
        s = diag_error(e)
    return 'R2_DIAG ' + s


def _emit(lines):
    """Печать строк; сбой записи в stdout (BrokenPipe, закрытый поток) — False, без повторной печати."""
    try:
        for s in lines:
            print(s)
        return True
    except Exception:  # noqa: BLE001
        return False


def _mute_stdout():
    """После сбоя stdout остаток буфера уходит в /dev/null: при выходе нет второй ошибки и код возврата тот же."""
    try:
        dn = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(dn, sys.stdout.fileno())
        finally:
            os.close(dn)
    except Exception:  # noqa: BLE001
        pass


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
        try:
            box['facts'] = collect()
            box['facts_sha'] = facts_sha(box['facts'])     # B12 (REL108 L-03): отпечаток всех фактов сразу после сбора
            box['kept'] = keep_obs(box['facts'], P['obs'])   # REL98 M-01: файл наблюдений ДО проверок и печати; сбой → COLLECT
        except Exception as e:  # noqa: BLE001 — B12: только запомнить класс; исключение уходит дальше, как в B11
            box['collect_exc'] = exc_code(e)
            raise
        return box['facts']
    d['collect'] = collect_keep
    call = d['call_seal']

    def call_checked(series, lease_id, sha):   # REL99 M-01: и первичная печать, и повтор — только с доказанным файлом
        try:
            got = proof_obs(sha, P)
            if 'kept' in box and box['kept'] != got:
                raise ObsRefused('obs_not_kept_file')
        except ObsRefused as e:
            box['obs_refused'] = str(e)
            raise
        box['checked'] = got
        return call(series, lease_id, sha)
    d['call_seal'] = call_checked
    r = UN.seal_unstarted(SERIES, lid, d)
    if 'obs_refused' in box:                 # функция печати не вызывалась: доказательство повтора не сходится
        r.update(seal='REFUSED_INCONSISTENT', status='BLOCKED_STOP_REVIEW', reason=f"obs:{box['obs_refused']}")
    code = 0 if r['status'] == 'SAFE_PRE_START' else 1     # B12: решение и код — до диагностики, от неё не зависят
    head = [line(r), obs_line(box.get('facts')),         # и при отказе: что именно просканировано (копия; носитель — файл)
            obs_file_line(box.get('kept') or box.get('checked')),
            'R2_OBS_CHECK ' + (f"ok {box['checked'][1]}" if 'checked' in box
                               else f"refused:{box['obs_refused']}" if 'obs_refused' in box else '-')[:200]]
    ok = _emit(head)
    if ok:
        ok = _emit([diag_line(r, box)])
    if ok:
        try:
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            ok = False
    if not ok:
        _mute_stdout()
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv))
