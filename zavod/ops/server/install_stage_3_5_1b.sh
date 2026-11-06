#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/install_stage_3_5_1b.sh
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-06 12:30 +02:00 (v0.3: версия программ — только из stdout, CI arm64: codex пишет предупреждение о /tmp; v0.2: поля закреплённых строк — шаблонами case вместо [[ =~ ]], сканер И.7а)
# ДАТА СОЗДАНИЯ: 2026-11-06 12:14 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сессия bb50840e-710a-4bb9-84b8-a44d1a8ea411)
# НАЗНАЧЕНИЕ: шаг 3.5.1б карты Завода v3.1 (решение оператора 2026-11-06 12:07) — установка на сервер Arm64 трёх
#   программ по закреплённым версиям и суммам (tools_pins_3_5_1b.txt): Claude CLI, Codex CLI и Google Chrome. Входы
#   (claude setup-token, codex login, вход в Chrome) — НЕ здесь: это шаг 3.5.2, их делает только оператор.
#   0) только чтение: пакет сверяется полностью (как в 3.5.1); шаг 3.5.1 уже пройден (отчёт ZAVOD_3_5_1=OK, выпуск
#      /opt/zavod/current, учётная запись zbrowser); список закреплённых файлов разобран; прежнее состояние —
#      либо его нет, либо оно ровно такое, какое ставит этот установщик; иначе отказ, ничего не изменено;
#   1) скачивание по закреплённым адресам (только https) в новую закрытую папку; размер и sha256 сверяются ДО
#      использования; файл переносится в хранилище /var/lib/zavod-install-3.5.1b/dl без замены (mv -nT);
#   2) Claude CLI и Codex CLI: архив проверяется и распаковывается без npm и без сценариев установки
#      (tools_tar_3_5_1b.py) в закрытую папку, опись папки = опись архива, затем перенос без замены в
#      /opt/zavod/tools/<имя>; программы — только для Arm64 (verify_tree.py elf); проба --version от nobody;
#   3) Chrome: сначала /etc/default/google-chrome (repo_add_once="false") — установщик Chrome тогда НЕ добавляет
#      источник обновлений Google; затем apt-get install закреплённого .deb (зависимости — из Ubuntu), apt-mark hold,
#      dpkg --verify, проба --version от nobody; в отчёте — файлы с битом setuid;
#   4) отчёт: строки ZAVOD_3_5_1B_* на экране и в НОВОМ файле /root/zavod-install-3.5.1b-<время>.txt.
#   Повтор той же команды: уже сверенные файлы и папки не скачиваются и не распаковываются заново, а сверяются.
# ВЫЗОВ: bash install_stage_3_5_1b.sh <папка распакованного пакета>. Коды: 0 — OK; 1 — отказ.
# ОГРАНИЧЕНИЯ: ничего не удаляет и не перезаписывает (испорченный файл хранилища откладывается переименованием в
#   новую папку bad-*). PATH и ссылки в /usr/local/bin не меняются: программы вызываются по полному пути. Ключей и
#   входов не создаёт и не читает. Секретов нет.
set -euo pipefail
export LC_ALL=C
PKG=${1:?usage: install_stage_3_5_1b.sh PACKAGE_DIR}
[ $# = 1 ] || { echo "REFUSED: unexpected arguments after the package folder: nothing changed" >&2; exit 1; }
PKG=$(cd "$PKG" && pwd -P)
die() { echo "REFUSED: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root"
exec 9>> /run/zavod-install-3.5.1b.lock
flock -n 9 || die "another install_stage_3_5_1b.sh run is in progress: nothing changed"
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ] || die "Ubuntu 24.04 only (found ${ID:-?} ${VERSION_ID:-?})"
[ "$(uname -m)" = aarch64 ] || die "this step is for the Arm64 server only (found $(uname -m)): nothing changed"
ARCH=arm64
TS=$(date -u +%Y%m%dT%H%M%S.%NZ)-$$
REPORT=/root/zavod-install-3.5.1b-$TS.txt
echo "=== ZAVOD 3.5.1b start $TS arch=$ARCH"

echo "=== 0. проверки до любых изменений (только чтение)"
M="$PKG/MANIFEST.sha256"
[ -f "$M" ] || die "no MANIFEST.sha256"
[ "$(sed -n '2p' "$M")" = "#arch $ARCH" ] || die "package is not for this processor ($ARCH): $(sed -n '2p' "$M")"
bash "$PKG/zavod/ops/server/install_server.sh" --check-only "$PKG" || die "package check failed: nothing changed"
python3 -I "$PKG/zavod/ops/server/verify_tree.py" closed "$PKG" || die "package folder is not closed: nothing changed"
COMMIT=$(sed -n '1s/^# zavod server package; source commit \([0-9a-f]\{40\}\)$/\1/p' "$M")
[ -n "$COMMIT" ] || die "manifest has no source commit"
MSHA=$(sha256sum "$M" | cut -c1-64)
echo "PACKAGE_MANIFEST commit=$COMMIT manifest_sha256=$MSHA"
TAR_PY="$PKG/zavod/ops/server/tools_tar_3_5_1b.py"
VERIFY="$PKG/zavod/ops/server/verify_tree.py"
PINS="$PKG/zavod/ops/server/tools_pins_3_5_1b.txt"

# Шаг 3.5.1 пройден: отчёт с ZAVOD_3_5_1=OK (владелец root, только для root), выпуск и учётная запись zbrowser.
R351=$(find /root -maxdepth 1 -type f -name 'zavod-install-3.5.1-*.txt' -user root -perm 600 -exec grep -lx ZAVOD_3_5_1=OK {} + | sort | tail -n 1) || true
[ -n "$R351" ] || die "step 3.5.1 is not done (no /root/zavod-install-3.5.1-*.txt with ZAVOD_3_5_1=OK): nothing changed"
[ -L /opt/zavod/current ] && [ -d /opt/zavod/current ] || die "/opt/zavod/current is missing: step 3.5.1 is not done"
id zbrowser > /dev/null 2>&1 || die "account zbrowser is missing: step 3.5.1 is not done"
echo "STEP_3_5_1=done report=$R351"

# Список закреплённых файлов: ровно три строки, каждое поле по своему образцу.
mapfile -t PIN < <(grep -v '^#' "$PINS")
[ "${#PIN[@]}" = 3 ] || die "tools_pins_3_5_1b.txt must have 3 pin lines, found ${#PIN[@]}"
NAME=() SIZE=() SUM=() URL=() DEST=() KIND=()
for l in "${PIN[@]}"; do
  read -r k n s h u d x <<< "$l"
  [ -z "${x:-}" ] && [ -n "${d:-}" ] || die "bad pin line: $l"
  case "$k" in npm|deb) ;; *) die "bad pin kind: $l" ;; esac
  # Образцы полей — постоянные шаблоны case (без регулярных выражений): лишний знак — отказ.
  case "$n" in [A-Za-z0-9]*.tgz|[A-Za-z0-9]*.deb) ;; *) die "bad pin file name: $l" ;; esac
  case "$n" in *[!A-Za-z0-9._+-]*) die "bad pin file name: $l" ;; esac
  case "$s" in ''|0*|*[!0-9]*) die "bad pin size: $l" ;; esac
  [ "${#h}" = 64 ] || die "bad pin sha256: $l"
  case "$h" in *[!0-9a-f]*) die "bad pin sha256: $l" ;; esac
  case "$u" in https://registry.npmjs.org/?*|https://dl.google.com/?*) ;; *) die "bad pin address: $l" ;; esac
  case "${u#https://}" in *[!A-Za-z0-9@/._+-]*|*..*|*//*) die "bad pin address: $l" ;; esac
  [ "${u##*/}" = "$n" ] || die "bad pin address: $l"
  case "$d" in [A-Za-z0-9]*) ;; *) die "bad pin folder or version: $l" ;; esac
  case "$d" in *[!A-Za-z0-9._+-]*) die "bad pin folder or version: $l" ;; esac
  KIND+=("$k") NAME+=("$n") SIZE+=("$s") SUM+=("$h") URL+=("$u") DEST+=("$d")
