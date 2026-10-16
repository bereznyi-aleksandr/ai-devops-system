# ДОКУМЕНТ: zavod/ops/server/render_user_data.py
# ВЕРСИЯ: v0.7  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 10:35 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-16 19:53 +03:00 (v0.7: L-S6-R12-01 и M-R13-02 аудита Codex — VERSION = v0.7 в выводе;
#   пакет git: install_release.sh v0.5 пересчитывает хеши выпуска через git с детектором коллизий SHA1DC; v0.6: аудит ChatGPT S6-prep R7, M-S6-R7-01 —
#   вторая строка user-data несёт и ADMIN_KEY_FINGERPRINT (ключ входа zadmin = путь к root): оператор сверяет его с
#   отпечатком своего закрытого ключа zavod_p1_admin до вставки (OD-5 v1.9 шаги 4 и 7), подмена ключа zadmin видна;
#   render сам проверяет вид всех трёх строк ключей (без опций перед типом ключа), а не только read_pub; v0.5: аудит ChatGPT S6-prep R6 —
#   L-S6-R6-01: ключ подписи разбирается строго (канонический base64 «туда-обратно», блок ssh-ed25519, 32 байта, без
#   хвоста). M-S6-R6-01: сверка «ключ = отпечаток» в этой программе — только защита от ошибки: её запускает агент, и
#   он мог бы подать свою пару. Поэтому отпечаток ключа подписи печатается во ВТОРОЙ строке user-data, и оператор
#   сверяет его со своим экраном (ssh-keygen -lf по ЗАКРЫТОМУ ключу) до вставки (OD-5 v1.7 шаг 7) и после создания
#   сервера — по файлу на сервере (шаг 8а). Граница — это сверка оператора и файл root на сервере; v0.4: аудит ChatGPT S6-prep R5 M-S6-R5-01 —
#   обязательный --release-signer-fingerprint: отпечаток SHA256 ключа подписи, который оператор прочитал на своём
#   экране (OD-5 шаг 4). Ключ подписи — только ssh-ed25519; отпечаток не того вида или не совпал с .pub — отказ ДО
#   вывода user-data: подменённый .pub на сервер не попадёт; v0.3: аудит ChatGPT S6-prep R2 M-S6-R2-02 —
#   третий открытый ключ --release-signer-pubkey: ключ подписи билетов выпуска Завода; кладётся в
#   /etc/zavod-p1/release_signers (root 0644) с ограничением namespaces="zavod-release-ticket@v1"; все три ключа
#   обязаны различаться; папка билетов /var/lib/zavod-p1/tickets root 0700; v0.2: пользователь admin переименован в zadmin: в Ubuntu уже есть группа admin, useradd отказывает (CI 38219321184))
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# ЗАМЕНЯЕТ: server/cloud-init.v0_1.SUPERSEDED.yaml (аудит ChatGPT S6-prep M-S6-02, M-S6-03, M-S6-05)
# НАЗНАЧЕНИЕ: этап 6, E6-1/E6-2 — собирает один файл user-data (cloud-init) для сервера продукта. Оператор вставляет
#   его в поле «User data» при создании сервера. Два входа, два ключа, оба ОТКРЫТЫЕ:
#   zadmin — личный вход оператора, полный sudo; ключ агентам не передаётся и ими не используется;
#   zavod — только выкладка: ключ с опцией restrict (без проброса и терминала), sudo только на
#   /opt/zavod-ops/install_release.sh, запись только в папку приёма /var/lib/zavod-incoming (zavod:zavod 0700).
#   Закрытый ключ zavod оператор кладёт в секрет GitHub (выкладку делает workflow, не агент).
#   В файл встраиваются (base64) install_release.sh, liveness_watch.py, sqlite_backup.py, службы, sshd, sudoers,
#   target.env (номер и имя репозитория, tenant — не секреты). Секретов в результате нет: токен бота оператор
#   кладёт сам в /etc/zavod-p1/secrets.env и watch.env после создания сервера.
# ВЫЗОВ: python3 render_user_data.py --admin-pubkey F --deploy-pubkey F --release-signer-pubkey F
#   --release-signer-fingerprint SHA256:… --repo-id N --repo O/R --tenant UUID > user-data.yaml
# ОГРАНИЧЕНИЯ: закрытый ключ (строка с PRIVATE KEY) — отказ; принимаются только ssh-ed25519 / ecdsa / rsa открытые ключи.
import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import sys

