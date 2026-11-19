#!/data/data/com.termux/files/usr/bin/bash
# ДОКУМЕНТ: zavod/ops/phone/zprobe_series_b15b.sh
# ВЕРСИЯ: v0.20 (выпуск B15, вариант B без нового выпуска сервера)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-19 21:59 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 22:40 +02:00
# v0.20: REL167 M-355-REL167-01 — контрольное чтение сбрасывается при любом не-DONE (обрыв или неполный ответ,
#   RUNNING, RC_PARTIAL, ABSENT, NO_PID): «два подряд» значит два соседних чтения, оба DONE и равные;
#   L-355-REL167-02 — якорь в anchors.log не дописывается, если такая строка уже есть.
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# ОСНОВАНИЕ: REL165 M-355-REL165-01, REL166 M01_VARIANT=B и M-355-REL166-02 (pb1trial5: обрыв ssh — вывод zprobe-start
#   со строкой ZPROBE_START CONFIRMED потерян, серия НЕВЕРНО). НОВЫЙ файл — копия zprobe_series_b15.sh v0.18 (тот не
#   меняется), меняется только запуск zprobe-start и получение его вывода:
#   1) запуск — одно ssh: на сервере (вход root) папка /root/zprobe-b (0700, root, не ссылка) и в ней НОВАЯ папка серии
#      (mkdir без -p: есть — отказ EXISTS, ничего не запущено). zprobe-start запускается отвязанно (setsid -f), его
#      подлинный stdout — в start.out, stderr — в start.err, код выхода — в start.rc («rc=N»); все три — только новыми
#      файлами (noclobber), владелец root, права 0600. Ответ запуска — строка ZPROBE_B ACK (подтверждение).
#   2) потеря подтверждения или обрыв — НИКОГДА не повторный запуск, только чтение: короткие ssh раз в READ_PAUSE с, не
#      больше READ_TRIES раз (60 × 75 > WAIT_S 3600 сервера). Чтение печатает состояние; после start.rc — длину, SHA-256
#      и base64 обоих файлов. Принимаются только два подряд одинаковых итога DONE; байты start.out на телефоне — равны
#      сумме сервера. Любой дефект (папка или файл не тот, ссылка, лишний файл, рассогласование, гибель процесса без
#      кода, чужая серия, повтор строк) — «НЕВЕРНО», серия не принята, повтора нет.
#   3) дальше всё как v0.18: start.out проверяется на одну строку ZPROBE_STATUS TERMINAL своей серии и строку unit=,
#      журнал и отметки забираются всегда, zprobe_verify.py (без изменений) требует одну строку CONFIRMED в start.out.
#   Код выхода zprobe-start обязан согласоваться с итоговой строкой: 0 — CONFIRMED, 4 — UNKNOWN или JOURNAL_REFUSED.
#   Ключ отпечатка — phone_zprobe_series_b15b.sh в zprobe_pins.txt (манифест zavod/ops/zprobe_pins_b15b.txt).
# НАЗНАЧЕНИЕ: серия проб с телефона оператора (Termux), протокол Завода v4 ред12, И.13 п. 2–3.
# ВЫЗОВ: bash <папка>/zprobe_series_b15b.sh <серия>  (zprobe_verify.py, zprobe_rules.py, zprobe_pins.txt, anchors.log — там же)
# ОГРАНИЧЕНИЯ: ключ входа берётся из ~/.ssh/zadmin2 и никуда не копируется; ничего не удаляет ни на телефоне, ни на сервере.
set -euo pipefail
S=${1:?usage: zprobe_series_b15b.sh <series>}
[[ $S =~ ^[0-9A-Za-z_-]{1,40}$ ]] || { echo "НЕВЕРНО: bad series name"; exit 2; }
H=root@178.105.20.190
K=$HOME/.ssh/zadmin2
SO=(-i "$K" -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o ServerAliveCountMax=4)
W=$(cd "$(dirname "$0")" && pwd -P)
pin_ok() {
  local want got
  want=$(awk -v k="$1" '$1==k{print $2}' "$W/zprobe_pins.txt")
  got=$(sha256sum "$2" | cut -d' ' -f1)
  [ -n "$want" ] && [ "$want" = "$got" ] || { echo "НЕВЕРНО: $2 differs from zprobe_pins.txt"; exit 2; }
}
[ -s "$W/zprobe_pins.txt" ] || { echo "НЕВЕРНО: zprobe_pins.txt missing"; exit 2; }
pin_ok phone_zprobe_series_b15b.sh "$W/zprobe_series_b15b.sh"
pin_ok phone_zprobe_verify.py "$W/zprobe_verify.py"
pin_ok phone_zprobe_rules.py "$W/zprobe_rules.py"
RC=$(awk '$1=="release_commit"{print $2}' "$W/zprobe_pins.txt")
[[ $RC =~ ^[0-9a-f]{40}$ ]] || { echo "НЕВЕРНО: release_commit missing in zprobe_pins.txt"; exit 2; }
set +e
RO=$(ssh "${SO[@]}" "$H" cat /usr/local/lib/zavod/probes-b15/RELEASE 2>/dev/null; printf 'X%s' "$?")
set -e
RSSH=${RO##*X}; RBODY=${RO%X*}
WANT=$(printf 'commit=%s\nversion=3.5.5-b15\n_' "$RC")
{ [ "$RSSH" = 0 ] && [ "${RBODY}_" = "$WANT" ]; } || { echo "НЕВЕРНО: server release is not B15"; exit 2; }
mkdir "$W/$S" 2>/dev/null || { echo "НЕВЕРНО: series $S already started on this phone"; exit 2; }
C=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
[[ $C =~ ^[0-9a-f]{32}$ ]] || { echo "НЕВЕРНО: challenge"; exit 2; }
(set -C; echo "$C" > "$W/$S/challenge")
mkdir "$W/$S/programs" "$W/$S/read"
for f in zprobe_verify.py zprobe_rules.py zprobe_pins.txt; do (set -C; cat "$W/$f" > "$W/$S/programs/$f"); done
(cd "$W/$S/programs" && set -C && sha256sum zprobe_verify.py zprobe_rules.py zprobe_pins.txt > ../programs.sha256)

# Сценарий запуска на сервере. Весь текст — одна функция: при обрыве передачи неполный текст не выполняется.
LS=$(cat <<'EOS'
zb_launch() {
  set -u; umask 077
  local D=/root/zprobe-b S=$1 C=$2 Z=/usr/local/lib/zavod/probes-b15/zprobe-start P _
  [[ $S =~ ^[0-9A-Za-z_-]{1,40}$ && $C =~ ^[0-9a-f]{32}$ ]] || { echo "ZPROBE_B REFUSED args"; return 2; }
  [ -x "$Z" ] || { echo "ZPROBE_B REFUSED no_zprobe_start series=$S"; return 2; }
  if [ ! -e "$D" ] && [ ! -L "$D" ]; then mkdir -m 0700 "$D" || { echo "ZPROBE_B REFUSED base_mkdir series=$S"; return 2; }; fi
  { [ ! -L "$D" ] && [ "$(stat -c '%u %a %F' -- "$D")" = "0 700 directory" ]; } || { echo "ZPROBE_B REFUSED base_unsafe series=$S"; return 2; }
  mkdir -m 0700 "$D/$S" 2>/dev/null || { echo "ZPROBE_B REFUSED EXISTS series=$S"; return 2; }
  setsid -f bash -c 'set -C; cd / || exit 1; echo "$$" > "$1/pid" || exit 1; "$4" "$2" "$3" "ПБ-1" < /dev/null > "$1/start.out" 2> "$1/start.err"; printf "rc=%s\n" "$?" > "$1/start.rc"' zprobe-b "$D/$S" "$S" "$C" "$Z" < /dev/null > /dev/null 2>&1 || { echo "ZPROBE_B REFUSED setsid series=$S"; return 2; }
  for _ in $(seq 1 20); do [ -s "$D/$S/pid" ] && break; sleep 0.5; done
  P=$(cat "$D/$S/pid" 2>/dev/null) || P=
  [[ $P =~ ^[0-9]{1,9}$ ]] || { echo "ZPROBE_B NO_PID series=$S"; return 3; }
  echo "ZPROBE_B ACK series=$S pid=$P"
}
zb_launch "$@"
EOS
)
# Сценарий чтения: только чтение, ничего не создаёт и не меняет. Последняя строка ответа — ZPROBE_B READ_END.
RS=$(cat <<'EOS'
zb_read() {
  set -u
  local D=/root/zprobe-b S=$1 P f X PID A RCL OB EB
  r() { echo "ZPROBE_B STATE $* series=$S"; echo "ZPROBE_B READ_END"; exit 0; }
  okf() { [ ! -L "$1" ] && [ -f "$1" ] && case "$(stat -c '%u %a %h %F' -- "$1")" in "0 600 1 regular file"|"0 600 1 regular empty file") true;; *) false;; esac; }
  [[ $S =~ ^[0-9A-Za-z_-]{1,40}$ ]] || r BAD_ARGS
  P=$D/$S
  if [ ! -e "$D" ] && [ ! -L "$D" ]; then r ABSENT; fi
  { [ ! -L "$D" ] && [ "$(stat -c '%u %a %F' -- "$D" 2>/dev/null)" = "0 700 directory" ]; } || r UNSAFE what=base
  if [ ! -e "$P" ] && [ ! -L "$P" ]; then r ABSENT; fi
  { [ ! -L "$P" ] && [ "$(stat -c '%u %a %F' -- "$P" 2>/dev/null)" = "0 700 directory" ]; } || r UNSAFE what=dir
  X=$(ls -A "$P" | grep -vxE 'pid|start\.out|start\.err|start\.rc' | head -n 1) || true
  [ -z "$X" ] || r UNSAFE what=extra
  for f in pid start.out start.err start.rc; do
    if [ -e "$P/$f" ] || [ -L "$P/$f" ]; then okf "$P/$f" || r UNSAFE what=$f; fi
  done
  [ -e "$P/pid" ] || r NO_PID
  PID=$(cat "$P/pid")
  { [[ $PID =~ ^[0-9]{1,9}$ ]] && [ "$(wc -c < "$P/pid")" = "$(( ${#PID} + 1 ))" ]; } || r BAD_PID
  if [ ! -e "$P/start.rc" ]; then
    A=0
    if [ -r "/proc/$PID/cmdline" ] && tr '\0' '\n' < "/proc/$PID/cmdline" | grep -qxF "$P"; then A=1; fi
    if [ ! -e "$P/start.rc" ]; then
      [ "$A" = 1 ] && r RUNNING out_bytes="$(wc -c < "$P/start.out" 2>/dev/null || echo 0)"
      r CHILD_DEAD
    fi
  fi
  [ -n "$(tail -c 1 "$P/start.rc")" ] && r RC_PARTIAL
  RCL=$(cat "$P/start.rc")
  { [ "$(wc -c < "$P/start.rc")" -le 8 ] && [ "$(wc -l < "$P/start.rc")" = 1 ] && [[ $RCL =~ ^rc=[0-9]{1,3}$ ]]; } || r BAD_RC
  for f in start.out start.err; do [ -e "$P/$f" ] || r NO_FILE what=$f; done
  OB=$(wc -c < "$P/start.out"); EB=$(wc -c < "$P/start.err")
  [ "$OB" -le 1048576 ] && [ "$EB" -le 65536 ] || r TOO_BIG
  echo "ZPROBE_B STATE DONE $RCL out_bytes=$OB out_sha256=$(sha256sum < "$P/start.out" | cut -c1-64) err_bytes=$EB err_sha256=$(sha256sum < "$P/start.err" | cut -c1-64) series=$S"
  echo "ZPROBE_B OUT"; base64 -w 0 < "$P/start.out"; echo
  echo "ZPROBE_B ERR"; base64 -w 0 < "$P/start.err"; echo
  echo "ZPROBE_B READ_END"
}
zb_read "$@"
EOS
)
set +e
printf '%s\n' "$LS" | ssh "${SO[@]}" "$H" bash -s -- "$S" "$C" > "$W/$S/launch.out" 2> "$W/$S/launch.err"
LRC=$?
cat "$W/$S/launch.out"
ACK=0
if [ "$(grep -c '^ZPROBE_B ' "$W/$S/launch.out")" = 1 ] && grep -qxE "ZPROBE_B ACK series=$S pid=[0-9]{1,9}" "$W/$S/launch.out"; then ACK=1; fi
(set -C; echo "ZPROBE_B LAUNCH ssh_rc=$LRC ack=$ACK" > "$W/$S/launch.txt")
if grep -q '^ZPROBE_B REFUSED ' "$W/$S/launch.out"; then
  echo "НЕВЕРНО: сервер отказал в запуске ($(grep -m1 '^ZPROBE_B REFUSED ' "$W/$S/launch.out" | cut -c1-80)) — серия не запущена, повтора нет"
  exit 2