done
[ "${KIND[*]}" = 'npm npm deb' ] || die "pins must be: npm npm deb (found ${KIND[*]})"
CLAUDE_DIR=/opt/zavod/tools/${DEST[0]}
CODEX_DIR=/opt/zavod/tools/${DEST[1]}
CHROME_VER=${DEST[2]}
CODEX_BIN=$CODEX_DIR/vendor/aarch64-unknown-linux-musl/bin/codex

# Папки: /opt/zavod и /opt/zavod/tools — root:root 0755, хранилище — root 0700, без ссылок.
dir_is() { [ -d "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%U:%G %a' "$1")" = "$2" ]; }
dir_is /opt/zavod 'root:root 755' || die "/opt/zavod is not a root:root 0755 folder: nothing changed"
TOOLS=/opt/zavod/tools
if [ -e "$TOOLS" ] || [ -L "$TOOLS" ]; then dir_is "$TOOLS" 'root:root 755' || die "$TOOLS is not a root:root 0755 folder: nothing changed"; fi
EVD=/var/lib/zavod-install-3.5.1b
DL=$EVD/dl
for p in "$EVD" "$DL"; do
  if [ -e "$p" ] || [ -L "$p" ]; then dir_is "$p" 'root:root 700' || die "$p is not a root-only folder: nothing changed"; fi
