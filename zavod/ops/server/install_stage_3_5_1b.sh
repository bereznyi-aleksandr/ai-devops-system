#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/install_stage_3_5_1b.sh
# ВЕРСИЯ: v0.13  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-06 19:25 +02:00 (v0.13: пустые последние поля dpkg-query не теряются — метка END (CI: FIELD conflicts/breaks/replaces у настоящего Chrome); v0.12 от 19:14: разбор полей control — продолжения строк (CI: KeyError на Description); v0.11 от 19:02: аудит ChatGPT STAGE351B R4 — у файлов Chrome сверяются ещё права, владелец и одна ссылка, дерево /opt/google закрыто; управляющая часть пакета (сценарии и поля) равна закреплённому .deb; v0.10: Chrome сверяется по каждому файлу с закреплённым .deb (CI: список сумм dpkg не равен списку .deb); v0.9 от 18:16: apt-get и apt-mark шага не берут замок сами (Debug::NoLocking) — замок уже у шага, найдено CI; v0.8 от 16:48: аудит ChatGPT STAGE351B R3 — замок apt и dpkg на весь шаг, чужие триггеры только из закрытого списка и только у пакетов, установленных до шага (снимок), без dpkg --configure --pending, установленный Chrome сверяется с закреплённым .deb по суммам файлов, у своих файлов одна ссылка; v0.7: аудит ChatGPT STAGE351B R2 — доводка только открытой установки (chrome-apt-open.txt), чужие триггеры только доказанные по .deb плана, dpkg только по названным пакетам, журнал и Unincorp пусты до OK, папка apt без ссылок и чужого; v0.6: незавершённые чужие пакеты только с ждущими триггерами (man-db, fontconfig) допускаются при доводке, если незавершён и пакет плана; v0.5: аудит ChatGPT STAGE351B R1B —
#   M-01 доводка оборванной установки Chrome (только пакеты плана этого шага, dpkg --configure -a и повтор того же
#   .deb); M-02 зависимости Chrome — только из архива Ubuntu (свой список источников и свои папки apt), отказ при
#   адресе dl.google.com в любом источнике системы; L-03 строгий список setuid (только chrome-sandbox 4755) и запуск
#   только внутри сессии SSH; Claude, сессия dd193696-ae30-4678-972a-0a8a66fe36cc; v0.4 от 12:59: поля .deb Chrome — по одному, CI arm64; повтор принимает состояние hold; v0.3: версия программ — только из stdout, CI arm64: codex пишет предупреждение о /tmp; v0.2: поля закреплённых строк — шаблонами case вместо [[ =~ ]], сканер И.7а)
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
#      dpkg --verify, проба --version от nobody; файлы с битом setuid или setgid — ровно один chrome-sandbox 4755;
#      зависимости — только из архива Ubuntu (свой список источников $EVD/apt, источники системы не читаются);
#      оборванная прежним запуском установка доводится до конца (только пакеты плана $EVD/chrome-apt-plan-*.txt);
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
# Только внутри сессии SSH на сервере (аудит L-351B-R1B-03): в окне телефона (Termux) шаг не идёт.
[ -n "${SSH_CONNECTION:-}" ] || die "run only inside an SSH root session on the server: nothing changed"
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
APTD=$EVD/apt
for p in "$EVD" "$DL" "$APTD"; do
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
# Аудит M-351B-R1B-02: канал обновлений Google под ЛЮБЫМ именем файла — строка (кроме примечаний) с адресом
# dl.google.com в любом файле источников, который читает apt; ссылка в никуда — тоже отказ.
src_google() {
  local f
  for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
    if [ ! -e "$f" ]; then
      if [ -L "$f" ]; then echo "$f"; fi
      continue
    fi
    if grep -v '^[[:space:]]*#' "$f" | grep -Eqi 'dl(-ssl)?\.google\.com'; then echo "$f"; fi
  done
}
G=$(src_google)
[ -z "$G" ] || die "APT source $(echo $G) points to dl.google.com or cannot be read (Google update source): nothing changed"
[ -f /usr/share/keyrings/ubuntu-archive-keyring.gpg ] || die "Ubuntu archive key /usr/share/keyrings/ubuntu-archive-keyring.gpg is missing: nothing changed"
# Аудит M-351B-R2-03: своя папка apt — без ссылок и чужого: всё принадлежит root, папки и файлы без записи группе и
# другим, только папки и обычные файлы, наверху — только свои имена. Проверка — до любой записи в неё (здесь и в
# apt_ready); писать внутрь root-папки 0700 может только root.
apt_tree_bad() {
  [ -e "$APTD" ] || [ -L "$APTD" ] || return 0
  find "$APTD" -mindepth 1 \( -type l -o ! -user root -o ! -group root -o \( ! -type d ! -type f \) -o -perm /022 \) -print | head -n 5
  find "$APTD" -mindepth 1 -maxdepth 1 ! -name sources ! -name prefs ! -name lists ! -name cache ! -name none.list ! -name none.pref -print | head -n 5
}
B=$(apt_tree_bad)
[ -z "$B" ] || die "$APTD has a link, a foreign owner or a foreign entry ($(echo $B | cut -c1-300)): nothing changed"
# Аудит M-351B-R1B-01, M-351B-R2-01, M-351B-R2-02: незавершённая работа dpkg (оборванная установка).
# Доводится только ОТКРЫТАЯ установка этого шага: файл $EVD/chrome-apt-open.txt (root 0600) перечисляет планы этой
# установки (каждый пишется до apt-get install) и закрывается (переименование в chrome-apt-closed-*) только после
# всех проверок шага 3; прежние закрытые планы разрешением не служат. Допускается только:
#  (1) незавершённый пакет из этих планов в той же версии;
#  (2) чужой пакет в triggers-pending (установлен, ждёт обработки триггера — например, указатель man-db), если КАЖДЫЙ
#      его ждущий триггер вызван пакетами плана: путь триггера — файл или папка из самих .deb плана (закреплённый
#      Chrome и пакеты Ubuntu в $APTD/cache/archives) или имя из их списка триггеров, пара «пакет триггер» есть в
#      закрытом списке TRIG_OK, а пакет до шага был установлен в той же версии (снимок chrome-apt-before-*);
#  (3) так же — каждый ещё не учтённый dpkg триггер (/var/lib/dpkg/triggers/Unincorp);
#  (4) запись журнала dpkg (/var/lib/dpkg/updates) только о пакетах (1) и (2).
# Всё прочее — отказ, ничего не изменено. Первая установка начинается только при чистом dpkg (ничего из этого нет),
# значит, чужих ждущих триггеров до шага не было.
# Аудит M-351B-R3-02: весь шаг держит замок apt и dpkg (/var/lib/dpkg/lock-frontend): другая установка (например,
# автообновление) не может менять пакеты между проверкой и доводкой; apt-get и dpkg этого шага работают под этим
# замком: apt-get и apt-mark его не берут сами (Debug::NoLocking — замок уже у шага), dpkg — тоже (DPKG_FRONTEND_LOCKED).
# Замок занят — отказ до изменений. Замок снимается, когда шаг закончился.
coproc LOCKER { exec python3 -I -c 'import fcntl, os, sys, time
p = int(sys.argv[1])
f = os.open("/var/lib/dpkg/lock-frontend", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o640)
try:
    fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    print("BUSY", flush=True)
    sys.exit(1)
print("LOCKED", flush=True)
while os.getppid() == p:
    time.sleep(0.5)' "$$"; }
LK=
read -r -t 60 LK <&"${LOCKER[0]}" || true
[ "$LK" = LOCKED ] || die "another apt or dpkg run holds /var/lib/dpkg/lock-frontend: nothing changed, repeat the command later"
export DPKG_FRONTEND_LOCKED=1
OPEN=$EVD/chrome-apt-open.txt
UNINC=/var/lib/dpkg/triggers/Unincorp
# Аудит M-351B-R3-04: свой файл — обычный, не ссылка, владелец и права ровно такие и ровно одно имя (жёсткой ссылки
# на чужой файл нет).
file_is() { [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%U:%G %a %h' "$1")" = "$2 1" ]; }
# Аудит M-351B-R3-01: чужой ждущий триггер допускается только из этого закрытого списка «пакет триггер» (обычные
# указатели Ubuntu, которые трогают зависимости Chrome) — и только если его вызвали .deb плана (trig_proven), а пакет
# был установлен в той же версии до шага (снимок chrome-apt-before-*). Широкие и прочие триггеры — отказ.
TRIG_OK='man-db /usr/share/man
fontconfig /usr/share/fonts
libc-bin ldconfig
desktop-file-utils /usr/share/applications
shared-mime-info /usr/share/mime/packages
mailcap /usr/lib/mime/packages
gtk-update-icon-cache /usr/share/icons/hicolor
hicolor-icon-theme /usr/share/icons/hicolor'
trig_listed() { printf '%s\n' "$TRIG_OK" | awk -v n="$1" -v t="$2" '(n == "-" || $1 == n) && $2 == t { f = 1 } END { exit !f }'; }
before_ok() { printf '%s\n' "$BEFORE" | awk -v n="$1" -v v="$2" '$1 == n && $2 == v && ($3 == "install" || $3 == "hold") && $4 == "ok" && $5 == "installed" { f = 1 } END { exit !f }'; }
dpkg_journal() { find /var/lib/dpkg/updates -mindepth 1 -maxdepth 1 | wc -l; }
# Доказательная база: «F путь» — файлы и папки из .deb плана, «T имя» — триггеры, которые они вызывают.
plan_proof() {
  local d pv
  for d in "$DL/${NAME[2]}" "$APTD"/cache/archives/*.deb; do
    { [ -f "$d" ] && [ ! -L "$d" ]; } || continue
    if [ "$d" = "$DL/${NAME[2]}" ]; then echo "${SUM[2]}  $d" | sha256sum -c --strict --status - || continue; fi
    pv=$(dpkg-deb --field "$d" Package Version 2> /dev/null | sed 's/^[A-Za-z]*: //' | tr '\n' ' ' | sed 's/ $//') || continue
    printf '%s\n' "$ALLOWED" | grep -qxF "$pv" || continue
    dpkg-deb --contents "$d" | awk '{ for (i = 1; i <= 5; i++) $i = ""; sub(/^ +/, ""); sub(/ -> .*/, ""); sub(/^\./, ""); sub(/\/$/, ""); print "F " $0 }'
    dpkg-deb --info "$d" triggers 2> /dev/null | awk '$1 ~ /^activate/ { print "T " $2 }' || true
  done
}
trig_proven() {
  printf '%s\n' "$PROOF" | awk -v t="$1" '($1 == "T" && $2 == t) || ($1 == "F" && substr(t, 1, 1) == "/" && (substr($0, 3) == t || index(substr($0, 3), t "/") == 1)) { f = 1; exit } END { exit !f }'
}
unfinished() {
  # Строка: желание, флаг ошибки (ok или reinstreq), состояние, имя, версия; пробелов внутри полей не бывает.
  # Вывод: «имя версия состояние» (у reinstreq состояние с приставкой reinstreq-).
  dpkg-query -W -f='${Status} ${binary:Package} ${Version}\n' \
    | awk '($3 ~ /^(half-installed|unpacked|half-configured|triggers-awaited|triggers-pending)$/ || $2 != "ok") { p = $4; sub(/:.*/, "", p); s = $3; if ($2 != "ok") s = $2 "-" $3; print p " " $5 " " s }' \
    | sort -u
}
UNFIN=$(unfinished)
JOURNAL=$(dpkg_journal)
UTRIG=
if [ -s "$UNINC" ]; then UTRIG=$(awk 'NF { print $1 }' "$UNINC" | sort -u); fi
RESUME='' OURS_PK=() TRIG_PK=()
if [ -n "$UNFIN" ] || [ "$JOURNAL" != 0 ] || [ -n "$UTRIG" ]; then
  PLANS=()
  if [ -e "$OPEN" ] || [ -L "$OPEN" ]; then
    file_is "$OPEN" 'root:root 600' || die "$OPEN is not a root 0600 file with one link: nothing changed"
    BEFS=()
    while read -r p; do
      { printf '%s\n' "$p" | grep -qxE 'chrome-apt-plan-[0-9]{8}T[0-9]{6}[.][0-9]+Z-[0-9]+[.]txt' && file_is "$EVD/$p" 'root:root 600' \
          && file_is "$EVD/${p/-plan-/-before-}" 'root:root 600'; } \
        || die "$OPEN names a plan that is not a root 0600 plan file of this step with its snapshot ($(echo "$p" | cut -c1-100)): nothing changed"
      PLANS+=("$EVD/$p")
      BEFS+=("$EVD/${p/-plan-/-before-}")
    done < "$OPEN"
  fi
  [ "${#PLANS[@]}" != 0 ] || die "dpkg has unfinished work not started by this step (packages: $(echo $UNFIN | cut -c1-300); journal entries: $JOURNAL; triggers not yet noted: $(echo $UTRIG | cut -c1-200)): nothing changed"
  ALLOWED=$(cat "${PLANS[@]}" | sort -u)
  BEFORE=$(cat "${BEFS[@]}")
  PROOF=$(plan_proof)
  BAD=
  while read -r n v s; do
    [ -n "$n" ] || continue
    if printf '%s\n' "$ALLOWED" | grep -qxF "$n $v"; then OURS_PK+=("$n"); continue; fi
    if [ "$s" != triggers-pending ]; then BAD="$BAD $n $v ($s)"; continue; fi
    TP=$(dpkg-query -W -f='${Triggers-Pending}' "$n" 2> /dev/null || true)
    if [ -z "$TP" ]; then BAD="$BAD $n $v ($s)"; continue; fi
    for t in $TP; do
      if ! trig_proven "$t"; then BAD="$BAD $n $v (trigger $t)"
      elif ! trig_listed "$n" "$t"; then BAD="$BAD $n $v (trigger $t not on the allowed list)"; fi
    done
    before_ok "$n" "$v" || BAD="$BAD $n $v (not installed in this version before the step)"
    TRIG_PK+=("$n")
  done <<< "$UNFIN"
  for t in $UTRIG; do
    if ! trig_proven "$t"; then BAD="$BAD not noted (trigger $t)"
    elif ! trig_listed - "$t"; then BAD="$BAD not noted (trigger $t not on the allowed list)"; fi
  done
  JPV=
  if [ "$JOURNAL" != 0 ]; then
    JPV=$(for jf in /var/lib/dpkg/updates/*; do if [ -f "$jf" ] && [ ! -L "$jf" ]; then cat "$jf"; fi; done \
      | awk 'BEGIN { RS = ""; FS = "\n" } { p = v = "-"; for (i = 1; i <= NF; i++) { if ($i ~ /^Package: /) p = substr($i, 10); if ($i ~ /^Version: /) v = substr($i, 10) } print p " " v }' | sort -u)
  fi
  while read -r n v; do
    [ -n "$n" ] || continue
    if printf '%s\n' "$ALLOWED" | grep -qxF "$n $v"; then continue; fi
    case " ${TRIG_PK[*]} " in *" $n "*) ;; *) BAD="$BAD $n $v (journal)" ;; esac
  done <<< "$JPV"
  [ -z "$BAD" ] || die "dpkg has unfinished work that is not this step's (not in its open plan, or a trigger its packages did not cause):$(echo "$BAD" | cut -c1-300): nothing changed"
  RESUME=yes
fi
CHROME_NOW=$(dpkg-query -W -f='${Status} ${Version}' google-chrome-stable 2>/dev/null || true)
case "$CHROME_NOW" in
  ''|'unknown ok not-installed '*|'deinstall ok config-files '*) CHROME_NOW= ;;
  "install ok installed $CHROME_VER"|"hold ok installed $CHROME_VER") ;;  # hold — после прежнего запуска
  *) { [ -n "$RESUME" ] && [ "${CHROME_NOW##* }" = "$CHROME_VER" ]; } \
       || die "google-chrome-stable is already in another state ($CHROME_NOW), not $CHROME_VER: nothing changed" ;;
esac
OURS_L=$(echo "${OURS_PK[*]}" | tr ' ' ','); TRIG_L=$(echo "${TRIG_PK[*]}" | tr ' ' ',')
echo "DPKG_UNFINISHED=$(printf '%s\n' "$UNFIN" | sed '/^$/d' | wc -l) journal=$JOURNAL not_noted=$(echo $UTRIG | wc -w) plan=${OURS_L:--} foreign_triggers=${TRIG_L:--} resume=${RESUME:-no}"
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
# По одному полю: при нескольких полях dpkg-deb -f печатает их с именами («Package: …»).
[ "$(dpkg-deb -f "$DEB" Package)/$(dpkg-deb -f "$DEB" Version)/$(dpkg-deb -f "$DEB" Architecture)" = "google-chrome-stable/$CHROME_VER/arm64" ] \
  || die "${NAME[2]} control fields are not google-chrome-stable $CHROME_VER arm64"
if [ ! -e "$DEF" ]; then
  (umask 022; set -C; printf '%s\n' "$want_def" > "$DEF")
fi
[ "$(cat "$DEF")" = "$want_def" ] || die "$DEF differs after writing"
# Аудит M-351B-R1B-02: свой список источников apt — только архив Ubuntu для Arm64 с ключом Ubuntu, свои папки списков
# и кэша в хранилище шага. Источники системы (/etc/apt/sources.list*), её настройки приоритетов и списки пакетов
# этот шаг не читает и не меняет; зависимость Chrome не может прийти из чужого источника.
want_src='Types: deb
URIs: http://ports.ubuntu.com/ubuntu-ports
Suites: noble noble-updates noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg'
APTO=(-o "Dir::Etc::SourceList=$APTD/none.list" -o "Dir::Etc::SourceParts=$APTD/sources" -o "Dir::Etc::Preferences=$APTD/none.pref"
      -o "Dir::Etc::PreferencesParts=$APTD/prefs" -o "Dir::State::Lists=$APTD/lists" -o "Dir::Cache=$APTD/cache" -o APT::Sandbox::User=root
      -o Debug::NoLocking=true)
apt_ready() {
  local d
  B=$(apt_tree_bad)
  [ -z "$B" ] || die "$APTD has a link, a foreign owner or a foreign entry ($(echo $B | cut -c1-300)): nothing installed"
  for d in "$APTD" "$APTD/sources" "$APTD/prefs" "$APTD/lists" "$APTD/lists/partial" "$APTD/cache" "$APTD/cache/archives" "$APTD/cache/archives/partial"; do
    if [ ! -d "$d" ]; then install -d -o root -g root -m 0700 "$d"; fi
  done
  if [ ! -e "$APTD/none.list" ]; then install -o root -g root -m 0600 /dev/null "$APTD/none.list"; fi
  if [ ! -e "$APTD/none.pref" ]; then install -o root -g root -m 0600 /dev/null "$APTD/none.pref"; fi
  if [ ! -e "$APTD/sources/ubuntu.sources" ]; then (umask 077; set -C; printf '%s\n' "$want_src" > "$APTD/sources/ubuntu.sources"); fi
  { [ "$(cat "$APTD/sources/ubuntu.sources")" = "$want_src" ] && [ ! -s "$APTD/none.list" ] && [ ! -s "$APTD/none.pref" ] \
    && [ -z "$(find "$APTD/prefs" -mindepth 1)" ] && [ "$(find "$APTD/sources" -mindepth 1)" = "$APTD/sources/ubuntu.sources" ]; } \
    || die "$APTD differs from what this step writes: nothing installed"
  apt-get "${APTO[@]}" update -qq > "$WORK/apt-update.out" 2>&1 \
    || { tail -n 30 "$WORK/apt-update.out" >&2; die "apt-get update (Ubuntu archive only) failed: nothing installed"; }
}
# План (пробный прогон apt-get -s): ничего не удаляется, другие установленные пакеты не меняются, ставится ровно
# google-chrome-stable закреплённой версии; план пишется в НОВЫЙ файл до установки — по нему доводится обрыв.
chrome_plan() {
  apt-get "${APTO[@]}" -s install --no-install-recommends "$DEB" > "$WORK/apt-plan.out" 2>&1 \
    || { tail -n 30 "$WORK/apt-plan.out" >&2; die "apt-get could not plan the Chrome install: nothing installed"; }
  if grep -q '^Remv ' "$WORK/apt-plan.out"; then
    die "installing Chrome would remove packages ($(grep '^Remv ' "$WORK/apt-plan.out" | cut -d' ' -f2 | tr '\n' ' ')): nothing installed"
  fi
  UPG=$(sed -n 's/^Inst \([^ ]*\) \[.*/\1/p' "$WORK/apt-plan.out" | grep -vx google-chrome-stable || true)
  [ -z "$UPG" ] || die "installing Chrome would change other installed packages ($(echo $UPG | cut -c1-300)): nothing installed"
  PLAN=$(sed -n 's/^Inst \([^ ]*\) \(\[[^]]*\] \)\{0,1\}(\([^ ]*\) .*/\1 \3/p' "$WORK/apt-plan.out" | sed 's/:[a-z0-9]* / /' | sort -u)
  printf '%s\n' "$PLAN" | grep -qx "google-chrome-stable $CHROME_VER" || die "apt plan does not install google-chrome-stable $CHROME_VER: nothing installed"
  (umask 077; set -C; printf '%s\n' "$PLAN" > "$EVD/chrome-apt-plan-$TS.txt")
  # Аудит M-351B-R3-01: снимок пакетов до установки (имя, версия, состояние) — по нему доводка узнаёт пакеты,
  # которые были до шага.
  (umask 077; set -C; dpkg-query -W -f='${Package} ${Version} ${Status}\n' | sort -u > "$EVD/chrome-apt-before-$TS.txt")
  file_is "$EVD/chrome-apt-plan-$TS.txt" 'root:root 600' && file_is "$EVD/chrome-apt-before-$TS.txt" 'root:root 600' \
    || die "plan or snapshot file is not a new root 0600 file: nothing installed"
  # Аудит M-351B-R2-02: план вносится в открытую установку ДО apt-get install; закрытие — после проверок шага 3.
  # Новый открытый файл создаётся только как новый (set -C), перед дописыванием — одна ссылка (M-351B-R3-04).
  if [ ! -e "$OPEN" ] && [ ! -L "$OPEN" ]; then (umask 077; set -C; : > "$OPEN"); fi
  file_is "$OPEN" 'root:root 600' || die "$OPEN is not a root 0600 file with one link: nothing installed"
  (umask 077; printf '%s\n' "chrome-apt-plan-$TS.txt" >> "$OPEN")
  echo "CHROME_APT_PLAN=$EVD/chrome-apt-plan-$TS.txt packages=$(printf '%s\n' "$PLAN" | wc -l) open=$OPEN"
}
chrome_apt() {
  apt_ready
  chrome_plan
  apt-get "${APTO[@]}" install -y -qq --no-install-recommends -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold "$DEB" > "$WORK/apt-chrome.out" 2>&1 \
    || { tail -n 30 "$WORK/apt-chrome.out" >&2; die "apt-get install of ${NAME[2]} failed: repeat the same command to finish it"; }
}
chrome_ok() {
  case "$(dpkg-query -W -f='${Status} ${Version}' google-chrome-stable 2>/dev/null)" in
    "install ok installed $CHROME_VER"|"hold ok installed $CHROME_VER") return 0 ;;
  esac
  return 1
}
if [ -n "$RESUME" ]; then
  # Аудит M-351B-R2-01, M-351B-R3-02: доводка обрыва — только названные пакеты: dpkg --configure пакетов плана (1),
  # dpkg --triggers-only чужих пакетов с доказанными триггерами из списка (2); общей доводки (--configure -a или
  # --pending) нет. Пакет, распакованный не до конца, ставится заново тем же закреплённым .deb. Весь шаг держит замок
  # apt и dpkg. Если после этого журнал dpkg или не учтённые триггеры остались — отказ ниже, сам шаг дальше не идёт.
  rc=0 rt=0
  if [ "${#OURS_PK[@]}" != 0 ]; then dpkg --configure "${OURS_PK[@]}" > "$WORK/dpkg-configure.out" 2>&1 || rc=$?; fi
  if [ "${#TRIG_PK[@]}" != 0 ]; then dpkg --triggers-only "${TRIG_PK[@]}" > "$WORK/dpkg-triggers.out" 2>&1 || rt=$?; fi
  if ! chrome_ok; then chrome_apt; fi
  echo "CHROME_RESUMED=$CHROME_VER (unfinished install finished; dpkg --configure ${OURS_L:--} rc=$rc; dpkg --triggers-only ${TRIG_L:--} rc=$rt)"
