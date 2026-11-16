#!/usr/bin/env bash
# ДОКУМЕНТ: test_r2cmd.sh (испытание команды оператора R2 — проверка только чтением, затем печать остатка pb1trial2)
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-16 20:51 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-16 21:08 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель), сменщик после HANDOFF_20261116_1916.
# v0.2 (REL91B M-01, L-01, L-02): команда — части CMD_R2_PARTS.txt (тело r2_precheck.sh); папка программ B10 ставится
#   из пакета выпуска (zprobe-release-3.5.5-b10.sh коммита 64a04f634) целями установщика B10 (ci_install_lib.py);
#   P00 — список команды = цели установщика; подмена любого модуля (zprobe_unstarted.py), лишний файл, режим, ссылка —
#   отказ ДО exec; чужой PATH не влияет; код всей вставки = rc.
# ЗАПУСК (от root, одноразовая машина CI, fetch-depth 0, из корня хранилища): test_r2cmd.sh <CMD_R2_PARTS.txt> <r2_precheck.sh>
#   Папки /usr/local/lib/zavod/probes-b10 и /var/lib/zavod/preserve этой машины, если есть, отодвигаются в *.ci-aside.
set -euo pipefail
CMD=$(cat "$1"); BODY=$2
export TERM=dumb
RELSH=64a04f634
D=$(cd "$(dirname "$0")" && pwd)
L=/usr/local/lib/zavod/probes-b10
PV=/var/lib/zavod/preserve
H=$PV/pb1trial2
SEAL=/var/lib/zavod/seal
fails=0
ok() { echo "PASS $1"; }
bad() { echo "FAIL $1: $2"; fails=$((fails + 1)); }
RC=
run() {  # ставит O (вывод) и RC (код всей вставки) в этой оболочке; bash — по абсолютному пути, как у оператора
  set +e; /bin/bash -c "$1" > "$T/out" 2>&1; RC=$?; set -e
  O=$(tr -d '\r' < "$T/out" | sed 's/\x1b\[[0-9;]*[A-Za-z]//g')
}
body() { grep -v '^rc=' <<< "$1" | sed '/^$/d'; }
refused() {  # $1 — имя, $2 — вывод, $3 — ожидаемая строка отказа
  [ "$(body "$2")" = "$3" ] && grep -qx 'rc=2' <<< "$2" && [ "$RC" = 2 ] && ok "$1" || bad "$1" "RC=$RC $2"
}
[ "$(id -u)" = 0 ] || { echo "FAIL setup not_root"; exit 1; }
for d in "$L" "$PV"; do [ -e "$d" ] && mv "$d" "$d.ci-aside.$$"; done
[ -e "$SEAL" ] && { echo "FAIL setup seal_exists"; exit 1; }
T=$(mktemp -d)
git show "$RELSH:zavod/ops/server/probes/zprobe-release-3.5.5-b10.sh" > "$T/rel.sh"
TS=$(sed -n 's/^TS=\([0-9a-f]\{64\}\)$/\1/p' "$T/rel.sh")
sed -n '/^__ZPROBE_PKG_BASE64__$/,$p' "$T/rel.sh" | tail -n +2 | base64 -d > "$T/pkg.tar"
[ "$(sha256sum < "$T/pkg.tar" | cut -c1-64)" = "$TS" ] || { echo "FAIL setup package_sum"; exit 1; }
mkdir "$T/pkg"; tar -C "$T/pkg" --no-same-owner -xf "$T/pkg.tar"
install -d -m 0755 -o root -g root /usr/local/lib/zavod
python3 -I -B "$D/ci_install_lib.py" "$T/pkg" > "$T/targets.txt"
install -d -m 0755 -o root -g root /var/lib/zavod "$PV"
reset_home() { rm -rf --one-file-system "$H" "$H.away"; install -d -m 0700 -o root -g root "$H"; }
keep() { cp -p "$L/$1" "$T/keep.$1"; }
back() { rm -f "$L/$1"; cp -p "$T/keep.$1" "$L/$1"; }

# P00. Список команды (имя, режим, сумма) = цели установщика B10 из пакета выпуска; тело команды = r2_precheck.sh
EXP=$(sed -n "/^EXP='/,/'\$/p" "$BODY" | sed "s/^EXP='//; s/'\$//" | sort)
[ "$(wc -l < "$T/targets.txt")" = 16 ] && [ "$EXP" = "$(sort "$T/targets.txt")" ] \
  && grep -qF "$(sha256sum < "$BODY" | cut -c1-64)" <<< "$CMD" && ok P00_list_equals_installer_targets \
  || bad P00_list_equals_installer_targets "$(diff <(echo "$EXP") <(sort "$T/targets.txt") | head -5)"