done
# Прежние папки программ — ровно как у закреплённых архивов (сверка описи — на шаге 2); здесь — что это папки.
for p in "$CLAUDE_DIR" "$CODEX_DIR"; do
  if [ -e "$p" ] || [ -L "$p" ]; then dir_is "$p" 'root:root 755' || die "$p exists and is not a root:root 0755 folder: nothing changed"; fi
done
# Chrome: настройка источника и его прежнее состояние.
DEF=/etc/default/google-chrome
want_def='repo_add_once="false"
repo_reenable_on_distupgrade="false"'
if [ -e "$DEF" ] || [ -L "$DEF" ]; then
  { [ -f "$DEF" ] && [ ! -L "$DEF" ] && [ "$(cat "$DEF")" = "$want_def" ]; } || die "$DEF exists and differs: nothing changed"
fi
for s in /etc/apt/sources.list.d/google-chrome.sources /etc/apt/sources.list.d/google-chrome.list; do
  [ ! -e "$s" ] && [ ! -L "$s" ] || die "$s exists (Google update source): nothing changed"
done
CHROME_NOW=$(dpkg-query -W -f='${Status} ${Version}' google-chrome-stable 2>/dev/null || true)
case "$CHROME_NOW" in
  ''|'unknown ok not-installed '*|'deinstall ok config-files '*) CHROME_NOW= ;;
  "install ok installed $CHROME_VER") ;;
  *) die "google-chrome-stable is already in another state ($CHROME_NOW), not $CHROME_VER: nothing changed" ;;
esac
# Места: архивы ~0,5 ГБ, программы ~0,8 ГБ, Chrome с зависимостями ~0,6 ГБ — нужно не меньше 3 ГБ свободных.
for p in /var/lib /opt; do
  free=$(df --output=avail -B1M "$p" | tail -n 1 | tr -d ' ')
  [ "$free" -ge 3072 ] || die "only ${free} MB free on $p, need 3072 MB: nothing changed"
done
command -v curl > /dev/null || die "curl is missing: nothing changed"
echo "PRECHECK=OK"