elif [ -z "$CHROME_NOW" ]; then
  chrome_apt
  echo "CHROME_INSTALLED=$CHROME_VER"
else
  echo "CHROME_REUSED=$CHROME_VER (already installed, not installed again)"
fi
chrome_ok || die "google-chrome-stable is not $CHROME_VER after install"
LEFT=$(unfinished)
[ -z "$LEFT" ] || die "dpkg still has unfinished packages: $(echo $LEFT | cut -c1-300)"
# Аудит M-351B-R2-02: журнал dpkg пуст и не учтённых триггеров нет — иначе не OK.
J=$(dpkg_journal)
{ [ "$J" = 0 ] && [ ! -s "$UNINC" ]; } || die "dpkg journal ($J entries) or triggers not yet noted remain after the install: nothing more is done"
# Аудит M-351B-R3-03, M-351B-R4-01: установленный google-chrome-stable — именно закреплённый .deb (сумма .deb сверена в
# шаге 1). Сверка идёт с самим .deb, не с базой dpkg (CI: список сумм в базе dpkg не равен списку внутри .deb):
# каждый обычный файл из .deb есть на диске обычным файлом с той же суммой sha256, теми же правами (включая setuid),
# тем же владельцем и одной ссылкой; каждая ссылка — с той же целью и владельцем; каждая папка — папкой (в /opt/google —
# и с теми же правами и владельцем). Дерево /opt/google закрыто: в нём нет ничего, чего нет в .deb (EXTRA). Иначе отказ.
CHF=$(dpkg-deb --fsys-tarfile "$DEB" | python3 -I -c 'import hashlib, os, stat, sys, tarfile
def h(f):
    d = hashlib.sha256()
    for b in iter(lambda: f.read(1048576), b""):
        d.update(b)
    return d.hexdigest()
n = 0
bad = []
names = set()
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as t:
    for m in t:
        q = (m.name[2:] if m.name.startswith("./") else m.name).rstrip("/")
        if q in ("", "."):
            continue
        p = "/" + q
        names.add(p)
        n += 1
        try:
            st = os.lstat(p)
        except OSError:
            bad.append("MISSING " + p)
            continue
        own = st.st_uid == m.uid and st.st_gid == m.gid
        if m.isdir():
            ok = stat.S_ISDIR(st.st_mode)
            if ok and p.startswith("/opt/google"):
                ok = own and stat.S_IMODE(st.st_mode) == (m.mode & 0o7777)
        elif m.issym():
            ok = stat.S_ISLNK(st.st_mode) and own and os.readlink(p) == m.linkname
        elif m.isreg():
            ok = stat.S_ISREG(st.st_mode) and own and st.st_nlink == 1 and stat.S_IMODE(st.st_mode) == (m.mode & 0o7777)
            if ok:
                with open(p, "rb") as g:
                    ok = h(g) == h(t.extractfile(m))
        else:
            ok = False
        if not ok:
            bad.append("MISMATCH " + p)
for r, ds, fs in os.walk("/opt/google"):
    for x in [r] + [os.path.join(r, y) for y in ds + fs]:
        if x not in names:
            bad.append("EXTRA " + x)
for x in bad[:5]:
    print(x)
print("FILES=%d BAD=%d" % (n, len(bad)))' 2> /dev/null || true)
CHF_LAST=$(printf '%s\n' "$CHF" | tail -n 1)
case "$CHF_LAST" in
  FILES=[1-9]*' BAD=0') echo "CHROME_FILES=OK ${CHF_LAST%% *} (each file of ${NAME[2]} is on disk with the same sha256, rights and owner; /opt/google has nothing else)" ;;
  *) die "installed google-chrome-stable is not the pinned ${NAME[2]} (its files differ): nothing more is done ($(printf '%s' "$CHF" | tr '\n' ' ' | cut -c1-300))" ;;
