#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/cell/install_cell.sh
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 13:47 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 15:33 +02:00 (v0.2: карантин и приём
#   архива — папки /var/lib/zavod/intake, zavod_intake.py, zquarantine@ и zimport@; карта 3.3.9)
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: установщик ячейки Завода на Ubuntu 24.04 (карта 3.3.8, протокол v3.1 Л.16–Л.28, И.12–И.12б):
#   (1) учётные записи служб без входа и без прав администратора; (2) папки с правами; (3) клетка zagent@ и
#   группа zagent.slice; (4) zagent-start с папками запросов 1730 root:zkernel; (5) вход root → роль базы
#   zstarter (peer, сопоставление zavod_cell); (6) карантин и доверенный приём архива (И.12г, И.12д).
#   Повторный запуск даёт тот же результат.
# ВЫЗОВ: sudo bash install_cell.sh [--pg-conf-dir /etc/postgresql/16/main | --no-pg]
# ОГРАНИЧЕНИЯ: ничего не удаляет; прежние pg_hba.conf и pg_ident.conf сохраняются копией рядом. Функции базы
#   (db/06_zavod_ext_04.sql) ставятся цепочкой базы, не этим файлом. Пароли и ключи не нужны и не пишутся.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ACCOUNTS=(zdb zkernel zgate zgithub ztelegram zquarantine zimport zbackup zbrowser)
ADMIN_GROUPS=(sudo adm wheel admin root lxd docker systemd-journal)
PG_CONF=''
NO_PG=0
while [ $# -gt 0 ]; do
  case "$1" in
    --pg-conf-dir) PG_CONF=$2; shift 2 ;;
    --no-pg) NO_PG=1; shift ;;
    *) echo "REFUSED: unknown argument $1" >&2; exit 2 ;;
  esac
done
die() { echo "REFUSED: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root"
[ "$(stat -c '%U:%a' /etc/systemd/system)" = root:755 ] || die "/etc/systemd/system must be root 755"

echo "=== 3.3.8.1 учётные записи"
for a in "${ACCOUNTS[@]}"; do
  if id "$a" >/dev/null 2>&1; then
    sh=$(getent passwd "$a" | cut -d: -f7)
    [ "$sh" = /usr/sbin/nologin ] || die "$a exists with shell $sh"
  else
    useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$a"
  fi
  for g in $(id -nG "$a"); do
    for bad in "${ADMIN_GROUPS[@]}"; do [ "$g" != "$bad" ] || die "$a is in admin group $g"; done
  done
  [ "$(id -u "$a")" != 0 ] || die "$a has uid 0"
  passwd -S "$a" | awk '{print $2}' | grep -qE '^(L|LK|NP)$' || die "$a has a usable password"
  echo "ACCOUNT $a uid=$(id -u "$a") groups=$(id -nG "$a") shell=nologin"
done

echo "=== 3.3.8.2 папки"
dir() { # путь владелец группа режим
  install -d -o "$2" -g "$3" -m "$4" "$1"
  chown "$2:$3" "$1"; chmod "$4" "$1"
  echo "DIR $1 $(stat -c '%U:%G %a' "$1")"
}
dir /etc/zavod root root 0755
if [ -d /var/lib/zavod ]; then
  [ "$(stat -c '%U' /var/lib/zavod)" = root ] || die "/var/lib/zavod not owned by root"
  case "$(stat -c '%a' /var/lib/zavod)" in *[2367]) die "/var/lib/zavod is writable by others";; esac
  echo "DIR /var/lib/zavod $(stat -c '%U:%G %a' /var/lib/zavod) (оставлена как есть)"
else
  dir /var/lib/zavod root root 0755
fi
dir /var/lib/zavod/start-archive root root 0700
dir /var/lib/zavod/start-rejected root root 0700
dir /var/lib/zavod/start-state root root 0700
dir /usr/local/lib/zavod root root 0755

echo "=== 3.3.8.3–3.3.8.4 программы, клетка, папки запросов"
install -o root -g root -m 0755 "$HERE/zagent-start" "$HERE/zagent-session" /usr/local/lib/zavod/
for u in zagent@.service zagent.slice zagent-start.service zagent-start.path zagent-start.timer; do
  install -o root -g root -m 0644 "$HERE/$u" "/etc/systemd/system/$u"
done
install -o root -g root -m 0644 "$HERE/zavod-cell.tmpfiles.conf" /etc/tmpfiles.d/zavod-cell.conf
systemd-tmpfiles --create /etc/tmpfiles.d/zavod-cell.conf
for d in start stop; do
  [ "$(stat -c '%U:%G %a' /run/zavod/$d)" = "root:zkernel 1730" ] || die "/run/zavod/$d rights"
