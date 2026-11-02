#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow21.sh — проба 3.3.10.2 (аудит M3310-R18-01, -02): printf %n пишет переменную по имени, цикл for в имя оболочки, systemd-tmpfiles с файлом не из дерева.
# ДАТА: 2026-11-02 21:20 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 15711aec-20c7-4a39-8052-69524f78b708)
HERE=$(cd "$(dirname "$0")" && pwd)
printf '%n' PATH
printf 'abc%n' BASH_ENV
printf '%-5ln' PATH
printf '%%%n' PATH
printf '\045n' PATH
for PATH in /tmp; do :; done
select BASH_ENV in /tmp/x; do :; done
systemd-tmpfiles --create /etc/tmpfiles.d/evil.conf
install -o root -g root -m 0644 "$HERE/missing21.tmpfiles.conf" /etc/tmpfiles.d/m.conf
systemd-tmpfiles --create /etc/tmpfiles.d/m.conf
install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/z.conf
cp /tmp/evil.conf /etc/tmpfiles.d/z.conf
systemd-tmpfiles --create /etc/tmpfiles.d/z.conf
printf '%%n is text\n'
install -o root -g root -m 0644 "$HERE/bad18.tmpfiles.conf" /etc/tmpfiles.d/ok.conf
systemd-tmpfiles --create /etc/tmpfiles.d/ok.conf
