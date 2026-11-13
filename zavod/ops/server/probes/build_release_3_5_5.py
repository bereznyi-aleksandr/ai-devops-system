#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-13 10:54 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-13 10:54 +02:00
# ИСПОЛНИТЕЛЬ: Claude (чат «Завод 3.5.5 ПБ-1 · 03», сессия 1bcc7ca2-137f-458a-8475-65a3e64abf2d)
# НАЗНАЧЕНИЕ: сборка выпуска 3.5.5 (ПБ-1) из коммита с программами (release_commit):
#   zavod/ops/zprobe_pins.txt — отпечатки SHA-256 (ключи — как ждут zprobe_verify.py, zprobe_series.sh,
#     zprobe_refs_check.py и zprobe_runner.py: десять файлов PINNED, release_commit, phone_*, pc_*);
#   zavod/ops/server/probes/zprobe-release-3.5.5.sh — один файл для сервера: внутри tar пакета (base64) с его
#     суммой; распаковывает в новую папку /var/lib/zavod/probes-pkg-<12 знаков коммита>, сверяет MANIFEST.sha256 и
#     запускает zprobe_release.py check|install.
#   Сборка детерминирована (те же байты при тех же входах): tar без времени и владельцев, порядок по имени.
#   Режим --verify: собрать в память и сравнить с файлами в дереве; плюс каждый файл пакета, кроме pins, обязан
#   быть байт в байт равен своей версии в release_commit (git show) — это проверка CI.
# ВЫЗОВ: python3 -I -B build_release_3_5_5.py <корень хранилища> <release_commit 40 hex> [--verify]
# ОГРАНИЧЕНИЯ: без --verify пишет только новые файлы (режим x): существующий не перезаписывается; ничего не удаляет.
import base64
import hashlib
import io
import os
import re
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
PROBES = 'zavod/ops/server/probes/'
FILES = [PROBES + n for n in ('pb1_session.py', 'zprobe_rules.py', 'zprobe_runner.py', 'zprobe_journal.py',
                              'zprobe-start', 'zprobe-run@.service', 'test_zprobe.py', 'zprobe_release.py')]
FILES += ['zavod/ops/server/cell/' + n for n in ('zavod-egress.nft', 'zavod-gate', 'zavod-proxy', 'zavod-gate.service',
                                                'zavod-proxy.service', 'zagent@.service')]
FILES += ['zavod/ops/phone/zprobe_verify.py', 'zavod/ops/phone/zprobe_series.sh', 'zavod/ops/pc/zprobe_refs.sh',
          'zavod/ops/pc/zprobe_refs_check.py', 'zavod/kernel/db/06_zavod_ext_04.sql']
EXEC = {PROBES + 'zprobe-start', PROBES + 'zprobe_release.py', 'zavod/ops/server/cell/zavod-gate',
        'zavod/ops/server/cell/zavod-proxy', 'zavod/ops/phone/zprobe_series.sh', 'zavod/ops/pc/zprobe_refs.sh'}
PINS_PATH = 'zavod/ops/zprobe_pins.txt'
SH_PATH = PROBES + 'zprobe-release-3.5.5.sh'
# ключ pins → файл (десять PINNED из zprobe_runner.py; phone_/pc_ — программы телефона и компьютера)
PIN_KEYS = [('pb1_session.py', PROBES + 'pb1_session.py'), ('zprobe_rules.py', PROBES + 'zprobe_rules.py'),
            ('zprobe_runner.py', PROBES + 'zprobe_runner.py'), ('zprobe_journal.py', PROBES + 'zprobe_journal.py'),
            ('zprobe-start', PROBES + 'zprobe-start'), ('zprobe-run@.service', PROBES + 'zprobe-run@.service'),
            ('zagent@.service', 'zavod/ops/server/cell/zagent@.service'),
            ('zavod-proxy', 'zavod/ops/server/cell/zavod-proxy'), ('zavod-gate', 'zavod/ops/server/cell/zavod-gate'),
            ('zavod-egress.nft', 'zavod/ops/server/cell/zavod-egress.nft'),
            ('phone_zprobe_verify.py', 'zavod/ops/phone/zprobe_verify.py'),
            ('phone_zprobe_rules.py', PROBES + 'zprobe_rules.py'),
            ('pc_zprobe_refs.sh', 'zavod/ops/pc/zprobe_refs.sh'),
            ('pc_zprobe_refs_check.py', 'zavod/ops/pc/zprobe_refs_check.py'),
            ('pc_zprobe_rules.py', PROBES + 'zprobe_rules.py')]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def read(root, rel):
    with open(os.path.join(root, rel), 'rb') as f:
        return f.read()


def pins_text(root, commit):
    out = ['# zprobe_pins.txt — отпечатки выпуска 3.5.5 (ПБ-1). Собрано build_release_3_5_5.py из release_commit.',
           '# Манифест для приёмки: git show <коммит этого файла>:zavod/ops/zprobe_pins.txt > manifest.txt',
           f'release_commit {commit}']
    out += [f'{k} {sha(read(root, p))}' for k, p in PIN_KEYS]
    return ('\n'.join(out) + '\n').encode('utf-8')