done
echo "DIR /run/zavod/start $(stat -c '%U:%G %a' /run/zavod/start)"
echo "DIR /run/zavod/stop $(stat -c '%U:%G %a' /run/zavod/stop)"

echo "=== 3.3.9 карантин и приём архива (И.12г, И.12д)"
# Опись пишет ядро (zkernel), читают все: она не тайна, важна её целостность. Архив кладёт привратник (zgate),
# карантин только читает. out/ — карантин пишет, приём читает по группе. accepted/ — приём пишет, zgithub читает.
dir /var/lib/zavod/intake root root 0755
dir /var/lib/zavod/intake/manifest zkernel zkernel 0755
dir /var/lib/zavod/intake/in zgate zquarantine 2750
dir /var/lib/zavod/intake/out zquarantine zimport 2750
dir /var/lib/zavod/intake/accepted zimport zgithub 2750
dir /var/lib/zavod/intake/accepted/.staging zimport zgithub 2700
dir /var/lib/zavod/intake/journal root root 0755
dir /var/lib/zavod/intake/journal/quarantine zquarantine zquarantine 0750
dir /var/lib/zavod/intake/journal/import zimport zimport 0750
dir /var/lib/zavod/intake/archive root root 0700
install -o root -g root -m 0755 "$HERE/zavod_intake.py" /usr/local/lib/zavod/zavod_intake.py
for u in zquarantine@.service zimport@.service; do
  install -o root -g root -m 0644 "$HERE/$u" "/etc/systemd/system/$u"
done
# Л.16–Л.28: ни у одной службы нет прав запуска через polkit. По умолчанию polkit спрашивает пароль
# администратора; правило ниже отвечает «нет» сразу и для учётных записей Завода, и для динамических сессий.
if [ -d /etc/polkit-1/rules.d ]; then
  install -o root -g root -m 0644 "$HERE/50-zavod-no-units.rules" /etc/polkit-1/rules.d/50-zavod-no-units.rules
  echo "POLKIT 50-zavod-no-units.rules installed"
else
  echo "POLKIT not present: units are managed by root only"
fi

if [ "$NO_PG" = 0 ]; then
  echo "=== 3.3.8.5 вход root → роль базы zstarter (peer, сопоставление zavod_cell)"
  if [ -z "$PG_CONF" ]; then
    PG_CONF=$(find /etc/postgresql -mindepth 2 -maxdepth 2 -type d -name main 2>/dev/null | sort | tail -1)
  fi
  [ -n "$PG_CONF" ] && [ -f "$PG_CONF/pg_hba.conf" ] || die "PostgreSQL config not found (use --pg-conf-dir or --no-pg)"
  ts=$(date -u '+%Y%m%dT%H%M%SZ')
  IDENT_LINE='zavod_cell      root                    zstarter'
  HBA_LINE='local   bem             zstarter                                peer map=zavod_cell'
  if ! grep -qE '^zavod_cell[[:space:]]+root[[:space:]]+zstarter[[:space:]]*$' "$PG_CONF/pg_ident.conf"; then
    cp -p "$PG_CONF/pg_ident.conf" "$PG_CONF/pg_ident.conf.before-zavod-$ts"
    printf '%s\n' "$IDENT_LINE" >> "$PG_CONF/pg_ident.conf"
  fi
  if ! grep -qE '^local[[:space:]]+bem[[:space:]]+zstarter[[:space:]]+peer[[:space:]]+map=zavod_cell' "$PG_CONF/pg_hba.conf"; then
    cp -p "$PG_CONF/pg_hba.conf" "$PG_CONF/pg_hba.conf.before-zavod-$ts"
    # Строка встаёт первой: pg_hba.conf читается сверху, первая подходящая строка решает.
    awk -v line="$HBA_LINE" 'BEGIN{done=0} !done && $0 !~ /^[[:space:]]*(#|$)/ {print line; done=1} {print} END{if(!done) print line}' \
      "$PG_CONF/pg_hba.conf.before-zavod-$ts" > "$PG_CONF/pg_hba.conf"
  fi
  systemctl reload postgresql.service
  echo "PG $PG_CONF: $(grep -cE 'map=zavod_cell' "$PG_CONF/pg_hba.conf") hba line, $(grep -cE '^zavod_cell' "$PG_CONF/pg_ident.conf") ident line"
fi

systemctl daemon-reload
systemctl enable --now zagent-start.path zagent-start.timer
systemd-analyze verify --man=no /etc/systemd/system/zagent-start.service /etc/systemd/system/zagent-start.path \
  /etc/systemd/system/zagent-start.timer /etc/systemd/system/zagent.slice "zagent@00000000000000000000000000000000.service" \
  "zquarantine@00000000000000000000000000000000.service" "zimport@00000000000000000000000000000000.service"
echo "ZAVOD_CELL_INSTALL=OK"
