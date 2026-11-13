#!/data/data/com.termux/files/usr/bin/bash
# ДОКУМЕНТ: zavod/ops/phone/zprobe_series.sh
# ВЕРСИЯ: v0.9  СТАТУС: DRAFT
# v0.9 (2026-11-13 07:55 +02:00, аудит R9 M-R9-01): подсказка приёмки — python3 -I -B из папки серии.
# v0.8 (2026-11-13 07:24 +02:00, аудит R7 M-R7-01): подсказка приёмки — манифест из коммита выпуска и ключ --fetch;
#   zprobe_verify.py на компьютере сам требует три нулевых кода fetch.txt и сверяет programs.sha256.
# v0.7 (2026-11-13 07:08 +02:00, аудит R6B): M-R6-01 сбой сервера (ssh с ненулевым кодом, нет SERIES_END, нет папки
#   journal) больше не обрывает телефон: коды ssh и scp сохраняются отдельно, started и journal забираются всегда,
#   нет журнала на сервере — пустая папка journal (пустая опись), и zprobe_verify.py явно пишет «серия прервана»;
#   L-R6-01 в папку серии новыми файлами копируются zprobe_verify.py, zprobe_rules.py, zprobe_pins.txt (programs/,
#   с их SHA-256 в programs.sha256) — компьютер сверяет их с манифестом выпуска до приёмки --refs.
# v0.6 (2026-11-13 05:59 +02:00, аудит R5 M-R5-01, M-R5-03): рядом с копией journal забирается копия папки отметок
#   начала started; итоговая подсказка — приёмка шага на компьютере командой zprobe_verify.py --refs по копии
#   папки серии (время прогона берётся из журнала, набранная строка ZPROBE_TIMES — только предварительно).
# v0.5 (2026-11-12 23:41 +02:00, аудит R4): журнал забирается папкой сегментов (scp -r в новую папку серии);
#   при «ВЕРНО» сохраняется строка ZPROBE_TIMES (times.txt) — её вводят в проверку снимков веток на компьютере.
# v0.4 (2026-11-12 23:14 +02:00, аудит R3 M-R3-01): «ВЕРНО» телефона — только половина приёмки; вторая — снимки
#   веток GitHub до и после серии с компьютера (ops/pc/zprobe_refs.sh, zprobe_refs_check.py), см. последнюю строку.
# ДАТА СОЗДАНИЯ: 2026-11-12 19:23 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-12 19:58 +02:00 (v0.3 по аудиту R2: L-09 сверка
#   SHA-256 своих программ с zprobe_pins.txt до связи с сервером; M-03 якорь — только дописывание в anchors.log,
#   последняя строка — действующий якорь, никакой замены файла)
# ИСПОЛНИТЕЛЬ: Claude (чаты 87eee078-952e-4855-8936-7f4d449aa9ac, c7307e9c-8e0e-4e24-997c-12d9fd3b0c71)
# НАЗНАЧЕНИЕ: серия проб с телефона оператора (Termux), протокол Завода v4 ред12, И.13 п. 2–3; DESIGN_3_5_5_PB1_v0_2.md,
#   раздел 6. Телефон сам делает вызов серии (32 hex) и хранит его у себя, запускает на сервере zprobe-start входом
#   администратора, забирает журнал, проверяет его zprobe_verify.py и при chain=OK переносит якорь (длина и сумма
#   журнала) — так прежняя история журнала не может быть переписана незаметно.
# ВЫЗОВ: bash zprobe_series.sh <серия>     (файлы zprobe_verify.py, zprobe_rules.py, zprobe_pins.txt — в ~/zprobe)
# ОГРАНИЧЕНИЯ: ключ входа берётся из ~/.ssh/zadmin2 и никуда не копируется; ничего не удаляет.
set -euo pipefail
S=${1:?usage: zprobe_series.sh <series>}
[[ $S =~ ^[0-9A-Za-z_-]{1,40}$ ]] || { echo "НЕВЕРНО: bad series name"; exit 2; }
H=root@178.105.20.190
K=$HOME/.ssh/zadmin2
W=$HOME/zprobe
for f in zprobe_verify.py zprobe_rules.py; do      # R2 L-09: телефон проверяет сам себя до запуска серии
  want=$(awk -v k="phone_$f" '$1==k{print $2}' "$W/zprobe_pins.txt")
  got=$(sha256sum "$W/$f" | cut -d' ' -f1)
  [ -n "$want" ] && [ "$want" = "$got" ] || { echo "НЕВЕРНО: $f differs from zprobe_pins.txt"; exit 2; }
