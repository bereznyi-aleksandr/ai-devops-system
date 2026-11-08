#!/usr/bin/env bash
{ set +x +v; } 2> /dev/null   # трассировка (bash -x, SHELLOPTS, BASH_ENV) показала бы введённый ключ — выключена сразу
# ДОКУМЕНТ: zavod/ops/server/login_3_5_2.sh
# ВЕРСИЯ: v0.5  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-08 21:36 +02:00 (v0.5: аудит ChatGPT STAGE352 R3 —
#   M-R3-01 статус Codex — ВЕСЬ вывод ровно «Logged in using ChatGPT» (лишняя строка до или после — отказ);
#   L-R3-01 проверка родительских процессов — при любой ошибке ps отказ (не «none_found»);
#   v0.4: аудит ChatGPT STAGE352 R2 —
#   M-R2-01 если после переноса вход Codex не подтвердился, codex-home уходит в .rejected-codex-home-* (повтор возможен);
#   L-R2-01 ответ Claude: пробелы убираются только по краям («O K» — FAILED); L-R2-02 статус Codex — строка ровно
#   «Logged in using ChatGPT»; Д3 до входа — отказ, если на сервере есть запись нажатий (pam_tty_audit), программа
#   записи сеанса (tlog) или сеанс идёт внутри script/tlog/asciinema/ttyrec/tmux/screen; L-02 после WORKS оператор
#   повторно набирает имя (claude-work / claude-personal), подтверждая аккаунт, — иначе ключ откладывается;
#   итог каждого переноса (mv -n) проверяется по наличию файла, а не по коду mv;
#   v0.3: аудит ChatGPT STAGE352 R1 —
#   M-04 программы claude и codex сверяются по описи папки (tools_tar_3_5_1b.py inventory, закреплённая сумма шага 3.5.1б,
#   сама tools_tar — по закреплённой SHA-256), весь путь до них — root и без записи для группы и других; M-05 вход Codex —
#   в новой временной папке; успех — только код 0, строка «Logged in…», auth.json root 600; затем перенос без замены;
#   неудача — папка откладывается; L-01 check сверяет папку ключей; L-02 оператор вводит адрес аккаунта (в отчёт);
#   внутренние программы запускаются с чистым окружением (env -i), дампы памяти выключены;
#   v0.2: M-01 успех проверки Claude — только код 0 и ответ ровно OK; M-02 «Not logged in» не принимается; M-03 xtrace;
#   v0.1: ключ сохраняется под именем только после успешной проверки)
# ДАТА СОЗДАНИЯ: 2026-11-08 20:36 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сменщик 03, сессия ae87bcd9)
# НАЗНАЧЕНИЕ: шаг 3.5.2 протокола v4 — разовые входы оператора на сервере zavod-1. Запускает ТОЛЬКО оператор, под root,
#   внутри своей сессии SSH. Агенты значений ключей не видят: программа значение не печатает, не пишет в журналы и не
#   отправляет по сети; печатает только имя, длину и итог проверки.
#   claude claude-work|claude-personal — claude setup-token (вход на телефоне по ссылке; ключ показывается только на
#       экране оператора) → оператор вводит адрес аккаунта и вставляет ключ (ввод не виден) → временный файл root 0400
#       → экран очищается → проверка одной просьбой → только при WORKS перенос без замены в /etc/zavod/secrets/<имя>.
#   check claude-work|claude-personal — та же проверка сохранённого ключа; печатает только WORKS или FAILED.
#   codex — codex login --device-auth (код вводится на телефоне) в новой папке; при успехе она становится
#       /etc/zavod/secrets/codex-home (root 0700, auth.json root 600).
#   Каждый запуск пишет НОВЫЙ отчёт /root/zavod-login-3.5.2-<время>.txt (без значений ключей).
# ВЫЗОВ: bash login_3_5_2.sh claude NAME | check NAME | codex. Коды: 0 — OK; 1 — отказ.
# ОГРАНИЧЕНИЯ: ничего не удаляет и не перезаписывает: файл ключа или codex-home уже есть — отказ (замена — решение
#   оператора, отдельным шагом); неудачный ключ и неудачная папка Codex откладываются (.rejected-*); временные папки
#   HOME остаются в /root (root 0700). Шаг 3.5.1б должен быть пройден.
set -euo pipefail
export LC_ALL=C PATH=/usr/sbin:/usr/bin:/sbin:/bin
umask 077
ulimit -c 0
die() { echo "REFUSED: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root"
[ -n "${SSH_CONNECTION:-}" ] || die "run only inside an SSH root session on the server: nothing changed"
exec 9>> /run/zavod-login-3.5.2.lock
flock -n 9 || die "another login_3_5_2.sh run is in progress: nothing changed"
CMD=${1:-}; NAME=${2:-}
case "$CMD" in
  claude|check) [ $# = 2 ] || die "usage: login_3_5_2.sh $CMD claude-work|claude-personal"
    case "$NAME" in claude-work|claude-personal) ;; *) die "name must be claude-work or claude-personal" ;; esac ;;
  codex) [ $# = 1 ] || die "usage: login_3_5_2.sh codex" ;;
  *) die "usage: login_3_5_2.sh claude NAME | check NAME | codex" ;;
