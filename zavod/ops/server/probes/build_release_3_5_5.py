#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5.py
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-13 10:54 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-13 11:59 +02:00
# ИСПОЛНИТЕЛЬ: Claude (v0.1 — чат «Завод 3.5.5 ПБ-1 · 03», 1bcc7ca2; v0.2 — чат «· 04», 70d36cf5)
# НАЗНАЧЕНИЕ: сборка выпуска 3.5.5 (ПБ-1) из коммита с программами (release_commit, коммит A'):
#   zavod/ops/zprobe_pins.txt — отпечатки SHA-256 (ключи — как ждут zprobe_verify.py, zprobe_series.sh,
#     zprobe_refs_check.py, zprobe_runner.py и zprobe_release.py: десять файлов PINNED, release_commit, phone_*, pc_*);
#   zavod/ops/server/probes/zprobe-release-3.5.5.sh — один файл для сервера: внутри tar пакета (base64), его сумма,
#     сумма описи MANIFEST.sha256 и число файлов. Проверяет сумму tar ДО создания чего-либо, создаёт НОВУЮ папку
#     /var/lib/zavod/probes-pkg-<12 знаков коммита> (mkdir, без переименований), распаковывает в неё и сверяет с
#     встроенной описью; уже существующая папка — только сверка со встроенной описью (сумма MANIFEST, все файлы, их
#     число, нет ссылок, владелец root, нет записи группе и прочим), без распаковки; затем zprobe_release.py.
#   v0.2 (аудит ChatGPT REL1): C-01 — ни одного mv; файлы пакета берутся из объектов git коммита (git show), а не из
#   рабочего дерева; M-06 — --verify требует, чтобы коммит B отличался от release_commit ровно двумя файлами
#   (pins и .sh) и в отслеживаемых файлах не было правок; Q4 — повтор сверяет папку со встроенной описью.
#   v0.3 (аудит ChatGPT REL2 L-01): сверка папки пакета — ещё и полный список всех её объектов (тип, права, путь;
#   сумма LS встроена в файл выпуска): лишний пустой каталог или файл — отказ; файл с несколькими ссылками — отказ.
#   Сборка детерминирована (те же байты при тех же входах): tar без времени и владельцев, порядок по имени.
# ВЫЗОВ: python3 -I -B build_release_3_5_5.py <корень хранилища git> <release_commit 40 hex> [--verify]
# ОГРАНИЧЕНИЯ: без --verify пишет только два новых файла (режим x): существующий не перезаписывается; ничего не удаляет
#   и не переименовывает.
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

SH_TEMPLATE = r'''#!/bin/bash
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe-release-3.5.5.sh (собран build_release_3_5_5.py v0.3, руками не править)
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT  ВЫПУСК: 3.5.5 (ПБ-1)  release_commit=@C@
# НАЗНАЧЕНИЕ: один файл выпуска для сервера zavod-1. Внутри — tar пакета (base64), его SHA-256, сумма описи
#   MANIFEST.sha256 и число файлов. Новая папка /var/lib/zavod/probes-pkg-@C12@: сумма tar проверяется ДО её
#   создания, папка создаётся mkdir (занята — сверка со встроенной описью без распаковки), затем распаковка и сверка.
#   Потом zprobe_release.py: check — проверки §11 и план установки; install — check и установка только новых файлов.
#   Ничего не удаляет, не переименовывает и не перезаписывает.
# ВЫЗОВ (root, сеанс SSH на zavod-1): bash <этот файл> check   |   bash <этот файл> install
set -eu -o pipefail
umask 022
M=${1:-}
case "$M" in check|install) ;; *) echo "usage: bash $0 check|install"; exit 2;; esac
[ "$(id -u)" = 0 ] || { echo "REFUSED: run as root"; exit 2; }
C=@C@
P=/var/lib/zavod/probes-pkg-@C12@
TS=@TS@
MS=@MS@
NF=@NF@
LS=@LS@
payload() { sed -n '/^__ZPROBE_PKG_BASE64__$/,$p' "$0" | tail -n +2 | base64 -d; }
pkg_ok() {
  [ -d "$P" ] && [ ! -L "$P" ] && [ -f "$P/MANIFEST.sha256" ] && [ ! -L "$P/MANIFEST.sha256" ] || return 1
  [ "$(sha256sum < "$P/MANIFEST.sha256" | cut -d' ' -f1)" = "$MS" ] || return 1
  (cd "$P" && sha256sum -c --strict --quiet MANIFEST.sha256) || return 1
  [ "$(find "$P" ! -type d | wc -l)" = "$NF" ] || return 1
  [ "$(cd "$P" && find . -printf '%y %m %p\n' | LC_ALL=C sort | sha256sum | cut -d' ' -f1)" = "$LS" ] || return 1
  [ -z "$(find "$P" \( -type l -o ! -user root -o ! -group root -o -perm /022 -o \( -type f -links +1 \) \) -print)" ] || return 1
}
if [ -e "$P" ] || [ -L "$P" ]; then
  pkg_ok || { echo "REFUSED: $P exists and differs from the embedded inventory of release $C, nothing changed"; exit 1; }
  echo "PACKAGE_DIR_EXISTS=$P (equal to the embedded inventory, not unpacked again)"
else
  [ "$(payload | sha256sum | cut -d' ' -f1)" = "$TS" ] || { echo "REFUSED: embedded package sum differs, nothing changed"; exit 1; }
  Q=/var/lib/zavod
  { [ -d "$Q" ] && [ ! -L "$Q" ] && [ "$(stat -c %u "$Q")" = 0 ] && [ -z "$(find "$Q" -maxdepth 0 -perm /022)" ]; } \
    || { echo "REFUSED: $Q is not a root-only plain folder, nothing changed"; exit 1; }
  mkdir -m 0755 "$P" || { echo "REFUSED: cannot create new folder $P, nothing changed"; exit 1; }
  payload | tar -C "$P" --no-same-owner -xf - \
    || { echo "REFUSED: unpacking into new $P failed; $P kept as evidence, nothing installed"; exit 1; }
  pkg_ok || { echo "REFUSED: new $P differs from the embedded inventory; kept as evidence, nothing installed"; exit 1; }
  echo "PACKAGE_UNPACKED=$P"
fi
exec python3 -I -B "$P/zavod/ops/server/probes/zprobe_release.py" "$M" "$P"
__ZPROBE_PKG_BASE64__
'''


