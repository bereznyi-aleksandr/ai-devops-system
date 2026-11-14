#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_unstarted.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-14 23:42 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проект B10 v0.18 — уборка серии B10 без сессии (4.1) и якорь бегунка (1.3 H2-B10, H9 б).
#   Бегунок: строка ZPROBE_LEASE_OPEN до INSERT аренды; сразу после INSERT и до любого шага — anchor_run.json
#   (серия, LID, boot_id, курсор и время последней записи журнала не раньше открытия аренды, время UTC).
#   Уборка: одна функция проверки (zprobe_checks.evaluate, вид 'b10') и один порядок печати (zprobe_seal.seal,
#   вид 'cleanup') — без копии кода; после печати снова H8 и H10 и чтение строки печати → SAFE_PRE_START.
# ДОПУЩЕНИЯ (на аудит): 1) эталон файла службы — строка списка установленных файлов B10 LIB/INSTALLED.sha256
#   («<sha256>  <путь>», путь /etc/systemd/system/zprobe-run-b10@.service ровно один раз; файл root, без записи
#   группы и всех) — сам список пишет установщик B10 (шаг сборщика выпуска); нет файла или строки → H2 не прошла;
#   2) курсор якоря берётся у записи с временем не раньше конца INSERT (секунды бегунка ≥ opened_at), для этого
#   бегунок сначала печатает строку ZPROBE_LEASE_ANCHOR и ждёт её (≤ 20 чтений по 0,5 с);
#   3) код выхода службы уборка берёт из EXIT_STATUS (systemd задаёт его строкам ExecStopPost); 75 → BLOCKED.
# ОГРАНИЧЕНИЯ: ничего не удаляет и не перезаписывает (только O_EXCL); SQL — только через функции, которые передаёт
#   вызывающий (psql через stdin); ключей не читает.
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import threading
import time

import zprobe_checks as C
import zprobe_dropin as DROP
import zprobe_seal as S

ANCHOR = 'anchor_run.json'
TEMPLATE = '/etc/systemd/system/zprobe-run-b10@.service'
MAX_LINE = 1 << 20
MAX_LIST = 64 * 1024
INSTALLED_LINE = re.compile(r'([0-9a-f]{64})  (/[A-Za-z0-9@._/-]{1,250})')
ANCHOR_FIELDS = {'series', 'lease_id', 'boot_id', 'cursor', 'cursor_us', 'at_utc'}
SAFE_STATES = ('SEALED_NOW', 'ALREADY_SEALED')


def lease_open_line(series, lid):
    """1.3 H2-B10: строка до INSERT аренды; её ищет evaluate (ровно одна, время ≤ T0)."""
    return f'ZPROBE_LEASE_OPEN series={series} lease_id={lid}'


def anchor_line(series, lid):
    return f'ZPROBE_LEASE_ANCHOR series={series} lease_id={lid}'


def series_taken(series, places):
    """1.3: имя pb1trial2 и любое имя, уже занятое в местах прежних серий, бегунок B10 не принимает (до аренды).
    Возвращает первое занятое место или None."""
    if series == C.B9_SERIES:
        return 'b9_residue'
    for p in places:
        if os.path.lexists(os.path.join(p, series)):
            return p
    return None


