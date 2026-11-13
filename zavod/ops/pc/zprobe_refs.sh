#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/pc/zprobe_refs.sh
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT
# v0.2 (2026-11-12 23:41 +02:00, аудит R4 M-R4-01, L-R4-02): в шапке снимка — имя серии и SHA-256 самой программы
#   (tool_sha256), её сверяет zprobe_refs_check.py с доверенным манифестом zprobe_pins.txt.
# ДАТА СОЗДАНИЯ: 2026-11-12 23:14 +02:00
# ИСПОЛНИТЕЛЬ: Claude (чат c7307e9c-8e0e-4e24-997c-12d9fd3b0c71)
# НАЗНАЧЕНИЕ: проба ПБ-1, аудит ChatGPT STAGE355 R3 M-R3-01 и NEW_NEGATIVE_5 — независимый внешний контроль:
#   снимок веток refs/heads/zprobe/* хранилища zavod-bereznyi/zavod-work ДО и ПОСЛЕ серии. Снимок делает
#   компьютер оператора (не сервер, не клетка) своим уже настроенным доступом на чтение; ключ и пароль программа
#   не читает и никуда не передаёт — git берёт их сам из менеджера учётных данных.
# ВЫЗОВ: bash zprobe_refs.sh before|after <папка серии> <серия>   → <папка>/refs_<when>.txt (новый файл, без замены)
# ОГРАНИЧЕНИЯ: только чтение (git ls-remote); ошибка чтения — код 3 и запись rc в файл, проверка даст НЕВЕРНО.
set -uo pipefail
U='usage: zprobe_refs.sh before|after <dir> <series>'
W=${1:?$U}; D=${2:?$U}; S=${3:?$U}
[[ $W == before || $W == after ]] || { echo "$U"; exit 2; }
[[ $S =~ ^[0-9A-Za-z_-]{1,40}$ ]] || { echo "bad series name"; exit 2; }
REPO=https://github.com/zavod-bereznyi/zavod-work
PREFIX='refs/heads/zprobe/*'
TOOL=$(sha256sum "$0" | cut -c1-64)
mkdir -p "$D"
OUT=$(GIT_TERMINAL_PROMPT=0 git ls-remote "$REPO" "$PREFIX" 2>/dev/null); RC=$?
F="$D/refs_$W.txt"
( set -C; { echo "ZPROBE_REFS v2"; echo "when=$W"; echo "series=$S"; echo "repo=$REPO"; echo "prefix=$PREFIX";
            echo "tool_sha256=$TOOL"; echo "time_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "rc=$RC"; echo "---";
            printf '%s\n' "$OUT"; } > "$F" ) \
  || { echo "refs_$W.txt already exists"; exit 2; }
sha256sum "$F"
[ "$RC" -eq 0 ] || exit 3
