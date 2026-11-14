#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zevidence_send.py (ставится как /usr/local/lib/zavod/zevidence-send)
# ВЕРСИЯ: v0.1 (выпуск B10)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-14 23:59 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 04» (869221b9)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 5 п.4 — команда входа ssh пользователя zevid (ForceCommand). Читает только
#   SSH_ORIGINAL_COMMAND, без оболочки; допускается ровно `send <серия>`; путь и номер от клиента не принимаются.
#   Выбор: наибольшее n с READY, в котором сумма MANIFEST совпала; папки без READY пропускаются. Перед отдачей —
#   физический состав = файлы строк ALLOW и FULL_RAW + MANIFEST.sha256 + READY, каждый файл открыт без ссылок,
#   размер и сумма out сверены заново. Архив tar в stdout: корень <серия>/<n>/, постоянный порядок, время 0,
#   хозяин 0. Любое иное — код 2 и одна строка причины в stderr.
# ДОПУЩЕНИЕ (на аудит): условие «серия есть в started/» не проверяется — zevid не в группе zprobe и не может читать
#   /var/lib/zavod/probes; к тому же серия B10 без запуска (SAFE_PRE_START) отметки started не имеет. Вместо него —
#   папка export/<серия> root:zevid 0750, не ссылка.
import hashlib
import io
import os
import re
import stat
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/usr/local/lib/zavod/probes-b10')
import zprobe_export_rules as E  # noqa: E402

EXPORT = '/var/lib/zavod/export'
N_RE = re.compile(r'[1-9][0-9]{0,3}')


class Bad(Exception):
    pass


def _dir(name, dir_fd, gid):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    except OSError:
        raise Bad(f'dir:{name}')
    st = os.fstat(fd)
    if (gid is not None and (st.st_uid != 0 or st.st_gid != gid)) or stat.S_IMODE(st.st_mode) & 0o027:
        os.close(fd)
        raise Bad(f'dir_owner:{name}')
    return fd


def _file(name, dir_fd, gid, limit=E.MAX_FILE):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=dir_fd)
    except FileNotFoundError:
        return None
    except OSError:
        raise Bad(f'file:{name}')
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit or stat.S_IMODE(st.st_mode) & 0o027 \
                or (gid is not None and (st.st_uid != 0 or st.st_gid != gid)):
            raise Bad(f'file_mode:{name}')
        got = b''
        while len(got) <= limit:
            part = os.read(fd, 65536)
            if not part:
                break
            got += part
    finally:
        os.close(fd)
    if len(got) > limit:
        raise Bad(f'file_size:{name}')
    return got


def _tree(fd, prefix, gid, out):
    """Все записи папки пакета: подпапки (без ссылок) и обычные файлы; иное — Bad."""
    for ent in sorted(os.listdir(fd)):
        st = os.stat(ent, dir_fd=fd, follow_symlinks=False)
        rel = prefix + ent
        if stat.S_ISDIR(st.st_mode):
            sfd = _dir(ent, fd, gid)
            try:
                _tree(sfd, rel + '/', gid, out)
            finally:
                os.close(sfd)
        elif stat.S_ISREG(st.st_mode):
            out[rel] = _file(ent, fd, gid)
        else:
            raise Bad(f'entry:{rel}')
    return out


def check_package(pfd, gid):
    """Пакет без READY → None (пропуск); READY не сходится → None; иначе {путь: байты} физического состава."""
    ready = _file('READY', pfd, gid, 128)
    if ready is None:
        return None
    man = _file('MANIFEST.sha256', pfd, gid, 1 << 20)
    if man is None or ready != (hashlib.sha256(man).hexdigest() + '\n').encode('ascii'):
        return None
    try:
        rows = E.parse_manifest(man)
    except E.Refused as e:
        raise Bad(f'manifest:{e}')
    files = _tree(pfd, '', gid, {})
    want = {f'{p}/{n}': (o, osz) for m, p, n, r, rsz, o, osz in rows if m != 'HASH_ONLY'}
    if set(files) != set(want) | {'MANIFEST.sha256', 'READY'}:
        raise Bad('package:set')
    for path, (o, osz) in want.items():
        data = files[path]
        if len(data) != osz or hashlib.sha256(data).hexdigest() != o:
            raise Bad(f'package:{path}')
    if len(files) > E.MAX_FILES or sum(len(v) for v in files.values()) > E.MAX_TOTAL + len(man) + len(ready):
        raise Bad('package:limits')
    return files


def pick(series, root=EXPORT, gid=None):
    """→ (n, {путь: байты}). gid None — без сверки хозяина (только тесты без root)."""
    rfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        sfd = _dir(series, rfd, gid)
    finally:
        os.close(rfd)
    try:
        ns = []
        for ent in os.listdir(sfd):
            if not N_RE.fullmatch(ent):
                raise Bad(f'entry:{ent}')
            ns.append(int(ent))
        for n in sorted(ns, reverse=True):
            pfd = _dir(str(n), sfd, gid)
            try:
                files = check_package(pfd, gid)
            finally:
                os.close(pfd)
            if files is not None:
                return n, files
    finally:
        os.close(sfd)
    raise Bad('no_ready_package')


def tar_bytes(series, n, files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.USTAR_FORMAT) as tf:
        dirs = set()
        for path in sorted(files):
            parts = path.split('/')[:-1]
            for i in range(len(parts) + 1):
                d = '/'.join([series, str(n)] + parts[:i])
                if d not in dirs:
                    dirs.add(d)
                    ti = tarfile.TarInfo(d)
                    ti.type, ti.mode, ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = \
                        tarfile.DIRTYPE, 0o755, 0, 0, 0, '', ''
                    tf.addfile(ti)
            ti = tarfile.TarInfo(f'{series}/{n}/{path}')
            ti.size, ti.mode, ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = len(files[path]), 0o644, 0, 0, 0, '', ''
            tf.addfile(ti, io.BytesIO(files[path]))
    return buf.getvalue()


def main(env=os.environ, out=None):
    out = out or sys.stdout.buffer
    cmd = env.get('SSH_ORIGINAL_COMMAND', '')
    parts = cmd.split(' ')
    if len(parts) != 2 or parts[0] != 'send' or not E.SERIES.fullmatch(parts[1]):
        print('ZEVIDENCE_REFUSED command', file=sys.stderr)
        return 2
    try:
        import grp
        gid = grp.getgrnam('zevid').gr_gid
        n, files = pick(parts[1], EXPORT, gid)
        data = tar_bytes(parts[1], n, files)
    except (Bad, OSError, KeyError) as e:
        print(f'ZEVIDENCE_REFUSED {type(e).__name__}:{e}'[:200], file=sys.stderr)
        return 2
    out.write(data)
    out.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
