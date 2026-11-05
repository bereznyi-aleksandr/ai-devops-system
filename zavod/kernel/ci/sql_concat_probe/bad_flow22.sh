#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow22.sh — проба 3.3.10.2 (аудит M3310-R19-01, -02, -03): systemctl запускает чужой юнит, установка файла настроек в условной ветке, nft с файлом того же имени из другой папки.
# ДАТА: 2026-11-02 21:54 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 2bf4a72a-0dfd-45e6-8828-338d117e688d); правка 2026-11-05 17:17 +02:00 (Claude, сессия c28394bb, карта 3.5.1): строка 20 — чужой юнит cron вместо ssh, потому что ssh.service стал юнитом ОС в SYSTEM_UNITS_OK сканера v0.24; правило и номер строки те же
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SERVICE=$1
if false; then install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/c1.conf; fi
systemd-tmpfiles --create /etc/tmpfiles.d/c1.conf
false && install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/c2.conf
systemd-tmpfiles --create /etc/tmpfiles.d/c2.conf
put3() { install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/c3.conf; }
put3
systemd-tmpfiles --create /etc/tmpfiles.d/c3.conf
install -o root -g root -m 0644 "$HERE/same22.nft" /etc/zavod/same22.nft
nft -f /etc/zavod/same22.nft
nft -f /etc/zavod/other22.nft
systemctl start "$SERVICE"
systemctl enable foreign22.service
systemctl start 'bad15@*.service'
systemctl restart cron
install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/ok22.conf
systemd-tmpfiles --create /etc/tmpfiles.d/ok22.conf
install -o root -g root -m 0644 "$HERE/bad18.nft" /etc/zavod/ok22.nft
nft -c -f /etc/zavod/ok22.nft
install -o root -g root -m 0644 "$HERE/bad16.service" /etc/systemd/system/bad16.service
systemctl start bad16.service
systemctl stop foreign22.service
systemctl start postgresql.service