esac
# Закреплено шагом 3.5.1б (коммит e7cdcb866499; суммы описи — из отчёта сервера 2026-11-08 и из CI 42287607225).
TAR_PY=/root/zavod-pkg-e7cdcb866499/zavod/ops/server/tools_tar_3_5_1b.py
TAR_SHA=453a5fa1c20a057d4552d75463f2df68bfccfdab91fe418041e1a7cdcc5f49b7
CLAUDE_DIR=/opt/zavod/tools/claude-code-2.1.318-linux-arm64
CLAUDE_INV=f75013813b7449d63592f1d3d396724cfeebcb4c78969968210e538fb6d1148e
CLAUDE=$CLAUDE_DIR/claude
CODEX_DIR=/opt/zavod/tools/codex-0.166.0-linux-arm64
CODEX_INV=ee29ebdbd518525cb3ab7857fe1cc64d519a9e477b3af87aef891bc3737cab63
CODEX=$CODEX_DIR/vendor/aarch64-unknown-linux-musl/bin/codex
SEC=/etc/zavod/secrets
TERMV=${TERM:-xterm}
case "$TERMV" in *[!A-Za-z0-9._-]*) TERMV=xterm ;; esac
TS=$(date -u +%Y%m%dT%H%M%S.%NZ)-$$
REPORT=/root/zavod-login-3.5.2-$TS.txt
LINES=()
say() { LINES+=("$1"); echo "$1"; }
finish() {
  (set -C; printf '%s\n' "ZAVOD_3_5_2_TIME=$TS" "${LINES[@]}" > "$REPORT")
  echo "--- report $REPORT (sha256 $(sha256sum "$REPORT" | cut -c1-64))"
}

