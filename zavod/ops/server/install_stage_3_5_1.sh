#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/install_stage_3_5_1.sh
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-05 17:03 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-05 17:03 +02:00 (v0.1: карта 3.5.1.2–3.5.1.7)
# ИСПОЛНИТЕЛЬ: Claude (сессия c28394bb-ae8a-47d6-aad3-111e08d58001)
# НАЗНАЧЕНИЕ: одна команда установки сервера Завода на этапе 3.5.1 (карта Завода v3.1, RISK_ARM64_3_4_1_v1_1):
#   0) сверка пакета с описью MANIFEST.sha256 (до любых изменений на сервере);
#   1) 3.5.1.2 — обновление системы (apt-get full-upgrade); если системе нужна перезагрузка — стоп с кодом 3 и
#      строкой REBOOT_REQUIRED: оператор перезагружает сервер и повторяет ту же команду;
#   2) 3.5.1.2 — пакеты git и gh; вход по паролю выключен (PasswordAuthentication no,
#      KbdInteractiveAuthentication no, PermitRootLogin prohibit-password — вход root только по ключу);
#   3) точка Б (проверка 7 RISK_ARM64): все сценарии пакета разбираются (bash -n, compile() для python), git, gh и
#      Node.js из архива пакета (во временной папке) запускаются на процессоре сервера;
#   4) 3.5.1.3–3.5.1.5 — install_server.sh (учётные записи, папки, база, ячейка, ядро, движок);
#   5) 3.5.1.6 — пробный пустой сеанс: пробная аренда (opened_by install-3.5.1.6) → файл запуска от zkernel →
#      сеанс в клетке поднялся, стены клетки держат → файл остановки → сеанс погас, запись INTERRUPTED;
#   6) 3.5.1.7 — отчёт: короткий блок строк ZAVOD_3_5_1_* на экране и в файле /root/zavod-install-3.5.1.txt.
#   Повторный запуск даёт тот же результат (каждый раз — новый пробный сеанс).
# ВЫЗОВ: sudo bash install_stage_3_5_1.sh <папка распакованного пакета> [--no-upgrade] [параметры install_cell.sh …]
#   --no-upgrade — только для CI (машина GitHub): без обновления системы и без проверки перезагрузки.
# ОГРАНИЧЕНИЯ: ничего не удаляет. Ключей не создаёт и не читает; проверяется только, что у root есть файл
#   authorized_keys (иначе выключение пароля закрыло бы вход). Пробная аренда остаётся в базе с пометкой
#   opened_by = install-3.5.1.6 у отдельного пробного заказчика (случайный tenant_id) — это след пробы, а не работа.
set -euo pipefail
export LC_ALL=C
PKG=${1:?usage: install_stage_3_5_1.sh PACKAGE_DIR [--no-upgrade] [install_cell.sh options]}
shift
UPGRADE=1
if [ "${1:-}" = --no-upgrade ]; then UPGRADE=0; shift; fi
PKG=$(cd "$PKG" && pwd -P)
die() { echo "REFUSED: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root"
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ] || die "Ubuntu 24.04 only (found ${ID:-?} ${VERSION_ID:-?})"
case "$(uname -m)" in
  x86_64) ARCH=x64 ;;
  aarch64) ARCH=arm64 ;;
  *) die "unsupported processor $(uname -m)" ;;
esac
REPORT=/root/zavod-install-3.5.1.txt
echo "=== ZAVOD 3.5.1 start $(date -u +%Y-%m-%dT%H:%M:%SZ) arch=$ARCH"

echo "=== 0. сверка пакета с описью"
M="$PKG/MANIFEST.sha256"
[ -f "$M" ] || die "no MANIFEST.sha256"
[ "$(sed -n '2p' "$M")" = "#arch $ARCH" ] || die "package is not for this processor ($ARCH): $(sed -n '2p' "$M")"
(cd "$PKG" && grep -v '^#' "$M" | sha256sum --check --strict --quiet) || die "package files differ from the manifest"
COMMIT=$(sed -n '1s/^# zavod server package; source commit \([0-9a-f]\{40\}\)$/\1/p' "$M")
[ -n "$COMMIT" ] || die "manifest has no source commit"
MSHA=$(sha256sum "$M" | cut -c1-64)
echo "PACKAGE_MANIFEST commit=$COMMIT manifest_sha256=$MSHA"

# Без вопросов на экране: needrestart сам перезапускает службы, при правленом файле настроек остаётся прежний.
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
echo "=== 1. обновление системы (3.5.1.2)"
if [ "$UPGRADE" = 1 ]; then
  apt-get update -qq
  apt-get full-upgrade -y -qq -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold > /dev/null
  if [ -e /var/run/reboot-required ]; then
    echo "REBOOT_REQUIRED: система обновлена, нужна перезагрузка. Введите reboot, войдите снова и повторите ту же команду."
    exit 3
  fi
  echo "SYSTEM_UPGRADE=OK"