echo "=== 1. закреплённые файлы: скачивание и сверка (размер и sha256 до использования)"
[ -d "$EVD" ] || install -d -o root -g root -m 0700 "$EVD"
[ -d "$DL" ] || install -d -o root -g root -m 0700 "$DL"
file_ok() { [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%s' "$1")" = "$2" ] && echo "$3  $1" | sha256sum -c --strict --status -; }
for i in 0 1 2; do
  F=$DL/${NAME[$i]}
  if [ -e "$F" ] || [ -L "$F" ]; then
    if file_ok "$F" "${SIZE[$i]}" "${SUM[$i]}" && [ "$(stat -c '%U:%G %a' "$F")" = 'root:root 400' ]; then
      echo "DOWNLOAD_REUSED=${NAME[$i]} sha256=${SUM[$i]}"
      continue
    fi
    B=$(mktemp -d "$EVD/bad-XXXXXX")
    mv -nT "$F" "$B/${NAME[$i]}"
    die "$F differs from the pin (size, sum or rights): set aside as $B/${NAME[$i]}; repeat the command to download again"
  fi
  D=$(mktemp -d "$EVD/dl-new-XXXXXX")
  curl -fsSL --proto '=https' --tlsv1.2 --retry 2 -o "$D/${NAME[$i]}" "${URL[$i]}" \
    || die "download of ${NAME[$i]} failed, partial file left in $D, nothing else changed"
  file_ok "$D/${NAME[$i]}" "${SIZE[$i]}" "${SUM[$i]}" \
    || die "${NAME[$i]} from ${URL[$i]} differs from the pin (size or sha256): left in $D, not used"
  chmod 0400 "$D/${NAME[$i]}"
  { mv -nT "$D/${NAME[$i]}" "$F" && [ ! -e "$D/${NAME[$i]}" ]; } || die "$F could not be put in place: file left in $D"
  file_ok "$F" "${SIZE[$i]}" "${SUM[$i]}" || die "$F failed its check after the move"
  echo "DOWNLOAD=OK ${NAME[$i]} size=${SIZE[$i]} sha256=${SUM[$i]}"
done

echo "=== 2. Claude CLI и Codex CLI: распаковка без npm, опись папки = опись архива"
[ -d "$TOOLS" ] || install -d -o root -g root -m 0755 "$TOOLS"
WORK=$(mktemp -d /tmp/zavod-351b-XXXXXX)
INV=()
for i in 0 1; do
  F=$DL/${NAME[$i]} P=$TOOLS/${DEST[$i]}
  python3 -I "$TAR_PY" list "$F" > "$WORK/want-$i.txt" || die "archive ${NAME[$i]} failed its check: nothing unpacked"
  if [ -e "$P" ]; then
    python3 -I "$TAR_PY" inventory "$P" > "$WORK/got-$i.txt" || die "$P failed its check: nothing changed"
    cmp -s "$WORK/want-$i.txt" "$WORK/got-$i.txt" \
      || die "$P differs from ${NAME[$i]} ($(diff "$WORK/want-$i.txt" "$WORK/got-$i.txt" | grep -c '^[<>]') lines): nothing changed"
    echo "TOOL_REUSED=$P (same as ${NAME[$i]}, not unpacked again)"
  else
    T=$(mktemp -d "$EVD/unpack-XXXXXX")
    python3 -I "$TAR_PY" unpack "$F" "$T/${DEST[$i]}" > "$WORK/unpacked-$i.txt" || die "unpack of ${NAME[$i]} failed: left in $T, $P not created"
    cmp -s "$WORK/want-$i.txt" "$WORK/unpacked-$i.txt" || die "unpacked ${NAME[$i]} differs from its listing: left in $T"
    python3 -I "$TAR_PY" inventory "$T/${DEST[$i]}" > "$WORK/staged-$i.txt" || die "staged ${DEST[$i]} failed its check: left in $T"
    cmp -s "$WORK/want-$i.txt" "$WORK/staged-$i.txt" || die "staged ${DEST[$i]} differs from ${NAME[$i]}: left in $T"
    { mv -nT "$T/${DEST[$i]}" "$P" && [ ! -e "$T/${DEST[$i]}" ]; } || die "$P could not be put in place: left in $T"
    python3 -I "$TAR_PY" inventory "$P" > "$WORK/got-$i.txt" || die "$P failed its check after the move"
    cmp -s "$WORK/want-$i.txt" "$WORK/got-$i.txt" || die "$P differs from ${NAME[$i]} after the move"
    echo "TOOL_UNPACKED=$P files=$(grep -vc '^-  ' "$WORK/got-$i.txt")"
  fi
  python3 -I "$VERIFY" elf "$ARCH" "$P" || die "$P has a program for another processor"
  INV+=("$(sha256sum < "$WORK/got-$i.txt" | cut -c1-64)")
done
[ -f "$CLAUDE_DIR/claude" ] && [ "$(stat -c '%a' "$CLAUDE_DIR/claude")" = 755 ] || die "$CLAUDE_DIR/claude is not a program file"
[ -f "$CODEX_BIN" ] && [ "$(stat -c '%a' "$CODEX_BIN")" = 755 ] || die "$CODEX_BIN is not a program file"
# Проба запуска: от nobody, пустое окружение, временная домашняя папка; самообновление Claude выключено.
H=$(mktemp -d /tmp/zavod-351b-home-XXXXXX)
chown nobody:nogroup "$H"
asnobody() { runuser -u nobody -- env -i HOME="$H" PATH=/usr/bin:/bin LANG=C.UTF-8 DISABLE_AUTOUPDATER=1 "$@" < /dev/null; }
# Версия — только из стандартного вывода; сообщения ошибок (stderr) — в файл, в отчёте их число строк.
CLAUDE_V=$(asnobody "$CLAUDE_DIR/claude" --version 2> "$WORK/claude-version.err" | head -n 1) || die "claude does not run: $(head -c 300 "$WORK/claude-version.err")"
CODEX_V=$(asnobody "$CODEX_BIN" --version 2> "$WORK/codex-version.err" | head -n 1) || die "codex does not run: $(head -c 300 "$WORK/codex-version.err")"
want_claude=${DEST[0]#claude-code-}; want_claude=${want_claude%-linux-arm64}
want_codex=${DEST[1]#codex-}; want_codex=${want_codex%-linux-arm64}
case "$CLAUDE_V" in "$want_claude "*) ;; *) die "claude --version says '$CLAUDE_V', not $want_claude" ;; esac
case "$CODEX_V" in *" $want_codex") ;; *) die "codex --version says '$CODEX_V', not $want_codex" ;; esac
echo "CLAUDE_CLI=OK path=$CLAUDE_DIR/claude version=\"$CLAUDE_V\" inventory_sha256=${INV[0]} stderr_lines=$(wc -l < "$WORK/claude-version.err")"
echo "CODEX_CLI=OK path=$CODEX_BIN version=\"$CODEX_V\" inventory_sha256=${INV[1]} stderr_lines=$(wc -l < "$WORK/codex-version.err")"