fi
READ_TRIES=${READ_TRIES:-75}; READ_PAUSE=${READ_PAUSE:-60}; ABSENT_MAX=${ABSENT_MAX:-3}
OUTCOME=; WHY=; PREV=; NABS=0; N=0
while [ "$N" -lt "$READ_TRIES" ]; do
  N=$((N + 1)); F=$W/$S/read/$(printf '%03d' "$N")
  printf '%s\n' "$RS" | ssh "${SO[@]}" "$H" bash -s -- "$S" > "$F.txt" 2> "$F.err"
  XRC=$?
  if [ "$XRC" != 0 ] || [ "$(tail -n 1 "$F.txt")" != "ZPROBE_B READ_END" ]; then   # RECONNECT / обрезанный ответ
    [ -n "$PREV" ] && echo "ЧТЕНИЕ $N: контрольное чтение сброшено"; PREV=; PREVF=
    echo "ЧТЕНИЕ $N: нет полного ответа (ssh_rc=$XRC) — только повтор чтения"; sleep "$READ_PAUSE"; continue
  fi
  if [ "$(grep -c '^ZPROBE_B READ_END$' "$F.txt")" != 1 ] || [ "$(grep -c '^ZPROBE_B STATE ' "$F.txt")" != 1 ]; then
    OUTCOME=BAD; WHY="read $N: повтор строк ответа"; break
  fi
  ST=$(grep '^ZPROBE_B STATE ' "$F.txt")
  case "$ST" in *" series=$S") ;; *) OUTCOME=BAD; WHY="read $N: чужая серия"; break;; esac
  KIND=$(printf '%s\n' "$ST" | cut -d' ' -f3)
  case "$KIND" in
    RUNNING|RC_PARTIAL)
      [ -n "$PREV" ] && echo "ЧТЕНИЕ $N: контрольное чтение сброшено"; PREV=; PREVF=
      NABS=0; echo "ЧТЕНИЕ $N: $KIND"; sleep "$READ_PAUSE"; continue;;
    ABSENT|NO_PID)
      [ -n "$PREV" ] && echo "ЧТЕНИЕ $N: контрольное чтение сброшено"; PREV=; PREVF=
      if [ "$ACK" = 1 ]; then OUTCOME=BAD; WHY="read $N: $KIND после подтверждения запуска"; break; fi
      NABS=$((NABS + 1)); echo "ЧТЕНИЕ $N: $KIND ($NABS из $ABSENT_MAX, подтверждения запуска не было)"
      if [ "$NABS" -ge "$ABSENT_MAX" ]; then OUTCOME=BAD; WHY="запуск не подтверждён и не найден ($KIND)"; break; fi
      sleep "$READ_PAUSE"; continue;;
    DONE) ;;
    *) OUTCOME=BAD; WHY="read $N: $(printf '%s\n' "$ST" | cut -d' ' -f3- | cut -c1-80)"; break;;
  esac
  [ "$(wc -l < "$F.txt")" = 6 ] && [ "$(sed -n 2p "$F.txt")" = "ZPROBE_B OUT" ] && [ "$(sed -n 4p "$F.txt")" = "ZPROBE_B ERR" ] \
    || { OUTCOME=BAD; WHY="read $N: форма ответа DONE"; break; }
  [[ $ST =~ ^ZPROBE_B\ STATE\ DONE\ rc=([0-9]{1,3})\ out_bytes=([0-9]+)\ out_sha256=([0-9a-f]{64})\ err_bytes=([0-9]+)\ err_sha256=([0-9a-f]{64})\ series=$S$ ]] \
    || { OUTCOME=BAD; WHY="read $N: строка DONE"; break; }
  ZRC=${BASH_REMATCH[1]}; OBY=${BASH_REMATCH[2]}; OSH=${BASH_REMATCH[3]}; EBY=${BASH_REMATCH[4]}; ESH=${BASH_REMATCH[5]}
  sed -n 3p "$F.txt" | base64 -d > "$F.out" 2>/dev/null; D1=$?
  sed -n 5p "$F.txt" | base64 -d > "$F.errout" 2>/dev/null; D2=$?
  if [ "$D1" != 0 ] || [ "$D2" != 0 ] || [ "$(wc -c < "$F.out")" != "$OBY" ] || [ "$(sha256sum < "$F.out" | cut -c1-64)" != "$OSH" ] \
     || [ "$(wc -c < "$F.errout")" != "$EBY" ] || [ "$(sha256sum < "$F.errout" | cut -c1-64)" != "$ESH" ]; then
    OUTCOME=BAD; WHY="read $N: байты не равны сумме сервера"; break
  fi
  if [ -z "$PREV" ]; then PREV=$ST; PREVF=$F; echo "ЧТЕНИЕ $N: DONE rc=$ZRC — контрольное чтение"; continue; fi
  if [ "$ST" = "$PREV" ]; then OUTCOME=DONE; break; fi
  OUTCOME=BAD; WHY="read $N: итог изменился между чтениями (подмена)"; break