else
  echo "SYSTEM_UPGRADE=SKIPPED (--no-upgrade, CI)"
fi

echo "=== 2. git, gh и вход только по ключу (3.5.1.2)"
need=()
for p in git gh openssh-server; do
  dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'install ok installed' || need+=("$p")
done
if [ ${#need[@]} -gt 0 ]; then
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends "${need[@]}" > /dev/null
fi
for p in git gh openssh-server; do dpkg-query -W -f='${Status}' "$p" | grep -q 'install ok installed' || die "package $p not installed"; done
# Без ключа у root выключение пароля закрыло бы вход на сервер: тогда — отказ, ничего не меняется.
[ -s /root/.ssh/authorized_keys ] || die "/root/.ssh/authorized_keys is empty: password login stays as is"
# Файл с началом имени 00- читается первым (Include /etc/ssh/sshd_config.d/*.conf), а у sshd действует первое
# значение — поэтому строки облачного образа (50-cloud-init.conf) его не перебивают.
D=/etc/ssh/sshd_config.d/00-zavod-no-password.conf
want='# zavod 3.5.1.2: вход только по ключу
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password'
if [ ! -f "$D" ] || [ "$(cat "$D")" != "$want" ]; then
  t=$(mktemp /etc/ssh/sshd_config.d/.zavod-XXXXXX)
  printf '%s\n' "$want" > "$t"
  chmod 0644 "$t"
  mv -T "$t" "$D"
fi
# Ubuntu 24.04 запускает sshd по сокету: папки /run/sshd может ещё не быть, без неё sshd -t не работает.
install -d -o root -g root -m 0755 /run/sshd
sshd -t || die "sshd configuration check failed"
T=$(sshd -T -C user=root,host=localhost,addr=127.0.0.1)
for kv in 'passwordauthentication no' 'kbdinteractiveauthentication no' 'permitrootlogin (without-password|prohibit-password)'; do
  printf '%s\n' "$T" | grep -qxE "$kv" || die "sshd effective setting is not: $kv"
done
if systemctl is-active --quiet ssh.service; then systemctl reload ssh.service; fi
echo "SSH_PASSWORD_LOGIN=OFF"

echo "=== 3. точка Б: программы запускаются на этом процессоре (проверка 7)"
n_sh=0 n_py=0
while IFS= read -r -d '' f; do
  first=$(head -n 1 "$f" | tr -d '\0' | cut -c1-80)
  case "$f" in
    *.py) kind=py ;;
    *.sh) kind=sh ;;
    *) case "$first" in
         '#!'*python*) kind=py ;;
         '#!'*bash*|'#!/bin/sh'*) kind=sh ;;
         *) kind= ;;
       esac ;;
  esac
  if [ "$kind" = sh ]; then bash -n "$f" || die "bash -n failed: ${f#"$PKG"/}"; n_sh=$((n_sh + 1)); fi
  if [ "$kind" = py ]; then
    python3 -I -c 'import sys; compile(open(sys.argv[1], "rb").read(), sys.argv[1], "exec")' "$f" \
      || die "python compile failed: ${f#"$PKG"/}"
    n_py=$((n_py + 1))
  fi
done < <(find "$PKG" -type f ! -path "$PKG/zavod/kernel/node_modules/*" ! -path "$PKG/runtime/*" ! -path "$PKG/engine/*" -print0)
[ "$n_sh" -gt 0 ] && [ "$n_py" -gt 0 ] || die "no scripts found in the package"
GITV=$(git --version) || die "git does not run"
GHV=$(gh --version | head -n 1) || die "gh does not run"
NODE_TAR=$(cd "$PKG/runtime" && ls node-v22.*-linux-"$ARCH".tar.xz)
NT=$(mktemp -d /tmp/zavod-point-b-node-XXXXXX)
tar -C "$NT" -xJf "$PKG/runtime/$NODE_TAR" --no-same-owner --strip-components=1
NODEV=$("$NT/bin/node" --version) || die "node from the package does not run on $ARCH"
python3 -I "$PKG/zavod/ops/server/verify_tree.py" elf "$ARCH" "$NT" "$PKG"
echo "POINT_B=OK sh=$n_sh py=$n_py git=\"$GITV\" gh=\"$GHV\" node=$NODEV"

echo "=== 4. установка сервера (3.5.1.3–3.5.1.5)"
OUT=$(mktemp /tmp/zavod-install-server-XXXXXX.out)
bash "$PKG/zavod/ops/server/install_server.sh" "$PKG" "$@" | tee "$OUT"
grep -qx ZAVOD_SERVER_INSTALL=OK "$OUT" || die "install_server.sh"