def sha(b):
    return hashlib.sha256(b).hexdigest()


LISTING_CMD = "find . -printf '%y %m %p\\n' | LC_ALL=C sort | sha256sum | cut -d' ' -f1"


def listing(dirs, blobs):
    """L-01 (REL2): что выдаст LISTING_CMD в папке пакета после распаковки tar (umask 022): «тип права путь»."""
    lines = ['d 755 .'] + [f'd 755 ./{d}' for d in dirs]
    lines += [f'f {"755" if p in EXEC else "644"} ./{p}' for p in blobs]
    return sha(('\n'.join(sorted(lines)) + '\n').encode('utf-8'))


def git(root, *args):
    p = subprocess.run(['git', '-C', root] + list(args), capture_output=True)
    if p.returncode != 0:
        raise SystemExit(f'RELEASE_REFUSED git {" ".join(args)} rc={p.returncode} {p.stderr.decode(errors="replace").strip()}')
    return p.stdout


def blob(root, commit, path):
    """Файл пакета — объект git коммита release_commit (не рабочее дерево)."""
    return git(root, 'show', f'{commit}:{path}')


def pins_text(get, commit):
    out = ['# zprobe_pins.txt — отпечатки выпуска 3.5.5 (ПБ-1). Собрано build_release_3_5_5.py из release_commit.',
           '# Манифест для приёмки: git show <коммит этого файла>:zavod/ops/zprobe_pins.txt > manifest.txt',
           f'release_commit {commit}']
    out += [f'{k} {sha(get(p))}' for k, p in PIN_KEYS]
    return ('\n'.join(out) + '\n').encode('utf-8')


def package(get, commit, pins):
    blobs = {p: get(p) for p in FILES}
    blobs[PINS_PATH] = pins
    blobs['RELEASE'] = f'commit={commit}\nversion=3.5.5\n'.encode('ascii')
    manifest = ''.join(f'{sha(b)}  {p}\n' for p, b in sorted(blobs.items())).encode('ascii')
    blobs['MANIFEST.sha256'] = manifest
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
    return buf.getvalue(), sha(manifest), len(blobs), listing(dirs, blobs)


def script(commit, tar, manifest_sha, nfiles, ls):
    head = SH_TEMPLATE
    for k, v in (('@C12@', commit[:12]), ('@C@', commit), ('@TS@', sha(tar)), ('@MS@', manifest_sha),
                 ('@NF@', str(nfiles)), ('@LS@', ls)):
        head = head.replace(k, v)
    return head.encode('utf-8') + base64.encodebytes(tar)


def build(root, commit):
    get = lambda p: blob(root, commit, p)  # noqa: E731
    pins = pins_text(get, commit)
    tar, msha, nf, ls = package(get, commit, pins)
    return pins, tar, script(commit, tar, msha, nf, ls)


def main():
    a = sys.argv[1:]
    if len(a) not in (2, 3) or not re.fullmatch(r'[0-9a-f]{40}', a[1]) or a[2:] not in ([], ['--verify']):
        print('usage: build_release_3_5_5.py <repo root> <release_commit> [--verify]')
        return 2
    root, commit = a[0], a[1]
    pins, tar, sh_b = build(root, commit)
    if a[2:] == ['--verify']:
        bad = [p for p, b in ((PINS_PATH, pins), (SH_PATH, sh_b)) if not os.path.isfile(os.path.join(root, p))
               or open(os.path.join(root, p), 'rb').read() != b]
        # M-06: коммит B = release_commit + ровно два файла выпуска; отслеживаемые файлы без правок
        changed = sorted(git(root, 'diff', '--name-only', commit, 'HEAD').decode().split())
        if changed != sorted([PINS_PATH, SH_PATH]):
            bad.append(f'HEAD differs from release_commit not only by pins and .sh: {changed}')
        dirty = git(root, 'status', '--porcelain', '--untracked-files=no').decode().split('\n')
        if any(dirty):
            bad.append(f'tracked files changed in the working tree: {[d for d in dirty if d]}')
        print(f'RELEASE_VERIFY={"FAIL" if bad else "OK"} commit={commit} tar_sha256={sha(tar)} sh_sha256={sha(sh_b)} '
              f'pins_sha256={sha(pins)} differs={bad}')
        return 1 if bad else 0
    for p, b in ((PINS_PATH, pins), (SH_PATH, sh_b)):
        with open(os.path.join(root, p), 'xb') as f:
            f.write(b)
    print(f'RELEASE_BUILT commit={commit} tar_sha256={sha(tar)} sh_sha256={sha(sh_b)} pins_sha256={sha(pins)} '
          f'sh_bytes={len(sh_b)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
