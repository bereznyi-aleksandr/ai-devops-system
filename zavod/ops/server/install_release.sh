#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/install_release.sh
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:40 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: этап 6, E6-2 — установка выпуска на сервере; вызывается адаптером Egress (одна строка outbox =
#   один вызов). Вторая линия сверки манифеста SR-13 на самом сервере: SHA-256 архива = artifact_sha256,
#   repo_id, repo_full_name и tenant_id = цель этого сервера из /etc/zavod-p1/target.env, head_sha — 40 hex.
#   Любое несовпадение — отказ с кодом до распаковки. Распаковка в releases/<head_sha>.partial → переименование
#   → атомарная смена ссылки current → перезапуск службы → запись в журнал. Повтор той же версии ничего не
#   меняет (идемпотентно: повторный вызов даёт тот же результат). Старые версии не удаляются — откат = ссылка.
# ВЫЗОВ: install_release.sh <manifest.json> <artifact.tar>; ROOT, TARGET_ENV, SERVICE, JOURNAL — для проверок.
# ОГРАНИЧЕНИЯ: секретов не читает; ничего не удаляет.
set -euo pipefail
MANIFEST=${1:?manifest}
ARTIFACT=${2:?artifact}
ROOT=${ROOT:-/opt/zavod-p1}
TARGET_ENV=${TARGET_ENV:-/etc/zavod-p1/target.env}
SERVICE=${SERVICE:-zavod-p1}
JOURNAL=${JOURNAL:-/var/lib/zavod-p1/install.jsonl}
RESTART=${RESTART:-systemctl restart}

refuse() { echo "INSTALL_REFUSED code=$1"; exit 3; }

# shellcheck source=/dev/null
. "$TARGET_ENV"
: "${REPO_ID:?}" "${REPO_FULL_NAME:?}" "${TENANT_ID:?}"

read_field() {
  python3 -I -c 'import json,sys; m=json.load(open(sys.argv[1],encoding="utf-8")); m=m.get("manifest",m); v=m.get(sys.argv[2]); print("" if v is None else v)' "$MANIFEST" "$1"
}
WANT_SHA=$(read_field artifact_sha256)
HEAD=$(read_field head_sha)
M_REPO_ID=$(read_field repo_id)
M_REPO=$(read_field repo_full_name)
M_TENANT=$(read_field tenant_id)

[[ "$HEAD" =~ ^[0-9a-f]{40}$ ]] || refuse BAD_HEAD
[[ "$M_REPO_ID" == "$REPO_ID" && "$M_REPO" == "$REPO_FULL_NAME" ]] || refuse TARGET_MISMATCH
[[ "$M_TENANT" == "$TENANT_ID" ]] || refuse TENANT_MISMATCH
GOT_SHA=$(sha256sum "$ARTIFACT" | cut -d' ' -f1)
[[ "$GOT_SHA" == "$WANT_SHA" ]] || refuse ARTIFACT_MISMATCH

DEST="$ROOT/releases/$HEAD"
if [[ -d "$DEST" ]]; then
  [[ "$(cat "$DEST/.artifact_sha256")" == "$GOT_SHA" ]] || refuse RELEASE_DIR_CONFLICT
  STATE=already_present
else
  [[ -e "$DEST.partial" ]] && mv "$DEST.partial" "$DEST.partial.$(date -u +%Y%m%dT%H%M%SZ).abandoned"
  mkdir -p "$DEST.partial"
  tar -xf "$ARTIFACT" -C "$DEST.partial"
  printf '%s' "$GOT_SHA" > "$DEST.partial/.artifact_sha256"
  mv "$DEST.partial" "$DEST"
  STATE=installed
fi
PREV=$(readlink "$ROOT/current" 2>/dev/null || true)
ln -sfn "$DEST" "$ROOT/current.next"
mv -T "$ROOT/current.next" "$ROOT/current"
$RESTART "$SERVICE"
printf '{"t":"%s","event":"install","state":"%s","head_sha":"%s","artifact_sha256":"%s","previous":"%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$STATE" "$HEAD" "$GOT_SHA" "$PREV" >> "$JOURNAL"
echo "INSTALL_OK state=$STATE head=$HEAD"
