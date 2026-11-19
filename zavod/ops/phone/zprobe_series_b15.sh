#!/data/data/com.termux/files/usr/bin/bash
# ДОКУМЕНТ: zavod/ops/phone/zprobe_series_b15.sh
# ВЕРСИЯ: v0.17 (выпуск B15)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-19 14:15 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 14:15 +02:00
# v0.17 (Claude, терминал zavod; выпуск B15, REL155 AGREED, DECISION_B15 v0.2 часть B): НОВЫЙ файл — копия
#   zprobe_series_b14.sh v0.16 (тот не меняется). Имена B15: /usr/local/lib/zavod/probes-b15/zprobe-start, выпуск
#   «version=3.5.5-b15», служба zprobe-run-b15@<серия>, ключ phone_zprobe_series_b15.sh, zavod/ops/zprobe_pins_b15.txt.
#   Новое: zprobe-start B15 запускает службу без ожидания и ждёт её сам; если связь оборвалась раньше итоговой строки
#   (нет «ZPROBE_START CONFIRMED|UNKNOWN|JOURNAL_REFUSED» в start.out), телефон серию НЕ повторяет, а спрашивает только
#   «zprobe-start --status <серия>» (чтение) раз в STATUS_PAUSE с, не больше STATUS_TRIES раз, пока итог не перестанет
#   быть STARTED или QUEUED; все ответы — в status.out (новый файл). Итог status.out печатается; серия без итога
#   TERMINAL — не принята (код 3), журнал всё равно забирается.
# Далее — история копируемого файла zprobe_series_b14.sh:
# v0.16 (Claude, терминал zavod; выпуск B14, REL139 AGREED): НОВЫЙ файл — копия zprobe_series_b13.sh v0.15 (тот и папка
#   ~/zprobe3 на телефоне не меняются). Отличаются только имена B14: запуск /usr/local/lib/zavod/probes-b14/zprobe-start,
#   проверка выпуска «cat .../probes-b14/RELEASE» = «commit=<release_commit>\nversion=3.5.5-b14\n» (иначе «НЕВЕРНО: server
#   release is not B14», код 2, до папки серии), строка start.out — zprobe-run-b14@<серия>, ключ отпечатков
#   phone_zprobe_series_b14.sh, подсказка приёмки — zavod/ops/zprobe_pins_b14.txt. Логика та же.
# Далее — история копируемого файла zprobe_series_b13.sh:
# v0.15 (REL127 M-355-REL127-02): подсказка приёмки — манифест B13 из файла zavod/ops/zprobe_pins_b13.txt (git show
#   <коммит отпечатков>:zavod/ops/zprobe_pins_b13.txt > manifest.txt) и сверка его SHA-256 с суммой своего zprobe_pins.txt
#   (печатается) до --refs; прежний путь zavod/ops/zprobe_pins.txt выпусков B8–B12 больше не называется.
# v0.14 правка 13:44 (REL126 L-355-REL126-01): start.out обязан содержать ровно одну строку
#   «ZPROBE_START unit=zprobe-run-b13@<серия>.service fragment=/etc/systemd/system/zprobe-run-b13@.service»; иначе
#   «НЕВЕРНО: started unit is not zprobe-run-b13@<серия>», журнал всё равно забирается, итог — код 3 (серия не принята).
# v0.14 (2026-11-18 13:38 +02:00, Claude; проект B13 v0.3, п. 3.1 а), REL125 M-02): НОВЫЙ файл — копия zprobe_series.sh v0.13
#   (тот и папка ~/zprobe2 не меняются). Серию начинает /usr/local/lib/zavod/probes-b13/zprobe-start. До любой связи с
#   сервером самопроверка: SHA-256 этого файла, zprobe_verify.py и zprobe_rules.py против ключей phone_zprobe_series_b13.sh,
#   phone_zprobe_verify.py, phone_zprobe_rules.py файла zprobe_pins.txt своей папки. До папки серии — проверка выпуска:
#   ssh только чтение «cat .../probes-b13/RELEASE» должен вернуть байт в байт «commit=<release_commit из zprobe_pins.txt>
#   \nversion=3.5.5-b13\n» (ключ release_commit в zprobe_pins.txt — как у выпусков B8–B12); иначе (и при коде ssh не 0) —
#   «НЕВЕРНО: server release is not B13», код 2, папка серии не создаётся, zprobe-start не запускается.
# Далее — история копируемого файла v0.13:
# v0.13 (2026-11-15 00:18 +02:00, Claude, чат «напарник · 04» (869221b9), помощник; проект B10 v0.18 раздел 7): серию
#   начинает /usr/local/lib/zavod/probes-b10/zprobe-start (B10 рядом с B8 и B9); остальное как в v0.12.
# v0.12 (2026-11-14 10:44 +02:00, проект B9 v0.9): серию начинает /usr/local/lib/zavod/probes-b9/zprobe-start;
#   его вывод start.out проверка телефона требует (строка ZPROBE_START CONFIRMED). Программы и pins B9 — в ~/zprobe2.
# v0.11 (2026-11-14 09:00 +02:00, проба pb1trial1, чат «· 05» c241e855): рабочая папка — папка самой программы, а не
#   всегда ~/zprobe: новый выпуск ставится в новую папку (~/zprobe2) без перезаписи прежних pins; якорь журнала
#   переносится в неё копией anchors.log (cp -n) из прежней папки.
# v0.10 (2026-11-13 11:21 +02:00, CI Zavod Kernel settings.test.mjs): адрес scp записан как ${H}: — тот же смысл, без
#   ложного совпадения с путём диска Windows (буква и двоеточие).
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
# ДАТА СОЗДАНИЯ исходного zprobe_series.sh: 2026-11-12 19:23 +02:00  ДАТА ОБНОВЛЕНИЯ исходного: 2026-11-12 19:58 +02:00 (v0.3 по аудиту R2: L-09 сверка
#   SHA-256 своих программ с zprobe_pins.txt до связи с сервером; M-03 якорь — только дописывание в anchors.log,
#   последняя строка — действующий якорь, никакой замены файла)
# ИСПОЛНИТЕЛЬ: Claude (чаты 87eee078-952e-4855-8936-7f4d449aa9ac, c7307e9c-8e0e-4e24-997c-12d9fd3b0c71)
# НАЗНАЧЕНИЕ: серия проб с телефона оператора (Termux), протокол Завода v4 ред12, И.13 п. 2–3; DESIGN_3_5_5_PB1_v0_2.md,
#   раздел 6. Телефон сам делает вызов серии (32 hex) и хранит его у себя, запускает на сервере zprobe-start входом
#   администратора, забирает журнал, проверяет его zprobe_verify.py и при chain=OK переносит якорь (длина и сумма
#   журнала) — так прежняя история журнала не может быть переписана незаметно.
# ВЫЗОВ: bash <папка>/zprobe_series_b15.sh <серия>  (zprobe_verify.py, zprobe_rules.py, zprobe_pins.txt, anchors.log — там же)
# ОГРАНИЧЕНИЯ: ключ входа берётся из ~/.ssh/zadmin2 и никуда не копируется; ничего не удаляет.
set -euo pipefail
S=${1:?usage: zprobe_series_b15.sh <series>}
[[ $S =~ ^[0-9A-Za-z_-]{1,40}$ ]] || { echo "НЕВЕРНО: bad series name"; exit 2; }
H=root@178.105.20.190
K=$HOME/.ssh/zadmin2
W=$(cd "$(dirname "$0")" && pwd -P)   # v0.11: папка самой программы (~/zprobe, ~/zprobe2 …)
pin_ok() {                                         # B13 п. 3.1 а), B14: ключ в zprobe_pins.txt своей папки против настоящих байт
  local want got
  want=$(awk -v k="$1" '$1==k{print $2}' "$W/zprobe_pins.txt")
  got=$(sha256sum "$2" | cut -d' ' -f1)
  [ -n "$want" ] && [ "$want" = "$got" ] || { echo "НЕВЕРНО: $2 differs from zprobe_pins.txt"; exit 2; }
}
[ -s "$W/zprobe_pins.txt" ] || { echo "НЕВЕРНО: zprobe_pins.txt missing"; exit 2; }
pin_ok phone_zprobe_series_b15.sh "$W/zprobe_series_b15.sh"
pin_ok phone_zprobe_verify.py "$W/zprobe_verify.py"
pin_ok phone_zprobe_rules.py "$W/zprobe_rules.py"
RC=$(awk '$1=="release_commit"{print $2}' "$W/zprobe_pins.txt")
[[ $RC =~ ^[0-9a-f]{40}$ ]] || { echo "НЕВЕРНО: release_commit missing in zprobe_pins.txt"; exit 2; }
set +e                                             # проверка выпуска сервера: только чтение, до папки серии
RO=$(ssh -i "$K" -o BatchMode=yes "$H" cat /usr/local/lib/zavod/probes-b15/RELEASE 2>/dev/null; printf 'X%s' "$?")
set -e
RSSH=${RO##*X}; RBODY=${RO%X*}
WANT=$(printf 'commit=%s\nversion=3.5.5-b15\n_' "$RC")
{ [ "$RSSH" = 0 ] && [ "${RBODY}_" = "$WANT" ]; } || { echo "НЕВЕРНО: server release is not B15"; exit 2; }
mkdir "$W/$S" 2>/dev/null || { echo "НЕВЕРНО: series $S already started on this phone"; exit 2; }
C=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
(set -C; echo "$C" > "$W/$S/challenge")
mkdir "$W/$S/programs"                             # L-R6-01: закреплённые программы — новыми файлами в папку серии
for f in zprobe_verify.py zprobe_rules.py zprobe_pins.txt; do (set -C; cat "$W/$f" > "$W/$S/programs/$f"); done
(cd "$W/$S/programs" && set -C && sha256sum zprobe_verify.py zprobe_rules.py zprobe_pins.txt > ../programs.sha256)
set +e                                             # M-R6-01: сбой сервера не обрывает телефон — забрать всё и проверить
ssh -i "$K" -o BatchMode=yes "$H" /usr/local/lib/zavod/probes-b15/zprobe-start "$S" "$C" ПБ-1 | tee "$W/$S/start.out"
SRC=${PIPESTATUS[0]}
STATUS_TRIES=${STATUS_TRIES:-60}; STATUS_PAUSE=${STATUS_PAUSE:-60}   # B15: до 60 × 60 с = WAIT_S сервера
END_RE='^ZPROBE_START (CONFIRMED|UNKNOWN|JOURNAL_REFUSED) '
TERM=1
if ! grep -Eq "$END_RE" "$W/$S/start.out"; then
  echo "ВНИМАНИЕ: нет итоговой строки zprobe-start (обрыв связи?) — серия НЕ повторяется, только --status"
  (set -C; : > "$W/$S/status.out")
  for _ in $(seq 1 "$STATUS_TRIES"); do
    ssh -i "$K" -o BatchMode=yes "$H" /usr/local/lib/zavod/probes-b15/zprobe-start --status "$S" >> "$W/$S/status.out" 2>&1
    LAST=$(grep '^ZPROBE_STATUS ' "$W/$S/status.out" | tail -n 1)
    case "$LAST" in
      "ZPROBE_STATUS STARTED "*|"ZPROBE_STATUS QUEUED "*|"") sleep "$STATUS_PAUSE";;
      *) break;;
    esac
  done
  echo "СОСТОЯНИЕ: ${LAST:-нет ответа --status}"
  case "$LAST" in "ZPROBE_STATUS TERMINAL "*) TERM=1;; *) TERM=0;; esac