done
[ -n "$OUTCOME" ] || { OUTCOME=BAD; WHY="нет итога за $READ_TRIES чтений"; }
SRC=255
if [ "$OUTCOME" = DONE ]; then
  (set -C; cat "$PREVF.out" > "$W/$S/start.out"; cat "$PREVF.errout" > "$W/$S/start.err"; echo "rc=$ZRC" > "$W/$S/start.rc")
  SRC=$ZRC
  echo "ZPROBE_B RESULT DONE rc=$ZRC out_sha256=$OSH"
else
  (set -C; : > "$W/$S/start.out")
  echo "НЕВЕРНО: $WHY — серия не принята, повторного запуска нет"
fi
cat "$W/$S/start.out"
NC=$(grep -c '^ZPROBE_START CONFIRMED ' "$W/$S/start.out")
NB=$(grep -cE '^ZPROBE_START (UNKNOWN|JOURNAL_REFUSED) ' "$W/$S/start.out")
COK=0
if [ "$OUTCOME" = DONE ]; then
  if [ "$ZRC" = 0 ] && [ "$NC" = 1 ] && [ "$NB" = 0 ]; then COK=1
  elif [ "$ZRC" = 4 ] && [ "$NC" = 0 ] && [ "$NB" = 1 ]; then echo "НЕВЕРНО: итог zprobe-start $(grep -oE '^ZPROBE_START (UNKNOWN|JOURNAL_REFUSED)' "$W/$S/start.out" | cut -d' ' -f2) — серия не принята"
  else echo "НЕВЕРНО: код zprobe-start $ZRC не согласован с итоговыми строками (CONFIRMED $NC, UNKNOWN/JOURNAL_REFUSED $NB)"; fi
