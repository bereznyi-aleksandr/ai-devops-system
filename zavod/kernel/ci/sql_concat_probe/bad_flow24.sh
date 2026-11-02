#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow24.sh — проба 3.3.10.2 (аудит M3310-R20-01, -02): builtin break в цикле установки; tee, dd of= и sort -o в путь из подстановки с тем же именем или окончанием, в том числе ниже nft по тексту.
# ДАТА: 2026-11-03 01:48 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 2bf4a72a-0dfd-45e6-8828-338d117e688d)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
for f in a; do install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/d24.conf; builtin break; done
systemd-tmpfiles --create /etc/tmpfiles.d/d24.conf
install -o root -g root -m 0644 "$HERE/bad18.nft" /etc/zavod/d24.nft
printf 'table inet x {}\n' | tee "$1/d24.nft" >/dev/null
nft -f /etc/zavod/d24.nft
install -o root -g root -m 0644 "$HERE/bad18.nft" /etc/zavod/x-e24.nft
dd if=/dev/zero of="$2-e24.nft" bs=1 count=1
nft -c -f /etc/zavod/x-e24.nft
install -o root -g root -m 0644 "$HERE/bad18.nft" /etc/zavod/f24.nft
nft -f /etc/zavod/f24.nft
sort -o "$3/f24.nft" /dev/null
install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/ok24.conf
systemd-tmpfiles --create /etc/tmpfiles.d/ok24.conf
install -o root -g root -m 0644 "$HERE/bad18.nft" /etc/zavod/ok24.nft
nft -c -f /etc/zavod/ok24.nft
printf 'x\n' > "$4/other24.txt"
cp -p "$4/ok24.nft" "$4/ok24.nft.$5.bak"
touch "/run/zavod/start/$5"