esac
# Аудит M-351B-R4-02: и управляющая часть пакета — та же, что в закреплённом .deb: каждый файл управляющего архива
# (postinst, prerm, postrm, triggers и прочие, кроме control и md5sums: суммы файлов сверены выше) побайтно равен файлу dpkg /var/lib/dpkg/info/
# google-chrome-stable.<имя>; других файлов пакета там нет (кроме list и md5sums, которые пишет сам dpkg); поля
# Package, Version, Architecture и все поля зависимостей в базе dpkg равны полям control из .deb. Иначе отказ.
CF_GOT=$(dpkg-query -W -f='${Package}\n${Version}\n${Architecture}\n${Pre-Depends}\n${Depends}\n${Recommends}\n${Suggests}\n${Provides}\n${Conflicts}\n${Breaks}\n${Replaces}\nEND' google-chrome-stable 2> /dev/null || true)
CTL=$(dpkg-deb --ctrl-tarfile "$DEB" | python3 -I -c 'import os, sys, tarfile
mem = {}
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as t:
    for m in t:
        q = (m.name[2:] if m.name.startswith("./") else m.name).rstrip("/")
        if q in ("", "."):
            continue
        mem[q] = t.extractfile(m).read() if m.isreg() else None
bad = []
D = "/var/lib/dpkg/info/"
pre = "google-chrome-stable."
have = {}
for x in os.listdir(D):
    if x.startswith(pre):
        have[x[len(pre):]] = D + x
    elif x.startswith("google-chrome-stable:"):
        bad.append("EXTRA " + D + x)
for q, b in sorted(mem.items()):
    if q in ("control", "md5sums"):
        continue
    x = have.pop(q, None)
    if b is None or x is None or os.path.islink(x) or not os.path.isfile(x):
        bad.append("CONTROL_FILE " + q)
        continue
    with open(x, "rb") as g:
        if g.read() != b:
            bad.append("CONTROL_FILE " + q)
for q in sorted(have):
    if q not in ("list", "md5sums"):
        bad.append("EXTRA " + have[q])
f = {}
k = None
for line in (mem.get("control") or b"").decode("utf-8", "replace").split("\n"):
    if line[:1] in (" ", "\t") and k:
        f[k] += line
    elif ":" in line:
        k, v = line.split(":", 1)
        k = k.strip().lower()
        f[k] = v
want = ["package", "version", "architecture", "pre-depends", "depends", "recommends", "suggests", "provides",
        "conflicts", "breaks", "replaces"]
got = sys.argv[1].split("\n")
if not got or got[-1] != "END" or len(got) != len(want) + 1:
    got = []
    bad.append("FIELD dpkg-query")
for i, k in enumerate(want):
    g = got[i] if i < len(got) else None
    if g is None or "".join(g.split()) != "".join(f.get(k, "").split()):
        bad.append("FIELD " + k)
for x in bad[:5]:
    print(x)
print("CONTROL_FILES=%d BAD=%d" % (len(mem), len(bad)))' "$CF_GOT" 2> /dev/null || true)
CTL_LAST=$(printf '%s\n' "$CTL" | tail -n 1)
case "$CTL_LAST" in
  CONTROL_FILES=[1-9]*' BAD=0') echo "CHROME_CONTROL=OK ${CTL_LAST%% *} (scripts and fields of the installed package equal ${NAME[2]})" ;;
  *) die "installed google-chrome-stable is not the pinned ${NAME[2]} (its control files or fields differ): nothing more is done ($(printf '%s' "$CTL" | tr '\n' ' ' | cut -c1-300))" ;;
