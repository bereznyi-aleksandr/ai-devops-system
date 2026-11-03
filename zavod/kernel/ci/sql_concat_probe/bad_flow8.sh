#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow8.sh — проба карты 3.3.10.2 (аудит M3310-R7-03): запрос к базе
#   из подстановок оболочки, код из строки, psql со входа и из переменной. ДАТА: 2026-11-02 03:47 +02:00
pgq() { local q=$1; shift; printf '%s\n' "$q" | psql -X -d bem "$@"; }
psql -X -d bem -c "$1"
pgq "SELECT * FROM t WHERE id = '$2'"
X="SELECT 1 FROM t WHERE id = '$2'"
eval "$3"
"$4" -X -d bem
psql -X -d bem <<SQL
SELECT $5;
SQL
pgq 'SELECT :x'
psql -X -d bem -c 'SELECT 1 \gexec'
python3 -c "$6"
node -e 'console.log(1)'
echo "$7" | psql -X -d bem
sh -c 'eval "$1"' sh "$8"
pgq "$9"
psql -X -d bem -f "$1"