echo "=== 3. Chrome (без источника обновлений Google)"
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
DEB=$DL/${NAME[2]}
[ "$(dpkg-deb -f "$DEB" Package Version Architecture | tr '\n' ' ')" = "google-chrome-stable $CHROME_VER arm64 " ] \
  || die "${NAME[2]} control fields are not google-chrome-stable $CHROME_VER arm64"
if [ ! -e "$DEF" ]; then
  (umask 022; set -C; printf '%s\n' "$want_def" > "$DEF")
fi
[ "$(cat "$DEF")" = "$want_def" ] || die "$DEF differs after writing"
if [ -z "$CHROME_NOW" ]; then
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold "$DEB" > "$WORK/apt-chrome.out" 2>&1 \
    || { tail -n 30 "$WORK/apt-chrome.out" >&2; die "apt-get install of ${NAME[2]} failed"; }
  echo "CHROME_INSTALLED=$CHROME_VER"
else
  echo "CHROME_REUSED=$CHROME_VER (already installed, not installed again)"
fi
[ "$(dpkg-query -W -f='${Status} ${Version}' google-chrome-stable)" = "install ok installed $CHROME_VER" ] || die "google-chrome-stable is not $CHROME_VER after install"
apt-mark hold google-chrome-stable > /dev/null
apt-mark showhold | grep -qx google-chrome-stable || die "google-chrome-stable is not on hold"
V=$(dpkg --verify google-chrome-stable 2>&1) || true
[ -z "$V" ] || die "installed Chrome files differ from the package: $V"
for s in /etc/apt/sources.list.d/google-chrome.sources /etc/apt/sources.list.d/google-chrome.list; do
  [ ! -e "$s" ] && [ ! -L "$s" ] || die "Chrome added an update source $s"
done
python3 -I "$VERIFY" elf "$ARCH" /opt/google/chrome || die "/opt/google/chrome has a program for another processor"
CHROME_V=$(asnobody /usr/bin/google-chrome-stable --version 2> "$WORK/chrome-version.err" | head -n 1) || die "chrome does not run: $(head -c 300 "$WORK/chrome-version.err")"
case "$CHROME_V" in "Google Chrome ${CHROME_VER%-*}"*) ;; *) die "google-chrome-stable --version says '$CHROME_V', not ${CHROME_VER%-*}" ;; esac
SUID=$(find /opt/google/chrome -xdev -type f -perm -4000 -printf '%p ' | sed 's/ $//')
echo "CHROME=OK version=\"$CHROME_V\" hold=yes update_source=none setuid=${SUID:-none} stderr_lines=$(wc -l < "$WORK/chrome-version.err")"

echo "=== 4. отчёт"
(umask 077; set -C
{
  echo "ZAVOD_3_5_1B_TIME=$TS"
  echo "ZAVOD_3_5_1B_HOST=$(hostname) arch=$ARCH os=$ID-$VERSION_ID kernel=$(uname -r)"
  echo "ZAVOD_3_5_1B_PACKAGE=commit=$COMMIT manifest_sha256=$MSHA pins_sha256=$(sha256sum "$PINS" | cut -c1-64)"
  for i in 0 1 2; do echo "ZAVOD_3_5_1B_PIN=${NAME[$i]} size=${SIZE[$i]} sha256=${SUM[$i]}"; done
  echo "ZAVOD_3_5_1B_CLAUDE=path=$CLAUDE_DIR/claude version=\"$CLAUDE_V\" inventory_sha256=${INV[0]}"
  echo "ZAVOD_3_5_1B_CODEX=path=$CODEX_BIN version=\"$CODEX_V\" inventory_sha256=${INV[1]}"
  echo "ZAVOD_3_5_1B_CHROME=package=google-chrome-stable=$CHROME_VER version=\"$CHROME_V\" hold=yes update_source=none setuid=${SUID:-none}"
  echo "ZAVOD_3_5_1B_DEFAULTS=$DEF sha256=$(sha256sum "$DEF" | cut -c1-64)"
  echo "ZAVOD_3_5_1B=OK"
} > "$REPORT")
echo "--- отчёт $REPORT (sha256 $(sha256sum "$REPORT" | cut -c1-64)):"
cat "$REPORT"
