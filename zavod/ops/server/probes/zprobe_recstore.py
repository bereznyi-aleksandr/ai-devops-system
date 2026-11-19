#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_recstore.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:57 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 12:57 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: B15, запись и чтение записей старта (I, Q, S, E) по проекту DECISION_B15_PUSH_AND_START v0.4 часть C
#   (на аудите ChatGPT REL154): файл данных <имя> и признак готовности <имя>.ok, который появляется только после
#   fsync данных и папки. Писатель: O_CREAT|O_EXCL|O_NOFOLLOW итогового имени (без rename), строка данных +
#   «END len=<N> sha256=<X>», fsync файла, fsync папки; затем <имя>.ok «OK sha256=<SHA-256 файла данных>» тем же
#   способом. Любая ошибка — исключение, .ok не создаётся, повтора нет. Читатель: запись есть только при .ok с верной
#   суммой; данные без .ok — PENDING (решает classify по состоянию службы); .ok без данных или с чужой суммой — CORRUPT.
# ОГРАНИЧЕНИЯ: офлайн до AGREED REL154. Сервер — Linux; на другой ОС fsync папки недоступен и писатель отказывает
#   (кроме тестов, которые подменяют операции через параметр ops).
import hashlib
import json
import os
import re

import zprobe_start_status as ST

_OK = re.compile(rb'OK sha256=([0-9a-f]{64})\n\Z')
_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
_RFLAGS = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
MAX_BYTES = 65536


class Ops:
    """Операции ФС одной точкой: тесты подменяют fsync и fsync_dir, чтобы проверить отказ на каждом шаге."""
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
    """Шаг 1 — данные, шаг 2 — .ok. Исключение на любом шаге: .ok нет (запись не считается сделанной)."""
    ops = ops or Ops()
    if '/' in name or name.startswith('.') or name.endswith('.ok'):
        raise ValueError('bad record name')
    data = encode(rec)
    _put(d, name, data, ops)
    _put(d, name + '.ok', f'OK sha256={hashlib.sha256(data).hexdigest()}\n'.encode(), ops)
    return hashlib.sha256(data).hexdigest()


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


def read_record(d, name, kind):
    """→ None (ни данных, ни .ok) | dict | ST.PENDING (данные без .ok) | ST.CORRUPT."""
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
    return ST.parse_record(kind, data)
