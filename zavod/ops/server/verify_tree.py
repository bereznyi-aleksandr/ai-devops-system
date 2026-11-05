# ДОКУМЕНТ: zavod/ops/server/verify_tree.py
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-03 07:16 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-05 16:59 +02:00 (v0.2: карта 3.5.1, RISK_ARM64_3_4_1_v1_1 —
#   режим elf: отказ при программе (файл ELF) чужого процессора; Claude, сессия c28394bb-ae8a-47d6-aad3-111e08d58001;
#   v0.1 от 2026-11-03 07:16: аудит M3311-R2-01/02)
# ИСПОЛНИТЕЛЬ: Claude (сессии 2bf4a72a-0dfd-45e6-8828-338d117e688d, c28394bb-ae8a-47d6-aad3-111e08d58001)
# НАЗНАЧЕНИЕ: install_server.sh проверяет уже существующие папки сервера перед использованием (карта 3.3.11.4):
#   node ARCHIVE DIR — папка Node.js в точности равна закреплённому архиву: тот же список, типы, байты файлов, цели
#     ссылок и права (права архива без записи для группы и других — их снимает установщик);
#   closed DIR — папка выпуска: только обычные файлы и папки.
#   elf ARCH DIR… — каждая программа (файл ELF) в папках собрана для процессора ARCH (x64 — e_machine 62,
#     arm64 — e_machine 183); программа другого процессора на сервере не запустится или запустится не та — отказ.
#     Символические ссылки не открываются (их цели — внутри тех же папок или вне проверки).
#     В режиме elf владелец и права не проверяются (их проверяют node и closed).
#   В обоих случаях: каждый файл и папка принадлежат root:root, без записи для группы и других, у файлов нет
#   жёстких ссылок; путь к папке без символических ссылок, все папки выше принадлежат root и закрыты на запись.
#   Совпадение имени папки или номера версии доказательством неизменности не считается.
# ВЫЗОВ: python3 -I verify_tree.py node ARCHIVE DIR | closed DIR | elf x64|arm64 DIR…. Отказ — строка REFUSED: … и код 1.
# ОГРАНИЧЕНИЯ: только читает; ничего не создаёт и не меняет.
import hashlib
import os
import stat
import sys
import tarfile


def refuse(msg):
    print('REFUSED: ' + msg, file=sys.stderr)
    sys.exit(1)


def closed_path(top):
    if os.path.realpath(top) != top:
        refuse(top + ': path has a symbolic link')
    p = top
    while p != '/':
        p = os.path.dirname(p)
        st = os.lstat(p)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            refuse(p + ': directory above ' + top + ' is not root-owned and closed for writing')


def walk(top):
    """Опись папки: путь -> (тип, права, байты-сумма или цель ссылки); проверка владельца, записи, жёстких ссылок."""
    found = {}
    for d, dirs, files in os.walk(top):
        for n in dirs + files:
            full = os.path.join(d, n)
            rel = os.path.relpath(full, top)
            st = os.lstat(full)
            if st.st_uid != 0 or st.st_gid != 0:
                refuse(top + ': not owned by root:root: ' + rel)
            if stat.S_ISLNK(st.st_mode):
                found[rel] = ('l', None, os.readlink(full))
                continue
            if st.st_mode & 0o022:
                refuse(top + ': writable for group or others: ' + rel)
            if stat.S_ISDIR(st.st_mode):
                found[rel] = ('d', stat.S_IMODE(st.st_mode), None)
            elif stat.S_ISREG(st.st_mode):
                if st.st_nlink != 1:
                    refuse(top + ': hard link: ' + rel)
                h = hashlib.sha256()
                with open(full, 'rb') as f:
                    for b in iter(lambda: f.read(1 << 20), b''):
                        h.update(b)
                found[rel] = ('f', stat.S_IMODE(st.st_mode), h.hexdigest())
            else:
                refuse(top + ': not a regular file, directory or link: ' + rel)
    return found


def check_top(top):
    st = os.lstat(top)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_gid != 0 or stat.S_IMODE(st.st_mode) != 0o755:
        refuse(top + ': not a root:root 0755 directory')


def expected_node(archive):
    want = {}
    with tarfile.open(archive) as t:
        for m in t:
            rel = os.path.normpath(m.name.split('/', 1)[1]) if '/' in m.name.strip('/') else ''
            if rel in ('', '.'):
                continue
            # папки, которых нет в архиве отдельной записью, tar создаёт с правами 0755
            parts = rel.split('/')
            for i in range(1, len(parts)):
                want.setdefault('/'.join(parts[:i]), ('d', 0o755, None))
            mode = m.mode & 0o7755
            if m.isdir():
                want[rel] = ('d', mode, None)
            elif m.isreg():
                h = hashlib.sha256()
                f = t.extractfile(m)
                for b in iter(lambda: f.read(1 << 20), b''):
                    h.update(b)
                want[rel] = ('f', mode, h.hexdigest())
            elif m.issym():
                want[rel] = ('l', None, m.linkname)
            else:
                refuse(archive + ': unsupported member type: ' + m.name)
    return want


ELF_MACHINE = {'x64': 62, 'arm64': 183}


def elf_scan(arch, tops):
    want = ELF_MACHINE[arch]
    count = 0
    for top in tops:
        if not os.path.isdir(top) or os.path.islink(top):
            refuse(top + ': not a directory')
        for d, dirs, files in os.walk(top):
            for n in files:
                full = os.path.join(d, n)
                if not stat.S_ISREG(os.lstat(full).st_mode):
                    continue
                with open(full, 'rb') as f:
                    head = f.read(20)
                if len(head) < 20 or head[:4] != b'\x7fELF':
                    continue
                order = 'little' if head[5] == 1 else 'big' if head[5] == 2 else None
                if order is None:
                    refuse(full + ': ELF file with unknown byte order')
                machine = int.from_bytes(head[18:20], order)
                if machine != want:
                    refuse(full + ': program for another processor (e_machine ' + str(machine) + ', need '
                           + str(want) + ' for ' + arch + ')')
                count += 1
    print('ELF_ARCH=OK arch=' + arch + ' programs=' + str(count))


def main(argv):
    if len(argv) >= 3 and argv[0] == 'elf' and argv[1] in ELF_MACHINE:
        elf_scan(argv[1], argv[2:])
        return
    if len(argv) == 3 and argv[0] == 'node':
        archive, top = argv[1], argv[2]
    elif len(argv) == 2 and argv[0] == 'closed':
        archive, top = None, argv[1]
    else:
        refuse('usage: verify_tree.py node ARCHIVE DIR | closed DIR | elf x64|arm64 DIR...')
    closed_path(top)
    check_top(top)
    found = walk(top)
    if archive is None:
        links = sorted(p for p, v in found.items() if v[0] == 'l')
        if links:
            refuse(top + ': symbolic link: ' + links[0])
        print('RELEASE_TREE=OK dir=' + top + ' entries=' + str(len(found)))
        return
    want = expected_node(archive)
    missing = sorted(set(want) - set(found))
    if missing:
        refuse(top + ': missing from the node tree: ' + missing[0])
    extra = sorted(set(found) - set(want))
    if extra:
        refuse(top + ': not in the node archive: ' + extra[0])
    diff = sorted(p for p in want if want[p] != found[p])
    if diff:
        refuse(top + ': node tree differs from the archive: ' + diff[0])
    print('NODE_TREE=OK dir=' + top + ' entries=' + str(len(found)))


if __name__ == '__main__':
    main(sys.argv[1:])