esac
# Повтор ничего не пишет: метка hold ставится, только если её ещё нет.
if ! apt-mark showhold | grep -qx google-chrome-stable; then apt-mark -o Debug::NoLocking=true hold google-chrome-stable > /dev/null; fi
apt-mark showhold | grep -qx google-chrome-stable || die "google-chrome-stable is not on hold"
V=$(dpkg --verify google-chrome-stable 2>&1) || true
[ -z "$V" ] || die "installed Chrome files differ from the package: $V"
for s in /etc/apt/sources.list.d/google-chrome.sources /etc/apt/sources.list.d/google-chrome.list; do
  [ ! -e "$s" ] && [ ! -L "$s" ] || die "Chrome added an update source $s"
done
G=$(src_google)
[ -z "$G" ] || die "Chrome added an update source: $(echo $G)"
python3 -I "$VERIFY" elf "$ARCH" /opt/google/chrome || die "/opt/google/chrome has a program for another processor"
CHROME_V=$(asnobody /usr/bin/google-chrome-stable --version 2> "$WORK/chrome-version.err" | head -n 1) || die "chrome does not run: $(head -c 300 "$WORK/chrome-version.err")"
case "$CHROME_V" in "Google Chrome ${CHROME_VER%-*}"*) ;; *) die "google-chrome-stable --version says '$CHROME_V', not ${CHROME_VER%-*}" ;; esac
# Аудит L-351B-R1B-03: файлы пакета Chrome с битом setuid или setgid — строго один chrome-sandbox 4755 root:root.
SUID=$(dpkg -L google-chrome-stable | while read -r f; do
  if [ -f "$f" ] && [ ! -L "$f" ] && { [ -u "$f" ] || [ -g "$f" ]; }; then echo "$f $(stat -c '%a %U:%G' "$f")"; fi
done)
[ "$SUID" = '/opt/google/chrome/chrome-sandbox 4755 root:root' ] \
  || die "setuid or setgid files of google-chrome-stable are not exactly chrome-sandbox 4755 root:root: $(echo $SUID | cut -c1-300)"
