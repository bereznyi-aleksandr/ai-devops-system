-- ДОКУМЕНТ: db/probe_final_ext04_mutation.sql
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-11-01 13:47 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 13:47 +02:00
-- ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
-- НАЗНАЧЕНИЕ: проба Z-EXT-04 — бронь запуска без проверки «другая сессия жива» ловит итоговая проверка
--   (FINAL_ZAVOD_FN_BODY_MISMATCH: lease_reserve_start). Подмена в транзакции и не фиксируется.
\set ON_ERROR_STOP on
BEGIN;
DO $probe$
DECLARE
    d text := pg_get_functiondef('bem_control.lease_reserve_start(uuid)'::regprocedure);
    a text := 'IF EXISTS (SELECT 1 FROM bem_control.session_start WHERE status IN (''STARTING'', ''RUNNING'')) THEN';
BEGIN
    IF position(a IN d) = 0 THEN
        RAISE EXCEPTION 'PROBE_ANCHOR_MISSING';
    END IF;
    EXECUTE replace(d, a, 'IF false THEN');
END
$probe$;
\ir 05_final_state_check_ext01.sql
ROLLBACK;