# 0. Проверки до изменений (только чтение).
R=$(find /root -maxdepth 1 -type f -name 'zavod-install-3.5.1b-*.txt' -user root -perm 600 -exec grep -lx ZAVOD_3_5_1B=OK {} + | sort | tail -n 1) || true
[ -n "$R" ] || die "step 3.5.1b is not done (no /root/zavod-install-3.5.1b-*.txt with ZAVOD_3_5_1B=OK): nothing changed"
safe_path() {  # путь без ссылок; он и все папки над ним — владелец root, без записи для группы и других
  local q=$1
  [ -e "$q" ] && [ "$(readlink -f -- "$q")" = "$q" ] || die "$q is missing or goes through a link: nothing changed"
  while :; do
    [ "$(stat -c %u -- "$q")" = 0 ] || die "$q is not owned by root: nothing changed"
    case "$(stat -c %A -- "$q")" in ?????w????|????????w?) die "$q is writable by group or others: nothing changed" ;; esac
    [ "$q" = / ] && break
    q=$(dirname -- "$q")
  done
}
tool_ok() {  # $1 папка программы, $2 закреплённая сумма описи, $3 файл программы
  safe_path "$TAR_PY"
  [ "$(sha256sum < "$TAR_PY" | cut -c1-64)" = "$TAR_SHA" ] || die "$TAR_PY differs from step 3.5.1b: nothing changed"
  safe_path "$1"; safe_path "$3"
  local got
  got=$(python3 -I "$TAR_PY" inventory "$1" | sha256sum | cut -c1-64) || die "$1 failed its inventory check: nothing changed"
  [ "$got" = "$2" ] || die "$1 differs from step 3.5.1b (inventory $got): nothing changed"
  [ -f "$3" ] && [ -x "$3" ] || die "$3 is missing: nothing changed"
}
safe_path /etc/zavod
sec_ok() {  # папка ключей: есть — root:root 0700 без ссылки; нет — создаётся (только если $1 = create)
  if [ -e "$SEC" ] || [ -L "$SEC" ]; then
    [ -d "$SEC" ] && [ ! -L "$SEC" ] && [ "$(stat -c '%U:%G %a' "$SEC")" = "root:root 700" ] \
      || die "$SEC exists but is not a root:root 700 folder: nothing changed"
  elif [ "${1:-}" = create ]; then
    mkdir -m 0700 "$SEC"
  else
    die "$SEC is missing: nothing to check"
  fi
}

no_recorder() {  # до входа: ничего не должно записывать нажатия и экран сеанса (только чтение)
  local p=$$ c f k=0
  command -v ps > /dev/null || die "ps is missing (needed to check the session): nothing changed"
  ! grep -rqs pam_tty_audit /etc/pam.d || die "keystroke recording (pam_tty_audit) is set in /etc/pam.d: nothing changed"
  for f in /usr/bin/tlog-rec-session /usr/bin/tlog-rec /usr/sbin/tlog-rec-session /usr/local/bin/tlog-rec-session; do
    [ ! -e "$f" ] || die "session recorder $f is installed: nothing changed"
  done
  while :; do  # вся цепочка родителей до процесса 1; не удалось прочитать хоть одно звено — отказ
    c=$(ps -o comm= -p "$p") && [ -n "$c" ] || die "cannot read process $p (session check failed): nothing changed"
    case "$c" in script|tlog*|asciinema|ttyrec|termrec|tmux*|screen)
      die "this session runs inside $c (it can keep the screen text): start the command in a plain SSH session; nothing changed" ;;
    esac
    p=$(ps -o ppid= -p "$p") || die "cannot read the parent of process $p (session check failed): nothing changed"
    p=${p//[[:space:]]/}
    case "$p" in ''|*[!0-9]*) die "unexpected parent process id (session check failed): nothing changed" ;; esac
    [ "$p" -gt 1 ] || break
    k=$((k + 1)); [ "$k" -lt 64 ] || die "too many parent processes (session check failed): nothing changed"
  done
  say "ZAVOD_3_5_2_RECORDER=none_found"
}

read_key() {  # чтение ключа без показа, проверка вида, запись в НОВЫЙ временный файл root 0400; путь — в TMPKEY
  local n=$1 v l
  printf 'Paste the key for %s and press Enter (it is not shown): ' "$n" >&2
  IFS= read -rs v || die "no key entered: nothing saved"
  echo >&2
  v=${v%$'\r'}
  case "$v" in sk-ant-oat*) ;; *) v=; die "this is not a Claude key (must begin with sk-ant-oat): nothing saved" ;; esac
  case "$v" in *[!A-Za-z0-9_-]*) v=; die "the key has a space or other unexpected sign: nothing saved" ;; esac
  l=${#v}
  [ "$l" -ge 80 ] && [ "$l" -le 300 ] || { v=; die "key length $l is outside 80..300: nothing saved"; }
  TMPKEY=$(mktemp "$SEC/.new-$n-XXXXXX")
  printf '%s' "$v" > "$TMPKEY"; v=
  chmod 0400 "$TMPKEY"
  KEYLEN=$l
}