def last_entry(cmd=('journalctl', '-n', '1', '-o', 'json', '--no-pager', '-q'), timeout=60, limit=MAX_LINE):
    """Последняя запись журнала тем же ограниченным чтением, что R1 v5: первая строка потока ≤ 1 МБ, не дольше
    timeout; если journalctl завершился сам — код 0. Возвращает {'cursor', 'us', 'boot'}; иное — Refused."""
    p = subprocess.Popen(list(cmd), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    killed = []
    timer = threading.Timer(timeout, lambda: (killed.append(1), p.kill()))
    timer.start()
    ln = b''
    try:
        ln = p.stdout.readline(limit + 1)
        if not ln:                       # конец потока: процесс закрыл вывод — дождаться его кода
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
    finally:
        timer.cancel()
        own = p.poll() is not None
        if not own:
            p.kill()
        rc = p.wait()
        p.stdout.close()
    if killed:
        raise S.Refused('anchor_timeout')
    if len(ln) > limit:
        raise S.Refused('too_big_out')
    if own and rc != 0:
        raise S.Refused(f'journalctl_rc_{rc}')
    if not ln.endswith(b'\n'):
        raise S.Refused('no_cursor')
    try:
        e = json.loads(ln)
        cur, us, boot = e['__CURSOR'], int(e['__REALTIME_TIMESTAMP']), e['_BOOT_ID']
    except (ValueError, KeyError, TypeError):
        raise S.Refused('no_cursor')
    if not isinstance(cur, str) or not S.CURSOR.fullmatch(cur) or not C.HEX32.fullmatch(str(boot)) or us <= 0:
        raise S.Refused('bad_cursor')
    return {'cursor': cur, 'us': us, 'boot': boot}


def take_anchor(series, lid, after_s, boot_now, now_utc, entry=last_entry, emit=DROP.emit, sleep=time.sleep,
                tries=20):
    """H9 б: бегунок печатает строку якоря и берёт курсор записи текущей загрузки со временем ≥ after_s (секунды
    бегунка после INSERT, поэтому ≥ opened_at). Возвращает документ anchor_run.json."""
    if not emit(anchor_line(series, lid)):
        raise S.Refused('anchor_emit')
    for i in range(tries):
        e = entry()
        if e['boot'] == boot_now and e['us'] // 1000000 >= after_s:
            return {'series': series, 'lease_id': lid, 'boot_id': boot_now, 'cursor': e['cursor'],
                    'cursor_us': e['us'], 'at_utc': now_utc()}
        if i + 1 < tries:
            sleep(0.5)
    raise S.Refused('anchor_no_entry')


def check_anchor(doc):
    """Закрытый состав anchor_run.json (его разбирает evaluate через сбор фактов)."""
    return isinstance(doc, dict) and set(doc) == ANCHOR_FIELDS and C.SERIES.fullmatch(str(doc['series'])) \
        and C.UUID.fullmatch(str(doc['lease_id'])) and C.HEX32.fullmatch(str(doc['boot_id'])) \
        and isinstance(doc['cursor'], str) and S.CURSOR.fullmatch(doc['cursor']) \
        and type(doc['cursor_us']) is int and doc['cursor_us'] > 0 and S.UTC.fullmatch(str(doc['at_utc']))


def write_anchor(dir_fd, doc):
    """anchor_run.json: эксклюзивно (O_EXCL|O_NOFOLLOW), root:root 0600, fsync файла и папки, перечитывание и сверка
    SHA-256. Возвращает SHA-256."""
    if not check_anchor(doc):
        raise S.Refused('anchor_schema')
    data = S.canon(doc)
    S.put_excl(ANCHOR, data, dir_fd)
    os.fsync(dir_fd)
    h = hashlib.sha256(data).hexdigest()
    if hashlib.sha256(S.read_small(ANCHOR, dir_fd, MAX_LINE)).hexdigest() != h:
        raise S.Refused('anchor_sha_mismatch')
    return h


def open_src(path):
    """Папка серии по дескриптору: каждый шаг от / без ссылок, владелец root, без записи для группы и всех
    (группа zprobe на чтение допустима: /run/zprobe/<серия> — root:zprobe 0750)."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in [x for x in path.split('/') if x] + [None]:
            st = os.fstat(fd)
            if st.st_uid != 0 or st.st_mode & 0o022:
                raise S.Refused(f'src_dir_owner:{path}')
            if part is None:
                break
            nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = nfd
    except BaseException:
        os.close(fd)
        raise
    return fd


def expected_fragment(installed, template=TEMPLATE):
    """1.3 Б: эталон файла службы — строка списка установленных файлов B10. {'path', 'sha'} или None."""
    try:
        fd = os.open(installed, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022 or st.st_size > MAX_LIST:
            return None
        raw = os.read(fd, MAX_LIST + 1)
    finally:
        os.close(fd)
    try:
        lines = raw.decode('ascii').split('\n')
    except UnicodeDecodeError:
        return None
    if lines[-1] != '':
        return None
    hits = []
    for ln in lines[:-1]:
        m = INSTALLED_LINE.fullmatch(ln)
        if not m:
            return None
        if m.group(2) == template:
            hits.append(m.group(1))
    return {'path': template, 'sha': hits[0]} if len(hits) == 1 else None


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def select_seal(lid, psql=C.psql_stdin):
    """4.4 п.1: строка lease_seal по аренде (только чтение). None — строки нет; ошибка psql — исключение."""
    out = psql("SELECT coalesce((SELECT json_build_object('series', series, 'proof_sha256', proof_sha256)::text "
               "FROM bem_control.lease_seal WHERE lease_id = :'id'::uuid), 'none')", id=lid)
    if out == 'none':
        return None
    row = json.loads(out)
    if not isinstance(row, dict) or set(row) != {'series', 'proof_sha256'}:
        raise ValueError('seal_row')
    return row


def call_seal(series, lid, sha, psql=C.psql_stdin):
    """4.2: один вызов функции печати, одна транзакция; ответ — строка результата."""
    return psql("SELECT bem_control.lease_seal_unstarted(:'s', :'id'::uuid, :'sha')", s=series, id=lid, sha=sha)


def seal_unstarted(series, lid, d):
    """4.1: уборка без сессии. d — внешние шаги: exit_status (строка или None), collect() → факты evaluate,
    recheck_facts() → {'svc', 'mask'}, select_row(lid), call_seal(series, lid, sha), open_source() → (fd, путь,
    entries), tool_version, now_utc(), root (папка seal). Итог: SAFE_PRE_START | BLOCKED_SESSION_UNKNOWN |
    BLOCKED_STOP_REVIEW; печать только по общему порядку 4.4."""
    out = {'status': 'BLOCKED_SESSION_UNKNOWN', 'seal': None, 'failed': [], 'reason': '-'}
    if d.get('exit_status') == str(DROP.EXIT_DIAG_LOST):
        out['reason'] = 'diag_lost_75'              # раздел 2 п.5в: причина отказа потеряна — печати нет
        return out
    box = {}

    def run_checks():
        try:
            ev = C.evaluate(d['collect']())
        except Exception as e:  # noqa: BLE001 — любой сбой сбора = условие не доказано
            ev = {'ok': False, 'failed': ['COLLECT'], 'checks': {}, 'error': type(e).__name__}
        box['ev'] = ev
        return ev

    def recheck():
        try:
            f = d['recheck_facts']()
            return C.h8_ok(f.get('svc')) and C.h10_ok(f.get('mask'))
        except Exception:  # noqa: BLE001
            return False

    try:
        r = S.seal('cleanup', series, lid, d['select_row'], d['call_seal'], run_checks, recheck, d['open_source'],
                   d['tool_version'], d['now_utc'], root=d.get('root', S.SEAL_ROOT))
    except Exception as e:  # noqa: BLE001 — исход вызова неизвестен: следующий запуск начнёт с п.1 (4.4 п.4)
        out['reason'] = f'seal_exc:{type(e).__name__}'
        out['failed'] = (box.get('ev') or {}).get('failed', [])
        return out
    out.update(seal=r['result'], k=r.get('k'), sha=r.get('sha'), reason=r.get('reason', '-'),
               failed=(box.get('ev') or {}).get('failed', []))
    if r['result'] == 'REFUSED_INCONSISTENT':
        out['status'] = 'BLOCKED_STOP_REVIEW'       # 4.4 п.2: итог уборки при несогласованной печати
        return out
    if r['result'] not in SAFE_STATES:
        return out
    try:
        row = d['select_row'](lid)
    except Exception:  # noqa: BLE001
        row = None
    sealed = isinstance(row, dict) and row.get('series') == series and row.get('proof_sha256') == r.get('sha')
    out['status'] = 'SAFE_PRE_START' if sealed and recheck() else 'BLOCKED_STOP_REVIEW'   # 4.1: тревога после печати
    return out