fi
UL="ZPROBE_START unit=zprobe-run-b15@$S.service fragment=/etc/systemd/system/zprobe-run-b15@.service"
UOK=0; [ "$(grep -c "^ZPROBE_START unit=" "$W/$S/start.out")" = 1 ] && grep -qxF "$UL" "$W/$S/start.out" && UOK=1
[ "$UOK" = 1 ] || echo "НЕВЕРНО: started unit is not zprobe-run-b15@$S (start.out) — серия не принята"
scp -r -i "$K" -o BatchMode=yes "${H}:/var/lib/zavod/probes/started" "$W/$S/started"; MRC=$?
scp -r -i "$K" -o BatchMode=yes "${H}:/var/lib/zavod/probes/journal" "$W/$S/journal"; JRC=$?
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
PS=$(sha256sum "$W/zprobe_pins.txt" | cut -d' ' -f1)           # сумма отпечатков, уже проверенных телефоном (pin_ok выше)
echo "  git show <коммит отпечатков>:zavod/ops/zprobe_pins_b15.txt > manifest.txt"
echo "  echo '$PS  manifest.txt' | sha256sum -c -        # до --refs: должно быть manifest.txt: OK, иначе манифест чужой"
echo "  cd <папка серии> && python3 -I -B programs/zprobe_verify.py journal $S <вызов из challenge> manifest.txt - --refs refs_before.txt refs_after.txt --fetch fetch.txt"
[ "$TERM" = 1 ] || echo "ВНИМАНИЕ: итог --status не TERMINAL — серия не принята"
[ "$SRC" = 0 ] && [ "$MRC" = 0 ] && [ "$JRC" = 0 ] && [ "$UOK" = 1 ] && [ "$TERM" = 1 ] && exit "$VRC"
exit 3
