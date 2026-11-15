#!/usr/bin/env bash
# ДОКУМЕНТ: test_sql08.sh (испытание команды «установка SQL 08» на PostgreSQL 16 с цепочкой базы до Z-EXT-05)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-15 21:40 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-15 21:40 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат f23e7e60.
# ЗАПУСК (от root): test_sql08.sh <строка команды CMD> <sql08_wrap.sql> <08_zavod_ext_06.sql> <05_final_state_check_ext01.sql>
# Строка команды испытывается своими байтами; заменяются ровно два места: путь пакета P и тело pkg_ok (оно дословно из
# допущенной VERIFY v0.1 и здесь проверяется только на равенство). Каждая проверка — одно нарушение.
set -euo pipefail
CMD=$(cat "$1"); WRAP=$2; SQL=$3; FINAL=$4
export TERM=dumb
T=$(mktemp -d); chmod 755 "$T"
PSQL=(runuser -u postgres -- psql -X -A -t -q -v ON_ERROR_STOP=1 -d bem)
fails=0
ok() { echo "PASS $1"; }
bad() { echo "FAIL $1: $2"; fails=$((fails + 1)); }
absent() { [ "$("${PSQL[@]}" -c "SELECT coalesce(to_regclass('bem_control.lease_seal')::text,'')||coalesce(to_regprocedure('bem_control.lease_seal_unstarted(text,uuid,text)')::text,'')" 2>/dev/null)" = "" ]; }

P_OLD='P=/var/lib/zavod/probes-pkg-cad786a7158b;'
pre=${CMD%%'pkg_ok || {'*}; PKG_DEF="pkg_ok() {${pre#*'pkg_ok() {'}"
NEW_DEF='pkg_ok() { [ -d "$P" ]; }; '
[ "$(grep -o "$P_OLD" <<< "$CMD" | wc -l)" = 1 ] && [ "${#PKG_DEF}" -gt 300 ] || { echo "FAIL setup"; exit 1; }
variant() {  # $1 — папка пакета-подставы
  local c=${CMD/"$P_OLD"/"P=$1;"}
  printf '%s' "${c/"$PKG_DEF"/"$NEW_DEF"}"
}
mkpkg() {  # $1 — папка, $2 — файл, который положить как 08
  mkdir -p "$1/zavod/kernel/db"; cp "$2" "$1/zavod/kernel/db/08_zavod_ext_06.sql"; chmod -R a+rX "$1"
}
run() { bash -c "$(variant "$1")" 2>&1 | tr -d '\r'; }

