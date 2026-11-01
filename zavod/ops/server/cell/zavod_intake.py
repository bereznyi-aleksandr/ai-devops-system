# ДОКУМЕНТ: zavod/ops/server/cell/zavod_intake.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 15:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 15:33 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# ОСНОВАНИЕ: протокол v3.1, И.12г (опись ядра и карантин), И.12д (доверенный приём), Л.44 (правило имён),
#   Л.22–Л.23 (zquarantine, zimport); карта 3.3.9.1–3.3.9.3.
# Python 3, только стандартная библиотека; запуск всегда с ключом -I (одна программа: соседние модули не грузятся).
# РЕЖИМЫ:
#   manifest-check LEASE        — строгая проверка описи ядра manifest/LEASE.json (лишнее поле — отказ);
#   quarantine LEASE            — от zquarantine: свой разбор in/LEASE.tar (только ustar), пределы во время чтения,
#                                 файлы в out/LEASE.partial/files, report.json последним, затем перенос в out/LEASE;
#   import LEASE [--no-openat2] — от zimport: после остановки карантина; openat2 (RESOLVE_BENEATH | NO_SYMLINKS |
#                                 NO_MAGICLINKS | NO_XDEV) или пошагово с O_NOFOLLOW; копия, сумма по копии,
#                                 сверка с отчётом и описью, права по описи, один перенос в accepted/LEASE;
#   archive LEASE STAGE         — от root (ExecStopPost=+): in/ и out/ этой аренды — в archive/, ничего не удаляет.
# Отказ — код 2 и строка «ZAVOD_INTAKE <режим> <аренда> REFUSED <причина>»; приём — код 0 и ACCEPTED.
# Каждый итог пишется ещё и в журнал JSONL своей учётной записи (journal/quarantine, journal/import).
import ctypes
import errno
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import time
import unicodedata

BASE = "/var/lib/zavod/intake"
LEASE_RE = re.compile(r"[0-9a-f]{32}")
MANIFEST_KEYS = {"v", "lease", "dirs", "max_files", "max_bytes", "max_file_bytes", "max_depth", "exec"}
REPORT_KEYS = {"v", "lease", "files"}
FILE_KEYS = {"path", "size", "sha256", "exec"}
CAP_FILES = 100_000
CAP_BYTES = 4 * 1024 ** 3
CAP_DEPTH = 32
CAP_DIRS = 32
CAP_JSON = 64 * 1024 * 1024
CHUNK = 1024 * 1024

# Правило имён Л.44 — тот же код, что promote/zavod_tree_policy.py v1.0 (учебный эталон).
FORBIDDEN_CHARS = set('<>:"/\\|?*')
IGNORABLE = [(0x00AD, 0x00AD), (0x034F, 0x034F), (0x061C, 0x061C), (0x115F, 0x1160), (0x17B4, 0x17B5),
             (0x180B, 0x180F), (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x206F), (0x3164, 0x3164),
             (0xFE00, 0xFE0F), (0xFEFF, 0xFEFF), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8), (0x1BCA0, 0x1BCA3),
             (0x1D173, 0x1D17A), (0xE0000, 0xE0FFF)]
BAD_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}
RESERVED = {"con", "prn", "aux", "nul", "conin$", "conout$"}
RESERVED |= {p + d for p in ("com", "lpt") for d in "0123456789¹²³"}

# Виды записей tar (POSIX ustar): только '0' / NUL — файл и '5' — папка; остальное — отказ всего архива.
TAR_TYPES = {b"1": "HARDLINK", b"2": "SYMLINK", b"3": "CHAR_DEVICE", b"4": "BLOCK_DEVICE", b"6": "FIFO",
             b"7": "CONTIGUOUS", b"x": "PAX_HEADER", b"g": "PAX_HEADER", b"L": "GNU_LONGNAME",
             b"K": "GNU_LONGNAME", b"S": "SPARSE", b"V": "GNU_VOLUME", b"M": "GNU_MULTIVOL"}

RESOLVE_ALL = 0x01 | 0x02 | 0x04 | 0x08  # NO_XDEV | NO_MAGICLINKS | NO_SYMLINKS | BENEATH
SYS_OPENAT2 = 437
RENAME_NOREPLACE = 1
LIBC = ctypes.CDLL(None, use_errno=True)
CALLS = {"openat2": 0, "fallback": 0}


