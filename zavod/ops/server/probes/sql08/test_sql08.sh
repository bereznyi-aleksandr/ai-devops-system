#!/usr/bin/env bash
# ДОКУМЕНТ: test_sql08.sh (испытание команды «установка SQL 08» на PostgreSQL 16 с цепочкой базы до Z-EXT-05)
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-15 21:40 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-15 22:25 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальные чаты f23e7e60 (v0.1) и 3ff53398 (v0.2).
# v0.2 (аудит REL81): S09 переменные PG* не действуют; S10 чужая база → отказ; S11 изменён внутренний триггер внешнего
#   ключа на chat_lease → откат; S12 два внутренних триггера на chat_lease есть и включены; S13a/b неясный итог psql
#   (поддельный psql) → INSTALL_OUTCOME_UNKNOWN / COMMITTED_FINAL_CHECK_FAILED, rc=5, без слов «rolled back».
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
GOT=$(grep -o 'digest [0-9a-f]\{64\}' <<< "$O" | head -1 | cut -d' ' -f2 || true)
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
"${PSQL[@]}" -c "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity WHERE query LIKE '%pg_sleep(40)%' AND pid <> pg_backend_pid()" > /dev/null
wait "$LP" 2>/dev/null || true
# 10. Чужая цель (база postgres вместо bem) → отказ до изменений (REL81 M-01)
O=$(printf %s%s%s "$W1" "$S8" "$W2" | runuser -u postgres -- psql -X -A -t -q -v ON_ERROR_STOP=1 -d postgres \
  -v expect="$EXP" -f - 2>&1 || true)
grep -q 'SQL08_REFUSED: wrong target' <<< "$O" && absent && ok S10_wrong_target || bad S10_wrong_target "$O"
# 11. Изменён внутренний триггер внешнего ключа на прежней chat_lease → сумма добавленного другая → откат (REL81 M-02)
O=$(core "$EXP" $'\nDO $q$ DECLARE t text; BEGIN FOR t IN SELECT tgname FROM pg_trigger WHERE tgrelid = \'bem_control.chat_lease\'::regclass AND tgisinternal AND tgconstrrelid = \'bem_control.lease_seal\'::regclass LOOP EXECUTE format(\'ALTER TABLE bem_control.chat_lease DISABLE TRIGGER %I\', t); END LOOP; END $q$;\n' || true)
grep -q 'SQL08_REFUSED: added' <<< "$O" && absent && ok S11_internal_fk_trigger || bad S11_internal_fk_trigger "$O"
# 13. Итог psql неясен (REL81 L-01): поддельный psql вместо настоящего, база не трогается
printf '#!/bin/sh\ncat >/dev/null; echo "ZPROBE_B10_SQL08_CHECKED added=1 digest=x"; echo "server closed the connection"; exit 2\n' > "$T/fake1"
printf '#!/bin/sh\ncat >/dev/null; echo "ZPROBE_B10_SQL08_CHECKED added=1 digest=x"; echo ZPROBE_B10_SQL08_COMMITTED; exit 3\n' > "$T/fake2"
chmod 755 "$T/fake1" "$T/fake2"
REAL='LC_ALL=C.UTF-8 psql -X'
fake() { local c; c=$(variant "$T/p4"); bash -c "${c/"$REAL"/"LC_ALL=C.UTF-8 $T/$1 -X"}" 2>&1 | tr -d '\r'; }
[ "$(grep -o "$REAL" <<< "$CMD" | wc -l)" = 1 ] || bad S13_setup "psql call not found once"
O=$(fake fake1); grep -q '^INSTALL_OUTCOME_UNKNOWN: COMMIT not confirmed' <<< "$O" && grep -q '^rc=5$' <<< "$O" \
  && ! grep -q 'rolled back' <<< "$O" && absent && ok S13a_outcome_unknown || bad S13a_outcome_unknown "$O"
O=$(fake fake2); grep -q '^ZPROBE_B10_SQL08=COMMITTED_FINAL_CHECK_FAILED' <<< "$O" && grep -q '^rc=5$' <<< "$O" \
  && ! grep -q 'rolled back' <<< "$O" && ok S13b_committed_check_failed || bad S13b_committed_check_failed "$O"
# 5. Штатная установка
O=$(run "$T/p4")
grep -q '^ZPROBE_B10_SQL08_CHECKED added=[0-9]* digest=[0-9a-f]* target=socket:5432/bem datadir=' <<< "$O" \
  && grep -qx 'ZPROBE_B10_SQL08_COMMITTED' <<< "$O" && grep -q '^rc=0$' <<< "$O" \
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

# 9. Переменные PG* у вызывающего не уводят команду: она всё равно приходит в bem через сокет (REL81 M-01)
O=$(PGHOST=/nonexistent PGPORT=1 PGSERVICE=zz_none PGDATABASE=postgres PGUSER=nobody PGOPTIONS='-c search_path=zz' run "$T/p4")
grep -q 'SQL08_ALREADY_PRESENT' <<< "$O" && grep -q '^rc=3$' <<< "$O" && ok S09_env_ignored || bad S09_env_ignored "$O"
# 12. Внутренние триггеры внешнего ключа lease_seal → chat_lease есть (2 на chat_lease) и включены
R=$("${PSQL[@]}" -c "SELECT count(*) FILTER (WHERE tgenabled = 'O') || '/' || count(*) FROM pg_trigger WHERE tgrelid = 'bem_control.chat_lease'::regclass AND tgisinternal AND tgconstrrelid = 'bem_control.lease_seal'::regclass")
[ "$R" = '2/2' ] && ok S12_fk_triggers_present || bad S12_fk_triggers_present "$R"

echo "SQL08_CI fails=$fails"
[ "$fails" = 0 ] && echo SQL08_CI=PASS
[ "$fails" = 0 ]
