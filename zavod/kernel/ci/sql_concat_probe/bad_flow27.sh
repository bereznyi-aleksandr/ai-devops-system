#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow27.sh — проба 3.5.1 (аудит ChatGPT STAGE351 R2 M-351-R2-01): текст keep_same изменён (сравнение байтов убрано) — точная форма установки не засчитывается: строка 16 — находка.
# ДАТА: 2026-11-05 22:23 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия e4640034-a723-4cee-bed1-c6b3a649419c)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
die() { echo "REFUSED: $*" >&2; exit 1; }
keep_same() {
  local m=$1 s=$2 d=$3
  if [ -e "$d" ] || [ -L "$d" ]; then
    { [ -f "$d" ] && [ ! -L "$d" ] && true && [ "$(stat -c '%U:%G %a' "$d")" = "root:root ${m#0}" ]; } \
      || die "$d exists and differs from the package (a new version needs a separate operator decision)"
  fi
}
keep_same 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/ok27.conf
[ -e /etc/tmpfiles.d/ok27.conf ] || install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/ok27.conf
systemd-tmpfiles --create /etc/tmpfiles.d/ok27.conf