class Refuse(Exception):
    pass


def key(name):
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", name).casefold())


def invisible(ch):
    o = ord(ch)
    if unicodedata.category(ch) in BAD_CATEGORIES:
        return True
    if unicodedata.category(ch) == "Zs" and ch != " ":
        return True
    return any(a <= o <= b for a, b in IGNORABLE)


def check_component(c):
    if c in ("", ".", ".."):
        raise Refuse("BAD_PATH_DOT_OR_EMPTY")
    for ch in c:
        if invisible(ch):
            raise Refuse("BAD_NAME_CONTROL_CHAR")
        if ch in FORBIDDEN_CHARS:
            raise Refuse("BAD_NAME_WINDOWS_CHAR")
    if c[-1] in ". ":
        raise Refuse("BAD_NAME_TRAILING_DOT_OR_SPACE")
    if key(c.split(".")[0].rstrip(" ")) in RESERVED:
        raise Refuse("BAD_NAME_WINDOWS_RESERVED")
    if key(c) == ".git" or key(c).startswith("git~"):
        raise Refuse("BAD_NAME_GIT")


def split_path(p, max_depth):
    if not isinstance(p, str) or not p or len(p.encode("utf-8", "surrogatepass")) > 4096:
        raise Refuse("BAD_PATH")
    if p.startswith("/"):
        raise Refuse("BAD_PATH_ABSOLUTE")
    parts = p.split("/")
    if ".." in parts:
        raise Refuse("BAD_PATH_DOTDOT")
    for c in parts:
        check_component(c)
    if len(parts) > max_depth:
        raise Refuse("TOO_DEEP")
    return parts


def path_key(parts):
    return "/".join(key(c) for c in parts)


def inside_dirs(p, is_dir, dirs):
    if any(p.startswith(d) for d in dirs):
        return True
    # папка-предок одной из разрешённых (например, «src» для «src/») допустима
    return is_dir and any(d.startswith(p + "/") for d in dirs)


def strict_json(data, what):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise Refuse(what + "_DUPLICATE_KEY")
            d[k] = v
        return d

    def no_const(_):
        raise Refuse(what + "_BAD_NUMBER")

    try:
        text = data.decode("utf-8", "strict")
        return json.loads(text, object_pairs_hook=pairs, parse_constant=no_const, parse_float=no_const)
    except Refuse:
        raise
    except (UnicodeDecodeError, ValueError):
        raise Refuse(what + "_NOT_JSON")


def is_int(v):
    return type(v) is int


def uid_of(name):
    return pwd.getpwnam(name).pw_uid


def read_owned_file(path, owner, limit, what):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        raise Refuse(what + "_MISSING")
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise Refuse(what + "_SYMLINK")
        raise
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise Refuse(what + "_NOT_REGULAR")
        if st.st_uid != uid_of(owner) or st.st_mode & 0o022:
            raise Refuse(what + "_BAD_OWNER")
        if st.st_size > limit:
            raise Refuse(what + "_TOO_LARGE")
        data = b""
        while len(data) <= limit:
            b = os.read(fd, CHUNK)
            if not b:
                break
            data += b
        if len(data) > limit:
            raise Refuse(what + "_TOO_LARGE")
        return data
    finally:
        os.close(fd)