check_file() {  # одна короткая просьба с ключом из файла $2 (чистое окружение); ответ не печатается; код 0 — работает
  local n=$1 f=$2 h out rc=0 a
  [ -f "$f" ] && [ ! -L "$f" ] && [ "$(stat -c '%U:%G %a %h' "$f")" = "root:root 400 1" ] \
    || die "$f is missing or not root:root 400: nothing checked"
  h=$(mktemp -d "/root/zavod-check-$n-XXXXXX")
  out=$(cd "$h" && env -i HOME="$h" PATH="$PATH" LANG=C.UTF-8 TERM=dumb CLAUDE_CODE_OAUTH_TOKEN="$(cat "$f")" \
        timeout 300 "$CLAUDE" -p 'Reply with exactly one word: OK' 2> /dev/null) || rc=$?
  # успех — только код 0 и ответ ровно «OK» (пробелы и переводы строки — только по краям, одна точка в конце);
  # «NOT OK», «O K», ошибка — FAILED
  a=${out#"${out%%[![:space:]]*}"}; a=${a%"${a##*[![:space:]]}"}; a=${a%.}
  if [ "$rc" = 0 ] && [ "$a" = OK ]; then out=; a=; say "ZAVOD_3_5_2_CHECK=$n WORKS"; return 0; fi
  say "ZAVOD_3_5_2_CHECK=$n FAILED rc=$rc answer_len=${#out}"; out=; a=; return 1
}

codex_status() {  # $1 — CODEX_HOME; код 0 и ВЕСЬ вывод ровно «Logged in using ChatGPT» (вход по коду устройства)
  local st src=0
  st=$(cd "$1" && env -i HOME="$1" CODEX_HOME="$1" PATH="$PATH" LANG=C.UTF-8 TERM=dumb "$CODEX" login status 2>&1) || src=$?
  CODEX_RC=$src
  [ "$src" = 0 ] && [ "$st" = 'Logged in using ChatGPT' ]   # $(…) убирает только конечные переводы строки
}

case "$CMD" in
  claude)
    tool_ok "$CLAUDE_DIR" "$CLAUDE_INV" "$CLAUDE"; sec_ok create
    [ ! -e "$SEC/$NAME" ] && [ ! -L "$SEC/$NAME" ] || die "$SEC/$NAME already exists: nothing changed"
    no_recorder
    H=$(mktemp -d "/root/zavod-login-$NAME-XXXXXX")
    echo "=== 1. claude setup-token: open the link on the phone and sign in to the account for $NAME."
    echo "       The key is shown on THIS screen only. Copy it (it begins with sk-ant-oat)."
    (cd "$H" && env -i HOME="$H" PATH="$PATH" LANG=C.UTF-8 TERM="$TERMV" "$CLAUDE" setup-token) \
      || die "claude setup-token failed: nothing saved"
    echo "=== 2. which account did you sign in with?"
    IFS= read -r -p "Type the e-mail of that Claude account and press Enter: " ACC || die "no e-mail entered: nothing saved"
    ACC=${ACC%$'\r'}
    case "$ACC" in *[!A-Za-z0-9@._+-]*|*@*@*|@*|*@|"") die "this is not an e-mail address: nothing saved" ;; *@*) ;; *) die "this is not an e-mail address: nothing saved" ;; esac
    echo "=== 3. paste the key"
    read_key "$NAME"
    printf '\033[H\033[2J\033[3J'   # убрать ключ с экрана и из прокрутки терминала
    echo "=== screen cleared (the key is no longer on this screen; clear the phone clipboard yourself)"
    echo "=== 4. check: one short request with the new key (it is saved only if it works)"
    if ! check_file "$NAME" "$TMPKEY"; then
      RJ=$(mktemp -u "$SEC/.rejected-$NAME-XXXXXX"); mv -nT "$TMPKEY" "$RJ"
      say "ZAVOD_3_5_2_NOT_SAVED=$NAME key_did_not_work kept_aside=$RJ"; finish; exit 1
    fi
    echo "=== 5. the key works. It will be saved as $NAME for account $ACC."
    IFS= read -r -p "To confirm the account, type the name $NAME again and press Enter: " CONF || CONF=
    CONF=${CONF%$'\r'}
    if [ "$CONF" != "$NAME" ]; then
      RJ=$(mktemp -u "$SEC/.rejected-$NAME-XXXXXX"); mv -nT "$TMPKEY" "$RJ"
      say "ZAVOD_3_5_2_NOT_SAVED=$NAME operator_did_not_confirm kept_aside=$RJ"; finish; exit 1
    fi
    mv -nT "$TMPKEY" "$SEC/$NAME"
    [ ! -e "$TMPKEY" ] || die "$SEC/$NAME appeared during the run: the key is left in $TMPKEY (root 0400), nothing replaced"
    say "ZAVOD_3_5_2_SAVED=$NAME file=$SEC/$NAME mode=$(stat -c '%U:%G %a' "$SEC/$NAME") len=$KEYLEN account_declared=$ACC confirmed_by_operator=yes"
    say "ZAVOD_3_5_2=OK step=claude name=$NAME"; finish ;;
  check)
    tool_ok "$CLAUDE_DIR" "$CLAUDE_INV" "$CLAUDE"; sec_ok
    check_file "$NAME" "$SEC/$NAME" || { finish; exit 1; }
    say "ZAVOD_3_5_2=OK step=check name=$NAME"; finish ;;
  codex)
    tool_ok "$CODEX_DIR" "$CODEX_INV" "$CODEX"; sec_ok create
    CH=$SEC/codex-home
    [ ! -e "$CH" ] && [ ! -L "$CH" ] || die "$CH already exists (Codex was signed in before): nothing changed"
    no_recorder
    C=$(mktemp -d "$SEC/.new-codex-home-XXXXXX")
    reject() { local RJ; RJ=$(mktemp -u "$SEC/.rejected-codex-home-XXXXXX"); mv -nT "$C" "$RJ"
      say "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN $1 kept_aside=$RJ"; finish; exit 1; }
    echo "=== 1. codex login --device-auth: open the link on the phone and enter the code shown here."
    (cd "$C" && env -i HOME="$C" CODEX_HOME="$C" PATH="$PATH" LANG=C.UTF-8 TERM="$TERMV" "$CODEX" login --device-auth) \
      || reject "login_rc=$?"
    codex_status "$C" || reject "status_rc=$CODEX_RC"
    A=$C/auth.json
    [ -f "$A" ] && [ ! -L "$A" ] && [ "$(stat -c '%u %h' "$A")" = "0 1" ] || reject "auth.json_missing_or_not_root"
    chmod 0600 "$A"; chmod -R go-rwx "$C"
    [ "$(stat -c '%U:%G %a' "$A")" = "root:root 600" ] || reject "auth.json_mode"
    mv -nT "$C" "$CH"
    [ ! -e "$C" ] || die "$CH appeared during the run: the new login is left in $C, nothing replaced"
    if ! codex_status "$CH"; then  # после переноса вход не подтвердился — папка уходит в сторону, повтор возможен
      RJ=$(mktemp -u "$SEC/.rejected-codex-home-XXXXXX")
      mv -nT "$CH" "$RJ" || true
      if [ ! -e "$CH" ] && [ -d "$RJ" ]; then say "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN_AFTER_MOVE rc=$CODEX_RC kept_aside=$RJ"
      else say "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN_AFTER_MOVE rc=$CODEX_RC home=$CH could_not_move_aside"; fi
      finish; exit 1
    fi
    say "ZAVOD_3_5_2_CODEX=LOGGED_IN home=$CH home_mode=$(stat -c '%U:%G %a' "$CH") auth_mode=$(stat -c '%U:%G %a' "$CH/auth.json")"
    say "ZAVOD_3_5_2=OK step=codex"; finish ;;
esac