done
mkdir "$W/$S" 2>/dev/null || { echo "НЕВЕРНО: series $S already started on this phone"; exit 2; }
C=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
(set -C; echo "$C" > "$W/$S/challenge")
mkdir "$W/$S/programs"                             # L-R6-01: закреплённые программы — новыми файлами в папку серии
for f in zprobe_verify.py zprobe_rules.py zprobe_pins.txt; do (set -C; cat "$W/$f" > "$W/$S/programs/$f"); done
(cd "$W/$S/programs" && set -C && sha256sum zprobe_verify.py zprobe_rules.py zprobe_pins.txt > ../programs.sha256)
set +e                                             # M-R6-01: сбой сервера не обрывает телефон — забрать всё и проверить
ssh -i "$K" -o BatchMode=yes "$H" /usr/local/lib/zavod/probes/zprobe-start "$S" "$C" ПБ-1 | tee "$W/$S/start.out"
SRC=${PIPESTATUS[0]}
scp -r -i "$K" -o BatchMode=yes "$H:/var/lib/zavod/probes/started" "$W/$S/started"; MRC=$?
scp -r -i "$K" -o BatchMode=yes "$H:/var/lib/zavod/probes/journal" "$W/$S/journal"; JRC=$?
[ -d "$W/$S/started" ] || mkdir "$W/$S/started"    # не забрано — пустая опись: проверка скажет «нет отметки начала»
[ -d "$W/$S/journal" ] || mkdir "$W/$S/journal"    # журнала ещё нет — пустая опись: «серия прервана»
(set -C; echo "ZPROBE_FETCH ssh_rc=$SRC started_rc=$MRC journal_rc=$JRC" > "$W/$S/fetch.txt")
cat "$W/$S/fetch.txt"
A=-
if [ -s "$W/anchors.log" ]; then A=$W/$S/anchor_in.txt; (set -C; tail -n 1 "$W/anchors.log" > "$A"); fi
python3 "$W/zprobe_verify.py" "$W/$S/journal" "$S" "$C" "$W/zprobe_pins.txt" "$A" | tee "$W/$S/verdict.txt"
VRC=${PIPESTATUS[0]}
set -e
if grep -q '| chain=OK |' "$W/$S/verdict.txt"; then
  N=$(sed -n 's/.*| anchor=\([0-9]*\):\([0-9a-f]\{64\}\)$/\1 \2/p' "$W/$S/verdict.txt")
  if [ -n "$N" ]; then echo "$N" >> "$W/anchors.log"; fi    # только дописывание; действует последняя строка
fi
echo "ИТОГ: $(head -n 1 "$W/$S/verdict.txt" | cut -d'|' -f1)"
(set -C; grep '^ZPROBE_TIMES ' "$W/$S/verdict.txt" > "$W/$S/times.txt") || true
[ "$SRC" = 0 ] && [ "$MRC" = 0 ] && [ "$JRC" = 0 ] || echo "ВНИМАНИЕ: сбой связи или сервера ($(cat "$W/$S/fetch.txt")) — серия не принята, даже если выше ВЕРНО"
echo "Приёмка шага: папка $W/$S целиком — на компьютер; там (M-R7-01: программа сама сверит fetch.txt и programs.sha256)"
echo "  git show <коммит выпуска>:zavod/ops/zprobe_pins.txt > manifest.txt"
echo "  cd <папка серии> && python3 -I -B programs/zprobe_verify.py journal $S <вызов из challenge> manifest.txt - --refs refs_before.txt refs_after.txt --fetch fetch.txt"
[ "$SRC" = 0 ] && [ "$MRC" = 0 ] && [ "$JRC" = 0 ] && exit "$VRC"
exit 3
