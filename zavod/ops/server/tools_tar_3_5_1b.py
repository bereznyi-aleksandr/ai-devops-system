#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/server/tools_tar_3_5_1b.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-06 12:14 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сессия bb50840e-710a-4bb9-84b8-a44d1a8ea411)
# НАЗНАЧЕНИЕ: шаг 3.5.1б карты Завода v3.1 — распаковка закреплённого архива npm (.tgz) с программой без npm и без
#   сценариев установки, и опись (список файлов с суммами) для сверки.
#   list TGZ        — проверяет архив и печатает его опись, ничего не пишет;
#   unpack TGZ DEST — DEST не должно быть, папка выше — есть; создаёт DEST (0755) и пишет файлы; печатает опись;
#   inventory DEST  — печатает опись готовой папки и отказывает при чём-то лишнем.
#   Опись: строки «sha256  mode  путь» (mode 644 или 755; папки — «-  755  путь/»), по алфавиту пути.
#   В архиве разрешены только обычные файлы и папки под «package/»; ссылки, устройства, «..», абсолютные пути,
#   двойники имён, пустые имена — отказ. Права приводятся к 0755/0644 (нет бита запуска — 0644), владельцем
#   остаётся тот, кто запустил (root); setuid и прочие особые биты не переносятся.
#   inventory: только обычные файлы и папки; без ссылок; у файла одна жёсткая ссылка; владелец root:root;
#   права ровно 0755/0644, у папок 0755.
# ВЫЗОВ: python3 -I tools_tar_3_5_1b.py list|unpack|inventory … Отказ — строка REFUSED: … и код 1.
# ОГРАНИЧЕНИЯ: ничего не удаляет и не перезаписывает (файлы создаются с O_EXCL, папки — mkdir без замены).
import hashlib
import os
import stat
import sys
import tarfile

PREFIX = 'package/'
CHUNK = 1 << 20


def refuse(msg):
    print('REFUSED: ' + msg, file=sys.stderr)
    sys.exit(1)


def clean_name(name):
    if not name.startswith(PREFIX):
        refuse('member outside package/: ' + repr(name))
    rel = name[len(PREFIX):].rstrip('/')
    if rel == '':
        return ''
    parts = rel.split('/')
    for p in parts:
        if p in ('', '.', '..') or '\0' in p or '\\' in p:
            refuse('bad member name: ' + repr(name))
    return rel


def members(tgz):
    seen = set()
    with tarfile.open(tgz, 'r:gz') as t:
        for m in t:
            rel = clean_name(m.name)
            if rel == '':
                if not m.isdir():
                    refuse('package/ is not a directory')
                continue
            if rel in seen:
                refuse('duplicate member: ' + rel)
            seen.add(rel)
            if m.isdir():
                yield t, m, rel, 'd'
            elif m.isreg():
                yield t, m, rel, 'f'
            else:
                refuse('not a regular file or directory: ' + rel)


def mode_of(m):
    return 0o755 if m.mode & 0o111 else 0o644


def line(kind, rel, mode, digest=None):
    if kind == 'd':
        return f'-  755  {rel}/'
    return f'{digest}  {mode:o}  {rel}'


def parents(rel):
    parts = rel.split('/')[:-1]
    return ['/'.join(parts[:i]) for i in range(1, len(parts) + 1)]


def finish(lines, dirs_named):
    # Папки, которые в архиве не названы, но нужны для файлов, тоже входят в опись: опись папки их увидит.
    for d in sorted(dirs_named):
        lines.add(line('d', d, 0o755))
    for x in sorted(lines, key=lambda s: s.split('  ', 2)[2]):
        print(x)


def do_list(tgz):
    lines, dirs = set(), set()
    for t, m, rel, kind in members(tgz):
        dirs.update(parents(rel))
        if kind == 'd':
            dirs.add(rel)
            continue
        h = hashlib.sha256()
        f = t.extractfile(m)
        n = 0
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
            n += len(b)
        if n != m.size:
            refuse('short member: ' + rel)
        lines.add(line('f', rel, mode_of(m), h.hexdigest()))
    finish(lines, dirs)


