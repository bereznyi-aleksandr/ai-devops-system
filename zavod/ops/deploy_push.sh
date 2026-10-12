#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/deploy_push.sh
# ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 10:35 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 16:52 +03:00 (v0.3: аудит ChatGPT S6-prep R11A M-S6-R11-01 —
#   пятый файл: объект коммита head (git cat-file commit), по нему сервер сверяет архив с head; v0.2: аудит ChatGPT
#   S6-prep R2 M-S6-R2-02 — передаются ещё билет выпуска и его подпись; сервер без верной подписи ничего не ставит)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: этап 6, E6-2 — передача выпуска на сервер. Запускается ТОЛЬКО в GitHub Actions (workflow выкладки
#   продукта), где закрытый ключ zavod лежит в секрете; агент Завода ключ не видит и не использует (аудит ChatGPT
#   S6-prep M-S6-05). Пять scp в папку приёма /var/lib/zavod-incoming и один ssh: sudo -n install_release.sh.
#   Печатает строку сервера INSTALL_OK|INSTALL_REFUSED; код возврата — код сервера.
# ВЫЗОВ: DEPLOY_KEY_FILE=... KNOWN_HOSTS_FILE=... deploy_push.sh HOST MANIFEST.json ARTIFACT.tar TICKET.json TICKET.sig COMMIT.obj
# ОГРАНИЧЕНИЯ: адрес — только IPv4/IPv6/имя без пробелов и ; ; проверка ключа хоста строгая (known_hosts от
#   оператора), BatchMode — без паролей. Ключ в журнал не пишется. Ничего не удаляет.
set -euo pipefail
HOST=${1:?host}
MANIFEST=${2:?manifest}
ARTIFACT=${3:?artifact}
TICKET=${4:?ticket}
SIG=${5:?ticket signature}
COMMIT=${6:?commit object}
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
scp -q -P "$PORT" "${OPTS[@]}" "$TICKET" "zavod@$HOST:$IN/ticket_$H8.json"
scp -q -P "$PORT" "${OPTS[@]}" "$SIG" "zavod@$HOST:$IN/ticket_$H8.sig"
scp -q -P "$PORT" "${OPTS[@]}" "$COMMIT" "zavod@$HOST:$IN/commit_$H8.obj"
set +e
ssh -p "$PORT" "${OPTS[@]}" "zavod@$HOST" sudo -n /opt/zavod-ops/install_release.sh "$IN/manifest_$H8.json" "$IN/artifact_$H8.tar" \
  "$IN/ticket_$H8.json" "$IN/ticket_$H8.sig" "$IN/commit_$H8.obj"
rc=$?
set -e
exit "$rc"