def load_manifest(lease):
    m = strict_json(read_owned_file(f"{BASE}/manifest/{lease}.json", "zkernel", 1024 * 1024, "MANIFEST"),
                    "MANIFEST")
    if not isinstance(m, dict) or set(m) != MANIFEST_KEYS:
        raise Refuse("MANIFEST_FIELDS")
    if not is_int(m["v"]) or m["v"] != 1:
        raise Refuse("MANIFEST_VERSION")
    if m["lease"] != lease:
        raise Refuse("MANIFEST_LEASE")
    for k, cap in (("max_files", CAP_FILES), ("max_bytes", CAP_BYTES), ("max_depth", CAP_DEPTH)):
        if not is_int(m[k]) or not 1 <= m[k] <= cap:
            raise Refuse("MANIFEST_LIMIT_" + k.upper())
    if not is_int(m["max_file_bytes"]) or not 1 <= m["max_file_bytes"] <= m["max_bytes"]:
        raise Refuse("MANIFEST_LIMIT_MAX_FILE_BYTES")
    dirs = m["dirs"]
    if not isinstance(dirs, list) or not 1 <= len(dirs) <= CAP_DIRS or len(set(map(str, dirs))) != len(dirs):
        raise Refuse("MANIFEST_DIRS")
    for d in dirs:
        if not isinstance(d, str) or not d.endswith("/"):
            raise Refuse("MANIFEST_DIRS")
        split_path(d[:-1], m["max_depth"])
    ex = m["exec"]
    if not isinstance(ex, list) or len(ex) > m["max_files"] or len(set(map(str, ex))) != len(ex):
        raise Refuse("MANIFEST_EXEC")
    for p in ex:
        split_path(p, m["max_depth"])
        if not inside_dirs(p, False, dirs):
            raise Refuse("MANIFEST_EXEC_OUTSIDE_DIRS")
    return m


# ---------- журнал ----------

