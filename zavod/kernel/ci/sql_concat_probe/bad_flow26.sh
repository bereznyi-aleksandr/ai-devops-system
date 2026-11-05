#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow26.sh — проба 3.5.1 (аудит ChatGPT STAGE351 R2 M-351-R2-01): установка «keep_same + [ -e ПУТЬ ] || install» засчитывается только в точной форме: строка 16 — точная форма (не находка); 19 — проверка другого пути; 21 — без keep_same; 24 — другой режим.
# ДАТА: 2026-11-05 22:23 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия e4640034-a723-4cee-bed1-c6b3a649419c)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
die() { echo "REFUSED: $*" >&2; exit 1; }
keep_same() {
  local m=$1 s=$2 d=$3
  if [ -e "$d" ] || [ -L "$d" ]; then
    { [ -f "$d" ] && [ ! -L "$d" ] && cmp -s "$s" "$d" && [ "$(stat -c '%U:%G %a' "$d")" = "root:root ${m#0}" ]; } \
      || die "$d exists and differs from the package (a new version needs a separate operator decision)"
  fi
}
keep_same 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/ok26.conf
[ -e /etc/tmpfiles.d/ok26.conf ] || install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/ok26.conf
systemd-tmpfiles --create /etc/tmpfiles.d/ok26.conf
keep_same 0644 "$HERE/bad18.nft" /etc/zavod/a26.nft
[ -e /etc/zavod/b26.nft ] || install -o root -g root -m 0644 "$HERE/bad18.nft" /etc/zavod/a26.nft
nft -c -f /etc/zavod/a26.nft
[ -e /etc/zavod/c26.nft ] || install -o root -g root -m 0644 "$HERE/bad18.nft" /etc/zavod/c26.nft
nft -c -f /etc/zavod/c26.nft
keep_same 0600 "$HERE/bad18.nft" /etc/zavod/d26.nft
[ -e /etc/zavod/d26.nft ] || install -o root -g root -m 0644 "$HERE/bad18.nft" /etc/zavod/d26.nft
nft -c -f /etc/zavod/d26.nft