VERSION = 'v0.7'
NAMESPACE = 'zavod-release-ticket@v1'
HERE = os.path.dirname(os.path.abspath(__file__))
OPS = os.path.dirname(HERE)
PUB = re.compile(r'^(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) [A-Za-z0-9+/=]{40,}( [^\r\n]{0,80})?$')
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
INCOMING = '/var/lib/zavod-incoming'

SSHD = """PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
AuthenticationMethods publickey
AllowUsers zadmin zavod
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
MaxAuthTries 3
"""
SUDOERS = """# zavod: только установка выпуска; переменные окружения не передаются (env_reset по умолчанию)
zavod ALL=(root) NOPASSWD: /opt/zavod-ops/install_release.sh
"""
CONTENT = {'services': 'Разработка ботов и сайтов', 'prices': 'Бот от 300 USD', 'contacts': 'Телефон +380 44 000 00 00'}


def read_pub(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    if 'PRIVATE KEY' in text:
        raise SystemExit('REFUSED: private key given; only the .pub file is accepted')
    line = text.strip()
    if '\n' in line or not PUB.match(line):
        raise SystemExit('REFUSED: not a single OpenSSH public key line')
    return line


FP = re.compile(r'^SHA256:[A-Za-z0-9+/]{43}$')


def key_blob(pub_line):
    # строгий base64: алфавит и «=» (validate=True) и каноничность — байты, закодированные обратно, дают ту же строку
    try:
        text = pub_line.split()[1]
        blob = base64.b64decode(text, validate=True)
    except (binascii.Error, IndexError):
        raise SystemExit('REFUSED: bad public key encoding')
    if base64.b64encode(blob).decode('ascii') != text:
        raise SystemExit('REFUSED: non-canonical public key encoding')
    return blob


def ed25519_blob(pub_line):
    # блок ключа: string "ssh-ed25519", string <32 байта>, ничего после
    blob = key_blob(pub_line)
    def take(off):
        if off + 4 > len(blob):
            raise SystemExit('REFUSED: bad ssh-ed25519 key blob')
        n = int.from_bytes(blob[off:off + 4], 'big')
        if off + 4 + n > len(blob):
            raise SystemExit('REFUSED: bad ssh-ed25519 key blob')
        return blob[off + 4:off + 4 + n], off + 4 + n
    kind, off = take(0)
    key, off = take(off)
    if pub_line.split()[0] != 'ssh-ed25519' or kind != b'ssh-ed25519' or len(key) != 32 or off != len(blob):
        raise SystemExit('REFUSED: release signer key must be a well-formed ssh-ed25519 key')
    return blob


def fingerprint(pub_line):
    # тот же отпечаток, что печатает ssh-keygen -lf: SHA-256 от двоичного ключа, base64 без «=»
    return 'SHA256:' + base64.b64encode(hashlib.sha256(key_blob(pub_line)).digest()).decode('ascii').rstrip('=')


def check_release_key(release_pub, release_fp):
    if not isinstance(release_fp, str) or not FP.match(release_fp):
        raise SystemExit('REFUSED: release signer fingerprint (SHA256:...) from the operator is required')
    ed25519_blob(release_pub)
    if fingerprint(release_pub) != release_fp:
        raise SystemExit('REFUSED: release signer key does not match the operator fingerprint')


def wf(path, content, perm, owner='root:root'):
    data = content if isinstance(content, bytes) else content.encode('utf-8')
    return {'path': path, 'permissions': perm, 'owner': owner, 'encoding': 'b64',
            'content': base64.b64encode(data).decode('ascii')}


def src(rel):
    with open(os.path.join(OPS, rel), 'rb') as f:
        return f.read()


def render(admin_pub, deploy_pub, release_pub, repo_id, repo, tenant, *, release_fp):
    if not (isinstance(repo_id, int) and repo_id > 0 and REPO.match(repo) and UUID.match(tenant)):
        raise SystemExit('REFUSED: bad target')
    if not all(isinstance(k, str) and PUB.match(k) for k in (admin_pub, deploy_pub, release_pub)):
        raise SystemExit('REFUSED: not a single OpenSSH public key line')
    if len({admin_pub.split()[1], deploy_pub.split()[1], release_pub.split()[1]}) != 3:
        raise SystemExit('REFUSED: admin, deploy and release signer keys must differ')
    check_release_key(release_pub, release_fp)
    signers = f'zavod-release namespaces="{NAMESPACE}" {" ".join(release_pub.split()[:2])}\n'
    target = f'REPO_ID="{repo_id}"\nREPO_FULL_NAME="{repo}"\nTENANT_ID="{tenant}"\n'
    cfg = {
        'users': [
            {'name': 'zadmin', 'groups': ['sudo'], 'shell': '/bin/bash', 'lock_passwd': True,
             'sudo': ['ALL=(ALL) NOPASSWD:ALL'], 'ssh_authorized_keys': [admin_pub]},
            {'name': 'zavod', 'shell': '/bin/bash', 'lock_passwd': True,
             'ssh_authorized_keys': ['restrict ' + deploy_pub]},
            {'name': 'p1', 'system': True, 'shell': '/usr/sbin/nologin', 'lock_passwd': True,
             'homedir': '/var/lib/zavod-p1', 'no_create_home': True},
        ],
        'disable_root': True,
        'ssh_pwauth': False,
        'package_update': True,
        'packages': ['ufw', 'unattended-upgrades', 'sqlite3', 'git'],
        'write_files': [
            wf('/etc/ssh/sshd_config.d/10-zavod.conf', SSHD, '0644'),
            wf('/etc/sudoers.d/90-zavod-deploy', SUDOERS, '0440'),
            wf('/opt/zavod-ops/install_release.sh', src('server/install_release.sh'), '0755'),
            wf('/opt/zavod-ops/liveness_watch.py', src('liveness_watch.py'), '0644'),
            wf('/opt/zavod-ops/sqlite_backup.py', src('sqlite_backup.py'), '0644'),
            wf('/etc/systemd/system/zavod-p1.service', src('server/zavod-p1.service'), '0644'),
            wf('/etc/systemd/system/zavod-p1-watch.service', src('server/zavod-p1-watch.service'), '0644'),
            wf('/etc/zavod-p1/target.env', target, '0644'),
            wf('/etc/zavod-p1/release_signers', signers, '0644'),
            wf('/etc/zavod-p1/content.json', json.dumps(CONTENT, ensure_ascii=False), '0644'),
        ],
        'runcmd': [
            ['install', '-d', '-o', 'p1', '-g', 'p1', '-m', '0750', '/var/lib/zavod-p1', '/var/lib/zavod-p1/backups'],
            ['install', '-d', '-o', 'zavod', '-g', 'zavod', '-m', '0700', INCOMING],
            ['install', '-d', '-o', 'root', '-g', 'root', '-m', '0700', '/var/lib/zavod-p1/tickets'],
            ['install', '-d', '-o', 'root', '-g', 'root', '-m', '0755', '/opt/zavod-p1', '/opt/zavod-p1/releases'],
            ['visudo', '-cf', '/etc/sudoers.d/90-zavod-deploy'],
            ['sshd', '-t'],
            ['systemctl', 'reload', 'ssh'],
            ['systemctl', 'daemon-reload'],
            ['ufw', 'default', 'deny', 'incoming'],
            ['ufw', 'default', 'allow', 'outgoing'],
            ['ufw', 'limit', '22/tcp'],
            ['ufw', '--force', 'enable'],
        ],
    }
    head = (f'#cloud-config\n# zavod/ops/server/render_user_data.py {VERSION}; секретов нет; '
            f'ключи открытые; repo {repo} ({repo_id}); tenant {tenant}; '
            f'RELEASE_KEY_FINGERPRINT {release_fp}; ADMIN_KEY_FINGERPRINT {fingerprint(admin_pub)} '
            f'(сверить оба со своими записями до вставки)\n')
    return head + json.dumps(cfg, ensure_ascii=False, indent=1) + '\n'


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--admin-pubkey', required=True)
    ap.add_argument('--deploy-pubkey', required=True)
    ap.add_argument('--release-signer-pubkey', required=True)
    ap.add_argument('--release-signer-fingerprint', required=True)
    ap.add_argument('--repo-id', type=int, required=True)
    ap.add_argument('--repo', required=True)
    ap.add_argument('--tenant', required=True)
    a = ap.parse_args(argv)
    sys.stdout.write(render(read_pub(a.admin_pubkey), read_pub(a.deploy_pubkey), read_pub(a.release_signer_pubkey), a.repo_id, a.repo, a.tenant,
                            release_fp=a.release_signer_fingerprint))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
