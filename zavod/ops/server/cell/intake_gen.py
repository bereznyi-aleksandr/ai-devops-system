# ДОКУМЕНТ: zavod/ops/server/cell/intake_gen.py
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 15:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 21:12 +02:00 (v0.2: случаи big и many для пробы раздела приёма, аудит M33-R2-04)
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: только для проверки в CI (карта 3.3.9.4, проба ПБ-4): делает архивы tar — правильный и испорченные
#   (ссылка, «..», устройство, двойники имён, «бомба», лишние данные и т. д.). Сервер Завода эту программу не ставит.
# ВЫЗОВ: python3 -I intake_gen.py CASE OUT.tar
import io
import sys
import tarfile

OK_FILES = [("src/a.py", b"print('zavod')\n"), ("src/sub/b.txt", b"hello\n"), ("tests/run.sh", b"#!/bin/sh\necho ok\n")]


def info(name, kind=tarfile.REGTYPE, size=0, mode=0o644, link=""):
    t = tarfile.TarInfo(name)
    t.type, t.size, t.mode, t.linkname, t.mtime = kind, size, mode, link, 1793520000
    t.uid = t.gid = 1000
    t.uname = t.gname = "agent"
    return t


def build(entries, fmt=tarfile.USTAR_FORMAT):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=fmt) as tf:
        for e in entries:
            if e[0] == "dir":
                tf.addfile(info(e[1], tarfile.DIRTYPE, mode=0o755))
            elif e[0] == "file":
                tf.addfile(info(e[1], size=len(e[2])), io.BytesIO(e[2]))
            else:
                tf.addfile(info(e[1], e[0], link=e[2] if len(e) > 2 else ""))
    return buf.getvalue()


def ok_entries():
    return [("dir", "src"), ("dir", "src/sub"), ("dir", "tests")] + [("file", n, d) for n, d in OK_FILES]


def raw_header(name, size):
    # заголовок с заявленным размером без данных — «бомба»: размер виден до чтения
    return info(name, size=size).tobuf(tarfile.USTAR_FORMAT, "utf-8", "surrogateescape")


def case(name):
    ok = ok_entries()
    if name == "ok":
        return build(ok)
    if name == "symlink":
        return build(ok + [(tarfile.SYMTYPE, "src/link", "/etc/passwd")])
    if name == "hardlink":
        return build(ok + [(tarfile.LNKTYPE, "src/h", "src/a.py")])
    if name == "chardev":
        return build(ok + [(tarfile.CHRTYPE, "src/dev")])
    if name == "fifo":
        return build(ok + [(tarfile.FIFOTYPE, "src/fifo")])
    if name == "dotdot":
        return build(ok + [("file", "src/../../etc/cron.d/x", b"x\n")])
    if name == "absolute":
        return build(ok + [("file", "/src/abs.txt", b"x\n")])
    if name == "outside":
        return build(ok + [("file", "docs/a.txt", b"x\n")])
    if name == "twin_case":
        return build(ok + [("file", "src/Readme.md", b"1\n"), ("file", "src/README.md", b"2\n")])
    if name == "twin_nfd":
        return build(ok + [("file", "src/café.txt", b"1\n"), ("file", "src/café.txt", b"2\n")])
    if name == "windows_name":
        return build(ok + [("file", "src/CON.txt", b"x\n")])
    if name == "control_char":
        return build(ok + [("file", "src/a\x01b.txt", b"x\n")])
    if name == "type_conflict":
        return build(ok + [("file", "src/x", b"1\n"), ("file", "src/x/y", b"2\n")])
    if name == "deep":
        return build(ok + [("file", "src/a/b/c/d.txt", b"x\n")])
    if name == "too_many":
        return build(ok + [("file", f"src/f{i}.txt", b"x\n") for i in range(8)])
    if name == "total_too_large":
        return build(ok + [("file", f"src/big{i}.bin", b"\1" * 30000) for i in range(3)])
    if name == "archive_too_large":
        return build(ok + [("file", "src/huge.bin", b"\2" * 400000)])
    if name == "bomb":
        # заголовок «8 ГБ» перед концом архива, данных нет
        body = build(ok)
        end = find_end(body)
        return body[:end] + raw_header("src/bomb.bin", 8 * 1024 ** 3 - 1) + body[end:end + 1024]
    if name == "gnu_format":
        return build(ok + [("file", "src/" + "n" * 120 + ".txt", b"x\n")], tarfile.GNU_FORMAT)
    if name == "pax_format":
        # заголовок pax ('x') tarfile пишет только для имён не из ASCII
        return build(ok + [("file", "src/é.txt", b"x\n")], tarfile.PAX_FORMAT)
    if name == "bad_checksum":
        b = bytearray(build(ok))
        b[1] ^= 0x01
        return bytes(b)
    if name == "trailing":
        return build(ok) + b"\x7f" * 512
    if name == "truncated":
        return build(ok)[:512 * 4 + 7]
    if name == "big":
        # 20 МБ в одном файле: несколько таких архивов заполняют учебный раздел приёма по месту
        return build(ok + [("file", "src/big.bin", b"\3" * (20 * 1024 ** 2))])
    if name == "many":
        # 2500 пустых файлов: исчерпывают учебный раздел приёма по числу inode
        return build([("dir", "src"), ("dir", "src/m")] + [("file", f"src/m/f{i:04d}", b"") for i in range(2500)])
    if name == "exec_missing":
        return build([e for e in ok if e[1] != "tests/run.sh"])
    raise SystemExit(f"unknown case {name}")


def find_end(data):
    # начало двух нулевых блоков конца архива (по границе 512)
    for off in range(0, len(data), 512):
        if data[off:off + 1024] == b"\0" * 1024:
            return off
    raise SystemExit("no end blocks")


if __name__ == "__main__":
    with open(sys.argv[2], "wb") as f:
        f.write(case(sys.argv[1]))