# P01. Нет папки pb1trial2
reset_home; rmdir "$H"; run "$CMD"; refused P01_no_dir "$O" "R2=REFUSED_INPUT precheck:not_dir:$H"
# P02. pb1trial2 — ссылка
reset_home; mv "$H" "$H.away"; ln -s "$H.away" "$H"; run "$CMD"; refused P02_symlink "$O" "R2=REFUSED_INPUT precheck:not_dir:$H"
rm -f "$H"
# P03. Владелец не root
reset_home; chown 65534:65534 "$H"; run "$CMD"; refused P03_owner "$O" "R2=REFUSED_INPUT precheck:owner:$H:65534:65534:700"
# P04. Запись для группы у родителя preserve
reset_home; chmod 0775 "$PV"; run "$CMD"; refused P04_parent_w "$O" "R2=REFUSED_INPUT precheck:mode:$PV:0:0:775"; chmod 0755 "$PV"
# P05. Запись для всех у папки программ B10
reset_home; chmod 0757 "$L"; run "$CMD"; refused P05_lib_w "$O" "R2=REFUSED_INPUT precheck:mode:$L:0:0:757"; chmod 0755 "$L"
# P06. Подменён импортируемый модуль zprobe_unstarted.py (REL91B M-01), два главных файла те же → отказ до exec
reset_home; keep zprobe_unstarted.py; printf '\n# x\n' >> "$L/zprobe_unstarted.py"
run "$CMD"; refused P06_module_swapped "$O" "R2=REFUSED_INPUT precheck:sha:zprobe_unstarted.py"; back zprobe_unstarted.py
# P07. Подменён zprobe_r2.py
reset_home; keep zprobe_r2.py; printf '\n' >> "$L/zprobe_r2.py"
run "$CMD"; refused P07_r2_swapped "$O" "R2=REFUSED_INPUT precheck:sha:zprobe_r2.py"; back zprobe_r2.py
# P08. Лишнее в папке программ (__pycache__) → lib_set
reset_home; mkdir "$L/__pycache__"; run "$CMD"; refused P08_extra_pycache "$O" "R2=REFUSED_INPUT precheck:lib_set"; rmdir "$L/__pycache__"
# P09. Режим файла другой (0600) → file_attr
reset_home; chmod 0600 "$L/zprobe_seal.py"; run "$CMD"; refused P09_file_mode "$O" "R2=REFUSED_INPUT precheck:file_attr:zprobe_seal.py:0:0:600"
chmod 0644 "$L/zprobe_seal.py"
# P10. Модуль заменён ссылкой на верную копию → not_file
reset_home; keep zprobe_checks.py; rm -f "$L/zprobe_checks.py"; ln -s "$T/keep.zprobe_checks.py" "$L/zprobe_checks.py"
run "$CMD"; refused P10_module_symlink "$O" "R2=REFUSED_INPUT precheck:not_file:zprobe_checks.py"; back zprobe_checks.py
# P11. Всё верно, preserve пустой → R2_PRECHECK=OK, затем настоящий zprobe_r2.py выпуска: REFUSED_INPUT preserve:, rc=2
reset_home; run "$CMD"
[ "$(body "$O" | head -1)" = "R2_PRECHECK=OK files=16 lib=$L" ] && body "$O" | sed -n 2p | grep -q '^R2=REFUSED_INPUT preserve:' \
  && [ "$(body "$O" | wc -l)" = 2 ] && grep -qx 'rc=2' <<< "$O" && [ "$RC" = 2 ] && [ ! -e "$SEAL" ] \
  && ok P11_exec_installed || bad P11_exec_installed "RC=$RC $O"
# P12. Чужой PATH у вызывающего (поддельные stat, sha256sum, cut, clear, tail, bash) не влияет: исход как P11
mkdir "$T/evil"; for u in stat sha256sum cut clear tail sort ls bash env base64 gunzip; do
  printf '#!/bin/sh\necho EVIL_%s\nexit 0\n' "$u" > "$T/evil/$u"; chmod 755 "$T/evil/$u"; done
reset_home; PATH="$T/evil:$PATH" run "$CMD"
! grep -q EVIL <<< "$O" && [ "$(body "$O" | head -1)" = "R2_PRECHECK=OK files=16 lib=$L" ] && [ "$RC" = 2 ] \
  && ok P12_caller_path_ignored || bad P12_caller_path_ignored "RC=$RC $O"
# P13. Испорчен один знак в первой части → transport_sha, ничего не запущено, код 2
reset_home; C2=$(sed '1s/^G=.\(.\)/G='"'"'\1\1/' <<< "$CMD"); run "$C2"
[ "$(body "$O" | grep -v '^R2_PART')" = 'R2=REFUSED_INPUT transport_sha' ] && grep -qx 'rc=2' <<< "$O" && [ "$RC" = 2 ] \
  && ok P13_transport_sha || bad P13_transport_sha "RC=$RC $O"
# P14. Части печатают R2_PARTi/n и длину (как ждёт оператор)
run "$CMD"; grep -q '^R2_PART1/2 1900$' <<< "$O" && ok P14_part_marks || bad P14_part_marks "$O"
# P15. Не root → проверка проходит, zprobe-start отказывает; код 2
reset_home; set +e; O=$(runuser -u nobody -- bash -c "$CMD" 2>&1); RC=$?; set -e
grep -qx 'ZPROBE_START REFUSED: must run as root' <<< "$O" && grep -qx 'rc=2' <<< "$O" && [ "$RC" = 2 ] \
  && ok P15_not_root || bad P15_not_root "RC=$RC $O"
# P16. Ни одна проверка не создала seal; папка программ снова равна целям
[ ! -e "$SEAL" ] && [ "$(cd "$L" && ls -A | LC_ALL=C sort)" = "$(cut -d' ' -f3 "$T/targets.txt" | LC_ALL=C sort)" ] \
  && ok P16_nothing_written || bad P16_nothing_written "$(ls -A /var/lib/zavod "$L")"

echo "R2CMD_CI fails=$fails"
[ "$fails" = 0 ] && echo R2CMD_CI=PASS
[ "$fails" = 0 ]
