#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/cell/install_cell.sh
# ВЕРСИЯ: v0.9  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 13:47 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 22:56 +02:00 (v0.9: карта 3.3.10 — учётная запись zproxy; привратник zavod-gate (вход zgate → роль zgate, сопоставление zavod_gate), посредник zavod-proxy со списком /etc/zavod/proxy-allow.conf, общий фильтр сервера nftables /etc/zavod/zavod-egress.nft (служба zavod-nft); v0.8: аудит M33-R3-02 — образ сеансов занимает место сразу, проверка запаса диска сервера --min-free; M33-R3-03 — журналы приёма на своём разделе intake-journal.img; M33-R3-04 — 1% раздела приёма для root; v0.7: аудит M33-R2-04 — служба zintake-archive@ для отказов карантина; приём на своём разделе
#   /var/lib/zavod/intake-fs.img с пределом места и inode, журналы приёма в /var/lib/zavod/intake-journal; v0.6: аудит M33-R2-02 — ключи служб в /etc/zavod/secrets/<служба>/ по И.7 п.4;
#   v0.5: аудит M33-03 — база
#   под zdb, свои папки служб; вопрос аудитора «д» — раздел сеансов /var/lib/zavod/session-fs.img; v0.4: аудит M33-06 — очередь
#   тревог /var/lib/zavod/alerts, служба доставки zavod-alert-notify, канал Telegram /etc/zavod/alert-deliver; v0.3: аудит M33-01 — вход zkernel → bem_kernel_rw
#   по сопоставлению zavod_kernel; v0.2: карантин и приём
#   архива — папки /var/lib/zavod/intake, zavod_intake.py, zquarantine@ и zimport@; карта 3.3.9)
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: установщик ячейки Завода на Ubuntu 24.04 (карта 3.3.8, протокол v3.1 Л.16–Л.28, И.12–И.12б):
#   (1) учётные записи служб без входа и без прав администратора; (2) папки с правами; (3) клетка zagent@ и
#   группа zagent.slice; (4) zagent-start с папками запросов 1730 root:zkernel; (5) вход root → роль базы
#   zstarter (peer, сопоставление zavod_cell); (6) карантин и доверенный приём архива (И.12г, И.12д);
#   (7) привратник команд агента, посредник сети и общий фильтр сервера (И.7а, И.12в; карта 3.3.10).
#   Повторный запуск даёт тот же результат.
# ВЫЗОВ: sudo bash install_cell.sh [--pg-conf-dir /etc/postgresql/16/main | --no-pg] [--session-fs-size 10G]
#   [--intake-fs-size 20G] [--intake-fs-inodes 1000000] [--intake-journal-size 1G] [--min-free 5G]
# ОГРАНИЧЕНИЯ: ничего не удаляет; прежние pg_hba.conf и pg_ident.conf сохраняются копией рядом. Функции базы
#   (db/06_zavod_ext_04.sql) ставятся цепочкой базы, не этим файлом. Пароли и ключи не нужны и не пишутся.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ACCOUNTS=(zdb zkernel zgate zgithub ztelegram zquarantine zimport zbackup zbrowser zproxy)
ADMIN_GROUPS=(sudo adm wheel admin root lxd docker systemd-journal)
PG_CONF=''
NO_PG=0
SESSION_FS_SIZE=10G
INTAKE_FS_SIZE=20G
INTAKE_FS_INODES=1000000
INTAKE_JOURNAL_SIZE=1G
MIN_FREE=5G
while [ $# -gt 0 ]; do
  case "$1" in
    --pg-conf-dir) PG_CONF=$2; shift 2 ;;
    --session-fs-size) SESSION_FS_SIZE=$2; shift 2 ;;
    --intake-fs-size) INTAKE_FS_SIZE=$2; shift 2 ;;
    --intake-fs-inodes) INTAKE_FS_INODES=$2; shift 2 ;;
    --intake-journal-size) INTAKE_JOURNAL_SIZE=$2; shift 2 ;;
    --min-free) MIN_FREE=$2; shift 2 ;;
    --no-pg) NO_PG=1; shift ;;
    *) echo "REFUSED: unknown argument $1" >&2; exit 2 ;;
  esac