# 0. Ожидаемая сумма добавленного: та, что в строке команды, должна совпасть с суммой этой цепочки
EXP=$(grep -o 'expect=[0-9a-f]\{64\}' <<< "$CMD" | cut -d= -f2)
M='--@@SQL08@@'; W=$(cat "$WRAP"; printf x); W=${W%x}; S8=$(cat "$SQL"; printf x); S8=${S8%x}
W1=${W%%"$M"*}; W2=${W#*"$M"}
core() {  # $1 — expect, $2 — добавка после файла 08
  printf %s%s%s%s "$W1" "$S8" "$2" "$W2" | "${PSQL[@]}" -v expect="$1" -f - 2>&1
}
O=$(core PRINT '' || true)
GOT=$(grep -o 'digest [0-9a-f]\{64\}' <<< "$O" | head -1 | cut -d' ' -f2)
echo "SQL08_EXPECT_DIGEST=$GOT"
[ -n "$GOT" ] && [ "$GOT" = "$EXP" ] && absent && ok S00_digest || bad S00_digest "command has $EXP, chain gives ${GOT:-none}: $(tail -3 <<< "$O")"

# 1. Другой файл 08 в пакете → отказ до базы
printf '\n-- x\n' | cat "$SQL" - > "$T/s08x.sql"; mkpkg "$T/p1" "$T/s08x.sql"
O=$(run "$T/p1"); grep -q 'REFUSED: 08_zavod_ext_06.sql differs; nothing run' <<< "$O" && grep -q '^rc=1$' <<< "$O" && absent \
  && ok S01_other_sql || bad S01_other_sql "$O"
# 2. Изменение прежнего объекта в той же транзакции → откат
O=$(core "$EXP" $'\nGRANT SELECT ON bem_control.chat_lease TO PUBLIC;\n' || true)
grep -q 'SQL08_REFUSED: 1 existing catalog rows removed or changed' <<< "$O" && absent && ok S02_changed_old || bad S02_changed_old "$O"
# 3. Лишний новый объект → другая сумма → откат
O=$(core "$EXP" $'\nCREATE TABLE bem_control.zz_extra (i int);\n' || true)
grep -q 'SQL08_REFUSED: added' <<< "$O" && absent && [ -z "$("${PSQL[@]}" -c "SELECT to_regclass('bem_control.zz_extra')")" ] \
  && ok S03_extra_object || bad S03_extra_object "$O"
# 4. Таблица аренды занята чужой транзакцией → ожидание не дольше lock_timeout, откат
mkpkg "$T/p4" "$SQL"
"${PSQL[@]}" -c "BEGIN; LOCK TABLE bem_control.chat_lease IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(40); COMMIT;" > /dev/null 2>&1 &
LP=$!; sleep 3
s=$(date +%s); O=$(run "$T/p4"); e=$(( $(date +%s) - s ))
grep -q 'ZPROBE_B10_SQL08=FAIL rolled back' <<< "$O" && grep -q '^rc=3$' <<< "$O" && grep -q 'lock timeout' <<< "$O" \
  && [ "$e" -lt 30 ] && absent && ok S04_lock_timeout || bad S04_lock_timeout "e=$e $O"
kill "$LP" 2>/dev/null || true; wait "$LP" 2>/dev/null || true
# 5. Штатная установка
O=$(run "$T/p4")
grep -q '^ZPROBE_B10_SQL08_CHECKED added=[0-9]* digest=' <<< "$O" && grep -q '^rc=0$' <<< "$O" \
  && grep -qx 'ZPROBE_B10_SQL08=OK table=bem_control.lease_seal function=bem_control.lease_seal_unstarted(text,uuid,text)' <<< "$O" \
  && ok S05_install || bad S05_install "$O"
# 6. После установки база равна цепочке CI с Z-EXT-06: терминальная проверка 05 проходит
"${PSQL[@]}" --single-transaction -f "$FINAL" > "$T/final1.out" 2>&1 && ok S06_final_check || bad S06_final_check "$(tail -5 "$T/final1.out")"
# 7. Повтор → отказ, ничего не меняется, проверка 05 снова проходит
O=$(run "$T/p4")
grep -q 'SQL08_ALREADY_PRESENT' <<< "$O" && grep -q '^rc=3$' <<< "$O" \
  && "${PSQL[@]}" --single-transaction -f "$FINAL" > "$T/final2.out" 2>&1 && ok S07_repeat || bad S07_repeat "$O"
# 8. Права функции: EXECUTE только у владельца, SECURITY DEFINER, строк печати нет
R=$("${PSQL[@]}" -c "SELECT p.prosecdef::text||'|'||pg_get_userbyid(p.proowner)||'|'||coalesce(p.proacl::text,'-')||'|'||(SELECT count(*) FROM bem_control.lease_seal) FROM pg_proc p WHERE p.oid = 'bem_control.lease_seal_unstarted(text,uuid,text)'::regprocedure")
[ "$R" = 'true|bem_control_owner|{bem_control_owner=X/bem_control_owner}|0' ] && ok S08_function_rights || bad S08_function_rights "$R"

echo "SQL08_CI fails=$fails"
[ "$fails" = 0 ] && echo SQL08_CI=PASS
[ "$fails" = 0 ]
