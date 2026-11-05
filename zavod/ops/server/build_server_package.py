# ДОКУМЕНТ: zavod/ops/server/build_server_package.py
# ВЕРСИЯ: v0.4  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-02 11:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-05 16:54 +02:00 (v0.4: карта 3.5.1, RISK_ARM64_3_4_1_v1_1 — ключ --arch x64|arm64: сервер zavod-1 на Arm64; Claude, сессия 82d68a2b-4e18-4e8c-9347-784577488ec2; v0.3 от 2026-11-03 03:34: аудит M3311-R1-03 — архив движка в пакете назван engine/flowable-rest-postgres.war (строка службы проходит проверку разрешений сканера); M3311-R1-02 — права файлов в описи строками #mode; аудит M3311-R1-01 — байты файлов берутся из объектов git коммита HEAD (git cat-file), а не из рабочей папки; отказ, если отслеживаемые файлы папок пакета отличаются от HEAD, и на любой режим git, кроме 100644 и 100755 (символическая ссылка 120000, подмодуль 160000); Claude, сессия 2bf4a72a-0dfd-45e6-8828-338d117e688d; v0.2 от 12:21: war движка собирается с драйверами pgjdbc и junixsocket — engine/flowable-rest-pg.war; v0.1 от 11:33: карта 3.3.11.1 и 3.3.11.4)
# ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
# НАЗНАЧЕНИЕ: сборка пакета установки сервера Завода одним архивом (протокол v3.1 И.7, Р.59; карта 3.3.11):
#   файлы берутся только из закрытого списка папок хранилища (по git, без тестов, проверок CI и Windows), модули ядра
#   ставятся npm ci по package-lock.json, внешние части (Flowable REST 8.0.0, драйвер pgjdbc) — по закреплённым
#   суммам из zavod/engine/ci/engine_ci.sh, Node.js 22 для ядра — по сумме NODE_PIN. В архив кладётся MANIFEST.sha256 — сумма каждого файла; на сервере
#   install_server.sh сверяет установленное с ним (3.3.11.4).
# ВЫЗОВ: python3 -I zavod/ops/server/build_server_package.py OUT_DIR [--externals DIR] [--arch x64|arm64]
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
# v0.4 (карта 3.5.1): сборка под процессор сервера — x64 (машины GitHub, ПК) или arm64 (сервер zavod-1, Hetzner CAX21);
# сумма arm64 — из того же SHASUMS256.txt (прочитано 2026-11-05). Остальные части пакета от процессора не зависят.
NODE_PINS = {
    'x64': ('node-v22.23.3-linux-x64.tar.xz', 'https://nodejs.org/dist/v22.23.3/node-v22.23.3-linux-x64.tar.xz',
            'df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de'),
    'arm64': ('node-v22.23.3-linux-arm64.tar.xz', 'https://nodejs.org/dist/v22.23.3/node-v22.23.3-linux-arm64.tar.xz',
              'a44aeb94849a299b22df10b9e622ec2f605c2183501bc40590705131de7c740f'),
}
NODE_PIN = NODE_PINS['x64']
# junixsocket 2.10.1 (2024-09-23): драйвер pgjdbc входит в базу только через сокет Linux, вход peer без пароля
# (PostgreSQL сервера слушает только сокет). Maven Central публикует для них только sha1 (прочитано 2026-11-02 с
# repo1.maven.org); sha256 закреплён по прогону CI 41428183172 (2026-11-02), где sha1 совпал. При sha256 = None сборка
# проверяет sha1 и печатает sha256.
MVN = 'https://repo1.maven.org/maven2/com/kohlschutter/junixsocket'
JUNIX_PINS = [
    ('junixsocket-common-2.10.1.jar', f'{MVN}/junixsocket-common/2.10.1/junixsocket-common-2.10.1.jar',
     'a057996cbf023e8bd5e4aededeba97fa1b1d3a9a', '19e5f7615ad2293f3532bc3f991b31396c1161834e89d9a6aa0c7def939c6729'),
    ('junixsocket-native-common-2.10.1.jar',
     f'{MVN}/junixsocket-native-common/2.10.1/junixsocket-native-common-2.10.1.jar',
     '0c9d8cc10a38ceca64695829ea6b4ee84e46d72f', '0126ce0baf1ceb575ef517807d4d2b14b9f32f06180204e12ec73ab4a772567a'),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def clean_tree():
    """Аудит M3311-R1-01: сборка только из зафиксированного коммита — отслеживаемые файлы папок пакета (и файл сумм
    движка) не должны отличаться от HEAD ни в рабочей папке, ни в индексе."""
    paths = [t for t, _ in TREES] + [ENGINE_CI, 'zavod/kernel/package.json', 'zavod/kernel/package-lock.json']
    out = subprocess.run(['git', '-C', ROOT, 'status', '--porcelain', '--untracked-files=no', '--'] + paths,
                         capture_output=True, text=True, check=True).stdout
    if out.strip():
        raise SystemExit('ZAVOD_SERVER_PACKAGE=FAIL worktree differs from HEAD: ' + out.split('\n')[0].strip())


def blob(path):
    """Байты файла из объекта git коммита HEAD (не из рабочей папки)."""
    return subprocess.run(['git', '-C', ROOT, 'cat-file', 'blob', f'HEAD:{path}'], capture_output=True,
                          check=True).stdout


def git_files():
    out = subprocess.run(['git', '-C', ROOT, 'ls-tree', '-r', '--full-tree', 'HEAD', '--'] + [t for t, _ in TREES],
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        meta, path = line.split('\t', 1)
        mode, kind, _obj = meta.split()
        for tree, skip in TREES:
            if path.startswith(tree + '/') and not re.search(skip, path):
                if kind != 'blob' or mode not in ('100644', '100755'):
                    raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL git mode {mode} {kind} is not a regular file: {path}')
                if SECRET.search(path) and not path.endswith('.example'):
                    raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL secret-like file in the tree: {path}')
                yield path, 0o755 if mode == '100755' else 0o644
                break


def pins():
    text = blob(ENGINE_CI).decode('utf-8')
    v = dict(re.findall(r'^([A-Z_0-9]+)=(\S+)$', text, re.M))
    ver = v['PGJDBC_VER']
    return [
        ('flowable-8.0.0.zip', v['FLOWABLE_ZIP_URL'], v['FLOWABLE_ZIP_SHA256']),
        (f'postgresql-{ver}.jar', v['PGJDBC_URL'].replace('$PGJDBC_VER', ver), v['PGJDBC_SHA256']),
    ], v['WAR_SHA256']


def fetch(src, name, url):
    if src:
        return open(os.path.join(src, name), 'rb').read()
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()


def war_with_drivers(war, jars):
    """Как engine_ci.sh: драйверы кладутся в WEB-INF/lib без сжатия и дописываются в WEB-INF/classpath.idx.
    Время записей — исходное у файлов war и 1980-01-01 у добавленных: тот же вход — тот же war."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(war)) as zi, zipfile.ZipFile(out, 'w') as zo:
        for info in zi.infolist():
            data = zi.read(info)
            if info.filename == 'WEB-INF/classpath.idx':
                data += ''.join(f'- "WEB-INF/lib/{n}"\n' for n in sorted(jars)).encode()
            ni = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            ni.compress_type, ni.external_attr = info.compress_type, info.external_attr
            zo.writestr(ni, data)
        for n in sorted(jars):
            zi2 = zipfile.ZipInfo(f'WEB-INF/lib/{n}', date_time=(1980, 1, 1, 0, 0, 0))
            zi2.compress_type, zi2.external_attr = zipfile.ZIP_STORED, 0o644 << 16
            zo.writestr(zi2, jars[n])
    return out.getvalue()


def externals(src):
    ((zip_name, zip_url, zip_sha), (jar_name, jar_url, jar_sha)), war_sha = pins()
    got = {}
    for name, url, want in ((zip_name, zip_url, zip_sha), (jar_name, jar_url, jar_sha), NODE_PIN):
        data = fetch(src, name, url)
        if sha(data) != want:
            raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL {name} sha256 {sha(data)} != {want}')
        got[name] = data
    for name, url, want1, want256 in JUNIX_PINS:
        data = fetch(src, name, url)
        if hashlib.sha1(data).hexdigest() != want1:
            raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL {name} sha1 {hashlib.sha1(data).hexdigest()} != {want1}')
        if want256 is None:
            print(f'ZAVOD_SERVER_PACKAGE_PIN_TODO {name} sha256={sha(data)}')
        elif sha(data) != want256:
            raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL {name} sha256 {sha(data)} != {want256}')
        got[name] = data
    with zipfile.ZipFile(io.BytesIO(got[zip_name])) as z:
        war = z.read('wars/flowable-rest.war')
    if sha(war) != war_sha:
        raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL flowable-rest.war sha256 {sha(war)} != {war_sha}')
    jars = {n: got[n] for n in [jar_name] + [p[0] for p in JUNIX_PINS]}
    return {'engine/flowable-rest-postgres.war': war_with_drivers(war, jars), f'runtime/{NODE_PIN[0]}': got[NODE_PIN[0]]}


def node_modules():
    """npm ci по package-lock.json ядра во временной папке: модули ставятся без запуска их сценариев."""
    out = {}
    with tempfile.TemporaryDirectory() as d:
        for f in ('package.json', 'package-lock.json'):
            with open(os.path.join(d, f), 'wb') as b:
                b.write(blob('zavod/kernel/' + f))
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
        print(__doc__ or 'usage: build_server_package.py OUT_DIR [--externals DIR] [--arch x64|arm64]', file=sys.stderr)
        return 2
    global NODE_PIN
    out_dir, ext, arch, rest = argv[0], None, 'x64', argv[1:]
    while rest:
        if rest[0] == '--externals' and len(rest) > 1:
            ext, rest = rest[1], rest[2:]
        elif rest[0] == '--arch' and len(rest) > 1 and rest[1] in NODE_PINS:
            arch, rest = rest[1], rest[2:]
        else:
            raise SystemExit(f'ZAVOD_SERVER_PACKAGE=FAIL unknown argument: {rest[0]}')
    NODE_PIN = NODE_PINS[arch]
    head = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True,
                          check=True).stdout.strip()
    clean_tree()
    files = {}
    for path, mode in git_files():
        files[path] = (blob(path), mode)
    for path, data in node_modules().items():
        files[path] = (data, 0o644)
    for path, data in externals(ext).items():
        files[path] = (data, 0o644)
    manifest = ''.join(f'{sha(d)}  {p}\n' for p, (d, _m) in sorted(files.items()))
    # Аудит M3311-R1-02: права каждого файла тоже в описи; установщик сверяет их до установки и после копирования.
    modes = ''.join(f'#mode {m:o} {p}\n' for p, (_d, m) in sorted(files.items()))
    manifest = f'# zavod server package; source commit {head}\n#arch {arch}\n' + modes + manifest
    files['MANIFEST.sha256'] = (manifest.encode(), 0o644)
    os.makedirs(out_dir, exist_ok=True)
    name = f'zavod-server-{head[:12]}.tar' if arch == 'x64' else f'zavod-server-{head[:12]}-{arch}.tar'
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
