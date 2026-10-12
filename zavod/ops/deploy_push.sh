#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/deploy_push.sh
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 10:35 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: этап 6, E6-2 — передача выпуска на сервер. Запускается ТОЛЬКО в GitHub Actions (workflow выкладки
#   продукта), где закрытый ключ zavod лежит в секрете; агент Завода ключ не видит и не использует (аудит ChatGPT
#   S6-prep M-S6-05). Два scp в папку приёма /var/lib/zavod-incoming и один ssh: sudo -n install_release.sh.
#   Печатает строку сервера INSTALL_OK|INSTALL_REFUSED; код возврата — код сервера.
# ВЫЗОВ: DEPLOY_KEY_FILE=... KNOWN_HOSTS_FILE=... deploy_push.sh HOST MANIFEST.json ARTIFACT.tar
# ОГРАНИЧЕНИЯ: адрес — только IPv4/IPv6/имя без пробелов и ; ; проверка ключа хоста строгая (known_hosts от
#   оператора), BatchMode — без паролей. Ключ в журнал не пишется. Ничего не удаляет.
set -euo pipefail
HOST=${1:?host}
MANIFEST=${2:?manifest}
ARTIFACT=${3:?artifact}
KEY=${DEPLOY_KEY_FILE:?DEPLOY_KEY_FILE}
KH=${KNOWN_HOSTS_FILE:?KNOWN_HOSTS_FILE}
PORT=${DEPLOY_PORT:-22}
IN=/var/lib/zavod-incoming

[[ "$HOST" =~ ^[A-Za-z0-9.:-]+$ ]] || { echo "DEPLOY_REFUSED code=BAD_HOST"; exit 2; }
[[ "$PORT" =~ ^[0-9]{1,5}$ ]] || { echo "DEPLOY_REFUSED code=BAD_PORT"; exit 2; }
HEAD=$(python3 -I -c 'import json,sys; m=json.load(open(sys.argv[1],encoding="utf-8")); m=m.get("manifest",m); print(m["head_sha"])' "$MANIFEST")
[[ "$HEAD" =~ ^[0-9a-f]{40}$ ]] || { echo "DEPLOY_REFUSED code=BAD_HEAD"; exit 2; }
H8=${HEAD:0:8}
OPTS=(-i "$KEY" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$KH")

scp -q -P "$PORT" "${OPTS[@]}" "$MANIFEST" "zavod@$HOST:$IN/manifest_$H8.json"
scp -q -P "$PORT" "${OPTS[@]}" "$ARTIFACT" "zavod@$HOST:$IN/artifact_$H8.tar"
set +e
ssh -p "$PORT" "${OPTS[@]}" "zavod@$HOST" sudo -n /opt/zavod-ops/install_release.sh "$IN/manifest_$H8.json" "$IN/artifact_$H8.tar"
rc=$?
set -e
exit "$rc"
