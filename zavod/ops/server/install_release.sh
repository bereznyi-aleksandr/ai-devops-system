#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/install_release.sh
# ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:40 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 11:11 +03:00 (v0.3: аудит ChatGPT
#   S6-prep R2. M-S6-R2-01 — программа tar больше не вызывается: архив читает python tarfile, сначала весь список
#   проверяется (только обычные файлы и папки; относительный путь без «..», «.», пустых частей, обратной черты и
#   управляющих знаков; без suid/sgid/sticky; не больше 20000 записей и 64 МиБ), потом файлы создаются заново
#   этим кодом (O_CREAT|O_EXCL|O_NOFOLLOW): владелец, группа, ссылки, устройства и права из архива не
#   переносятся, права только 0644 или 0755; после записи дерево проверяется второй раз отдельным проходом (lstat:
#   только файлы и папки, без suid/sgid/sticky и записи для группы/всех, владелец — этот процесс, у файла одна
#   жёсткая ссылка) и только потом переключается current. Почему не распаковка от p1: файлы выпуска принадлежат
#   root и только читаются ботом — бот p1 не может переписать собственный код. M-S6-R2-02 — третий и четвёртый
#   аргумент: билет выпуска (JSON) и его подпись ssh-keygen -Y sign ключом выпуска Завода (пространство имён
#   zavod-release-ticket@v1); открытая часть — /etc/zavod-p1/release_signers из user-data. Без верной подписи —
#   отказ TICKET_BAD_SIGNATURE до всего остального; поля билета обязаны совпасть с манифестом (head_sha,
#   artifact_sha256, manifest_sha256, repo_id, repo_full_name, tenant_id, work_item_id), срок — не больше часа
#   и не истёк; билеты идут только вперёд: принимается билет новее последнего принятого или повтор последнего
#   (тот же номер и те же байты) — старый билет (откат подменой) — TICKET_STALE. Один запуск за раз (flock).
#   v0.2: M-S6-02/M-S6-03 — узкое правило sudo от zavod; входы — обычные файлы прямо в папке приёма, копия в
#   папку root с O_NOFOLLOW; под sudo переменные окружения сбрасываются)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: этап 6, E6-2 — установка выпуска на сервере; вызывается адаптером Egress (одна строка outbox =
#   один вызов). Вторая линия сверки манифеста SR-13 на самом сервере: подпись билета Завода, SHA-256 архива =
#   artifact_sha256, repo_id, repo_full_name и tenant_id = цель этого сервера из /etc/zavod-p1/target.env,
#   head_sha — 40 hex. Любое несовпадение — отказ с кодом до распаковки. Проверенная запись в
#   releases/<head_sha>.partial → независимая проверка дерева → переименование → атомарная смена ссылки current →
#   перезапуск службы → запись в журнал. Повтор той же версии ничего не меняет. Старые версии не удаляются.
# ВЫЗОВ: sudo /opt/zavod-ops/install_release.sh <manifest.json> <artifact.tar> <ticket.json> <ticket.sig>
#   (все четыре — прямо в /var/lib/zavod-incoming); ROOT, TARGET_ENV, SERVICE, JOURNAL, INCOMING, RESTART,
#   RELEASE_SIGNERS, TICKETS — только для проверок без sudo.
# ОГРАНИЧЕНИЯ: секретов не читает (подпись проверяется открытым ключом); ничего не удаляет.
set -euo pipefail
MANIFEST=${1:?manifest}
ARTIFACT=${2:?artifact}
TICKET=${3:?ticket}
SIG=${4:?ticket signature}
ROOT=${ROOT:-/opt/zavod-p1}
TARGET_ENV=${TARGET_ENV:-/etc/zavod-p1/target.env}
SERVICE=${SERVICE:-zavod-p1}
JOURNAL=${JOURNAL:-/var/lib/zavod-p1/install.jsonl}
RESTART=${RESTART:-systemctl restart}
INCOMING=${INCOMING:-/var/lib/zavod-incoming}
RELEASE_SIGNERS=${RELEASE_SIGNERS:-/etc/zavod-p1/release_signers}
TICKETS=${TICKETS:-/var/lib/zavod-p1/tickets}
NAMESPACE=zavod-release-ticket@v1

refuse() { echo "INSTALL_REFUSED code=$1"; exit 3; }

exec 9>>"$ROOT/.install.lock"
flock -w 120 9 || refuse LOCK_TIMEOUT

