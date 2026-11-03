#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow25.sh — проба 3.3.10.2 (аудит M3310-R21-01, -02): остановка чужого юнита (stop, disable --now, mask --now, шаблон экземпляров); sort --compress-program и его сокращение, слово из подстановки у sort; install -s и --strip-program; systemd-analyze вне закрытых форм; pg_ctlcluster вне списка программ. Юнит foreign25.service (ExecStop, ExecStopPost) дерево не ставит.
# ДАТА: 2026-11-03 02:19 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 2bf4a72a-0dfd-45e6-8828-338d117e688d)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
systemctl stop foreign25.service
systemctl disable --now foreign25.service
systemctl disable foreign25.service --now
systemctl mask --now foreign25
systemctl stop 'foreign25@*.service'
systemctl stop 'zz*.service'
sort --compress-program=sh /dev/null
sort --compress-prog=sh /dev/null
sort "$1" /dev/null
install -s -m 0644 "$HERE/bad18.nft" /tmp/x25
install --strip-program=sh -m 0644 "$HERE/bad18.nft" /tmp/y25
systemd-analyze verify --generators=yes /tmp/x25.service
pg_ctlcluster 16 main stop
install -o root -g root -m 0644 "$HERE/bad16.service" /etc/systemd/system/ok25.service
install -o root -g root -m 0644 "$HERE/bad16.service" /etc/systemd/system/ok25@.service
systemctl stop ok25.service
systemctl stop 'ok25@*.service'
systemctl disable --now ok25.service
systemctl disable foreign25.service
systemctl mask --runtime foreign25.service
systemctl stop postgresql.service
sort -u -o /tmp/s25 /dev/null
sort -k2,2 -t: -- "$2"
systemd-analyze security --no-pager ok25.service