fi
TERM_RE="^ZPROBE_STATUS TERMINAL series=$S "
TERM=0; NST=$(grep -c '^ZPROBE_STATUS ' "$W/$S/start.out")
if [ "$NST" = 1 ] && grep -q "$TERM_RE" "$W/$S/start.out"; then TERM=1
else echo "НЕВЕРНО: start.out — нужна ровно одна строка ZPROBE_STATUS TERMINAL series=$S (строк ZPROBE_STATUS: $NST)"; fi
UL="ZPROBE_START unit=zprobe-run-b15@$S.service fragment=/etc/systemd/system/zprobe-run-b15@.service"
UOK=0; [ "$(grep -c "^ZPROBE_START unit=" "$W/$S/start.out")" = 1 ] && grep -qxF "$UL" "$W/$S/start.out" && UOK=1
[ "$UOK" = 1 ] || echo "НЕВЕРНО: started unit is not zprobe-run-b15@$S (start.out) — серия не принята"
scp -r "${SO[@]}" "${H}:/var/lib/zavod/probes/started" "$W/$S/started"; MRC=$?
scp -r "${SO[@]}" "${H}:/var/lib/zavod/probes/journal" "$W/$S/journal"; JRC=$?
[ -d "$W/$S/started" ] || mkdir "$W/$S/started"
[ -d "$W/$S/journal" ] || mkdir "$W/$S/journal"
(set -C; echo "ZPROBE_FETCH ssh_rc=$SRC started_rc=$MRC journal_rc=$JRC" > "$W/$S/fetch.txt")
cat "$W/$S/fetch.txt"
A=-
if [ -s "$W/anchors.log" ]; then A=$W/$S/anchor_in.txt; (set -C; tail -n 1 "$W/anchors.log" > "$A"); fi
python3 "$W/zprobe_verify.py" "$W/$S/journal" "$S" "$C" "$W/zprobe_pins.txt" "$A" | tee "$W/$S/verdict.txt"
VRC=${PIPESTATUS[0]}
set -e
if grep -q '| chain=OK |' "$W/$S/verdict.txt"; then
  NA=$(sed -n 's/.*| anchor=\([0-9]*\):\([0-9a-f]\{64\}\)$/\1 \2/p' "$W/$S/verdict.txt")
  if [ -n "$NA" ]; then
    if grep -qxF "$NA" "$W/anchors.log" 2>/dev/null; then echo "ЯКОРЬ $NA уже есть в anchors.log — не дописан"; else echo "$NA" >> "$W/anchors.log"; fi
  fi
