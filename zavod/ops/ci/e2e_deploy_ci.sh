#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/ci/e2e_deploy_ci.sh
# ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 10:39 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 10:45 +03:00 (v0.2: shellcheck SC2024/SC2015 исправлены; пользователь admin переименован в zadmin: в Ubuntu уже есть группа admin, useradd отказывает (CI 38219321184))
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: только для CI. Сквозная проверка реальной схемы прав сервера (аудит ChatGPT S6-prep M-S6-02/03/05)
#   на одноразовой машине GitHub после apply_user_data_ci.py:
#   1) sudoers: zavod может только install_release.sh; sudo -n id и sudo -n cat /etc/shadow — отказ;
#   2) zavod не может править установщик и /etc/zavod-p1; папка приёма zavod 0700;
#   3) ключ выкладки не входит как zadmin;
#   4) выкладка deploy_push.sh по ssh/scp как zavod: INSTALL_OK, служба zavod-p1 активна; повтор — already_present;
#   5) подмена байта архива — INSTALL_REFUSED code=ARTIFACT_MISMATCH, current не меняется.
# ВЫЗОВ: e2e_deploy_ci.sh DEPLOY_KEY ADMIN_KEY REPO_ID REPO TENANT   (ключи — одноразовые, созданы в этом прогоне CI)
# ОГРАНИЧЕНИЯ: ничего не удаляет; закрытые ключи в журнал не пишутся. Каждая проверка печатает CHECK <имя> PASS.
set -euo pipefail
DKEY=${1:?deploy key}
AKEY=${2:?admin key}
REPO_ID=${3:?}
REPO=${4:?}
TENANT=${5:?}
T=${RUNNER_TEMP:?}
HERE=$(cd "$(dirname "$0")" && pwd)
PUSH="$HERE/../deploy_push.sh"
pass() { echo "CHECK $1 PASS"; }
fail() { echo "CHECK $1 FAIL"; exit 1; }
OPTS=(-o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$T/kh")

for _ in 1 2 3 4 5; do nc -z 127.0.0.1 22 && break; timeout 1 tail -f /dev/null || true; done
ssh-keyscan -t ed25519 127.0.0.1 2>/dev/null > "$T/kh"
[ -s "$T/kh" ] || fail known_hosts

sudo visudo -c >/dev/null && pass visudo
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
[ "$(stat -c '%U %a' /var/lib/zavod-incoming)" = "zavod 700" ] || fail incoming_mode
pass file_modes

if ssh -i "$DKEY" "${OPTS[@]}" zadmin@127.0.0.1 true 2>/dev/null; then fail deploy_key_as_admin; fi
ssh -i "$AKEY" "${OPTS[@]}" zadmin@127.0.0.1 true || fail admin_login
pass key_separation
if ssh -i "$DKEY" "${OPTS[@]}" zavod@127.0.0.1 sudo -n /bin/cat /etc/shadow >/dev/null 2>&1; then fail ssh_zavod_shadow; fi
pass ssh_zavod_no_shadow

sudo install -m 0600 -o root -g root /dev/null /etc/zavod-p1/secrets.env
mkdir -p "$T/rel/bot"
printf 'import time\nwhile True:\n    time.sleep(60)\n' > "$T/rel/bot/__main__.py"
tar -C "$T/rel" -cf "$T/artifact.tar" bot
SHA=$(sha256sum "$T/artifact.tar" | cut -d' ' -f1)
HEAD=$(git rev-parse HEAD)
python3 -I -c 'import json,sys; a=sys.argv; json.dump({"manifest":{"artifact_sha256":a[1],"head_sha":a[2],"repo_id":int(a[3]),"repo_full_name":a[4],"tenant_id":a[5]}},open(a[6],"w"))' \
  "$SHA" "$HEAD" "$REPO_ID" "$REPO" "$TENANT" "$T/manifest.json"

DEPLOY_KEY_FILE="$DKEY" KNOWN_HOSTS_FILE="$T/kh" bash "$PUSH" 127.0.0.1 "$T/manifest.json" "$T/artifact.tar" | tee "$T/deploy1.out"
grep -q "^INSTALL_OK state=installed head=$HEAD$" "$T/deploy1.out" || fail deploy_installed
timeout 3 tail -f /dev/null || true
systemctl is-active --quiet zavod-p1 || { sudo systemctl status zavod-p1 --no-pager || true; fail service_active; }
[ "$(readlink -f /opt/zavod-p1/current)" = "/opt/zavod-p1/releases/$HEAD" ] || fail current_link
pass deploy_as_zavod

DEPLOY_KEY_FILE="$DKEY" KNOWN_HOSTS_FILE="$T/kh" bash "$PUSH" 127.0.0.1 "$T/manifest.json" "$T/artifact.tar" | tee "$T/deploy2.out"
grep -q "^INSTALL_OK state=already_present head=$HEAD$" "$T/deploy2.out" || fail deploy_repeat
pass deploy_repeat_noop

cp "$T/artifact.tar" "$T/artifact_bad.tar"
python3 -I -c 'import sys; p=sys.argv[1]; b=bytearray(open(p,"rb").read()); b[600]^=1; open(p,"wb").write(b)' "$T/artifact_bad.tar"
H2=$(printf '%040d' 7)
python3 -I -c 'import json,sys; a=sys.argv; json.dump({"manifest":{"artifact_sha256":a[1],"head_sha":a[2],"repo_id":int(a[3]),"repo_full_name":a[4],"tenant_id":a[5]}},open(a[6],"w"))' \
  "$SHA" "$H2" "$REPO_ID" "$REPO" "$TENANT" "$T/manifest_bad.json"
set +e
DEPLOY_KEY_FILE="$DKEY" KNOWN_HOSTS_FILE="$T/kh" bash "$PUSH" 127.0.0.1 "$T/manifest_bad.json" "$T/artifact_bad.tar" > "$T/deploy3.out"
rc=$?
set -e
cat "$T/deploy3.out"
[ "$rc" -ne 0 ] || fail tampered_rc
grep -q '^INSTALL_REFUSED code=ARTIFACT_MISMATCH$' "$T/deploy3.out" || fail tampered_refused
[ "$(readlink -f /opt/zavod-p1/current)" = "/opt/zavod-p1/releases/$HEAD" ] || fail current_kept
pass tampered_refused
echo "E2E_DEPLOY_CI PASS head=$HEAD"