SUID=${SUID%% *}
# Установка этого шага закрыта: открытый файл переименовывается (не удаляется); повтор без открытой установки ничего
# не пишет.
CLOSED=-
if [ -e "$OPEN" ] || [ -L "$OPEN" ]; then
  CLOSED=$EVD/chrome-apt-closed-$TS.txt
  mv -n "$OPEN" "$CLOSED"
  { [ ! -e "$OPEN" ] && file_is "$CLOSED" 'root:root 600'; } || die "could not close $OPEN"
  echo "CHROME_APT_CLOSED=$CLOSED"
fi
echo "CHROME=OK version=\"$CHROME_V\" hold=yes update_source=none setuid=$SUID stderr_lines=$(wc -l < "$WORK/chrome-version.err")"

echo "=== 4. отчёт"
(umask 077; set -C
{
  echo "ZAVOD_3_5_1B_TIME=$TS"
  echo "ZAVOD_3_5_1B_HOST=$(hostname) arch=$ARCH os=$ID-$VERSION_ID kernel=$(uname -r)"
  echo "ZAVOD_3_5_1B_PACKAGE=commit=$COMMIT manifest_sha256=$MSHA pins_sha256=$(sha256sum "$PINS" | cut -c1-64)"
  for i in 0 1 2; do echo "ZAVOD_3_5_1B_PIN=${NAME[$i]} size=${SIZE[$i]} sha256=${SUM[$i]}"; done
  echo "ZAVOD_3_5_1B_CLAUDE=path=$CLAUDE_DIR/claude version=\"$CLAUDE_V\" inventory_sha256=${INV[0]}"
  echo "ZAVOD_3_5_1B_CODEX=path=$CODEX_BIN version=\"$CODEX_V\" inventory_sha256=${INV[1]}"
  echo "ZAVOD_3_5_1B_CHROME=package=google-chrome-stable=$CHROME_VER version=\"$CHROME_V\" hold=yes update_source=none setuid=$SUID"
  echo "ZAVOD_3_5_1B_APT=sources=$APTD/sources/ubuntu.sources sha256=$(sha256sum "$APTD/sources/ubuntu.sources" 2>/dev/null | cut -c1-64) plans=$(find "$EVD" -maxdepth 1 -name 'chrome-apt-plan-*.txt' | wc -l) closed_now=$CLOSED open=none"
  echo "ZAVOD_3_5_1B_DEFAULTS=$DEF sha256=$(sha256sum "$DEF" | cut -c1-64)"
  echo "ZAVOD_3_5_1B=OK"
} > "$REPORT")
echo "--- отчёт $REPORT (sha256 $(sha256sum "$REPORT" | cut -c1-64)):"
cat "$REPORT"
