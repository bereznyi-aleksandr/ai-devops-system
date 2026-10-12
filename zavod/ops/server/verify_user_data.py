# ДОКУМЕНТ: zavod/ops/server/verify_user_data.py
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 14:42 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: аудит ChatGPT S6-prep R7, M-S6-R7-01 — проверка готового user-data.yaml ДО вставки у провайдера.
#   Файл первичной настройки сервера собирает агент, и он мог бы, сохранив верный ключ подписи, добавить себе путь к
#   root (лишний ключ zadmin, широкий sudo, служба от root). Программа берёт из файла только входы (два ключа входа,
#   ключ подписи, отпечаток, цель), заново собирает user-data кодом этого коммита и требует совпадения байт в байт.
#   Любое добавление — USERDATA_MISMATCH. При совпадении печатает SHA-256 файла и перечень всех прав и файлов.
# КТО ГРАНИЦА: не эта программа (её запускает агент) — её вывод и сам файл проверяет независимый аудитор и называет
#   USERDATA_SHA256 в своём ответе; оператор вставляет у провайдера только файл с этой суммой (функция
#   Copy-ZavodUserData, OD-5 v1.8 шаг 7). Программа — способ для аудитора и CI проверить, что в файле нет ничего,
#   кроме собранного проверенным кодом.
# ОГРАНИЧЕНИЯ: секретов не читает; на вход — только user-data.yaml (открытые ключи).
import base64
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_user_data as ru  # noqa: E402

VERSION = 'v0.1'


class Mismatch(Exception):
    pass


def inputs(text):
    lines = text.split('\n')
    if len(lines) < 3 or lines[0] != '#cloud-config':
        raise Mismatch('first line is not #cloud-config')
    m = re.search(r'RELEASE_KEY_FINGERPRINT (SHA256:[A-Za-z0-9+/]{43}) ', lines[1])
    if not m:
        raise Mismatch('no RELEASE_KEY_FINGERPRINT in line 2')
    try:
        cfg = json.loads('\n'.join(lines[2:]))
        users = {u['name']: u for u in cfg['users']}
        admin = users['zadmin']['ssh_authorized_keys'][0]
        deploy = users['zavod']['ssh_authorized_keys'][0]
        files = {f['path']: base64.b64decode(f['content'], validate=True).decode('utf-8') for f in cfg['write_files']}
        signer = files['/etc/zavod-p1/release_signers'].split()
        env = dict(line.split('=', 1) for line in files['/etc/zavod-p1/target.env'].split('\n') if line)
        target = (int(env['REPO_ID'].strip('"')), env['REPO_FULL_NAME'].strip('"'), env['TENANT_ID'].strip('"'))
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        raise Mismatch(f'cannot read inputs: {type(e).__name__}')
    if not deploy.startswith('restrict '):
        raise Mismatch('deploy key is not restricted')
    return cfg, admin, deploy[len('restrict '):], ' '.join(signer[2:4]), target, m.group(1)


def verify(data):
    text = data.decode('utf-8')
    cfg, admin, deploy, release, target, fp = inputs(text)
    try:
        expected = ru.render(admin, deploy, release, *target, release_fp=fp)
    except SystemExit as e:
        raise Mismatch(f'render refused the inputs: {e}')
    if expected.encode('utf-8') != data:
        exp = expected.split('\n')
        got = text.split('\n')
        n = next((i for i in range(max(len(exp), len(got))) if i >= len(exp) or i >= len(got) or exp[i] != got[i]), 0)
        raise Mismatch(f'differs from the audited render at line {n + 1}')
    report = [f'USERDATA_OK sha256={hashlib.sha256(data).hexdigest()} bytes={len(data)} '
              f'render={ru.VERSION} verify={VERSION}',
              f'USER zadmin key {ru.fingerprint(admin)} sudo ALL (личный вход оператора)',
              f'USER zavod key {ru.fingerprint(deploy)} restrict; sudo только /opt/zavod-ops/install_release.sh',
              'USER p1 системный, без входа',
              f'RELEASE_SIGNER {fp}',
              f'TARGET repo_id={target[0]} repo={target[1]} tenant={target[2]}']
    for f in cfg['write_files']:
        body = base64.b64decode(f['content'])
        report.append(f"FILE {f['path']} {f['owner']} {f['permissions']} sha256={hashlib.sha256(body).hexdigest()}")
    report.append(f"RUNCMD {len(cfg['runcmd'])} команд, PACKAGES {' '.join(cfg['packages'])}")
    return '\n'.join(report) + '\n'


def main(argv):
    if len(argv) != 1:
        sys.stderr.write('usage: verify_user_data.py <user-data.yaml>\n')
        return 2
    with open(argv[0], 'rb') as f:
        data = f.read()
    try:
        out, rc = verify(data), 0
    except (Mismatch, UnicodeDecodeError) as e:
        out, rc = f'USERDATA_MISMATCH {e}\n', 1
    sys.stdout.buffer.write(out.encode('utf-8'))
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
