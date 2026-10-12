# ДОКУМЕНТ: zavod/ops/external_check.py
# ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:40 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 10:32 +03:00 (v0.2: аудит ChatGPT
#   S6-prep M-S6-01 — сканируются ВСЕ порты 1–65535, а не 1–1024 и список; 512 потоков, ожидание 0.7 с; пользователи
#   по умолчанию admin, zavod, root)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: этап 6, E6-1 — проверка сервера СНАРУЖИ: (1) все TCP-порты 1–65535 — открыты только объявленные;
#   (2) вход по паролю невозможен: клиент ssh без ключа получает отказ, в котором сервер предлагает только publickey
#   (для пользователей admin, zavod и root). Итог — одна строка JSON и код 0|1.
# ВЫЗОВ: python3 external_check.py HOST [--declared 22] [--users admin,zavod,root] [--timeout 0.7]
# ОГРАНИЧЕНИЯ: только stdlib и клиент ssh. Ключи не используются (PubkeyAuthentication=no), пароль не вводится
#   (BatchMode=yes). Адрес сервера секретом не считается. Сканировать только свой сервер.
import argparse
import json
import socket
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

VERSION = 'v0.2'
ALL_PORTS = range(1, 65536)


def open_ports(host, ports, timeout=0.7, workers=512):
    def probe(p):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            return p if s.connect_ex((host, p)) == 0 else None
        finally:
            s.close()
    with ThreadPoolExecutor(workers) as ex:
        return sorted(p for p in ex.map(probe, ports) if p is not None)


def password_refused(host, user, port=22):
    with tempfile.NamedTemporaryFile(prefix='kh_', delete=False) as kh:
        known = kh.name
    cmd = ['ssh', '-p', str(port), '-o', 'BatchMode=yes', '-o', 'PubkeyAuthentication=no',
           '-o', 'PreferredAuthentications=password,keyboard-interactive', '-o', 'StrictHostKeyChecking=accept-new',
           '-o', f'UserKnownHostsFile={known}', '-o', 'ConnectTimeout=10', f'{user}@{host}', 'true']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    err = r.stderr.strip().splitlines()
    last = next((s for s in reversed(err) if 'Permission denied' in s), '')
    methods = last[last.find('(') + 1:last.rfind(')')] if '(' in last else ''
    return {'user': user, 'rc': r.returncode, 'methods': methods, 'refused': r.returncode != 0 and methods == 'publickey'}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('host')
    ap.add_argument('--declared', default='22')
    ap.add_argument('--users', default='admin,zavod,root')
    ap.add_argument('--timeout', type=float, default=0.7)
    a = ap.parse_args(argv)
    declared = sorted(int(x) for x in a.declared.split(',') if x)
    ports = list(ALL_PORTS)
    found = open_ports(a.host, ports, timeout=a.timeout)
    pw = [password_refused(a.host, u, declared[0] if declared else 22) for u in a.users.split(',') if u]
    ok = found == declared and all(x['refused'] for x in pw)
    print(json.dumps({'tool': f'external_check {VERSION}', 'scanned': len(ports), 'declared': declared, 'open': found,
                      'password_login': pw, 'result': 'PASS' if ok else 'FAIL'}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
