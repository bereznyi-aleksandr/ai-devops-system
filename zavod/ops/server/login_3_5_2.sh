#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/login_3_5_2.sh
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  (ключ сохраняется под именем только после успешной проверки)
# ДАТА СОЗДАНИЯ: 2026-11-08 20:36 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сменщик 03, сессия ae87bcd9)
# НАЗНАЧЕНИЕ: шаг 3.5.2 протокола v4 — разовые входы оператора на сервере zavod-1. Запускает ТОЛЬКО оператор, под root,
#   внутри своей сессии SSH. Агенты значений ключей не видят: программа значение не печатает, не пишет в журналы и не
#   отправляет по сети; печатает только имя, длину и итог проверки.
#   claude claude-work|claude-personal — claude setup-token (вход на телефоне по ссылке; ключ показывается только на
#       экране оператора) → оператор вставляет ключ (ввод не виден) → НОВЫЙ файл /etc/zavod/secrets/<имя>
#       (root, 0400; папка root 0700) → экран очищается → проверка check.
#   check claude-work|claude-personal — одна короткая просьба к Claude с этим ключом; печатает только WORKS или FAILED.
#   codex — codex login --device-auth (код вводится на телефоне) в CODEX_HOME=/etc/zavod/secrets/codex-home (root 0700);
#       затем codex login status; печатает только «Logged in» или отказ.
#   Каждый запуск пишет НОВЫЙ отчёт /root/zavod-login-3.5.2-<время>.txt (без значений ключей).
# ВЫЗОВ: bash login_3_5_2.sh claude NAME | check NAME | codex. Коды: 0 — OK; 1 — отказ.
# ОГРАНИЧЕНИЯ: ничего не удаляет и не перезаписывает: файл ключа с тем же именем — отказ (замена ключа — решение
#   оператора, отдельным шагом); временные папки HOME входа остаются в /root (root 0700). Шаг 3.5.1б должен быть пройден.
set -euo pipefail
export LC_ALL=C
umask 077
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
CLAUDE=/opt/zavod/tools/claude-code-2.1.318-linux-arm64/claude
CODEX=/opt/zavod/tools/codex-0.166.0-linux-arm64/vendor/aarch64-unknown-linux-musl/bin/codex
SEC=/etc/zavod/secrets
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
tool_ok() {  # обычный файл root, без ссылок на пути, запуск только для root и группы
  [ -f "$1" ] && [ -x "$1" ] && [ "$(readlink -f "$1")" = "$1" ] && [ "$(stat -c %U "$1")" = root ] \
    || die "program $1 is missing or not as installed by step 3.5.1b: nothing changed"
}
[ -d /etc/zavod ] && [ ! -L /etc/zavod ] && [ "$(stat -c %U:%G /etc/zavod)" = root:root ] \
  || die "/etc/zavod is missing or not root:root (step 3.5.1 not done): nothing changed"
closed_dir() {  # папка root:root 0700 без ссылки; нет — создаётся
  if [ -e "$1" ] || [ -L "$1" ]; then
    [ -d "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%U:%G %a' "$1")" = "root:root 700" ] \
      || die "$1 exists but is not a root:root 700 folder: nothing changed"
  else
    mkdir -m 0700 "$1"
  fi
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

check_file() {  # одна короткая просьба с ключом из файла $2; ответ не печатается; код 0 — работает
  local n=$1 f=$2 h out rc=0
  [ -f "$f" ] && [ ! -L "$f" ] && [ "$(stat -c '%U:%G %a' "$f")" = "root:root 400" ] \
    || die "$f is missing or not root:root 400: nothing checked"
  h=$(mktemp -d "/root/zavod-check-$n-XXXXXX")
  out=$(cd "$h" && HOME=$h CLAUDE_CODE_OAUTH_TOKEN=$(cat "$f") timeout 300 "$CLAUDE" -p 'Reply with exactly one word: OK' 2>/dev/null) || rc=$?
  case "$out" in
    *OK*) out=; say "ZAVOD_3_5_2_CHECK=$n WORKS"; return 0 ;;
    *) say "ZAVOD_3_5_2_CHECK=$n FAILED rc=$rc answer_len=${#out}"; out=; return 1 ;;
  esac
}

case "$CMD" in
  claude)
    tool_ok "$CLAUDE"; closed_dir "$SEC"
    [ ! -e "$SEC/$NAME" ] && [ ! -L "$SEC/$NAME" ] || die "$SEC/$NAME already exists: nothing changed"
    H=$(mktemp -d "/root/zavod-login-$NAME-XXXXXX")
    echo "=== 1. claude setup-token: open the link on the phone and sign in to the account for $NAME."
    echo "       The key is shown on THIS screen only. Copy it (it begins with sk-ant-oat)."
    (cd "$H" && HOME=$H "$CLAUDE" setup-token) || die "claude setup-token failed: nothing saved"
    echo "=== 2. paste the key"
    read_key "$NAME"
    printf '\033[H\033[2J\033[3J'   # убрать ключ с экрана и из прокрутки терминала
    echo "=== screen cleared (the key is no longer on the screen)"
    echo "=== 3. check: one short request with the new key (it is saved only if it works)"
    if ! check_file "$NAME" "$TMPKEY"; then
      RJ=$(mktemp -u "$SEC/.rejected-$NAME-XXXXXX"); mv -nT "$TMPKEY" "$RJ"
      say "ZAVOD_3_5_2_NOT_SAVED=$NAME key_did_not_work kept_aside=$RJ"; finish; exit 1
    fi
    mv -nT "$TMPKEY" "$SEC/$NAME"
    [ ! -e "$TMPKEY" ] || die "$SEC/$NAME appeared during the run: the key is left in $TMPKEY (root 0400), nothing replaced"
    say "ZAVOD_3_5_2_SAVED=$NAME file=$SEC/$NAME mode=$(stat -c '%U:%G %a' "$SEC/$NAME") len=$KEYLEN"
    say "ZAVOD_3_5_2=OK step=claude name=$NAME"; finish ;;
  check)
    tool_ok "$CLAUDE"
    check_file "$NAME" "$SEC/$NAME" || { finish; exit 1; }
    say "ZAVOD_3_5_2=OK step=check name=$NAME"; finish ;;
  codex)
    tool_ok "$CODEX"; closed_dir "$SEC"
    CH=$SEC/codex-home
    if [ -e "$CH/auth.json" ] || [ -L "$CH/auth.json" ]; then die "Codex is already signed in ($CH/auth.json exists): nothing changed"; fi
    closed_dir "$CH"
    echo "=== 1. codex login --device-auth: open the link on the phone and enter the code shown here."
    (cd "$CH" && CODEX_HOME=$CH "$CODEX" login --device-auth) || die "codex login failed"
    st=$(cd "$CH" && CODEX_HOME=$CH "$CODEX" login status 2>&1) || true
    case "$st" in *"Logged in"*) ;; *) say "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN"; finish; exit 1 ;; esac
    [ -f "$CH/auth.json" ] && [ ! -L "$CH/auth.json" ] || die "codex says logged in but $CH/auth.json is missing"
    chmod go-rwx "$CH/auth.json"
    say "ZAVOD_3_5_2_CODEX=LOGGED_IN home=$CH auth_mode=$(stat -c '%U:%G %a' "$CH/auth.json")"
    say "ZAVOD_3_5_2=OK step=codex"; finish ;;
esac