def do_unpack(tgz, dest):
    if os.path.lexists(dest):
        refuse(dest + ' already exists: nothing unpacked')
    parent = os.path.dirname(os.path.abspath(dest))
    if not os.path.isdir(parent) or os.path.islink(parent):
        refuse(parent + ' is not a directory')
    # Сначала весь архив проверяется по именам и видам записей (без записи на диск): отказ — папка не создаётся.
    for _t, _m, _rel, _kind in members(tgz):
        pass
    old = os.umask(0o022)
    try:
        os.mkdir(dest, 0o755)
        lines, dirs = set(), set()
        for t, m, rel, kind in members(tgz):
            for d in parents(rel) + ([rel] if kind == 'd' else []):
                if d not in dirs:
                    p = os.path.join(dest, d)
                    if os.path.lexists(p):
                        if not (os.path.isdir(p) and not os.path.islink(p)):
                            refuse('not a directory in the way: ' + d)
                    else:
                        os.mkdir(p, 0o755)
                    dirs.add(d)
            if kind == 'd':
                continue
            mode = mode_of(m)
            p = os.path.join(dest, rel)
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            h = hashlib.sha256()
            n = 0
            with os.fdopen(fd, 'wb') as out:
                f = t.extractfile(m)
                while True:
                    b = f.read(CHUNK)
                    if not b:
                        break
                    h.update(b)
                    out.write(b)
                    n += len(b)
            if n != m.size:
                refuse('short member: ' + rel)
            os.chmod(p, mode, follow_symlinks=False)
            lines.add(line('f', rel, mode, h.hexdigest()))
        for d in dirs:
            os.chmod(os.path.join(dest, d), 0o755, follow_symlinks=False)
        finish(lines, dirs)
    finally:
        os.umask(old)


def do_inventory(top):
    st = os.lstat(top)
    if not stat.S_ISDIR(st.st_mode):
        refuse(top + ': not a directory')
    if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (0, 0, 0o755):
        refuse(top + ': not root:root 0755')
    lines, dirs = set(), set()
    for d, dns, fns in os.walk(top):
        dns.sort()
        for n in dns + fns:
            full = os.path.join(d, n)
            rel = os.path.relpath(full, top).replace(os.sep, '/')
            s = os.lstat(full)
            if (s.st_uid, s.st_gid) != (0, 0):
                refuse(top + ': not root:root: ' + rel)
            if stat.S_ISDIR(s.st_mode):
                if stat.S_IMODE(s.st_mode) != 0o755:
                    refuse(top + ': directory mode is not 755: ' + rel)
                dirs.add(rel)
            elif stat.S_ISREG(s.st_mode):
                mode = stat.S_IMODE(s.st_mode)
                if mode not in (0o755, 0o644):
                    refuse(top + f': file mode {mode:o} is not 755 or 644: ' + rel)
                if s.st_nlink != 1:
                    refuse(top + ': hard link: ' + rel)
                h = hashlib.sha256()
                with open(full, 'rb') as f:
                    while True:
                        b = f.read(CHUNK)
                        if not b:
                            break
                        h.update(b)
                lines.add(line('f', rel, mode, h.hexdigest()))
            else:
                refuse(top + ': not a regular file or directory: ' + rel)
    finish(lines, dirs)


def main(argv):
    if len(argv) == 2 and argv[0] == 'list':
        do_list(argv[1])
    elif len(argv) == 3 and argv[0] == 'unpack':
        do_unpack(argv[1], argv[2])
    elif len(argv) == 2 and argv[0] == 'inventory':
        do_inventory(argv[1])
    else:
        refuse('usage: tools_tar_3_5_1b.py list TGZ | unpack TGZ DEST | inventory DEST')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
