# ДОКУМЕНТ: zavod/ops/server/build_server_package.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-02 11:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-02 11:33 +02:00 (v0.1: карта 3.3.11.1 и 3.3.11.4)
# ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
# НАЗНАЧЕНИЕ: сборка пакета установки сервера Завода одним архивом (протокол v3.1 И.7, Р.59; карта 3.3.11):
#   файлы берутся только из закрытого списка папок хранилища (по git, без тестов, проверок CI и Windows), модули ядра
#   ставятся npm ci по package-lock.json, внешние части (Flowable REST 8.0.0, драйвер pgjdbc) — по закреплённым
#   суммам из zavod/engine/ci/engine_ci.sh, Node.js 22 для ядра — по сумме NODE_PIN. В архив кладётся MANIFEST.sha256 — сумма каждого файла; на сервере
#   install_server.sh сверяет установленное с ним (3.3.11.4).
# ВЫЗОВ: python3 -I zavod/ops/server/build_server_package.py OUT_DIR [--externals DIR]
#   DIR — папка с уже скачанными flowable-8.0.0.zip, postgresql-<версия>.jar и архивом Node.js; без него они
#   скачиваются.
# ОГРАНИЧЕНИЯ: архив одинаков при одинаковом входе (порядок, время 0, владелец root, права из git). Ключей,
#   паролей и файлов настроек с секретами в пакете нет: файлы *.env и папки secrets — отказ сборки.
import hashlib
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()
# Закрытый список: (папка хранилища, исключения по шаблону пути)
TREES = [
    ('bem954/H1_31_PACKAGE_R51', r'(^|/)EVIDENCE_|\.md$'),
    ('zavod/kernel', r'^zavod/kernel/(tests|ci|win|node_modules)/'),
    ('zavod/engine', r'^zavod/engine/(tests|ci)/'),
    ('zavod/ops/server', r'^zavod/ops/server/(cell/(.*_ci\.sh|test_.*\.py|egress_session_probe\.py|intake_gen\.py)|'
                         r'.*SUPERSEDED.*|render_.*|apply_user_data\.py|verify_user_data\.py|install_release\.sh|'
                         r'zavod-p1.*|build_server_package\.py)$'),
]
SECRET = re.compile(r'(\.env$|(^|/)secrets?/|\.key$|\.pem$|id_ed25519|id_rsa)')
ENGINE_CI = 'zavod/engine/ci/engine_ci.sh'
# Node.js для ядра (ядру нужна версия 22, в Ubuntu 24.04 её нет): та же версия, что у проверок CI (setup-node),
# сумма — из https://nodejs.org/dist/v22.23.3/SHASUMS256.txt (прочитано 2026-11-02).
NODE_PIN = ('node-v22.23.3-linux-x64.tar.xz', 'https://nodejs.org/dist/v22.23.3/node-v22.23.3-linux-x64.tar.xz',
            'df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git_files():
    out = subprocess.run(['git', '-C', ROOT, 'ls-files', '-s', '--'] + [t for t, _ in TREES],
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        mode, _obj, _stage, path = line.split(None, 3)
        for tree, skip in TREES:
            if path.startswith(tree + '/') and not re.search(skip, path):
                if SECRET.search(path) and not path.endswith('.example'):
                    raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL secret-like file in the tree: {path}')
                yield path, 0o755 if mode == '100755' else 0o644
                break


def pins():
    text = open(os.path.join(ROOT, ENGINE_CI), encoding='utf-8').read()
    v = dict(re.findall(r'^([A-Z_0-9]+)=(\S+)$', text, re.M))
    ver = v['PGJDBC_VER']
    return [
        ('flowable-8.0.0.zip', v['FLOWABLE_ZIP_URL'], v['FLOWABLE_ZIP_SHA256']),
        (f'postgresql-{ver}.jar', v['PGJDBC_URL'].replace('$PGJDBC_VER', ver), v['PGJDBC_SHA256']),
    ], v['WAR_SHA256']


def externals(src):
    ((zip_name, zip_url, zip_sha), (jar_name, jar_url, jar_sha)), war_sha = pins()
    got = {}
    for name, url, want in ((zip_name, zip_url, zip_sha), (jar_name, jar_url, jar_sha), NODE_PIN):
        if src:
            data = open(os.path.join(src, name), 'rb').read()
        else:
            with urllib.request.urlopen(url, timeout=300) as r:
                data = r.read()
        if sha(data) != want:
            raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL {name} sha256 {sha(data)} != {want}')
        got[name] = data
    with zipfile.ZipFile(io.BytesIO(got[zip_name])) as z:
        war = z.read('wars/flowable-rest.war')
    if sha(war) != war_sha:
        raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL flowable-rest.war sha256 {sha(war)} != {war_sha}')
    return {'engine/flowable-rest.war': war, f'engine/{jar_name}': got[jar_name], f'runtime/{NODE_PIN[0]}': got[NODE_PIN[0]]}


def node_modules():
    """npm ci по package-lock.json ядра во временной папке: модули ставятся без запуска их сценариев."""
    out = {}
    with tempfile.TemporaryDirectory() as d:
        for f in ('package.json', 'package-lock.json'):
            with open(os.path.join(ROOT, 'zavod/kernel', f), 'rb') as a, open(os.path.join(d, f), 'wb') as b:
                b.write(a.read())
        subprocess.run(['npm', 'ci', '--ignore-scripts', '--no-fund', '--no-audit', '--omit=dev'], cwd=d, check=True,
                       stdout=subprocess.DEVNULL)
        base = os.path.join(d, 'node_modules')
        for dp, dns, fns in os.walk(base):
            dns.sort()
            for fn in sorted(fns):
                p = os.path.join(dp, fn)
                if os.path.islink(p):
                    raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL link in node_modules: {p}')
                rel = os.path.relpath(p, base).replace(os.sep, '/')
                if rel == '.package-lock.json':
                    continue
                out['zavod/kernel/node_modules/' + rel] = open(p, 'rb').read()
    return out


def main(argv):
    if not argv:
        print(__doc__ or 'usage: build_server_package.py OUT_DIR [--externals DIR]', file=sys.stderr)
        return 2
    out_dir, ext = argv[0], None
    if argv[1:3] and argv[1] == '--externals':
        ext = argv[2]
    head = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True,
                          check=True).stdout.strip()
    files = {}
    for path, mode in git_files():
        files[path] = (open(os.path.join(ROOT, path), 'rb').read(), mode)
    for path, data in node_modules().items():
        files[path] = (data, 0o644)
    for path, data in externals(ext).items():
        files[path] = (data, 0o644)
    manifest = ''.join(f'{sha(d)}  {p}\n' for p, (d, _m) in sorted(files.items()))
    manifest = f'# zavod server package; source commit {head}\n' + manifest
    files['MANIFEST.sha256'] = (manifest.encode(), 0o644)
    os.makedirs(out_dir, exist_ok=True)
    name = f'zavod-server-{head[:12]}.tar'
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.PAX_FORMAT) as t:
        dirs = sorted({os.path.dirname(p) for p in files} - {''})
        alldirs = sorted({'/'.join(d.split('/')[:i]) for d in dirs for i in range(1, d.count('/') + 2)})
        for d in alldirs:
            ti = tarfile.TarInfo(d)
            ti.type, ti.mode, ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = tarfile.DIRTYPE, 0o755, 0, 0, 0, 'root', 'root'
            t.addfile(ti)
        for p in sorted(files):
            data, mode = files[p]
            ti = tarfile.TarInfo(p)
            ti.size, ti.mode, ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = len(data), mode, 0, 0, 0, 'root', 'root'
            t.addfile(ti, io.BytesIO(data))
    with open(os.path.join(out_dir, name), 'wb') as f:
        f.write(buf.getvalue())
    with open(os.path.join(out_dir, 'MANIFEST.sha256'), 'wb') as f:
        f.write(manifest.encode())
    print(f'ZAVOD_SERVER_PACKAGE=OK file={name} files={len(files)} sha256={sha(buf.getvalue())} '
          f'manifest_sha256={sha(manifest.encode())}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
