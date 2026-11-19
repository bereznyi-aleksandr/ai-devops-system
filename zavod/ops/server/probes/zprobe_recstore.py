#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_recstore.py
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:57 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 13:06 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: B15, запись и чтение записей старта (I, Q, S, E), проект DECISION_B15_PUSH_AND_START часть C.
#   Писатель: (1) <имя>: O_CREAT|O_EXCL|O_NOFOLLOW итогового имени (без rename), строка данных +
#   «END len=<N> sha256=<X>», fsync файла, fsync папки; (2) <имя>.ok.part тем же способом со строкой
#   «OK sha256=<SHA-256 файла данных>», fsync файла, fsync папки; (3) жёсткая ссылка link(<имя>.ok.part, <имя>.ok) —
#   имя .ok появляется только у содержимого, уже сброшенного на диск; link не заменяет существующее имя (EEXIST);
#   (4) fsync папки. Любая ошибка — исключение, повтора нет. Файлы не удаляются и не заменяются (.ok.part остаётся).
#   Читатель: запись есть только при .ok с верной суммой и после барьера чтения — сам читатель делает fsync файла
#   данных, файла .ok и папки и лишь после их успеха отвечает «запись есть»; сбой барьера — CORRUPT (UNKNOWN).
#   Данные без .ok — PENDING (решает classify по состоянию службы); .ok без данных или с чужой суммой — CORRUPT.
# v0.2 (аудит REL154 M-355-REL154-02): в v0.1 имя .ok было видно до fsync его содержимого и папки — параллельный
#   --status мог ответить STARTED при ошибке записи. Теперь — шаги (2)–(4) и барьер чтения.
# ОГРАНИЧЕНИЯ: офлайн до AGREED. Сервер — Linux; на другой ОС fsync папки недоступен и писатель отказывает (кроме
#   тестов, которые подменяют операции через параметр ops). Барьер чтения не лечит потерю данных, о которой ядро уже
#   сообщило писателю (ошибка fsync у писателя): писатель тогда падает, служба кончается без E — итог
#   FAILED_AFTER_START или UNKNOWN, повтора нет.
import hashlib
import json
import os
import re

import zprobe_start_status as ST

_OK = re.compile(rb'OK sha256=([0-9a-f]{64})\n\Z')
_NOFOLLOW = getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_BINARY', 0)
_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW
_RFLAGS = os.O_RDONLY | _NOFOLLOW
MAX_BYTES = 65536


class Ops:
    """Операции ФС одной точкой: тесты подменяют их, чтобы проверить порядок шагов и отказ на каждом шаге."""
    def open(self, path, flags, mode=0o444):
        return os.open(path, flags, mode)

    def write_all(self, fd, data):
        view = memoryview(data)
        while view:
            n = os.write(fd, view)
            if n <= 0:
                raise OSError('short write')
            view = view[n:]

    def fsync(self, fd):
        os.fsync(fd)

    def close(self, fd):
        os.close(fd)

    def link(self, src, dst):
        os.link(src, dst)

    def fsync_dir(self, d):
        if os.name != 'posix':
            raise OSError('fsync of a directory needs Linux')
        fd = os.open(d, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_CLOEXEC', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def encode(rec):
    body = (json.dumps(rec, sort_keys=True, ensure_ascii=True) + '\n').encode()
    return body + f'END len={len(body)} sha256={hashlib.sha256(body).hexdigest()}\n'.encode()


def _put(d, name, data, ops):
    fd = ops.open(os.path.join(d, name), _FLAGS, 0o444)
    try:
        ops.write_all(fd, data)
        ops.fsync(fd)
    finally:
        ops.close(fd)
    ops.fsync_dir(d)


def write_record(d, name, rec, ops=None):
    """Шаги (1)–(4). Исключение на любом шаге: имени .ok нет или оно не сброшено — запись не считается сделанной."""
    ops = ops or Ops()
    if '/' in name or '\\' in name or name.startswith('.') or name.endswith(('.ok', '.part')):
        raise ValueError('bad record name')
    data = encode(rec)
    h = hashlib.sha256(data).hexdigest()
    _put(d, name, data, ops)
    _put(d, name + '.ok.part', f'OK sha256={h}\n'.encode(), ops)
    ops.link(os.path.join(d, name + '.ok.part'), os.path.join(d, name + '.ok'))
    ops.fsync_dir(d)
    return h


def _read(path):
    try:
        fd = os.open(path, _RFLAGS)
    except FileNotFoundError:
        return None
    except OSError:
        return ST.CORRUPT          # символьная ссылка (ELOOP) и прочее — не доверять
    try:
        chunks, total = [], 0
        while True:
            b = os.read(fd, 8192)
            if not b:
                break
            total += len(b)
            if total > MAX_BYTES:
                return ST.CORRUPT
            chunks.append(b)
        return b''.join(chunks)
    finally:
        os.close(fd)


def _barrier(d, names, ops):
    """fsync каждого файла (открыт только для чтения) и папки. True — всё сброшено на диск."""
    try:
        for n in names:
            fd = os.open(os.path.join(d, n), _RFLAGS)
            try:
                ops.fsync(fd)
            finally:
                os.close(fd)
        ops.fsync_dir(d)
        return True
    except OSError:
        return False


def read_record(d, name, kind, ops=None):
    """→ None (ни данных, ни .ok) | dict | ST.PENDING (данные без .ok) | ST.CORRUPT."""
    ops = ops or Ops()
    data, ok = _read(os.path.join(d, name)), _read(os.path.join(d, name + '.ok'))
    if ST.CORRUPT in (data, ok):
        return ST.CORRUPT
    if data is None:
        return None if ok is None else ST.CORRUPT
    if ok is None:
        return ST.PENDING          # и обрезанные данные: писатель мог упасть до .ok — это не порча, а «ещё нет»
    m = _OK.match(ok)
    if not m or m.group(1) != hashlib.sha256(data).hexdigest().encode():
        return ST.CORRUPT
    rec = ST.parse_record(kind, data)
    if rec == ST.CORRUPT:
        return ST.CORRUPT
    if not _barrier(d, (name, name + '.ok'), ops):
        return ST.CORRUPT
    return rec