STAGE=$(mktemp -d "${TMPDIR:-/tmp}/zavod-install.XXXXXX")
take() {
  [[ "$(dirname -- "$1")" == "$INCOMING" ]] || return 1
  python3 -I -c 'import os,stat,sys
fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW)
if not stat.S_ISREG(os.fstat(fd).st_mode): sys.exit(1)
with os.fdopen(fd, "rb") as src, open(sys.argv[2], "xb") as dst:
    dst.write(src.read(64 * 1024 * 1024 + 1))' "$1" "$2" 2>/dev/null
}
if ! take "$MANIFEST" "$STAGE/manifest.json" || ! take "$ARTIFACT" "$STAGE/artifact.tar" \
   || ! take "$TICKET" "$STAGE/ticket.json" || ! take "$SIG" "$STAGE/ticket.sig"; then
  refuse BAD_INPUT_PATH
fi
MANIFEST="$STAGE/manifest.json"
ARTIFACT="$STAGE/artifact.tar"
TICKET="$STAGE/ticket.json"
SIG="$STAGE/ticket.sig"

[[ -f "$RELEASE_SIGNERS" ]] || refuse NO_RELEASE_SIGNER
ssh-keygen -Y verify -f "$RELEASE_SIGNERS" -I zavod-release -n "$NAMESPACE" -s "$SIG" < "$TICKET" >/dev/null 2>&1 \
  || refuse TICKET_BAD_SIGNATURE

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

# Билет: поля = манифест, срок, порядок. Печатает «OK <ticket_id> <sha256 билета>» или «ERR <код>».
mkdir -p -m 0700 "$TICKETS"
TCHECK=$(python3 -I - "$TICKET" "$MANIFEST" "$TICKETS/last_ticket.json" "$(date -u +%s)" <<'PY'
import hashlib, json, re, sys
tp, mp, lp, now = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
def err(code):
    print("ERR " + code)
    sys.exit(0)
raw = open(tp, "rb").read()
try:
    t = json.loads(raw.decode("utf-8"))
    m = json.load(open(mp, encoding="utf-8"))
except (ValueError, UnicodeDecodeError):
    err("TICKET_BAD_FORMAT")
m = m.get("manifest", m) if isinstance(m, dict) else {}
if not isinstance(t, dict) or t.get("v") != 1:
    err("TICKET_BAD_FORMAT")
tid = t.get("ticket_id")
if not isinstance(tid, str) or not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", tid):
    err("TICKET_BAD_FORMAT")
for k in ("head_sha", "artifact_sha256", "manifest_sha256", "repo_id", "repo_full_name", "tenant_id", "work_item_id"):
    if k not in m or t.get(k) != m.get(k):
        err("TICKET_MISMATCH")
iss, exp = t.get("issued_at"), t.get("expires_at")
if not (isinstance(iss, int) and isinstance(exp, int)) or isinstance(iss, bool) or isinstance(exp, bool):
    err("TICKET_BAD_FORMAT")
if exp <= iss or exp - iss > 3600 or iss > now + 300:
    err("TICKET_BAD_FORMAT")
if now > exp:
    err("TICKET_EXPIRED")
sha = hashlib.sha256(raw).hexdigest()
try:
    last = json.load(open(lp, encoding="utf-8"))
except FileNotFoundError:
    last = None
if last is not None:
    same = last.get("ticket_id") == tid and last.get("ticket_sha256") == sha
    if not same and not iss > int(last.get("issued_at", 0)):
        err("TICKET_STALE")
print("OK %s %s %d" % (tid, sha, iss))
PY
) || refuse TICKET_CHECK_FAILED
read -r T_OK T_ID T_SHA T_ISS <<<"$TCHECK"
[[ "$T_OK" == OK ]] || refuse "${T_ID:-TICKET_BAD_FORMAT}"

[[ "$HEAD" =~ ^[0-9a-f]{40}$ ]] || refuse BAD_HEAD
[[ "$M_REPO_ID" == "$REPO_ID" && "$M_REPO" == "$REPO_FULL_NAME" ]] || refuse TARGET_MISMATCH
[[ "$M_TENANT" == "$TENANT_ID" ]] || refuse TENANT_MISMATCH
GOT_SHA=$(sha256sum "$ARTIFACT" | cut -d' ' -f1)
[[ "$GOT_SHA" == "$WANT_SHA" ]] || refuse ARTIFACT_MISMATCH

# Билет принят: он становится последним (повтор того же билета разрешён, старый — нет).
printf '{"ticket_id":"%s","ticket_sha256":"%s","issued_at":%s,"head_sha":"%s"}\n' "$T_ID" "$T_SHA" "$T_ISS" "$HEAD" \
  > "$TICKETS/last_ticket.json.next"
mv -f "$TICKETS/last_ticket.json.next" "$TICKETS/last_ticket.json"
printf '{"t":"%s","ticket_id":"%s","ticket_sha256":"%s","issued_at":%s,"head_sha":"%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$T_ID" "$T_SHA" "$T_ISS" "$HEAD" >> "$TICKETS/accepted.jsonl"

