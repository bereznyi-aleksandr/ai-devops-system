#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/install_stage_3_5_1.sh
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-05 17:03 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-05 17:53 +02:00 (v0.2: аудит ChatGPT STAGE351 R1 —
#   C-351-R1-01: вход по паролю выключается только из SSH-сеанса, вошедшего по ключу; настройка-кандидат проверяется
#   до изменения действующей (с адресом этого сеанса); файл настройки не заменяется; после включения — второй вход
#   по ключу новым окном (код 4 RELOGIN_REQUIRED, повтор той же команды); M-351-R1-01: полная сверка пакета
#   (install_server.sh --check-only, verify_tree.py closed) до первого изменения системы; M-351-R1-02: отчёт — новый
#   файл на каждый запуск, ничего не перезаписывается; M-351-R1-03: --no-upgrade и имитация обновления — только на
#   машине CI GitHub; L-351-R1-01: одна пробная аренда на коммит выпуска, их число и номера — в отчёте;
#   v0.1 от 17:03: карта 3.5.1.2–3.5.1.7)
# ИСПОЛНИТЕЛЬ: Claude (сессии c28394bb-ae8a-47d6-aad3-111e08d58001, e4640034-a723-4cee-bed1-c6b3a649419c)
# НАЗНАЧЕНИЕ: одна команда установки сервера Завода на этапе 3.5.1 (карта Завода v3.1, RISK_ARM64_3_4_1_v1_1):
#   0) только чтение: пакет сверяется полностью (опись, лишние файлы, ссылки, права, владелец root, закрытые папки
#      выше); команда идёт в SSH-сеансе root, вошедшем ПО КЛЮЧУ (журнал sshd: «Accepted publickey» для адреса и
#      порта этого сеанса); настройка входа «только по ключу» проверяется кандидатом во временной папке (sshd -t,
#      sshd -T с адресом этого сеанса — условия Match учтены);
#   1) 3.5.1.2 — обновление системы (apt-get full-upgrade); нужна перезагрузка — стоп с кодом 3 и строкой
#      REBOOT_REQUIRED: оператор перезагружает сервер и повторяет ту же команду;
#   2) 3.5.1.2 — пакеты git и gh; вход по паролю выключен файлом /etc/ssh/sshd_config.d/00-zavod-no-password.conf
#      (PasswordAuthentication no, KbdInteractiveAuthentication no, PermitRootLogin prohibit-password). Первый
#      запуск создаёт файл (только если его нет), проверяет sshd и выходит с кодом 4 RELOGIN_REQUIRED: прежнее окно
#      не закрывать, войти по ключу ВТОРЫМ окном и в нём повторить ту же команду. Повтор идёт дальше, только если
#      его сеанс вошёл по ключу ПОСЛЕ создания файла — так доказано, что вход по ключу работает с новой настройкой;
#   3) точка Б (проверка 7 RISK_ARM64): все сценарии пакета разбираются (bash -n, compile() для python), git, gh и
#      Node.js из архива пакета (во временной папке) запускаются на процессоре сервера;
#   4) 3.5.1.3–3.5.1.5 — install_server.sh (учётные записи, папки, база, ячейка, ядро, движок);
#   5) 3.5.1.6 — пробный пустой сеанс (один на коммит выпуска): пробная аренда (opened_by install-3.5.1.6) → файл
#      запуска от zkernel → сеанс в клетке поднялся, стены клетки держат → файл остановки → сеанс погас, запись
#      INTERRUPTED; при повторе того же выпуска новая аренда не создаётся, называется прежняя;
#   6) 3.5.1.7 — отчёт: блок строк ZAVOD_3_5_1_* на экране и в НОВОМ файле /root/zavod-install-3.5.1-<время>.txt.
# ВЫЗОВ: в SSH-сеансе root, вошедшем по ключу: bash install_stage_3_5_1.sh <папка распакованного пакета>
#   [параметры install_cell.sh …]. Коды: 0 — OK; 3 — нужна перезагрузка; 4 — нужен второй вход по ключу; 1 — отказ.
#   --no-upgrade (сразу после папки) — только машина CI GitHub (GITHUB_ACTIONS=true и /home/runner/work); на сервере —
#   отказ. ZAVOD_CI_APT_SIM=1 — там же: обновление в режиме имитации (apt-get -s), ветка REBOOT_REQUIRED работает.
# ОГРАНИЧЕНИЯ: ничего не удаляет и не перезаписывает (неудачная настройка входа переименовывается в *.REFUSED-<время>,
#   sshd её больше не читает). Ключей не создаёт и не читает. Пробная аренда остаётся в базе с пометкой
#   opened_by = install-3.5.1.6 у отдельного пробного заказчика (случайный tenant_id) — это след пробы, а не работа.
#   Запасной вход при потере SSH — консоль сервера на сайте Hetzner.
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
# Аудит M-351-R1-03: режимы CI на сервере не принимаются (случайно скопированная команда CI — отказ до изменений).
CI_MACHINE=0
if [ "${GITHUB_ACTIONS:-}" = true ] && [ -d /home/runner/work ]; then CI_MACHINE=1; fi
[ "$UPGRADE" = 1 ] || [ "$CI_MACHINE" = 1 ] || die "--no-upgrade is for the CI machine only: run the command without it"
APT_SIM=0
if [ -n "${ZAVOD_CI_APT_SIM:-}" ]; then
  [ "$CI_MACHINE" = 1 ] && [ "$ZAVOD_CI_APT_SIM" = 1 ] || die "ZAVOD_CI_APT_SIM is for the CI machine only"
  APT_SIM=1
fi
TS=$(date -u +%Y%m%dT%H%M%SZ)
REPORT=/root/zavod-install-3.5.1-$TS.txt
echo "=== ZAVOD 3.5.1 start $TS arch=$ARCH"

echo "=== 0. проверки до любых изменений (только чтение)"
M="$PKG/MANIFEST.sha256"
[ -f "$M" ] || die "no MANIFEST.sha256"
[ "$(sed -n '2p' "$M")" = "#arch $ARCH" ] || die "package is not for this processor ($ARCH): $(sed -n '2p' "$M")"
# Аудит M-351-R1-01: та же полная сверка, что и в install_server.sh (опись, лишние файлы, ссылки, жёсткие ссылки,
# права), — до первого изменения; плюс владелец root и закрытые папки пакета и выше (verify_tree.py closed).
bash "$PKG/zavod/ops/server/install_server.sh" --check-only "$PKG" || die "package check failed: nothing changed"
python3 -I "$PKG/zavod/ops/server/verify_tree.py" closed "$PKG" || die "package folder is not closed: nothing changed"
COMMIT=$(sed -n '1s/^# zavod server package; source commit \([0-9a-f]\{40\}\)$/\1/p' "$M")
[ -n "$COMMIT" ] || die "manifest has no source commit"
MSHA=$(sha256sum "$M" | cut -c1-64)
echo "PACKAGE_MANIFEST commit=$COMMIT manifest_sha256=$MSHA"

# Аудит C-351-R1-01: команда идёт в SSH-сеансе root, и этот сеанс вошёл по ключу.
read -r CIP CPORT _ <<< "${SSH_CONNECTION:-}"
[ -n "${CPORT:-}" ] || die "run this command in an SSH session of root logged in by key (not from a console): nothing changed"
# Строка журнала sshd о входе именно этого сеанса (адрес и порт); с аргументом — только после этого времени (эпоха).
accepted() {
  local since=()
  [ -z "${1:-}" ] || since=(--since "@$1")
  # grep без -q читает журнал до конца: ранний выход grep -q оборвал бы journalctl, и pipefail дал бы ложный провал
  journalctl -t sshd -t sshd-session --no-pager -o cat "${since[@]}" \
    | grep -F "Accepted publickey for root from $CIP port $CPORT ssh2" > /dev/null
}
accepted || die "this SSH session ($CIP port $CPORT) did not log in by key: log in with ssh -i <key> root@<server> and repeat; nothing changed"
echo "SSH_SESSION=key from=$CIP port=$CPORT"
D=/etc/ssh/sshd_config.d/00-zavod-no-password.conf
want='# zavod 3.5.1.2: вход только по ключу
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password'
# Ubuntu 24.04 запускает sshd по сокету: папки /run/sshd может ещё не быть, без неё sshd -t не работает.
[ -d /run/sshd ] || install -d -o root -g root -m 0755 /run/sshd
# Действующие значения для адреса этого сеанса (условия Match учтены): вход по ключу есть, по паролю нет.
effective_ok() {
  local T kv
  T=$(sshd -T -f "$1" -C "user=root,host=$CIP,addr=$CIP") || return 1
  for kv in 'pubkeyauthentication yes' 'passwordauthentication no' 'kbdinteractiveauthentication no' \
            'permitrootlogin (without-password|prohibit-password)'; do
    printf '%s\n' "$T" | grep -qxE "$kv" || { echo "sshd effective setting is not: $kv" >&2; return 1; }
  done
}
# Кандидат: строки файла первыми, затем действующая настройка целиком (у sshd действует первое значение —
# как у файла 00- в sshd_config.d, который читается первым). Временная папка в /tmp, действующая настройка не трогается.
CAND=$(mktemp -d /tmp/zavod-sshd-candidate-XXXXXX)
printf '%s\nInclude /etc/ssh/sshd_config\n' "$want" > "$CAND/sshd_config"
sshd -t -f "$CAND/sshd_config" || die "candidate sshd configuration does not pass sshd -t: nothing changed"
effective_ok "$CAND/sshd_config" || die "candidate sshd configuration is not key-only for $CIP: nothing changed"
echo "SSH_CANDIDATE=OK"
if [ -e "$D" ] || [ -L "$D" ]; then
  { [ -f "$D" ] && [ ! -L "$D" ] && [ "$(cat "$D")" = "$want" ]; } || die "$D exists and differs: nothing changed"
fi

# Без вопросов на экране: needrestart сам перезапускает службы, при правленом файле настроек остаётся прежний.
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
echo "=== 1. обновление системы (3.5.1.2)"
if [ "$UPGRADE" = 1 ]; then
  apt-get update -qq
  if [ "$APT_SIM" = 1 ]; then
    apt-get -s full-upgrade > /dev/null
  else
    apt-get full-upgrade -y -qq -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold > /dev/null
  fi
  if [ -e /var/run/reboot-required ]; then
    echo "REBOOT_REQUIRED: система обновлена, нужна перезагрузка. Введите reboot, войдите снова по ключу и повторите ту же команду."
    exit 3
  fi
  if [ "$APT_SIM" = 1 ]; then echo "SYSTEM_UPGRADE=SIMULATED (CI)"; else echo "SYSTEM_UPGRADE=OK"; fi
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
if [ ! -e "$D" ]; then
  # Первый проход: файл создаётся только если его нет (set -C), затем проверка действующей настройки. Провал —
  # файл переименовывается (sshd читает только *.conf), прежняя настройка снова действует; затем отказ.
  [ -s /root/.ssh/authorized_keys ] || die "/root/.ssh/authorized_keys is empty: password login stays as is"
  (umask 022; set -C; printf '%s\n' "$want" > "$D")
  if ! sshd -t || ! effective_ok /etc/ssh/sshd_config; then
    mv -n "$D" "$D.REFUSED-$TS"
    [ ! -e "$D" ] || die "sshd check failed and $D could not be set aside"
    die "sshd check failed with $D; it is set aside as $D.REFUSED-$TS, the previous settings stay"
  fi
  if systemctl is-active --quiet ssh.service; then systemctl reload ssh.service; fi
  echo "SSH_PASSWORD_LOGIN=OFF file=$D"
  echo "RELOGIN_REQUIRED: вход по паролю выключен. Это окно НЕ закрывайте. Откройте второе окно, войдите по ключу"
  echo "  (ssh -i <ключ> root@<сервер>) и во втором окне повторите ту же команду. Не вышло войти — в этом окне:"
  echo "  mv $D $D.ARCHIVED-$TS; systemctl reload ssh.service"
  exit 4
fi
effective_ok /etc/ssh/sshd_config || die "sshd effective settings are not key-only for $CIP"
MT=$(stat -c %Y "$D")
if ! accepted "$MT"; then
  echo "RELOGIN_REQUIRED: этот сеанс начался до выключения пароля ($D). Войдите по ключу новым окном и повторите команду в нём."
  exit 4
fi
echo "SSH_RELOGIN=OK session=$CIP:$CPORT logged in by key after $D ($(date -u -d "@$MT" +%Y-%m-%dT%H:%M:%SZ))"

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
# Аудит L-351-R1-01: проба — одна на коммит выпуска; при повторе того же выпуска называется прежняя (новых OPEN нет).
PREV=$(pgv "SELECT l.lease_id FROM bem_control.chat_lease l JOIN bem_control.session_start s ON s.lease_id = l.lease_id
      WHERE l.opened_by = 'install-3.5.1.6' AND l.code_commit = :'c' AND s.status = 'INTERRUPTED'
      ORDER BY l.lease_id LIMIT 1" "c=$COMMIT")
if [ -n "$PREV" ]; then
  LID=$PREV
  echo "PROBE_SESSION=OK lease=$LID cage=closed stopped=INTERRUPTED reused=1 (probe of this release already done)"
else
  LID=$(cat /proc/sys/kernel/random/uuid)
  L=${LID//-/}
  HOLDER="install-3.5.1.6-$TS"
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
fi
PROBES=$(pgv "SELECT count(*) || ' ' || coalesce(string_agg(lease_id::text, ',' ORDER BY lease_id), '')
      FROM bem_control.chat_lease WHERE opened_by = 'install-3.5.1.6'")
echo "PROBE_LEASES=${PROBES% *} ids=${PROBES#* } (opened_by install-3.5.1.6, role 01_install_probe: probe trace, not work)"

echo "=== 6. отчёт (3.5.1.7)"
REL=$(readlink -f /opt/zavod/current)
INV=$(cd "$REL" && grep -v '^#' MANIFEST.sha256 | sha256sum | cut -c1-64)
# Аудит M-351-R1-02: каждый запуск — новый файл отчёта (имя со временем, set -C), прежние остаются.
(umask 077; set -C
{
  echo "ZAVOD_3_5_1_TIME=$TS"
  echo "ZAVOD_3_5_1_HOST=$(hostname) arch=$ARCH os=$ID-$VERSION_ID kernel=$(uname -r)"
  echo "ZAVOD_3_5_1_PACKAGE=commit=$COMMIT manifest_sha256=$MSHA"
  echo "ZAVOD_3_5_1_RELEASE=$REL inventory_sha256=$INV"
  grep -E '^ZAVOD_SERVER_(OS|RELEASE)=' "$OUT" | sed 's/^/ZAVOD_3_5_1_/'
  for p in git gh openssh-server; do echo "ZAVOD_3_5_1_PKG=$(dpkg-query -W -f='${Package}=${Version}' "$p")"; done
  grep -E '^ZAVOD_SERVER_OS_PACKAGE=' "$OUT" | sed 's/^ZAVOD_SERVER_OS_PACKAGE=/ZAVOD_3_5_1_PKG=/'
  echo "ZAVOD_3_5_1_SSH=password_off relogin_by_key=$CIP:$CPORT"
  echo "ZAVOD_3_5_1_POINT_B=sh=$n_sh py=$n_py node=$NODEV"
  echo "ZAVOD_3_5_1_PROBE=lease=$LID INTERRUPTED probe_leases=${PROBES% *}"
  echo "ZAVOD_3_5_1=OK"
} > "$REPORT")
echo "--- отчёт $REPORT (sha256 $(sha256sum "$REPORT" | cut -c1-64)):"
cat "$REPORT"
