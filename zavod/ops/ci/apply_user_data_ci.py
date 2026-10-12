# ДОКУМЕНТ: zavod/ops/ci/apply_user_data_ci.py
# ВЕРСИЯ: v0.1  СТАТУС: SUPERSEDED
# ДАТА СОЗДАНИЯ: 2026-10-12 10:39 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 15:07 +03:00 (статус SUPERSEDED: заменён
#   zavod/ops/server/apply_user_data.py v0.1, который CI запускает через стартер оператора; файл не вызывается)
# ЗАМЕНЁН НА: zavod/ops/server/apply_user_data.py
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: только для CI (задание ops в zavod-kernel.yml). Применяет на одноразовой машине GitHub тот же
#   user-data, что собирает server/render_user_data.py для настоящего сервера: пользователи admin/zavod/p1, их
#   открытые ключи, все write_files байт в байт с правами и владельцем, все runcmd кроме ufw (брандмауэр машины
#   GitHub не трогаем). Так CI проверяет реальную схему прав (аудит ChatGPT S6-prep M-S6-02/03), а не её описание.
# ВЫЗОВ: sudo -E python3 -I zavod/ops/ci/apply_user_data_ci.py USER_DATA
# ОГРАНИЧЕНИЯ: отказывается работать вне GitHub Actions (нужны CI=true, GITHUB_ACTIONS=true) и не от root —
#   защита от случайного запуска на машине разработчика. Ничего не удаляет.
import base64
import json
import os
import pwd
import subprocess
import sys


def sh(*cmd):
    subprocess.run(list(cmd), check=True)


def user(u):
    name = u['name']
    try:
        pwd.getpwnam(name)
    except KeyError:
        if u.get('system'):
            sh('useradd', '-r', '-M', '-d', u.get('homedir', '/nonexistent'), '-s', u['shell'], name)
        else:
            sh('useradd', '-m', '-s', u['shell'], name)
    for g in u.get('groups', []):
        sh('usermod', '-aG', g, name)
    for rule in u.get('sudo', []):
        path = f'/etc/sudoers.d/80-ci-user-{name}'
        with open(path, 'x', encoding='utf-8') as f:
            f.write(f'{name} {rule}\n')
        os.chmod(path, 0o440)
        sh('visudo', '-cf', path)
    keys = u.get('ssh_authorized_keys')
    if keys:
        home = pwd.getpwnam(name).pw_dir
        d = os.path.join(home, '.ssh')
        os.makedirs(d, mode=0o700, exist_ok=True)
        p = os.path.join(d, 'authorized_keys')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('\n'.join(keys) + '\n')
        os.chmod(p, 0o600)
        sh('chown', '-R', f'{name}:{name}', d)


def write_file(w):
    data = base64.b64decode(w['content']) if w.get('encoding') == 'b64' else w['content'].encode('utf-8')
    os.makedirs(os.path.dirname(w['path']), exist_ok=True)
    with open(w['path'], 'wb') as f:
        f.write(data)
    os.chmod(w['path'], int(w['permissions'], 8))
    sh('chown', w.get('owner', 'root:root'), w['path'])


def run(cmd):
    if cmd[0] == 'ufw':
        return 'skipped'
    if cmd[:2] == ['systemctl', 'reload'] and subprocess.run(cmd).returncode != 0:
        sh('systemctl', 'restart', cmd[2])
        return 'restarted'
    sh(*cmd)
    return 'ok'


def main(argv):
    if os.environ.get('CI') != 'true' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.geteuid() != 0:
        print('REFUSED: CI-only helper, run as root inside GitHub Actions', file=sys.stderr)
        return 2
    with open(argv[0], encoding='utf-8') as f:
        head, body = f.read().split('\n', 1)
    if head != '#cloud-config':
        print('REFUSED: not cloud-config', file=sys.stderr)
        return 2
    cfg = json.loads(body.split('\n', 1)[1])
    for u in cfg['users']:
        user(u)
    os.makedirs('/run/sshd', exist_ok=True)
    for w in cfg['write_files']:
        write_file(w)
    done = [[' '.join(c), run(c)] for c in cfg['runcmd']]
    print(json.dumps({'applied': 'apply_user_data_ci v0.1', 'users': [u['name'] for u in cfg['users']],
                      'files': [w['path'] for w in cfg['write_files']], 'runcmd': done}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
