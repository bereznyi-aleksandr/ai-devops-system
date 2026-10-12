# ДОКУМЕНТ: zavod/ops/server/render_user_data.py
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 10:35 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# ЗАМЕНЯЕТ: server/cloud-init.v0_1.SUPERSEDED.yaml (аудит ChatGPT S6-prep M-S6-02, M-S6-03, M-S6-05)
# НАЗНАЧЕНИЕ: этап 6, E6-1/E6-2 — собирает один файл user-data (cloud-init) для сервера продукта. Оператор вставляет
#   его в поле «User data» при создании сервера. Два входа, два ключа, оба ОТКРЫТЫЕ:
#   admin — личный вход оператора, полный sudo; ключ агентам не передаётся и ими не используется;
#   zavod — только выкладка: ключ с опцией restrict (без проброса и терминала), sudo только на
#   /opt/zavod-ops/install_release.sh, запись только в папку приёма /var/lib/zavod-incoming (zavod:zavod 0700).
#   Закрытый ключ zavod оператор кладёт в секрет GitHub (выкладку делает workflow, не агент).
#   В файл встраиваются (base64) install_release.sh, liveness_watch.py, sqlite_backup.py, службы, sshd, sudoers,
#   target.env (номер и имя репозитория, tenant — не секреты). Секретов в результате нет: токен бота оператор
#   кладёт сам в /etc/zavod-p1/secrets.env и watch.env после создания сервера.
# ВЫЗОВ: python3 render_user_data.py --admin-pubkey F --deploy-pubkey F --repo-id N --repo O/R --tenant UUID > user-data.yaml
# ОГРАНИЧЕНИЯ: закрытый ключ (строка с PRIVATE KEY) — отказ; принимаются только ssh-ed25519 / ecdsa / rsa открытые ключи.
import argparse
import base64
import json
import os
import re
import sys

VERSION = 'v0.1'
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
AllowUsers admin zavod
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


def wf(path, content, perm, owner='root:root'):
    data = content if isinstance(content, bytes) else content.encode('utf-8')
    return {'path': path, 'permissions': perm, 'owner': owner, 'encoding': 'b64',
            'content': base64.b64encode(data).decode('ascii')}


def src(rel):
    with open(os.path.join(OPS, rel), 'rb') as f:
        return f.read()


def render(admin_pub, deploy_pub, repo_id, repo, tenant):
    if not (isinstance(repo_id, int) and repo_id > 0 and REPO.match(repo) and UUID.match(tenant)):
        raise SystemExit('REFUSED: bad target')
    if admin_pub.split()[1] == deploy_pub.split()[1]:
        raise SystemExit('REFUSED: admin and deploy keys must differ')
    target = f'REPO_ID="{repo_id}"\nREPO_FULL_NAME="{repo}"\nTENANT_ID="{tenant}"\n'
    cfg = {
        'users': [
            {'name': 'admin', 'groups': ['sudo'], 'shell': '/bin/bash', 'lock_passwd': True,
             'sudo': ['ALL=(ALL) NOPASSWD:ALL'], 'ssh_authorized_keys': [admin_pub]},
            {'name': 'zavod', 'shell': '/bin/bash', 'lock_passwd': True,
             'ssh_authorized_keys': ['restrict ' + deploy_pub]},
            {'name': 'p1', 'system': True, 'shell': '/usr/sbin/nologin', 'lock_passwd': True,
             'homedir': '/var/lib/zavod-p1', 'no_create_home': True},
        ],
        'disable_root': True,
        'ssh_pwauth': False,
        'package_update': True,
        'packages': ['ufw', 'unattended-upgrades', 'sqlite3'],
        'write_files': [
            wf('/etc/ssh/sshd_config.d/10-zavod.conf', SSHD, '0644'),
            wf('/etc/sudoers.d/90-zavod-deploy', SUDOERS, '0440'),
            wf('/opt/zavod-ops/install_release.sh', src('server/install_release.sh'), '0755'),
            wf('/opt/zavod-ops/liveness_watch.py', src('liveness_watch.py'), '0644'),
            wf('/opt/zavod-ops/sqlite_backup.py', src('sqlite_backup.py'), '0644'),
            wf('/etc/systemd/system/zavod-p1.service', src('server/zavod-p1.service'), '0644'),
            wf('/etc/systemd/system/zavod-p1-watch.service', src('server/zavod-p1-watch.service'), '0644'),
            wf('/etc/zavod-p1/target.env', target, '0644'),
            wf('/etc/zavod-p1/content.json', json.dumps(CONTENT, ensure_ascii=False), '0644'),
        ],
        'runcmd': [
            ['install', '-d', '-o', 'p1', '-g', 'p1', '-m', '0750', '/var/lib/zavod-p1', '/var/lib/zavod-p1/backups'],
            ['install', '-d', '-o', 'zavod', '-g', 'zavod', '-m', '0700', INCOMING],
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
            f'ключи открытые; repo {repo} ({repo_id}); tenant {tenant}\n')
    return head + json.dumps(cfg, ensure_ascii=False, indent=1) + '\n'


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--admin-pubkey', required=True)
    ap.add_argument('--deploy-pubkey', required=True)
    ap.add_argument('--repo-id', type=int, required=True)
    ap.add_argument('--repo', required=True)
    ap.add_argument('--tenant', required=True)
    a = ap.parse_args(argv)
    sys.stdout.write(render(read_pub(a.admin_pubkey), read_pub(a.deploy_pubkey), a.repo_id, a.repo, a.tenant))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