fi
echo "ИТОГ: $(head -n 1 "$W/$S/verdict.txt" | cut -d'|' -f1)"
(set -C; grep '^ZPROBE_TIMES ' "$W/$S/verdict.txt" > "$W/$S/times.txt") || true
[ "$SRC" = 0 ] && [ "$MRC" = 0 ] && [ "$JRC" = 0 ] || echo "ВНИМАНИЕ: сбой связи, сервера или zprobe-start ($(cat "$W/$S/fetch.txt")) — серия не принята, даже если выше ВЕРНО"
echo "Приёмка шага: папка $W/$S целиком — на компьютер; там (программа сама сверит fetch.txt и programs.sha256)"
PS=$(sha256sum "$W/zprobe_pins.txt" | cut -d' ' -f1)
echo "  git show <коммит отпечатков>:zavod/ops/zprobe_pins_b15b.txt > manifest.txt"
echo "  echo '$PS  manifest.txt' | sha256sum -c -        # до --refs: должно быть manifest.txt: OK, иначе манифест чужой"
echo "  cd <папка серии> && python3 -I -B programs/zprobe_verify.py journal $S <вызов из challenge> manifest.txt - --refs refs_before.txt refs_after.txt --fetch fetch.txt"
[ "$OUTCOME" = DONE ] && [ "$COK" = 1 ] && [ "$SRC" = 0 ] && [ "$MRC" = 0 ] && [ "$JRC" = 0 ] && [ "$UOK" = 1 ] && [ "$TERM" = 1 ] && exit "$VRC"
exit 3