done
die() { echo "REFUSED: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root"
command -v nft >/dev/null || die "nft not found: install the nftables package first (3.3.10.5)"
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
# Очередь тревог (аудит M33-06): spool — ещё не в базе, stored — записаны в базу, rejected — испорчены.
for d in alerts alerts/spool alerts/stored alerts/rejected; do dir "/var/lib/zavod/$d" root root 0700; done
dir /usr/local/lib/zavod root root 0755

echo "=== 3.3.8.3–3.3.8.4 программы, клетка, папки запросов, тревоги"
install -o root -g root -m 0755 "$HERE/zagent-start" "$HERE/zagent-session" "$HERE/zavod-alert-notify" \
  "$HERE/zavod-alert-telegram" /usr/local/lib/zavod/
# Канал тревог: по умолчанию Telegram; работает от ztelegram, ключ бота кладёт оператор в
# /etc/zavod/secrets/ztelegram/alert-telegram.env (владелец ztelegram, 0400; И.7 п.4).
# Уже стоящий канал не заменяется.
[ -e /etc/zavod/alert-deliver ] || install -o root -g root -m 0755 "$HERE/zavod-alert-telegram" /etc/zavod/alert-deliver
for u in zagent@.service zagent.slice zagent-start.service zagent-start.path zagent-start.timer \
         zavod-alert-notify.service zavod-alert-notify.timer; do
  install -o root -g root -m 0644 "$HERE/$u" "/etc/systemd/system/$u"
done
install -o root -g root -m 0644 "$HERE/zavod-cell.tmpfiles.conf" /etc/tmpfiles.d/zavod-cell.conf
systemd-tmpfiles --create /etc/tmpfiles.d/zavod-cell.conf
for d in start stop; do
  [ "$(stat -c '%U:%G %a' /run/zavod/$d)" = "root:zkernel 1730" ] || die "/run/zavod/$d rights"
done
echo "DIR /run/zavod/start $(stat -c '%U:%G %a' /run/zavod/start)"
echo "DIR /run/zavod/stop $(stat -c '%U:%G %a' /run/zavod/stop)"

echo "=== место на диске сервера под образы разделов (аудит M33-R3-02)"
# Образы разделов (сеансы, приём, журналы приёма) занимают своё место на диске сервера сразу (fallocate),
# поэтому их заполнение потом диск сервера не тратит. До резервирования проверяем, что после него на диске
# сервера останется не меньше --min-free для базы, копий и журналов; иначе установка останавливается.
to_bytes() { numfmt --from=iec "$1"; }
still_needed() { # образ размер → сколько байт образ ещё займёт на диске сервера
  local want have
  if [ -e "$1" ]; then want=$(stat -c %s "$1"); have=$(du -B1 "$1" | cut -f1); else want=$(to_bytes "$2"); have=0; fi
  if [ "$want" -gt "$have" ]; then echo $((want - have)); else echo 0; fi
}
NEED=$(( $(still_needed /var/lib/zavod/session-fs.img "$SESSION_FS_SIZE") + $(still_needed /var/lib/zavod/intake-fs.img "$INTAKE_FS_SIZE") + $(still_needed /var/lib/zavod/intake-journal.img "$INTAKE_JOURNAL_SIZE") ))
AVAIL=$(df --output=avail -B1 /var/lib/zavod | tail -1 | tr -d ' ')
[ $((AVAIL - NEED)) -ge "$(to_bytes "$MIN_FREE")" ] \
  || die "server disk: images need $((NEED >> 20)) MB, free $((AVAIL >> 20)) MB, must keep $MIN_FREE free"
echo "SERVER_DISK free_MB=$((AVAIL >> 20)) images_need_MB=$((NEED >> 20)) keep=$MIN_FREE"

echo "=== раздел сеансов с пределом места (вопрос аудитора «д», И.12б)"
# Рабочие папки сеансов (StateDirectory с DynamicUser) лежат в /var/lib/private/zagent — это отдельный раздел
# из файла-образа. Уже созданный образ не пересоздаётся: данные сеансов не теряются при повторной установке.
IMG=/var/lib/zavod/session-fs.img
if [ ! -e "$IMG" ]; then
  fallocate -l "$SESSION_FS_SIZE" "$IMG"
  chmod 0600 "$IMG"
  mkfs.ext4 -q -F -L zagent -m 0 -E nodiscard "$IMG"  # nodiscard: иначе mkfs снова делает файл разреженным
fi
# Аудит M33-R3-02: образ, созданный прежней версией «разреженным», получает всё своё место сейчас;
# содержимое не меняется (заполняются только пустоты файла).
fallocate -l "$(stat -c %s "$IMG")" "$IMG"
[ "$(blkid -o value -s TYPE "$IMG")" = ext4 ] || die "$IMG is not ext4"
install -d -o root -g root -m 0700 /var/lib/private
install -d -o root -g root -m 0755 /var/lib/private/zagent
install -o root -g root -m 0644 "$HERE/var-lib-private-zagent.mount" /etc/systemd/system/var-lib-private-zagent.mount
systemctl daemon-reload
systemctl enable --now var-lib-private-zagent.mount
chown root:root /var/lib/private/zagent
chmod 0755 /var/lib/private/zagent
echo "SESSION_FS $(findmnt -n -o FSTYPE,SIZE /var/lib/private/zagent) image_allocated_MB=$(du -B1M "$IMG" | cut -f1)"

echo "=== 3.3.9 карантин и приём архива (И.12г, И.12д)"
# Опись пишет ядро (zkernel), читают все: она не тайна, важна её целостность. Архив кладёт привратник (zgate),
# карантин только читает. out/ — карантин пишет, приём читает по группе. accepted/ — приём пишет, zgithub читает.
# Аудит M33-R2-04: всё это — на своём разделе из файла-образа с пределом места и числа файлов (inode). Отказы и их
# перенос в archive/ остаются внутри раздела; журналы приёма — вне его, чтобы итог записался и при полном разделе.
# Аудит M33-R3-04: 1% раздела отложен для root (-m 1): карантин и приём (не root) упираются в «нет места» раньше,
# и архиватор (root) переносит отказ и при полном разделе.
# Уже созданный образ не пересоздаётся. Файлы в /var/lib/zavod/intake до раздела — отказ установки (ничего не удаляем).
INTAKE=/var/lib/zavod/intake
INTAKE_IMG=/var/lib/zavod/intake-fs.img
install -d -o root -g root -m 0755 "$INTAKE"
if ! mountpoint -q "$INTAKE" && [ -n "$(ls -A "$INTAKE")" ]; then
  die "$INTAKE has files outside the intake partition: move them away first"
fi
if [ ! -e "$INTAKE_IMG" ]; then
  # Всё место образа занимается сразу (не «разреженный» файл): заполнение раздела потом не тратит диск сервера.
  # Места на диске сервера не хватает — fallocate откажет, установка остановится.
  fallocate -l "$INTAKE_FS_SIZE" "$INTAKE_IMG"
  chmod 0600 "$INTAKE_IMG"
  mkfs.ext4 -q -F -L zintake -m 1 -E nodiscard -N "$INTAKE_FS_INODES" "$INTAKE_IMG"  # nodiscard: иначе mkfs снова делает файл разреженным
fi
fallocate -l "$(stat -c %s "$INTAKE_IMG")" "$INTAKE_IMG"
[ "$(blkid -o value -s TYPE "$INTAKE_IMG")" = ext4 ] || die "$INTAKE_IMG is not ext4"
install -o root -g root -m 0644 "$HERE/var-lib-zavod-intake.mount" /etc/systemd/system/var-lib-zavod-intake.mount
systemctl daemon-reload
systemctl enable --now var-lib-zavod-intake.mount
mountpoint -q "$INTAKE" || die "$INTAKE is not mounted"
# раздел прежней версии (-m 0) получает запас для root на ходу, через своё устройство
tune2fs -m 1 "$(findmnt -n -o SOURCE "$INTAKE")" >/dev/null
echo "INTAKE_FS $(findmnt -n -o FSTYPE,SIZE "$INTAKE") inodes=$(df --output=itotal "$INTAKE" | tail -1 | tr -d ' ') image_allocated_MB=$(du -B1M "$INTAKE_IMG" | cut -f1)"
dir /var/lib/zavod/intake root root 0755
dir /var/lib/zavod/intake/manifest zkernel zkernel 0755
dir /var/lib/zavod/intake/in zgate zquarantine 2750
dir /var/lib/zavod/intake/out zquarantine zimport 2750
dir /var/lib/zavod/intake/accepted zimport zgithub 2750
dir /var/lib/zavod/intake/accepted/.staging zimport zgithub 2700
# Аудит M33-R3-03: журналы приёма — на своём разделе из файла-образа (место занято сразу), не на диске сервера.
JOURNAL_DIR=/var/lib/zavod/intake-journal
JOURNAL_IMG=/var/lib/zavod/intake-journal.img
JOURNAL_UNIT=$(systemd-escape --path --suffix=mount "$JOURNAL_DIR")
install -d -o root -g root -m 0755 "$JOURNAL_DIR"
if ! mountpoint -q "$JOURNAL_DIR" && [ -n "$(ls -A "$JOURNAL_DIR")" ]; then
  die "$JOURNAL_DIR has files outside the journal partition: move them away first"
fi
if [ ! -e "$JOURNAL_IMG" ]; then
  fallocate -l "$INTAKE_JOURNAL_SIZE" "$JOURNAL_IMG"
  chmod 0600 "$JOURNAL_IMG"
  mkfs.ext4 -q -F -L zijournal -m 0 -E nodiscard -N 1024 "$JOURNAL_IMG"
fi
fallocate -l "$(stat -c %s "$JOURNAL_IMG")" "$JOURNAL_IMG"
[ "$(blkid -o value -s TYPE "$JOURNAL_IMG")" = ext4 ] || die "$JOURNAL_IMG is not ext4"
install -o root -g root -m 0644 "$HERE/intake-journal.mount" "/etc/systemd/system/$JOURNAL_UNIT"
systemctl daemon-reload
systemctl enable --now "$JOURNAL_UNIT"
mountpoint -q "$JOURNAL_DIR" || die "$JOURNAL_DIR is not mounted"
echo "INTAKE_JOURNAL_FS $(findmnt -n -o FSTYPE,SIZE "$JOURNAL_DIR") image_allocated_MB=$(du -B1M "$JOURNAL_IMG" | cut -f1)"
dir /var/lib/zavod/intake-journal root root 0755
dir /var/lib/zavod/intake-journal/quarantine zquarantine zquarantine 0750
dir /var/lib/zavod/intake-journal/import zimport zimport 0750
dir /var/lib/zavod/intake/archive root root 0700
install -o root -g root -m 0755 "$HERE/zavod_intake.py" /usr/local/lib/zavod/zavod_intake.py
for u in zquarantine@.service zimport@.service zintake-archive@.service; do
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

echo "=== 3.3.10 привратник, посредник сети, общий фильтр сервера"
install -o root -g root -m 0755 "$HERE/zavod-gate" "$HERE/zavod-proxy" /usr/local/lib/zavod/
for u in zavod-gate.service zavod-proxy.service zavod-nft.service; do
  install -o root -g root -m 0644 "$HERE/$u" "/etc/systemd/system/$u"
done
# Правила фильтра — часть кода, заменяются всегда; список адресов посредника — настройка оператора, уже стоящий
# не заменяется (И.12в: GitHub в нём быть не должно).
install -o root -g root -m 0644 "$HERE/zavod-egress.nft" /etc/zavod/zavod-egress.nft
[ -e /etc/zavod/proxy-allow.conf ] || install -o root -g root -m 0644 "$HERE/proxy-allow.conf" /etc/zavod/proxy-allow.conf
[ "$(stat -c '%U:%a' /etc/zavod/proxy-allow.conf)" = root:644 ] || die "/etc/zavod/proxy-allow.conf must be root 644"
if grep -qiE '(^|[[:space:].])github(usercontent)?\.com' /etc/zavod/proxy-allow.conf; then die "GitHub in proxy-allow.conf (I.12v)"; fi
nft -c -f /etc/zavod/zavod-egress.nft || die "nft rules do not load"

echo "=== свои папки служб (И.7, Л.16–Л.25; аудит M33-03)"
# Рабочая папка каждой службы — только её (0700). Папка ключей (И.7 п.4: /etc/zavod/secrets/<учётная запись>/,
# читает только сама служба) — у служб с ключами внешних сервисов: GitHub (zgithub), бот Telegram (ztelegram),
# копия (zbackup); ключи (файлы 0400) кладёт оператор, установщик их не пишет.
dir /var/lib/zavod/svc root root 0755
for a in zkernel zgate zgithub ztelegram zquarantine zimport zbackup zbrowser; do dir "/var/lib/zavod/svc/$a" "$a" "$a" 0700; done
dir /etc/zavod/secrets root root 0755
for a in zgithub ztelegram zbackup; do dir "/etc/zavod/secrets/$a" "$a" "$a" 0700; done

if [ "$NO_PG" = 0 ]; then
  echo "=== 3.3.8.5 вход root → zstarter (zavod_cell), zkernel → bem_kernel_rw (zavod_kernel, аудит M33-01); peer"
  if [ -z "$PG_CONF" ]; then
    PG_CONF=$(find /etc/postgresql -mindepth 2 -maxdepth 2 -type d -name main 2>/dev/null | sort | tail -1)
  fi
  [ -n "$PG_CONF" ] && [ -f "$PG_CONF/pg_hba.conf" ] || die "PostgreSQL config not found (use --pg-conf-dir or --no-pg)"
  ts=$(date -u '+%Y%m%dT%H%M%SZ')
  # И.7, Л.17 (аудит M33-03): сервер базы работает под zdb и видит только свои файлы. Учётная запись postgres
  # остаётся входом администратора в базу (sudo -u postgres psql), файлов базы она больше не читает.
  # Настройки — root:zdb 0640: сервер их читает, но поменять не может. Сокет — в /var/run/postgresql
  # (2775 postgres:postgres), поэтому zdb входит в группу postgres. Сети нет (Л.17), значит и SSL не нужен.
  PG_VER=$(basename "$(dirname "$PG_CONF")"); PG_NAME=$(basename "$PG_CONF")
  PG_DATA=$(sed -n "s/^data_directory[[:space:]]*=[[:space:]]*'\([^']*\)'.*/\1/p" "$PG_CONF/postgresql.conf")
  [ -n "$PG_DATA" ] && [ -d "$PG_DATA" ] || die "data_directory not found in $PG_CONF/postgresql.conf"
  if [ "$(stat -c '%U' "$PG_DATA")" != zdb ] || [ "$(stat -c '%U' "$PG_CONF")" != root ]; then
    pg_ctlcluster "$PG_VER" "$PG_NAME" stop || true
    printf "listen_addresses = ''\nssl = off\n" > "$PG_CONF/conf.d/20-zavod-zdb.conf"
    chown -R zdb:zdb "$PG_DATA"
    chown -R root:zdb "$PG_CONF"
    find "$PG_CONF" -type d -exec chmod 0750 {} +
    find "$PG_CONF" -type f -exec chmod 0640 {} +
    PG_LOG="/var/log/postgresql/postgresql-$PG_VER-$PG_NAME.log"
    if [ -e "$PG_LOG" ]; then chown zdb:adm "$PG_LOG"; fi
    usermod -aG postgres zdb
    systemctl start "postgresql@$PG_VER-$PG_NAME.service"
  fi
  echo "PG server owner $(stat -c '%U:%G %a' "$PG_DATA"), config $(stat -c '%U:%G %a' "$PG_CONF")"
  # Пары «сопоставление, учётная запись Linux, роль базы»; у каждой своя строка pg_hba (только база bem).
  for pair in 'zavod_cell root zstarter' 'zavod_kernel zkernel bem_kernel_rw' 'zavod_gate zgate zgate'; do
    read -r MAP OSUSER DBROLE <<< "$pair"
    if ! grep -qE "^${MAP}[[:space:]]+${OSUSER}[[:space:]]+${DBROLE}[[:space:]]*\$" "$PG_CONF/pg_ident.conf"; then
      cp -p "$PG_CONF/pg_ident.conf" "$PG_CONF/pg_ident.conf.before-zavod-$MAP-$ts"
      printf '%-15s %-23s %s\n' "$MAP" "$OSUSER" "$DBROLE" >> "$PG_CONF/pg_ident.conf"
    fi
    if ! grep -qE "^local[[:space:]]+bem[[:space:]]+${DBROLE}[[:space:]]+peer[[:space:]]+map=${MAP}" "$PG_CONF/pg_hba.conf"; then
      cp -p "$PG_CONF/pg_hba.conf" "$PG_CONF/pg_hba.conf.before-zavod-$MAP-$ts"
      HBA_LINE=$(printf 'local   bem             %-31s peer map=%s' "$DBROLE" "$MAP")
      # Строка встаёт первой: pg_hba.conf читается сверху, первая подходящая строка решает.
      awk -v line="$HBA_LINE" 'BEGIN{done=0} !done && $0 !~ /^[[:space:]]*(#|$)/ {print line; done=1} {print} END{if(!done) print line}' \
        "$PG_CONF/pg_hba.conf.before-zavod-$MAP-$ts" > "$PG_CONF/pg_hba.conf"
    fi
  done
  systemctl reload postgresql.service
  echo "PG $PG_CONF: $(grep -cE 'map=zavod_(cell|kernel|gate)' "$PG_CONF/pg_hba.conf") hba lines, $(grep -cE '^zavod_(cell|kernel|gate)' "$PG_CONF/pg_ident.conf") ident lines"
fi

systemctl daemon-reload
systemctl enable --now zagent-start.path zagent-start.timer zavod-alert-notify.timer
# Фильтр — раньше посредника и сессий; повторный запуск перечитывает правила и новый код служб.
systemctl enable zavod-nft.service zavod-gate.service zavod-proxy.service
systemctl restart zavod-nft.service
systemctl restart zavod-gate.service zavod-proxy.service
nft list table inet zavod >/dev/null || die "table inet zavod not loaded"
systemd-analyze verify --man=no /etc/systemd/system/zagent-start.service /etc/systemd/system/zagent-start.path \
  /etc/systemd/system/zavod-alert-notify.service /etc/systemd/system/zavod-alert-notify.timer \
  /etc/systemd/system/var-lib-private-zagent.mount /etc/systemd/system/var-lib-zavod-intake.mount \
  "/etc/systemd/system/$JOURNAL_UNIT" \
  /etc/systemd/system/zagent-start.timer /etc/systemd/system/zagent.slice "zagent@00000000000000000000000000000000.service" \
  "zquarantine@00000000000000000000000000000000.service" "zimport@00000000000000000000000000000000.service" \
  "zintake-archive@00000000000000000000000000000000.service" \
  /etc/systemd/system/zavod-gate.service /etc/systemd/system/zavod-proxy.service /etc/systemd/system/zavod-nft.service
echo "ZAVOD_CELL_INSTALL=OK"
