#!/usr/bin/env bash
# ДОКУМЕНТ: test_r2cmd.sh (испытание команды оператора R2 — печать остатка pb1trial2 с проверкой папки только чтением)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-16 20:51 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель), сменщик после HANDOFF_20261116_1916.
# НАЗНАЧЕНИЕ: REL90 L-355-REL90-02 без переустановки B10. Команда CMD_R2.txt до запуска установленного zprobe-start
#   сама проверяет только чтением путь /var/lib/zavod/preserve/pb1trial2 так же, как S.open_root (каждый шаг от / —
#   каталог, не ссылка, root:root, без записи для группы и всех) и суммы установленных zprobe_r2.py и zprobe-start
#   (= выпуск B10, коммит cad786a71). Не сошлось — R2=REFUSED_INPUT precheck:…, rc=2, zprobe-start не запускается.
# ЗАПУСК (от root, одноразовая машина CI, fetch-depth 0): test_r2cmd.sh <CMD_R2.txt>
#   Команда испытывается своими байтами. Папки /usr/local/lib/zavod/probes-b10 и /var/lib/zavod/preserve этой машины,
#   если есть, отодвигаются в *.ci-aside (машина одноразовая). Печать ни в одной проверке не доходит до базы.
set -euo pipefail
CMD=$(cat "$1")
export TERM=dumb
REL=cad786a71
L=/usr/local/lib/zavod/probes-b10
PV=/var/lib/zavod/preserve
H=$PV/pb1trial2
SEAL=/var/lib/zavod/seal
fails=0
ok() { echo "PASS $1"; }
bad() { echo "FAIL $1: $2"; fails=$((fails + 1)); }
run() { bash -c "$1" 2>&1 | tr -d '\r' | sed 's/\x1b\[[0-9;]*[A-Za-z]//g'; }   # clear при TERM=dumb
body() { grep -v '^rc=' <<< "$1"; }
[ "$(id -u)" = 0 ] || { echo "FAIL setup not_root"; exit 1; }
for d in "$L" "$PV"; do [ -e "$d" ] && mv "$d" "$d.ci-aside.$$"; done
[ -e "$SEAL" ] && { echo "FAIL setup seal_exists"; exit 1; }
T=$(mktemp -d)
git archive "$REL" zavod/ops/server/probes | tar -x -C "$T"
install -d -m 0755 -o root -g root /usr/local/lib/zavod "$L"
for f in "$T"/zavod/ops/server/probes/*.py; do install -m 0644 -o root -g root "$f" "$L/"; done
install -m 0755 -o root -g root "$T/zavod/ops/server/probes/zprobe-start" "$L/zprobe-start"
install -d -m 0755 -o root -g root /var/lib/zavod "$PV"
reset_home() { rm -rf --one-file-system "$H" "$H.away"; install -d -m 0700 -o root -g root "$H"; }

# P00. Суммы в команде = файлы выпуска B10 (коммит cad786a71), байты команды — те, что в хранилище
grep -qF "$(sha256sum < "$L/zprobe_r2.py" | cut -c1-64)" <<< "$CMD" \
  && grep -qF "$(sha256sum < "$L/zprobe-start" | cut -c1-64)" <<< "$CMD" && ok P00_release_sums || bad P00_release_sums "-"
# P01. Нет папки pb1trial2 → precheck:not_dir, rc=2, zprobe-start не запущен
reset_home; rmdir "$H"
O=$(run "$CMD")
[ "$(body "$O")" = "R2=REFUSED_INPUT precheck:not_dir:$H" ] && grep -qx 'rc=2' <<< "$O" && ok P01_no_dir || bad P01_no_dir "$O"
# P02. pb1trial2 — ссылка на верную папку → not_dir
reset_home; mv "$H" "$H.away"; ln -s "$H.away" "$H"
O=$(run "$CMD")
[ "$(body "$O")" = "R2=REFUSED_INPUT precheck:not_dir:$H" ] && grep -qx 'rc=2' <<< "$O" && ok P02_symlink || bad P02_symlink "$O"
rm -f "$H"
# P03. Владелец не root → owner
reset_home; chown 65534:65534 "$H"
O=$(run "$CMD")
[ "$(body "$O")" = "R2=REFUSED_INPUT precheck:owner:$H:65534:65534:700" ] && grep -qx 'rc=2' <<< "$O" \
  && ok P03_owner || bad P03_owner "$O"
# P04. Запись для группы (0770) → mode
reset_home; chmod 0770 "$H"
O=$(run "$CMD")
[ "$(body "$O")" = "R2=REFUSED_INPUT precheck:mode:$H:0:0:770" ] && grep -qx 'rc=2' <<< "$O" && ok P04_group_w || bad P04_group_w "$O"
# P05. Запись для всех у родителя preserve (0757) → mode на preserve
reset_home; chmod 0757 "$PV"
O=$(run "$CMD")
[ "$(body "$O")" = "R2=REFUSED_INPUT precheck:mode:$PV:0:0:757" ] && grep -qx 'rc=2' <<< "$O" && ok P05_parent_w || bad P05_parent_w "$O"
chmod 0755 "$PV"
# P06/P07. Установленный zprobe_r2.py или zprobe-start не те → r2_sha / start_sha
reset_home; cp -p "$L/zprobe_r2.py" "$T/r2.keep"; printf '\n' >> "$L/zprobe_r2.py"
O=$(run "$CMD")
[ "$(body "$O")" = "R2=REFUSED_INPUT precheck:r2_sha" ] && grep -qx 'rc=2' <<< "$O" && ok P06_r2_sha || bad P06_r2_sha "$O"
cp -p "$T/r2.keep" "$L/zprobe_r2.py"
cp -p "$L/zprobe-start" "$T/st.keep"; printf '\n' >> "$L/zprobe-start"
O=$(run "$CMD")
[ "$(body "$O")" = "R2=REFUSED_INPUT precheck:start_sha" ] && grep -qx 'rc=2' <<< "$O" && ok P07_start_sha || bad P07_start_sha "$O"
cp -p "$T/st.keep" "$L/zprobe-start"
# P08. Папка верная, но пустая → R2_PRECHECK=OK, дальше настоящий zprobe_r2.py выпуска отказывает на state.json
#   (R2=REFUSED_INPUT preserve:…, rc=2) — значит exec дошёл до установленной программы; seal не создан
reset_home
O=$(run "$CMD")
[ "$(body "$O" | head -1)" = R2_PRECHECK=OK ] && body "$O" | sed -n 2p | grep -q '^R2=REFUSED_INPUT preserve:' \
  && [ "$(body "$O" | wc -l)" = 2 ] && grep -qx 'rc=2' <<< "$O" && [ ! -e "$SEAL" ] && ok P08_exec_installed || bad P08_exec_installed "$O"
# P09. Не root → zprobe-start отказывает (must run as root), rc=2
O=$(runuser -u nobody -- bash -c "$CMD" 2>&1 | tr -d '\r')
grep -qx 'ZPROBE_START REFUSED: must run as root' <<< "$O" && grep -qx 'rc=2' <<< "$O" && ok P09_not_root || bad P09_not_root "$O"
# P10. Ни одна проверка не создала seal и не тронула preserve, кроме папок самого теста
[ ! -e "$SEAL" ] && [ "$(ls -A "$PV")" = pb1trial2 ] && ok P10_nothing_written || bad P10_nothing_written "$(ls -A "$PV" /var/lib/zavod)"

echo "R2CMD_CI fails=$fails"
[ "$fails" = 0 ] && echo R2CMD_CI=PASS
[ "$fails" = 0 ]
