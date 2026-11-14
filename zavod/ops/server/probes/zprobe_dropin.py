#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_dropin.py
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-14 23:00 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 09» (3037f186)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 2 — запись причины отказа дополнения (drop-in) ДО решения об отказе.
#   Сравнение свойств службы до и после дополнения (только в памяти, сырой вывод не пишется), файл
#   dropin_check.json (эксклюзивно, целиком, fsync, перечитывание и сверка SHA-256), строка журнала
#   ZPROBE_DROPIN_CHECK (только безопасные имена, без значений) и решение: идти дальше, отказ или код 75.
#   Подключение к бегунку B10 — отдельным шагом выпуска B10 (раздел 7); сам модуль ничего не запускает.
# ДОПУЩЕНИЕ (на аудит): сравнение OK, но dropin_check.json не записан → тоже стоп (dropin_check_unwritten):
#   без записанной диагностики сессия не начинается. Проект говорит только о случае отказа (п. 5а).
import errno
import hashlib
import json
import os
import re

SENSITIVE = re.compile(r'Environment|Credential|Exec|LogExtraFields|Secret|Token|Key|Password')
MAX_VALUE = 512        # п. 2: длиннее — обрезка с пометкой
MAX_CHANGED = 200      # п. 3: больше — сравнение неполное
MAX_LOG_NAMES = 40     # п. 4: имён в строке журнала не больше
EXIT_DIAG_LOST = 75    # п. 5в
SAFE_NAME = re.compile(r'[A-Za-z0-9]{1,64}')


def compare(p_before, p_after, allowed, systemd, at):
    """Документ dropin_check.json по п. 3. Значения чувствительных имён не хранятся и не хешируются."""
    changed = sorted(k for k in set(p_before) | set(p_after) if p_before.get(k) != p_after.get(k))
    values, cut = {}, False
    for k in changed[:MAX_CHANGED]:
        b, a = p_before.get(k), p_after.get(k)
        if SENSITIVE.search(k):
            values[k] = {'redacted': True, 'len_before': len(b or ''), 'len_after': len(a or '')}
            continue
        v = {}
        for side, s in (('before', b), ('after', a)):
            if s is not None and len(s) > MAX_VALUE:
                s, cut = s[:MAX_VALUE], True
                v[side + '_truncated'] = True
            v[side] = s
        values[k] = v
    allowed = sorted(allowed)
    extra = sorted(set(changed) - set(allowed))
    complete = len(changed) <= MAX_CHANGED and not cut
    result = 'STOP' if not complete else ('REFUSED' if extra else 'OK')
    return {'systemd': systemd, 'at': at, 'compared': len(set(p_before) | set(p_after)), 'changed': changed,
            'values': values, 'allowed': allowed, 'extra': extra, 'complete': complete, 'result': result}


def write_check(path, data):
    """Эксклюзивное создание, запись целиком, fsync файла и папки, перечитывание и сверка SHA-256.
    Возвращает код: '-' — записано и сверено; иначе имя ошибки (EEXIST, ENOSPC, …) или sha_mismatch."""
    want = hashlib.sha256(data).hexdigest()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        dfd = os.open(os.path.dirname(path) or '.', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            got = b''
            while True:
                part = os.read(fd, 65536)
                if not part:
                    break
                got += part
        finally:
            os.close(fd)
    except OSError as e:
        return errno.errorcode.get(e.errno, 'OSError')
    return '-' if hashlib.sha256(got).hexdigest() == want else 'sha_mismatch'


def log_line(doc, diag, code):
    """Строка п. 4: только результат, имена (безопасные, ≤40) и число; значения свойств — никогда."""
    names = [k if SAFE_NAME.fullmatch(k) else '?' for k in doc['changed'][:MAX_LOG_NAMES]]
    return (f"ZPROBE_DROPIN_CHECK result={doc['result']} diag={diag} code={code} n={len(doc['changed'])} "
            f"changed={','.join(names) or '-'}")


def emit(line):
    """Запись строки в журнал службы (stdout службы идёт в journald). False — запись не удалась."""
    try:
        data = (line + '\n').encode('ascii', 'replace')
        view = memoryview(data)
        while view:
            view = view[os.write(1, view):]
        return True
    except OSError:
        return False


def decide(p_before, p_after, allowed, systemd, at, path, writer=write_check, logger=emit):
    """Порядок п. 3–5: файл → строка журнала → решение. Возвращает словарь:
    proceed — можно к start; abort — причина Abort или None; exit_code — 75 при потере всех каналов;
    diag_status — OK или DIAGNOSTICS_INCOMPLETE (для evidence); code — ошибка записи или '-'; doc — документ."""
    doc = compare(p_before, p_after, allowed, systemd, at)
    code = writer(path, json.dumps(doc, sort_keys=True, ensure_ascii=True).encode('ascii'))
    wrote = code == '-'
    diag = 'OK' if wrote and doc['complete'] else 'INCOMPLETE'
    logged = logger(log_line(doc, diag, code))
    out = {'doc': doc, 'code': code, 'diag_status': 'OK' if wrote else 'DIAGNOSTICS_INCOMPLETE',
           'logged': logged, 'exit_code': None}
    if doc['result'] == 'STOP':
        out.update(proceed=False, abort='diag_overflow')
    elif doc['result'] == 'REFUSED':
        out.update(proceed=False, abort='dropin_changed_other_props')   # п. 5а: отказ остаётся отказом
    elif not wrote:
        out.update(proceed=False, abort='dropin_check_unwritten')       # допущение из шапки
    else:
        out.update(proceed=True, abort=None)
    if not wrote and not logged:
        out['exit_code'] = EXIT_DIAG_LOST                                # п. 5в: последний канал — код выхода
    return out