def package(root, commit, pins):
    blobs = {p: read(root, p) for p in FILES}
    blobs[PINS_PATH] = pins
    blobs['RELEASE'] = f'commit={commit}\nversion=3.5.5\n'.encode('ascii')
    blobs['MANIFEST.sha256'] = ''.join(f'{sha(b)}  {p}\n' for p, b in sorted(blobs.items())).encode('ascii')
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.GNU_FORMAT) as t:
        dirs = sorted({os.path.dirname(p)[:i] for p in blobs for i in
                       [m.end() - 1 for m in re.finditer('/', os.path.dirname(p) + '/')] if os.path.dirname(p)[:i]})
        for d in dirs:
            ti = tarfile.TarInfo(d)
            ti.type, ti.mode, ti.mtime = tarfile.DIRTYPE, 0o755, 0
            t.addfile(ti)
        for p in sorted(blobs):
            ti = tarfile.TarInfo(p)
            ti.size, ti.mtime = len(blobs[p]), 0
            ti.mode = 0o755 if p in EXEC else 0o644
            t.addfile(ti, io.BytesIO(blobs[p]))
    return buf.getvalue()


def script(commit, tar):
    head = f'''#!/bin/bash
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe-release-3.5.5.sh (собран build_release_3_5_5.py, руками не править)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ВЫПУСК: 3.5.5 (ПБ-1)  release_commit={commit}
# НАЗНАЧЕНИЕ: один файл выпуска для сервера zavod-1. Внутри — tar пакета (base64) и его SHA-256. Распаковывает
#   пакет в НОВУЮ папку /var/lib/zavod/probes-pkg-{commit[:12]} (уже есть — только сверка MANIFEST.sha256, без
#   распаковки), затем запускает zprobe_release.py: check — проверки §11 (чтение + испытания в новой папке),
#   install — check и установка только новых файлов. Ничего не удаляет и не перезаписывает.
# ВЫЗОВ (root, сеанс SSH на zavod-1): bash <этот файл> check   |   bash <этот файл> install
set -eu
M=${{1:-}}
case "$M" in check|install) ;; *) echo "usage: bash $0 check|install"; exit 2;; esac
[ "$(id -u)" = 0 ] || {{ echo "REFUSED: run as root"; exit 2; }}
C={commit}
P=/var/lib/zavod/probes-pkg-${{C:0:12}}
TS={sha(tar)}
if [ -e "$P" ] || [ -L "$P" ]; then
  {{ [ -d "$P" ] && [ ! -L "$P" ]; }} || {{ echo "REFUSED: $P is not a plain folder, nothing changed"; exit 1; }}
  echo "PACKAGE_DIR_EXISTS=$P (not unpacked again)"
else
  T=$(mktemp -d "$P.new-XXXXXX")
  sed -n '/^__ZPROBE_PKG_BASE64__$/,$p' "$0" | tail -n +2 | base64 -d > "$T/pkg.tar"
  echo "$TS  $T/pkg.tar" | sha256sum -c --strict --quiet - || {{ echo "REFUSED: embedded package sum differs, left in $T"; exit 1; }}
  tar -C "$T" --no-same-owner -xf "$T/pkg.tar"
  mv -nT "$T" "$P"
  [ ! -e "$T" ] || {{ echo "REFUSED: $P appeared meanwhile, new copy left in $T"; exit 1; }}
  echo "PACKAGE_UNPACKED=$P"
fi
(cd "$P" && sha256sum -c --strict --quiet MANIFEST.sha256) || {{ echo "REFUSED: $P differs from release $C, nothing installed"; exit 1; }}
exec python3 -I -B "$P/zavod/ops/server/probes/zprobe_release.py" "$M" "$P"
__ZPROBE_PKG_BASE64__
'''
    return head.encode('utf-8') + base64.encodebytes(tar)


def main():
    a = sys.argv[1:]
    if len(a) not in (2, 3) or not re.fullmatch(r'[0-9a-f]{40}', a[1]) or a[2:] not in ([], ['--verify']):
        print('usage: build_release_3_5_5.py <repo root> <release_commit> [--verify]')
        return 2
    root, commit = a[0], a[1]
    pins = pins_text(root, commit)
    tar = package(root, commit, pins)
    sh = script(commit, tar)
    if a[2:] == ['--verify']:
        bad = [p for p, b in ((PINS_PATH, pins), (SH_PATH, sh)) if read(root, p) != b]
        for p in FILES:
            git = subprocess.run(['git', '-C', root, 'show', f'{commit}:{p}'], capture_output=True)
            if git.returncode != 0 or git.stdout != read(root, p):
                bad.append(p + ' (differs from release_commit)')
        print(f'RELEASE_VERIFY={"FAIL" if bad else "OK"} commit={commit} tar_sha256={sha(tar)} sh_sha256={sha(sh)} '
              f'pins_sha256={sha(pins)} differs={bad}')
        return 1 if bad else 0
    for p, b in ((PINS_PATH, pins), (SH_PATH, sh)):
        with open(os.path.join(root, p), 'xb') as f:
            f.write(b)
    print(f'RELEASE_BUILT commit={commit} tar_sha256={sha(tar)} sh_sha256={sha(sh)} pins_sha256={sha(pins)} '
          f'sh_bytes={len(sh)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
