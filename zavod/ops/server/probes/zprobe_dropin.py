#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_dropin.py
# ВЕРСИЯ: v0.2 (B13)  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 12:44 +02:00
# v0.2 (Claude, терминал zavod; B13, REL123 REVISE M-355-REL123-01, L-355-REL123-01): ОДНО смысловое сравнение для всех
#   потребителей. Свойства-наборы systemd 255 (SET_PROPS, закрытый список) сравниваются как наборы: только перестановка —
#   «reordered», не изменение; дубликат или неразборчивый элемент — «unparsed» → STOP. MemoryAvailable (RUNTIME_PROPS) —
#   замер: оба значения число/infinity → «runtime», иначе изменение. Всё прочее — строгое сравнение строк, как в v0.1.
#   В документе: raw_changed (все строковые отличия, для разбора), changed (смысловые), reordered, runtime, unparsed,
#   stop_reason, rule. Значения пишутся для ВСЕХ raw_changed (обрезка любого → STOP, как в v0.1).
#   Порядок файл → журнал → решение и код 75 — без изменений.
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
RULE = 'B13.v0.2'
# systemd 255, org.freedesktop.systemd1.Unit: зависимости (тип «as» — список имён юнитов) и RequiresMountsFor (список путей).
# `systemctl show` печатает их через пробел в порядке внутренней хеш-таблицы — порядок не значим (man systemd.unit 255,
# раздел [Unit]). Командных свойств (ExecStart*, ExecCondition и т. п.) и ограничений здесь НЕТ: их порядок и значения важны.
SET_PROPS = frozenset({
    'Requires', 'Requisite', 'Wants', 'BindsTo', 'PartOf', 'Upholds',
    'RequiredBy', 'RequisiteOf', 'WantedBy', 'BoundBy', 'UpheldBy', 'ConsistsOf',
    'Conflicts', 'ConflictedBy', 'Before', 'After',
    'OnFailure', 'OnFailureOf', 'OnSuccess', 'OnSuccessOf',
    'Triggers', 'TriggeredBy', 'PropagatesReloadTo', 'ReloadPropagatedFrom',
    'PropagatesStopTo', 'StopPropagatedFrom', 'JoinsNamespaceOf', 'RequiresMountsFor'})
RUNTIME_PROPS = frozenset({'MemoryAvailable'})   # замер ядра, меняется сам (CI 44282558463: и без дополнения)
SET_TOKEN = re.compile(r'[A-Za-z0-9@._:/\\-]{1,255}')
RUNTIME_VALUE = re.compile(r'[0-9]{1,20}|infinity')
assert not (SET_PROPS | RUNTIME_PROPS) & {'ExecStart', 'ExecStartEx', 'DropInPaths'}
assert not any(SENSITIVE.search(k) for k in SET_PROPS | RUNTIME_PROPS)


def _tokens(s):
    """Элементы набора или None — неразборчиво (чужие знаки, дубликат)."""
    t = s.split()
    if any(not SET_TOKEN.fullmatch(x) for x in t) or len(set(t)) != len(t):
        return None
    return t


def classify(k, b, a):
    """Класс отличия одного свойства: same | reordered | runtime | unparsed | changed.
    Появление или пропажа свойства (None с одной стороны) — всегда changed."""
    if b == a:
        return 'same'
    if b is None or a is None:
        return 'changed'
    if k in SET_PROPS:
        tb, ta = _tokens(b), _tokens(a)
        if tb is None or ta is None:
            return 'unparsed'
        return 'reordered' if sorted(tb) == sorted(ta) else 'changed'
    if k in RUNTIME_PROPS:
        return 'runtime' if RUNTIME_VALUE.fullmatch(b) and RUNTIME_VALUE.fullmatch(a) else 'changed'
    return 'changed'


def compare(p_before, p_after, allowed, systemd, at):
    """Документ dropin_check.json (B10 п. 3 + B13). Значения чувствительных имён не хранятся и не хешируются.
    allowed — только ключи самого дополнения (DROPIN_KEYS); замеры и перестановки сюда НЕ добавляются."""
    raw = sorted(k for k in set(p_before) | set(p_after) if p_before.get(k) != p_after.get(k))
    cls = {k: classify(k, p_before.get(k), p_after.get(k)) for k in raw}
    changed = [k for k in raw if cls[k] == 'changed']
    values, cut = {}, False
    for k in raw[:MAX_CHANGED]:
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
    unparsed = [k for k in raw if cls[k] == 'unparsed']
    complete = len(raw) <= MAX_CHANGED and not cut
    stop = 'overflow' if not complete else ('unparsed' if unparsed else None)
    result = 'STOP' if stop else ('REFUSED' if extra else 'OK')
    return {'rule': RULE, 'systemd': systemd, 'at': at, 'compared': len(set(p_before) | set(p_after)),
            'raw_changed': raw, 'changed': changed,
            'reordered': [k for k in raw if cls[k] == 'reordered'], 'runtime': [k for k in raw if cls[k] == 'runtime'],
            'unparsed': unparsed, 'values': values, 'allowed': allowed, 'extra': extra, 'complete': complete,
            'stop_reason': stop, 'result': result}


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
    def names(xs):
        return ','.join(k if SAFE_NAME.fullmatch(k) else '?' for k in xs[:MAX_LOG_NAMES]) or '-'
    return (f"ZPROBE_DROPIN_CHECK result={doc['result']} diag={diag} code={code} n={len(doc['changed'])} "
            f"changed={names(doc['changed'])} raw={len(doc['raw_changed'])} reordered={names(doc['reordered'])} "
            f"runtime={names(doc['runtime'])} unparsed={names(doc['unparsed'])}")


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
        out.update(proceed=False, abort='diag_overflow' if doc['stop_reason'] == 'overflow' else 'dropin_props_unparsed')
    elif doc['result'] == 'REFUSED':
        out.update(proceed=False, abort='dropin_changed_other_props')   # п. 5а: отказ остаётся отказом
    elif not wrote:
        out.update(proceed=False, abort='dropin_check_unwritten')       # допущение из шапки
    else:
        out.update(proceed=True, abort=None)
    if not wrote and not logged:
        out['exit_code'] = EXIT_DIAG_LOST                                # п. 5в: последний канал — код выхода
    return out
