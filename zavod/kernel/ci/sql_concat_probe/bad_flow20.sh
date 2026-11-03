#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow20.sh — проба 3.3.10.2 (аудит M3310-R17B-01..03, -05): trap, косвенная запись PATH, путь с .., cd и ln в папку кода, nft и systemd-tmpfiles с чужим файлом.
# ДАТА: 2026-11-02 20:53 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 99955367-6fde-4cea-9e08-fbd6a564e8af)
trap 'psql -f /tmp/query.sql' EXIT
trap 'sh -c "psql -f /tmp/query.sql"' ERR
read PATH <<< '/tmp'
printf -v PATH '%s' /tmp
: "${PATH:=/tmp}"
(( PATH = 0 ))
read -a BASH_ENV <<< '/tmp/x'
wait -p PATH
printf '[Service]\nExecStart=/tmp/run\n' > /tmp/../etc/systemd/system/zagent.service.d/override.conf
touch /tmp/../etc/zavod/proxy-allow.conf
cd /etc/systemd/system
ln -s /etc/systemd/system /tmp/units
nft -f /tmp/override.nft
nft flush ruleset
systemd-tmpfiles --create /tmp/override.conf
systemd-tmpfiles --create