# Проверенная запись архива (M-S6-R2-01): сначала весь список, потом создание файлов этим кодом.
extract() {
  timeout 300 python3 -I - "$1" "$2" <<'PY'
import os, stat, sys, tarfile
src, dest = sys.argv[1], sys.argv[2]
MAX_FILES, MAX_BYTES = 20000, 64 * 1024 * 1024
def bad(why):
    print("BAD " + why)
    sys.exit(4)
def parts_of(name):
    if not name or name.startswith("/") or "\\" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        bad("path")
    p = name.split("/")
    if p[-1] == "":
        p = p[:-1]
    if not p or len(p) > 32 or any(x in ("", ".", "..") or len(x.encode("utf-8")) > 255 for x in p):
        bad("path")
    if p == [".artifact_sha256"]:
        bad("path")
    return p
os.umask(0o022)
try:
    with tarfile.open(src, mode="r:") as t:
        plan, kinds, total = [], {}, 0
        for m in t:
            if len(plan) >= MAX_FILES:
                bad("count")
            p = parts_of(m.name)
            key = "/".join(p)
            if m.type == tarfile.DIRTYPE:
                kind = "d"
            elif m.type in (tarfile.REGTYPE, tarfile.AREGTYPE):
                kind = "f"
            else:
                bad("type")
            if m.mode & 0o7000:
                bad("mode")
            for i in range(1, len(p)):
                if kinds.get("/".join(p[:i])) == "f":
                    bad("parent")
            if key in kinds:
                if kinds[key] == "d" and kind == "d":
                    continue
                bad("duplicate")
            kinds[key] = kind
            if kind == "f":
                total += m.size
                if total > MAX_BYTES:
                    bad("size")
            plan.append((kind, p, m))
        os.mkdir(dest, 0o755)
        for kind, p, m in plan:
            path = os.path.join(dest, *p)
            os.makedirs(os.path.dirname(path), mode=0o755, exist_ok=True)
            if kind == "d":
                if not os.path.isdir(path) or os.path.islink(path):
                    os.mkdir(path, 0o755)
                continue
            mode = 0o755 if m.mode & 0o111 else 0o644
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            n = 0
            with os.fdopen(fd, "wb") as out:
                f = t.extractfile(m)
                while True:
                    chunk = f.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    n += len(chunk)
            if n != m.size:
                bad("size")
except (tarfile.TarError, OSError, EOFError):
    bad("read")
print("EXTRACTED %d" % len(plan))
PY
}
# Независимая проверка дерева перед переключением current.
check_tree() {
  python3 -I - "$1" <<'PY'
import os, stat, sys
root = sys.argv[1]
uid = os.geteuid()
def bad(why, p):
    print("BAD %s %s" % (why, os.path.relpath(p, root)))
    sys.exit(4)
def look(p):
    st = os.lstat(p)
    if not (stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)):
        bad("type", p)
    if st.st_mode & 0o7022:
        bad("mode", p)
    if st.st_uid != uid:
        bad("owner", p)
    if stat.S_ISREG(st.st_mode) and st.st_nlink != 1:
        bad("links", p)
look(root)
for dp, dns, fns in os.walk(root, followlinks=False):
    for n in dns + fns:
        look(os.path.join(dp, n))
print("TREE_OK")
PY
}

DEST="$ROOT/releases/$HEAD"
if [[ -d "$DEST" ]]; then
  [[ "$(cat "$DEST/.artifact_sha256")" == "$GOT_SHA" ]] || refuse RELEASE_DIR_CONFLICT
  check_tree "$DEST" >/dev/null || refuse BAD_RELEASE_TREE
  STATE=already_present
else
  [[ -e "$DEST.partial" ]] && mv "$DEST.partial" "$DEST.partial.$(date -u +%Y%m%dT%H%M%SZ).abandoned"
  extract "$ARTIFACT" "$DEST.partial" >/dev/null || refuse BAD_ARTIFACT_CONTENT
  printf '%s' "$GOT_SHA" > "$DEST.partial/.artifact_sha256"
  chmod 0644 "$DEST.partial/.artifact_sha256"
  if ! check_tree "$DEST.partial" >/dev/null; then
    mv "$DEST.partial" "$DEST.partial.$(date -u +%Y%m%dT%H%M%SZ).rejected"
    refuse BAD_RELEASE_TREE
  fi
  mv "$DEST.partial" "$DEST"
  STATE=installed
fi
PREV=$(readlink "$ROOT/current" 2>/dev/null || true)
ln -sfn "$DEST" "$ROOT/current.next"
mv -T "$ROOT/current.next" "$ROOT/current"
$RESTART "$SERVICE"
printf '{"t":"%s","event":"install","state":"%s","head_sha":"%s","artifact_sha256":"%s","previous":"%s","ticket_id":"%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$STATE" "$HEAD" "$GOT_SHA" "$PREV" "$T_ID" >> "$JOURNAL"
echo "INSTALL_OK state=$STATE head=$HEAD"