def journal(sub, lease, result, reason, **extra):
    print(f"ZAVOD_INTAKE {sub} {lease} {result} {reason}", flush=True)
    jdir = {"quarantine": "quarantine", "import": "import"}.get(sub)
    if not jdir:
        return
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stage": sub, "lease": lease,
           "result": result, "reason": reason, **extra}
    line = (json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    fd = os.open(f"{BASE}/journal/{jdir}/{sub}.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW
                 | os.O_CLOEXEC, 0o640)
    try:
        os.write(fd, line)
        os.fsync(fd)
    finally:
        os.close(fd)


# ---------- карантин ----------

def read_exact(fd, n):
    buf = b""
    while len(buf) < n:
        b = os.read(fd, n - len(buf))
        if not b:
            raise Refuse("ARCHIVE_TRUNCATED")
        buf += b
    return buf


def octal(field, what):
    if field[:1] and field[0] & 0x80:
        raise Refuse("ARCHIVE_BASE256_" + what)
    s = field.split(b"\0", 1)[0].strip(b" ")
    if not s or any(c not in b"01234567" for c in s):
        raise Refuse("ARCHIVE_BAD_NUMBER_" + what)
    return int(s, 8)


def cstr(field):
    return field.split(b"\0", 1)[0]


def mkdirs(root_fd, parts, created):
    # папки создаёт только эта программа в своей новой папке; повторное открытие — без перехода по ссылкам
    fd = os.dup(root_fd)
    try:
        for i, c in enumerate(parts):
            if (root_fd, tuple(parts[:i + 1])) not in created:
                try:
                    os.mkdir(c, 0o750, dir_fd=fd)
                except FileExistsError:
                    pass
                created.add((root_fd, tuple(parts[:i + 1])))
            nfd = os.open(c, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = nfd
        return fd
    except BaseException:
        os.close(fd)
        raise


def quarantine(lease):
    if os.geteuid() != uid_of("zquarantine"):
        raise Refuse("NOT_ZQUARANTINE")
    m = load_manifest(lease)
    dirs, ex = m["dirs"], set(m["exec"])
    out_fd = os.open(f"{BASE}/out", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    for name in (lease, lease + ".partial"):
        try:
            os.lstat(name, dir_fd=out_fd)
            raise Refuse("OUT_EXISTS")
        except FileNotFoundError:
            pass
    try:
        tfd = os.open(f"{BASE}/in/{lease}.tar", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        raise Refuse("ARCHIVE_MISSING")
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise Refuse("ARCHIVE_SYMLINK")
        raise
    st = os.fstat(tfd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != uid_of("zgate"):
        raise Refuse("ARCHIVE_NOT_REGULAR")
    limit = m["max_bytes"] + 1024 * (2 * m["max_files"] + 64) + 20480
    if st.st_size > limit:
        raise Refuse("ARCHIVE_TOO_LARGE")
    os.mkdir(lease + ".partial", 0o750, dir_fd=out_fd)
    pfd = os.open(lease + ".partial", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=out_fd)
    os.mkdir("files", 0o750, dir_fd=pfd)
    ffd = os.open("files", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=pfd)
    seen, file_keys, ancestor_keys, created = {}, set(), set(), set()
    files, total, entries, consumed = [], 0, 0, 0
    max_entries = 2 * m["max_files"] + 64
    while True:
        # читаем не дальше размера, снятого при открытии: дописанное после этого не разбирается
        if consumed + 512 > st.st_size:
            raise Refuse("ARCHIVE_TRUNCATED")
        hdr = read_exact(tfd, 512)
        consumed += 512
        if hdr == b"\0" * 512:
            if consumed + 512 > st.st_size or read_exact(tfd, 512) != b"\0" * 512:
                raise Refuse("ARCHIVE_BAD_END")
            consumed += 512
            rest = st.st_size - consumed
            if rest > 10240 or rest % 512:
                raise Refuse("ARCHIVE_TRAILING_DATA")
            if rest and any(read_exact(tfd, rest)):
                raise Refuse("ARCHIVE_TRAILING_DATA")
            break
        entries += 1
        if entries > max_entries:
            raise Refuse("TOO_MANY_ENTRIES")
        if hdr[257:265] != b"ustar\x0000":
            raise Refuse("ARCHIVE_NOT_USTAR")
        if octal(hdr[148:156], "CHECKSUM") != sum(hdr[:148]) + 8 * 32 + sum(hdr[156:]):
            raise Refuse("ARCHIVE_BAD_CHECKSUM")
        tf = hdr[156:157]
        if tf in TAR_TYPES:
            raise Refuse("ENTRY_" + TAR_TYPES[tf])
        if tf not in (b"0", b"\0", b"5"):
            raise Refuse("ENTRY_UNSUPPORTED_TYPE")
        is_dir = tf == b"5"
        size = octal(hdr[124:136], "SIZE")
        if cstr(hdr[157:257]):
            raise Refuse("ENTRY_LINKNAME")
        name, prefix = cstr(hdr[0:100]), cstr(hdr[345:500])
        raw = prefix + b"/" + name if prefix else name
        try:
            p = raw.decode("utf-8", "strict")
        except UnicodeDecodeError:
            raise Refuse("BAD_NAME_NOT_UTF8")
        if is_dir:
            if size:
                raise Refuse("ENTRY_DIR_WITH_DATA")
            if p.endswith("/"):
                p = p[:-1]
        elif p.endswith("/"):
            raise Refuse("BAD_PATH")
        parts = split_path(p, m["max_depth"])
        if not inside_dirs(p, is_dir, dirs):
            raise Refuse("PATH_OUTSIDE_DIRS")
        k = path_key(parts)
        if k in seen:
            raise Refuse("NAME_TWIN")
        for i in range(1, len(parts)):
            if "/".join(key(c) for c in parts[:i]) in file_keys:
                raise Refuse("TYPE_CONFLICT")
        if not is_dir and k in ancestor_keys:
            raise Refuse("TYPE_CONFLICT")
        seen[k] = is_dir
        for i in range(1, len(parts)):
            ancestor_keys.add("/".join(key(c) for c in parts[:i]))
        if is_dir:
            os.close(mkdirs(ffd, parts, created))
            continue
        if len(files) + 1 > m["max_files"]:
            raise Refuse("TOO_MANY_FILES")
        if size > m["max_file_bytes"]:
            raise Refuse("FILE_TOO_LARGE")
        if total + size > m["max_bytes"]:
            raise Refuse("TOTAL_TOO_LARGE")
        if consumed + size > st.st_size:
            raise Refuse("ARCHIVE_TRUNCATED")
        file_keys.add(k)
        dfd = mkdirs(ffd, parts[:-1], created)
        try:
            wfd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o640,
                          dir_fd=dfd)
        finally:
            os.close(dfd)
        h, left = hashlib.sha256(), size
        try:
            while left:
                b = read_exact(tfd, min(CHUNK, left))
                h.update(b)
                os.write(wfd, b)
                left -= len(b)
            os.fsync(wfd)
        finally:
            os.close(wfd)
        consumed += size
        pad = (512 - size % 512) % 512
        if pad:
            read_exact(tfd, pad)
            consumed += pad
        total += size
        files.append({"path": p, "size": size, "sha256": h.hexdigest(), "exec": p in ex})
    os.close(tfd)
    got = {f["path"] for f in files}
    if not ex <= got:
        raise Refuse("EXEC_FILE_MISSING")
    files.sort(key=lambda f: f["path"].encode())
    report = (json.dumps({"v": 1, "lease": lease, "files": files}, ensure_ascii=False, separators=(",", ":"))
              + "\n").encode()
    rfd = os.open("report.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o640,
                  dir_fd=pfd)
    try:
        os.write(rfd, report)
        os.fsync(rfd)
    finally:
        os.close(rfd)
    os.fsync(pfd)
    rename_noreplace(out_fd, lease + ".partial", out_fd, lease)
    os.fsync(out_fd)
    return len(files), total


def rename_noreplace(sfd, src, dfd, dst):
    if LIBC.renameat2(sfd, src.encode(), dfd, dst.encode(), RENAME_NOREPLACE) != 0:
        e = ctypes.get_errno()
        if e == errno.EEXIST:
            raise Refuse("TARGET_EXISTS")
        raise OSError(e, os.strerror(e))


# ---------- приём ----------

class OpenHow(ctypes.Structure):
    _fields_ = [("flags", ctypes.c_uint64), ("mode", ctypes.c_uint64), ("resolve", ctypes.c_uint64)]


def open_beneath(dirfd, rel, flags, use_openat2):
    if use_openat2:
        how = OpenHow(flags | os.O_CLOEXEC | os.O_NOFOLLOW, 0, RESOLVE_ALL)
        LIBC.syscall.restype = ctypes.c_long
        fd = LIBC.syscall(ctypes.c_long(SYS_OPENAT2), ctypes.c_int(dirfd), ctypes.c_char_p(rel.encode()),
                          ctypes.byref(how), ctypes.c_size_t(ctypes.sizeof(how)))
        if fd >= 0:
            CALLS["openat2"] += 1
            return fd, True
        e = ctypes.get_errno()
        if e not in (errno.ENOSYS, errno.EPERM):
            if e in (errno.ELOOP, errno.EXDEV, errno.ENOTDIR):
                raise Refuse("PATH_ESCAPE_OR_LINK")
            if e == errno.ENOENT:
                raise Refuse("FILE_MISSING")
            raise OSError(e, os.strerror(e), rel)
    # запасной путь: по одной части, каждая папка — O_DIRECTORY | O_NOFOLLOW, то же устройство
    dev = os.fstat(dirfd).st_dev
    fd = os.dup(dirfd)
    parts = rel.split("/")
    if any(c in ("", ".", "..") for c in parts):
        raise Refuse("PATH_ESCAPE_OR_LINK")
    try:
        for i, c in enumerate(parts):
            last = i == len(parts) - 1
            fl = (flags if last else os.O_RDONLY | os.O_DIRECTORY) | os.O_NOFOLLOW | os.O_CLOEXEC
            try:
                nfd = os.open(c, fl, dir_fd=fd)
            except OSError as e:
                if e.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise Refuse("PATH_ESCAPE_OR_LINK")
                if e.errno == errno.ENOENT:
                    raise Refuse("FILE_MISSING")
                raise
            os.close(fd)
            fd = nfd
            if os.fstat(fd).st_dev != dev:
                raise Refuse("PATH_ESCAPE_OR_LINK")
        CALLS["fallback"] += 1
        return fd, False
    except BaseException:
        os.close(fd)
        raise


def quarantine_alive(qu):
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/status", "rb") as f:
                for line in f:
                    if line.startswith(b"Uid:"):
                        if str(qu).encode() in line.split()[1:]:
                            return True
                        break
        except OSError:
            continue
    return False


def walk_out(fd, rel, qu, dev, found):
    with os.scandir(fd) as it:
        names = [e.name for e in it]
    for name in names:
        st = os.lstat(name, dir_fd=fd)
        p = rel + name
        if st.st_dev != dev or st.st_uid != qu:
            raise Refuse("OUT_FOREIGN_ENTRY")
        if stat.S_ISDIR(st.st_mode):
            sub = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                walk_out(sub, p + "/", qu, dev, found)
            finally:
                os.close(sub)
        elif stat.S_ISREG(st.st_mode):
            found.add(p)
        else:
            raise Refuse("OUT_NOT_REGULAR")


def do_import(lease, use_openat2):
    if os.geteuid() != uid_of("zimport"):
        raise Refuse("NOT_ZIMPORT")
    qu = uid_of("zquarantine")
    if quarantine_alive(qu):
        raise Refuse("QUARANTINE_PROCESS_ALIVE")
    m = load_manifest(lease)
    dirs, ex = m["dirs"], set(m["exec"])
    base_fd = os.open(f"{BASE}/out", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        lfd = os.open(lease, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=base_fd)
    except FileNotFoundError:
        raise Refuse("OUT_MISSING")
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.ENOTDIR):
            raise Refuse("OUT_NOT_DIRECTORY")
        raise
    lst = os.fstat(lfd)
    if not stat.S_ISDIR(lst.st_mode) or lst.st_uid != qu:
        raise Refuse("OUT_BAD_OWNER")
    dev = lst.st_dev
    rfd, _ = open_beneath(lfd, "report.json", os.O_RDONLY, use_openat2)
    try:
        rst = os.fstat(rfd)
        if not stat.S_ISREG(rst.st_mode) or rst.st_nlink != 1 or rst.st_dev != dev or rst.st_uid != qu:
            raise Refuse("REPORT_NOT_REGULAR")
        if rst.st_size > CAP_JSON:
            raise Refuse("REPORT_TOO_LARGE")
        data = b""
        while True:
            b = os.read(rfd, CHUNK)
            if not b:
                break
            data += b
            if len(data) > CAP_JSON:
                raise Refuse("REPORT_TOO_LARGE")
    finally:
        os.close(rfd)
    r = strict_json(data, "REPORT")
    if not isinstance(r, dict) or set(r) != REPORT_KEYS or not is_int(r["v"]) or r["v"] != 1 or r["lease"] != lease:
        raise Refuse("REPORT_FIELDS")
    if not isinstance(r["files"], list):
        raise Refuse("REPORT_FIELDS")
    files, keys, total = r["files"], set(), 0
    if len(files) > m["max_files"]:
        raise Refuse("TOO_MANY_FILES")
    for f in files:
        if not isinstance(f, dict) or set(f) != FILE_KEYS or not is_int(f["size"]) or type(f["exec"]) is not bool \
                or not isinstance(f["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", f["sha256"]):
            raise Refuse("REPORT_FIELDS")
        parts = split_path(f["path"], m["max_depth"])
        if not inside_dirs(f["path"], False, dirs):
            raise Refuse("PATH_OUTSIDE_DIRS")
        k = path_key(parts)
        if k in keys:
            raise Refuse("NAME_TWIN")
        keys.add(k)
        if not 0 <= f["size"] <= m["max_file_bytes"]:
            raise Refuse("FILE_TOO_LARGE")
        total += f["size"]
        if f["exec"] != (f["path"] in ex):
            raise Refuse("EXEC_MISMATCH")
    if total > m["max_bytes"]:
        raise Refuse("TOTAL_TOO_LARGE")
    for f in files:
        parts = f["path"].split("/")
        for i in range(1, len(parts)):
            if "/".join(key(c) for c in parts[:i]) in keys:
                raise Refuse("TYPE_CONFLICT")
    paths = {f["path"] for f in files}
    if not ex <= paths:
        raise Refuse("EXEC_FILE_MISSING")
    ffd, _ = open_beneath(lfd, "files", os.O_RDONLY | os.O_DIRECTORY, use_openat2)
    try:
        fst = os.fstat(ffd)
        if fst.st_dev != dev or fst.st_uid != qu:
            raise Refuse("OUT_FOREIGN_ENTRY")
        found = set()
        walk_out(ffd, "", qu, dev, found)
    finally:
        os.close(ffd)
    if found - paths:
        raise Refuse("EXTRA_FILE")
    if paths - found:
        raise Refuse("FILE_MISSING")
    acc_fd = os.open(f"{BASE}/accepted", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.lstat(lease, dir_fd=acc_fd)
        raise Refuse("ACCEPTED_EXISTS")
    except FileNotFoundError:
        pass
    stg_fd = os.open(".staging", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=acc_fd)
    tmp = f"{lease}.{os.getpid()}.{time.time_ns()}"
    os.mkdir(tmp, 0o700, dir_fd=stg_fd)
    tfd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=stg_fd)
    created = set()
    for f in sorted(files, key=lambda f: f["path"].encode()):
        parts = f["path"].split("/")
        sfd, _ = open_beneath(lfd, "files/" + f["path"], os.O_RDONLY, use_openat2)
        try:
            st = os.fstat(sfd)
            if not stat.S_ISREG(st.st_mode):
                raise Refuse("OUT_NOT_REGULAR")
            if st.st_nlink != 1:
                raise Refuse("HARDLINK_IN_OUT")
            if st.st_dev != dev or st.st_uid != qu:
                raise Refuse("OUT_FOREIGN_ENTRY")
            if st.st_size != f["size"]:
                raise Refuse("SIZE_MISMATCH")
            dfd = mkdirs(tfd, parts[:-1], created)
            try:
                wfd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                              0o600, dir_fd=dfd)
                n = 0
                try:
                    while True:
                        b = os.read(sfd, CHUNK)
                        if not b:
                            break
                        n += len(b)
                        if n > f["size"]:
                            raise Refuse("SIZE_MISMATCH")
                        os.write(wfd, b)
                    os.fsync(wfd)
                finally:
                    os.close(wfd)
                if n != f["size"]:
                    raise Refuse("SIZE_MISMATCH")
                # сумма — по копии zimport, а не по файлу карантина
                cfd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
                h = hashlib.sha256()
                try:
                    while True:
                        b = os.read(cfd, CHUNK)
                        if not b:
                            break
                        h.update(b)
                finally:
                    os.close(cfd)
                if h.hexdigest() != f["sha256"]:
                    raise Refuse("SHA256_MISMATCH")
                os.chmod(parts[-1], 0o750 if f["path"] in ex else 0o640, dir_fd=dfd, follow_symlinks=False)
            finally:
                os.close(dfd)
        finally:
            os.close(sfd)
    os.chmod(tmp, 0o750, dir_fd=stg_fd)
    os.fsync(tfd)
    os.close(tfd)
    rename_noreplace(stg_fd, tmp, acc_fd, lease)
    os.fsync(acc_fd)
    return len(files), total


# ---------- архив ----------

def archive(lease, stage):
    if os.geteuid() != 0:
        raise Refuse("NOT_ROOT")
    if stage == "quarantine" and os.environ.get("SERVICE_RESULT") == "success":
        return "SKIPPED_IMPORT_ARCHIVES"
    dest = f"{BASE}/archive/{lease}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{stage}"
    os.mkdir(dest, 0o700)
    moved = []
    for src, name in ((f"{BASE}/in/{lease}.tar", "in.tar"), (f"{BASE}/out/{lease}", "out"),
                      (f"{BASE}/out/{lease}.partial", "out.partial")):
        try:
            os.lstat(src)
        except FileNotFoundError:
            continue
        os.rename(src, f"{dest}/{name}")
        moved.append(name)
    return "MOVED_" + ("+".join(moved) or "NOTHING")


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("manifest-check", "quarantine", "import", "archive") \
            or not LEASE_RE.fullmatch(a[1]):
        print("usage: zavod_intake.py manifest-check|quarantine|import|archive LEASE(32 hex) ...", file=sys.stderr)
        return 64
    sub, lease = a[0], a[1]
    os.umask(0o027)
    try:
        if sub == "manifest-check" and len(a) == 2:
            load_manifest(lease)
            journal(sub, lease, "OK", "-")
        elif sub == "quarantine" and len(a) == 2:
            n, total = quarantine(lease)
            journal(sub, lease, "ACCEPTED", "-", files=n, bytes=total)
        elif sub == "import" and (len(a) == 2 or a[2:] == ["--no-openat2"]):
            n, total = do_import(lease, len(a) == 2)
            journal(sub, lease, "ACCEPTED", "-", files=n, bytes=total, **CALLS)
        elif sub == "archive" and len(a) == 3 and a[2] in ("quarantine", "import"):
            journal(sub, lease, "OK", archive(lease, a[2]))
        else:
            print("bad arguments", file=sys.stderr)
            return 64
        return 0
    except Refuse as e:
        journal(sub, lease, "REFUSED", str(e))
        return 2
    except OSError as e:
        journal(sub, lease, "REFUSED", "OS_ERROR_" + errno.errorcode.get(e.errno, str(e.errno)))
        return 3


if __name__ == "__main__":
    sys.exit(main())
