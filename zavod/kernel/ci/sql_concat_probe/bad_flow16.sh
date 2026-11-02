#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow16.sh — проба 3.3.10.2 (самопроверка R15): сценарий пишет файл
#   с именем файла дерева или с суффиксом кода и запускает файл дерева из чужой папки.
# ДАТА: 2026-11-02 10:42 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
printf 'x' > /tmp/bad_flow15.py
printf 'x' >> "$1/evil.mjs"
echo x | tee /tmp/hook.sh
python3 -I /tmp/bad_flow15.py
