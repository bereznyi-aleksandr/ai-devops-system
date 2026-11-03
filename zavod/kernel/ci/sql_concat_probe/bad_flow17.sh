#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow17.sh — проба 3.3.10.2 (аудит M3310-R15B-02, -04, -05): файл
#   дерева по относительному пути, имя программы в $'…' и команда в опции ssh.
# ДАТА: 2026-11-02 15:09 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
python3 ../../tmp/bad_flow15.py
cd /tmp; python3 ./bad_flow15.py
$'\x70sql' -f /tmp/query.sql
ssh -o 'ProxyCommand=psql -f /tmp/query.sql' host
ssh -oProxyCommand=true host
ssh -F /tmp/ssh_config host
