#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/ci/e2e_deploy_ci.sh
# ВЕРСИЯ: v0.4  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 10:39 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 16:52 +03:00 (v0.4: аудит ChatGPT S6-prep R11A M-S6-R11-01 —
#   выпуски — настоящие коммиты одноразового git-репозитория (git archive + git cat-file commit); новые проверки:
#   верная подпись оператора, верные repo/head, но чужой архив — ARTIFACT_NOT_FROM_HEAD; объект другого коммита —
#   COMMIT_NOT_HEAD; current не меняется. v0.3: аудит ChatGPT S6-prep R2 —
#   шестой аргумент: одноразовый ключ подписи билетов; каждая выкладка несёт билет с подписью ssh-keygen -Y;
#   новые проверки: билет, подписанный чужим ключом, — TICKET_BAD_SIGNATURE (M-S6-R2-02); архив с файлом
#   suid root — BAD_ARTIFACT_CONTENT, current не меняется (M-S6-R2-01); в выпусках нет suid/sgid, записи для
#   группы/всех, ссылок и чужого владельца; старый билет после нового — TICKET_STALE. v0.2: visudo на
#   90-zavod-deploy; shellcheck SC2024/SC2015; пользователь admin переименован в zadmin)
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: только для CI. Сквозная проверка реальной схемы прав сервера (аудит ChatGPT S6-prep M-S6-02/03/05,
#   R2 M-S6-R2-01/02) на одноразовой машине GitHub после apply_user_data_ci.py:
#   1) sudoers: zavod может только install_release.sh; sudo -n id и sudo -n cat /etc/shadow — отказ;
#   2) zavod не может править установщик и /etc/zavod-p1; папка приёма zavod 0700;
#   3) ключ выкладки не входит как zadmin;
#   4) выкладка deploy_push.sh по ssh/scp как zavod с подписанным билетом: INSTALL_OK, служба zavod-p1 активна;
#      повтор того же билета — already_present;
#   5) подмена байта архива — ARTIFACT_MISMATCH; чужая подпись билета — TICKET_BAD_SIGNATURE; архив с suid root —
#      BAD_ARTIFACT_CONTENT; во всех трёх current не меняется;
#   6) дерево выпусков безопасно; второй выпуск ставится, старый билет после него — TICKET_STALE.
# ВЫЗОВ: e2e_deploy_ci.sh DEPLOY_KEY ADMIN_KEY REPO_ID REPO TENANT SIGN_KEY   (ключи — одноразовые, созданы в этом
#   прогоне CI)
# ОГРАНИЧЕНИЯ: ничего не удаляет; закрытые ключи в журнал не пишутся. Каждая проверка печатает CHECK <имя> PASS.
set -euo pipefail
DKEY=${1:?deploy key}
AKEY=${2:?admin key}
REPO_ID=${3:?}
REPO=${4:?}
TENANT=${5:?}
SKEY=${6:?release signing key}
T=${RUNNER_TEMP:?}
HERE=$(cd "$(dirname "$0")" && pwd)
PUSH="$HERE/../deploy_push.sh"
NS=zavod-release-ticket@v1
WORK_ITEM=3f1c2b9e-7d4a-4c1e-9b8f-2a6d5e4c3b21
pass() { echo "CHECK $1 PASS"; }
fail() { echo "CHECK $1 FAIL"; exit 1; }
OPTS=(-o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$T/kh")
TN=0

# manifest SHA HEAD OUT — манифест для этого сервера (поля, которые сверяет сервер)
manifest() {
  python3 -I -c 'import hashlib,json,sys; a=sys.argv; json.dump({"manifest":{"artifact_sha256":a[1],"head_sha":a[2],"repo_id":int(a[3]),"repo_full_name":a[4],"tenant_id":a[5],"work_item_id":a[6],"manifest_sha256":hashlib.sha256((a[1]+a[2]).encode()).hexdigest()}},open(a[7],"w"))' \
    "$1" "$2" "$REPO_ID" "$REPO" "$TENANT" "$WORK_ITEM" "$3"
}
# ticket MANIFEST OUT KEY — билет из полей манифеста, каждый следующий новее; подпись OUT.sig
ticket() {
  TN=$((TN + 1))
  python3 -I -c 'import json,sys,time,uuid; m=json.load(open(sys.argv[1]))["manifest"]; n=int(time.time())+int(sys.argv[3])
t={"v":1,"ticket_id":str(uuid.uuid4()),"issued_at":n,"expires_at":n+900}
t.update({k:m[k] for k in ("head_sha","artifact_sha256","manifest_sha256","repo_id","repo_full_name","tenant_id","work_item_id")})
json.dump(t,open(sys.argv[2],"w"))' "$1" "$2" "$TN"
  ssh-keygen -Y sign -q -n "$NS" -f "$3" "$2" >/dev/null 2>&1 || fail ticket_sign
}
push() {
  DEPLOY_KEY_FILE="$DKEY" KNOWN_HOSTS_FILE="$T/kh" bash "$PUSH" 127.0.0.1 "$@"
}
refused() {  # refused NAME CODE MANIFEST ARTIFACT TICKET COMMIT — отказ с кодом, current прежний
  local name=$1 code=$2 rc
  shift 2
  set +e
  push "$1" "$2" "$3" "$3.sig" "$4" > "$T/$name.out"
  rc=$?
  set -e
  cat "$T/$name.out"
  [ "$rc" -ne 0 ] || fail "${name}_rc"
  grep -q "^INSTALL_REFUSED code=$code$" "$T/$name.out" || fail "$name"
  [ "$(readlink -f /opt/zavod-p1/current)" = "/opt/zavod-p1/releases/$HEAD" ] || fail "${name}_current_kept"
  pass "$name"
}

for _ in 1 2 3 4 5; do nc -z 127.0.0.1 22 && break; timeout 1 tail -f /dev/null || true; done
ssh-keyscan -t ed25519 127.0.0.1 2>/dev/null > "$T/kh"
[ -s "$T/kh" ] || fail known_hosts

sudo visudo -cf /etc/sudoers.d/90-zavod-deploy >/dev/null || fail visudo
pass visudo
SUDO_L=$(sudo -l -U zavod)
printf '%s\n' "$SUDO_L" > "$T/sudo_l.out"
grep -q '(root) NOPASSWD: /opt/zavod-ops/install_release.sh' "$T/sudo_l.out" || fail sudo_rule
if grep -Eq 'NOPASSWD: *ALL|\(ALL( : ALL)?\) *ALL' "$T/sudo_l.out"; then fail sudo_no_all; fi
pass sudo_only_install
if sudo -u zavod sudo -n id >/dev/null 2>&1; then fail zavod_sudo_id; fi
if sudo -u zavod sudo -n /bin/cat /etc/shadow >/dev/null 2>&1; then fail zavod_shadow; fi
pass zavod_no_other_sudo
if sudo -u zavod test -w /opt/zavod-ops/install_release.sh; then fail installer_writable; fi
if sudo -u zavod test -w /etc/zavod-p1/target.env; then fail target_writable; fi
if sudo -u zavod test -w /etc/zavod-p1/release_signers; then fail signers_writable; fi
[ "$(stat -c '%U %a' /var/lib/zavod-incoming)" = "zavod 700" ] || fail incoming_mode
pass file_modes

if ssh -i "$DKEY" "${OPTS[@]}" zadmin@127.0.0.1 true 2>/dev/null; then fail deploy_key_as_admin; fi
ssh -i "$AKEY" "${OPTS[@]}" zadmin@127.0.0.1 true || fail admin_login
pass key_separation
if ssh -i "$DKEY" "${OPTS[@]}" zavod@127.0.0.1 sudo -n /bin/cat /etc/shadow >/dev/null 2>&1; then fail ssh_zavod_shadow; fi
pass ssh_zavod_no_shadow

sudo install -m 0600 -o root -g root /dev/null /etc/zavod-p1/secrets.env
# release N — коммит одноразового репозитория продукта: артефакт = git archive, объект = git cat-file commit
G=(git -C "$T/rel" -c user.name=zavod-ci -c user.email=ci@zavod.invalid)
git init -q "$T/rel"
mkdir -p "$T/rel/bot"
release() {
  printf 'import time\nwhile True:\n    time.sleep(%s)\n' "$2" > "$T/rel/bot/__main__.py"
  "${G[@]}" add bot
  "${G[@]}" commit -q -m "release $1"
  "${G[@]}" archive --format=tar HEAD > "$T/artifact$1.tar"
  "${G[@]}" cat-file commit HEAD > "$T/commit$1.obj"
  "${G[@]}" rev-parse HEAD
}
HEAD=$(release '' 60)
SHA=$(sha256sum "$T/artifact.tar" | cut -d' ' -f1)
manifest "$SHA" "$HEAD" "$T/manifest.json"
ticket "$T/manifest.json" "$T/ticket1.json" "$SKEY"

push "$T/manifest.json" "$T/artifact.tar" "$T/ticket1.json" "$T/ticket1.json.sig" "$T/commit.obj" | tee "$T/deploy1.out"
grep -q "^INSTALL_OK state=installed head=$HEAD$" "$T/deploy1.out" || fail deploy_installed
timeout 3 tail -f /dev/null || true
systemctl is-active --quiet zavod-p1 || { sudo systemctl status zavod-p1 --no-pager || true; fail service_active; }
[ "$(readlink -f /opt/zavod-p1/current)" = "/opt/zavod-p1/releases/$HEAD" ] || fail current_link
pass deploy_as_zavod

push "$T/manifest.json" "$T/artifact.tar" "$T/ticket1.json" "$T/ticket1.json.sig" "$T/commit.obj" | tee "$T/deploy2.out"
grep -q "^INSTALL_OK state=already_present head=$HEAD$" "$T/deploy2.out" || fail deploy_repeat
pass deploy_repeat_noop

cp "$T/artifact.tar" "$T/artifact_bad.tar"
python3 -I -c 'import sys; p=sys.argv[1]; b=bytearray(open(p,"rb").read()); b[600]^=1; open(p,"wb").write(b)' "$T/artifact_bad.tar"
manifest "$SHA" "$(printf '%040d' 7)" "$T/manifest_bad.json"
ticket "$T/manifest_bad.json" "$T/ticket_bad.json" "$SKEY"
refused tampered_refused ARTIFACT_MISMATCH "$T/manifest_bad.json" "$T/artifact_bad.tar" "$T/ticket_bad.json" "$T/commit.obj"

manifest "$SHA" "$(printf '%040d' 8)" "$T/manifest_forged.json"
ticket "$T/manifest_forged.json" "$T/ticket_forged.json" "$DKEY"
refused forged_ticket_refused TICKET_BAD_SIGNATURE "$T/manifest_forged.json" "$T/artifact.tar" "$T/ticket_forged.json" "$T/commit.obj"

python3 -I -c 'import io,sys,tarfile
with tarfile.open(sys.argv[1], "w") as t:
    for name, mode in (("bot/__main__.py", 0o644), ("bot/rootshell", 0o4755)):
        ti = tarfile.TarInfo(name); ti.size = 2; ti.mode = mode; ti.uid = 0; ti.gid = 0
        t.addfile(ti, io.BytesIO(b"x\n"))' "$T/artifact_suid.tar"
SUID_SHA=$(sha256sum "$T/artifact_suid.tar" | cut -d' ' -f1)
HEAD3=$(release 3 62)
manifest "$SUID_SHA" "$HEAD3" "$T/manifest_suid.json"
ticket "$T/manifest_suid.json" "$T/ticket_suid.json" "$SKEY"
refused setuid_tar_refused BAD_ARTIFACT_CONTENT "$T/manifest_suid.json" "$T/artifact_suid.tar" "$T/ticket_suid.json" "$T/commit3.obj"
[ ! -e "/opt/zavod-p1/releases/$HEAD3" ] || fail setuid_release_dir

# M-S6-R11-01: подпись оператора верная, repo и head (настоящий коммит 3) верные, манифест и билет согласованы с
# чужим архивом (тот же путь, другой код) — сервер не ставит: дерево архива не дерево head
mkdir -p "$T/evil/bot"
printf 'import os\nos.system("id")\n' > "$T/evil/bot/__main__.py"
tar -C "$T/evil" -cf "$T/artifact_evil.tar" bot
EVIL_SHA=$(sha256sum "$T/artifact_evil.tar" | cut -d' ' -f1)
manifest "$EVIL_SHA" "$HEAD3" "$T/manifest_evil.json"
ticket "$T/manifest_evil.json" "$T/ticket_evil.json" "$SKEY"
refused foreign_artifact_refused ARTIFACT_NOT_FROM_HEAD "$T/manifest_evil.json" "$T/artifact_evil.tar" "$T/ticket_evil.json" "$T/commit3.obj"
[ ! -e "/opt/zavod-p1/releases/$HEAD3" ] || fail foreign_release_dir
# объект другого коммита (1) при билете на коммит 3 — не тот head
manifest "$(sha256sum "$T/artifact3.tar" | cut -d' ' -f1)" "$HEAD3" "$T/manifest_c3.json"
ticket "$T/manifest_c3.json" "$T/ticket_c3.json" "$SKEY"
refused commit_not_head_refused COMMIT_NOT_HEAD "$T/manifest_c3.json" "$T/artifact3.tar" "$T/ticket_c3.json" "$T/commit.obj"

HEAD2=$(release 2 61)
SHA2=$(sha256sum "$T/artifact2.tar" | cut -d' ' -f1)
manifest "$SHA2" "$HEAD2" "$T/manifest2.json"
ticket "$T/manifest2.json" "$T/ticket2.json" "$SKEY"
push "$T/manifest2.json" "$T/artifact2.tar" "$T/ticket2.json" "$T/ticket2.json.sig" "$T/commit2.obj" | tee "$T/deploy4.out"
grep -q "^INSTALL_OK state=installed head=$HEAD2$" "$T/deploy4.out" || fail deploy_second
HEAD=$HEAD2
refused stale_ticket_refused TICKET_STALE "$T/manifest.json" "$T/artifact.tar" "$T/ticket1.json" "$T/commit.obj"

BAD_TREE=$(sudo find /opt/zavod-p1/releases -mindepth 1 \( -perm /7022 -o ! -user root -o ! \( -type f -o -type d \) \) -print)
[ -z "$BAD_TREE" ] || { printf '%s\n' "$BAD_TREE"; fail release_tree_safe; }
pass release_tree_safe
echo "E2E_DEPLOY_CI PASS head=$HEAD"
