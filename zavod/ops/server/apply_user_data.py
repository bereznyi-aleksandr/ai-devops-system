# ДОКУМЕНТ: zavod/ops/server/apply_user_data.py
# ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 15:05 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 15:26 +03:00 (v0.2: аудит ChatGPT S6-prep R9,
#   L-S6-R9-01 — поля безопасности верхнего уровня больше не пропускаются молча. До любого изменения: неизвестное
#   поле верхнего уровня или пользователя — отказ; disable_root обязан быть true, ssh_pwauth — false (иначе отказ).
#   Их действие задаёт вставка sshd 10-zavod.conf; после записи файлов и ДО перезагрузки sshd программа читает
#   действующие настройки `sshd -T` и требует permitrootlogin no, passwordauthentication no,
#   kbdinteractiveauthentication no, pubkeyauthentication yes, authenticationmethods publickey; не так — отказ,
#   sshd не перезагружается, брандмауэр и запись «applied» не делаются.)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: аудит ChatGPT S6-prep R8, M-S6-R8-01 — первичная настройка сервера без буфера обмена компьютера агента.
#   Короткий стартер (render_starter.py), который оператор вставляет у провайдера С ТЕЛЕФОНА, скачивает с GitHub по
#   коммиту user-data.yaml и эту программу, сверяет обе ПОЛНЫЕ суммы SHA-256 и только тогда запускает её от root.
#   Программа применяет тот же cloud-config, что собирает render_user_data.py: пакеты, пользователи с ключами и
#   правилами sudo, все write_files байт в байт с правами и владельцем, все команды runcmd (включая ufw).
#   Заменяет CI-помощник zavod/ops/ci/apply_user_data_ci.py: CI теперь гоняет ЭТУ программу через тот же стартер.
# ВЫЗОВ: python3 -I apply_user_data.py user-data.yaml (от root; на сервере — только из стартера).
# ОГРАНИЧЕНИЯ: ничего не удаляет. Только стандартная библиотека Python (на сервере больше ничего нет). Брандмауэр
#   пропускается лишь на машине GitHub (ZAVOD_APPLY_CI_SKIP_FIREWALL=1 при CI=true и GITHUB_ACTIONS=true): ufw limit
#   на 22 мешает сквозной проверке по ssh на 127.0.0.1. Секретов не читает и не пишет.
import base64
import json
import os
import pwd
import subprocess
import sys

VERSION = 'v0.2'
TOP = {'users', 'disable_root', 'ssh_pwauth', 'package_update', 'packages', 'write_files', 'runcmd'}
USER = {'name', 'groups', 'shell', 'lock_passwd', 'sudo', 'ssh_authorized_keys', 'system', 'homedir', 'no_create_home'}
FILE = {'path', 'content', 'encoding', 'permissions', 'owner'}
# disable_root: true и ssh_pwauth: false — это то, что sshd обязан действительно применять (`sshd -T`).
SSHD_EFFECTIVE = {'permitrootlogin': 'no', 'passwordauthentication': 'no', 'kbdinteractiveauthentication': 'no',
                  'pubkeyauthentication': 'yes', 'authenticationmethods': 'publickey'}


def sh(*cmd, env=None):
    subprocess.run(list(cmd), check=True, env=env)


def ci_skip_firewall():
    e = os.environ
    return e.get('ZAVOD_APPLY_CI_SKIP_FIREWALL') == '1' and e.get('CI') == 'true' and e.get('GITHUB_ACTIONS') == 'true'


def packages(cfg):
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive')
    if cfg.get('package_update'):
        sh('apt-get', 'update', '-q', env=env)
    if cfg.get('packages'):
        sh('apt-get', 'install', '-y', '-q', *cfg['packages'], env=env)


def user(u):
    name = u['name']
    try:
        pwd.getpwnam(name)
    except KeyError:
        if u.get('system'):
            sh('useradd', '-r', '-M', '-d', u.get('homedir', '/nonexistent'), '-s', u['shell'], name)
        else:
            sh('useradd', '-m', '-s', u['shell'], name)
    if u.get('lock_passwd'):
        sh('usermod', '-L', name)
    for g in u.get('groups', []):
        sh('usermod', '-aG', g, name)
    for rule in u.get('sudo', []):
        path = f'/etc/sudoers.d/80-zavod-user-{name}'
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
    if cmd[0] == 'ufw' and ci_skip_firewall():
        return 'skipped (CI)'
    if cmd[:2] == ['systemctl', 'reload'] and subprocess.run(cmd).returncode != 0:
        sh('systemctl', 'restart', cmd[2])
        return 'restarted'
    sh(*cmd)
    return 'ok'


def parse(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    lines = text.split('\n', 2)
    if len(lines) < 3 or lines[0] != '#cloud-config' or not lines[1].startswith('# '):
        raise SystemExit('REFUSED: not a zavod cloud-config')
    return validate(json.loads(lines[2]))


def validate(cfg):
    # L-S6-R9-01: всё, что программа не применяет сама, — отказ до любого изменения (fail-closed).
    def refuse(why):
        raise SystemExit('REFUSED: ' + why)
    if not isinstance(cfg, dict):
        refuse('cloud-config is not an object')
    extra = set(cfg) - TOP
    if extra:
        refuse('unsupported top-level field ' + ', '.join(sorted(extra)))
    if cfg.get('disable_root') is not True or cfg.get('ssh_pwauth') is not False:
        refuse('disable_root must be true and ssh_pwauth false')
    for u in cfg.get('users', []):
        if set(u) - USER:
            refuse('unsupported user field ' + ', '.join(sorted(set(u) - USER)))
    for w in cfg.get('write_files', []):
        if set(w) - FILE:
            refuse('unsupported write_files field ' + ', '.join(sorted(set(w) - FILE)))
    return cfg


def sshd_mismatch(text):
    # вывод `sshd -T`: «ключ значение» по строке, ключи в нижнем регистре
    got = {}
    for line in text.splitlines():
        k, _, v = line.partition(' ')
        got.setdefault(k.lower(), v.strip())
    return sorted(f'{k}={got.get(k)!r} (need {v!r})' for k, v in SSHD_EFFECTIVE.items() if got.get(k) != v)


def check_sshd():
    r = subprocess.run(['sshd', '-T'], capture_output=True, text=True)
    bad = ['sshd -T failed: ' + r.stderr.strip()] if r.returncode != 0 else sshd_mismatch(r.stdout)
    if bad:
        raise SystemExit('REFUSED: effective sshd settings do not match disable_root/ssh_pwauth: ' + '; '.join(bad))


def main(argv):
    if len(argv) != 1:
        print('usage: apply_user_data.py user-data.yaml', file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        print('REFUSED: run as root', file=sys.stderr)
        return 2
    cfg = parse(argv[0])
    packages(cfg)
    for u in cfg['users']:
        user(u)
    os.makedirs('/run/sshd', exist_ok=True)
    for w in cfg['write_files']:
        write_file(w)
    check_sshd()
    done =[[' '.join(c), run(c)] for c in cfg['runcmd']]
    out = json.dumps({'applied': f'apply_user_data {VERSION}', 'users': [u['name'] for u in cfg['users']],
                      'files': [w['path'] for w in cfg['write_files']], 'runcmd': done}, ensure_ascii=False, indent=1)
    print(out)
    with open('/var/log/zavod-apply.json', 'w', encoding='utf-8') as f:
        f.write(out + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
