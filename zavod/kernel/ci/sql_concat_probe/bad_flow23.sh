#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow23.sh — проба 3.3.10.2 (аудит M3310-R20-01, -02): builtin continue в цикле установки, запись в путь из подстановки после верной установки.
# ДАТА: 2026-11-03 01:48 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 2bf4a72a-0dfd-45e6-8828-338d117e688d)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
for f in a; do builtin continue; install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/d23.conf; done
systemd-tmpfiles --create /etc/tmpfiles.d/d23.conf
install -o root -g root -m 0644 "$HERE/bad18.nft" /etc/zavod/d23.nft
p=$(printf %s /etc/zavod/d23.nft)
printf 'table inet x {}\n' > "$p"
nft -f /etc/zavod/d23.nft