echo "=== 5. пробный пустой сеанс (3.5.1.6)"
# Запрос к базе — только постоянный текст, значения — переменными psql (как cell_ci.sh, аудит M3310-R7-03).
pgv() {
  local q=$1 a v=(); shift
  for a in "$@"; do v+=(-v "$a"); done
  printf '%s\n' "$q" | runuser -u postgres -- psql -X -A -t -q -v ON_ERROR_STOP=1 -d bem "${v[@]}"
}
state() { pgv "SELECT coalesce((SELECT status FROM bem_control.session_start WHERE lease_id = :'l'::uuid), 'NONE')" "l=$1"; }
pass() { systemctl start zagent-start.service; }
active() { systemctl is-active "zagent@$1.service" 2>/dev/null || true; }
LID=$(cat /proc/sys/kernel/random/uuid)
L=${LID//-/}
HOLDER="install-3.5.1.6-$(date -u +%Y%m%dT%H%M%SZ)"
pgv "INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
      holder_session, rules_commit, code_commit, status, opened_by)
      VALUES (:'id', gen_random_uuid(), '01_install_probe', 'P00001', 1, gen_random_uuid(), :'holder',
      :'commit', :'commit', 'OPEN', 'install-3.5.1.6')" "id=$LID" "holder=$HOLDER" "commit=$COMMIT" > /dev/null
runuser -u zkernel -- touch "/run/zavod/start/$L"
up=0
for _ in $(seq 1 24); do pass; if [ "$(active "$L")" = active ]; then up=1; break; fi; sleep 5; done
[ "$up" = 1 ] || { journalctl -u zagent-start.service -n 30 --no-pager; die "probe session did not start"; }
ready=0
for _ in $(seq 1 30); do
  if journalctl -u "zagent@$L.service" --no-pager | grep -q 'ZAGENT_SESSION ready'; then ready=1; break; fi
  sleep 1
done
[ "$ready" = 1 ] || die "probe session not ready"
J=$(journalctl -u "zagent@$L.service" --no-pager)
for p in write_etc write_var_lib write_home read_shadow net_public net_db sudo; do
  printf '%s\n' "$J" | grep -q "ZAGENT_PROBE $p=DENIED" || die "cage wall $p is not closed"
done
printf '%s\n' "$J" | grep -q 'ZAGENT_PROBE write_own=OK' || die "cage own workdir is not writable"
[ "$(pgv "SELECT bem_control.lease_mark_running(:'l'::uuid)" "l=$LID")" = RUNNING ] || die "probe lease not RUNNING"
runuser -u zkernel -- touch "/run/zavod/stop/$L"
down=0
for _ in $(seq 1 24); do pass; if [ "$(active "$L")" != active ]; then down=1; break; fi; sleep 5; done
[ "$down" = 1 ] || die "probe session did not stop"
pass
[ "$(state "$LID")" = INTERRUPTED ] || die "probe lease state $(state "$LID"), not INTERRUPTED"
echo "PROBE_SESSION=OK lease=$LID cage=closed stopped=INTERRUPTED"

echo "=== 6. отчёт (3.5.1.7)"
REL=$(readlink -f /opt/zavod/current)
INV=$(cd "$REL" && grep -v '^#' MANIFEST.sha256 | sha256sum | cut -c1-64)
{
  echo "ZAVOD_3_5_1_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "ZAVOD_3_5_1_HOST=$(hostname) arch=$ARCH os=$ID-$VERSION_ID kernel=$(uname -r)"
  echo "ZAVOD_3_5_1_PACKAGE=commit=$COMMIT manifest_sha256=$MSHA"
  echo "ZAVOD_3_5_1_RELEASE=$REL inventory_sha256=$INV"
  grep -E '^ZAVOD_SERVER_(OS|RELEASE)=' "$OUT" | sed 's/^/ZAVOD_3_5_1_/'
  for p in git gh openssh-server; do echo "ZAVOD_3_5_1_PKG=$(dpkg-query -W -f='${Package}=${Version}' "$p")"; done
  grep -E '^ZAVOD_SERVER_OS_PACKAGE=' "$OUT" | sed 's/^ZAVOD_SERVER_OS_PACKAGE=/ZAVOD_3_5_1_PKG=/'
  echo "ZAVOD_3_5_1_SSH=password_off"
  echo "ZAVOD_3_5_1_POINT_B=sh=$n_sh py=$n_py node=$NODEV"
  echo "ZAVOD_3_5_1_PROBE=lease=$LID INTERRUPTED"
  echo "ZAVOD_3_5_1=OK"
} > "$REPORT.new"
chmod 0600 "$REPORT.new"
mv -T "$REPORT.new" "$REPORT"
echo "--- отчёт $REPORT (sha256 $(sha256sum "$REPORT" | cut -c1-64)):"
cat "$REPORT"
