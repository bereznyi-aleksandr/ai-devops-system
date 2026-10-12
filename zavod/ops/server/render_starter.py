# ДОКУМЕНТ: zavod/ops/server/render_starter.py
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 15:05 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: аудит ChatGPT S6-prep R8, M-S6-R8-01 — короткий стартер первичной настройки сервера. Его вставляет
#   оператор у провайдера С ТЕЛЕФОНА, скопировав из ответа независимого аудитора в окне ChatGPT; компьютер с агентом
#   и его буфер обмена в доставке не участвуют. Стартер скачивает с GitHub по ТОЧНОМУ коммиту (содержимое коммита
#   изменить нельзя) user-data.yaml и apply_user_data.py, сверяет ПОЛНЫЕ SHA-256 обоих (sha256sum -c --strict) и
#   только при совпадении запускает применение от root. Подмена любого файла — отказ до применения.
#   Аудитор получает фактический user-data оператора, проверяет его (verify_user_data.py) и сам пересобирает
#   стартер по этому шаблону; совпавший текст он приводит в ответе целиком вместе с двумя отпечатками ключей.
# ВЫЗОВ: python3 -I render_starter.py --commit <40 hex> --user-data <файл> [--apply <файл>]
#   --base/--proto — только для проверок (локальный file://); боевой стартер — с https://raw.githubusercontent.com.
# ОГРАНИЧЕНИЯ: секретов нет: только открытый адрес репозитория, коммит и суммы.
import argparse
import hashlib
import os
import re
import sys

VERSION = 'v0.1'
REPO_RAW = 'https://raw.githubusercontent.com/bereznyi-aleksandr/ai-devops-system'
UD_PATH = 'p1/user-data.yaml'
APPLY_PATH = 'server/apply_user_data.py'
HEX40 = re.compile(r'^[0-9a-f]{40}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def starter(commit, ud_sha, apply_sha, *, base=None, proto='=https'):
    if not HEX40.match(commit or '') or not HEX64.match(ud_sha or '') or not HEX64.match(apply_sha or ''):
        raise SystemExit('REFUSED: commit must be 40 hex, sums must be 64 hex')
    if proto not in ('=https', '=file'):
        raise SystemExit('REFUSED: bad proto')
    base = base or f'{REPO_RAW}/{commit}/zavod/ops'
    if "'" in base or '\n' in base:
        raise SystemExit('REFUSED: bad base')
    return ('#!/bin/sh\n'
            f'# zavod p1 starter {VERSION}, commit {commit}\n'
            'set -eu\n'
            f"B='{base}'\n"
            'W=$(mktemp -d)\n'
            'cd "$W"\n'
            f"curl -fsSL --proto '{proto}' -o user-data.yaml \"$B/{UD_PATH}\"\n"
            f"curl -fsSL --proto '{proto}' -o apply_user_data.py \"$B/{APPLY_PATH}\"\n"
            f"printf '%s  %s\\n' {ud_sha} user-data.yaml {apply_sha} apply_user_data.py | sha256sum -c --strict -\n"
            'exec python3 -I apply_user_data.py user-data.yaml\n')


def sha_file(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--commit', required=True)
    ap.add_argument('--user-data', required=True)
    ap.add_argument('--apply', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apply_user_data.py'))
    ap.add_argument('--base')
    ap.add_argument('--proto', default='=https')
    a = ap.parse_args(argv)
    text = starter(a.commit, sha_file(a.user_data), sha_file(a.apply), base=a.base, proto=a.proto)
    sys.stdout.buffer.write(text.encode('utf-8'))
    sys.stderr.write(f'STARTER_SHA256 {hashlib.sha256(text.encode("utf-8")).hexdigest()}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
