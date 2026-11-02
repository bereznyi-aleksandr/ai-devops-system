#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow15.sh — проба 3.3.10.2 (аудит M3310-R14-04, -05): psql -f за docker
#   и ssh, команда ssh одним словом и из подстановки, интерпретатор запускает файл не из проверенного дерева.
# ДАТА: 2026-11-02 10:25 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
docker run --rm -v /tmp:/tmp postgres:16 psql -f /tmp/query.sql
ssh host psql -f /tmp/query.sql
ssh host 'psql -f /tmp/query.sql'
ssh host "$1"
python3 zavod/ops/server/cell/worker15.data
bash script15.txt
node runner15.data
