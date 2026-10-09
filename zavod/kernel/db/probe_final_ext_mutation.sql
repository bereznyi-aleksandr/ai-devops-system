-- ДОКУМЕНТ: db/probe_final_ext_mutation.sql
-- ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
-- ДАТА СОЗДАНИЯ: 2026-10-07 17:08 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 17:08 +03:00
-- ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
-- НАЗНАЧЕНИЕ: проба аудита Z3 M-Z3-01. Внутри транзакции подменяет claim_outbox_batch так, что
--   истёкшая аренда после начала отправки больше не уходит в UNKNOWN_OUTCOME, и запускает
--   05_final_state_check_ext01.sql. Ожидаемо: отказ FINAL_ZAVOD_FN_BODY_MISMATCH; изменение
--   не фиксируется (ошибка обрывает транзакцию, сессия закрывается без COMMIT).
-- ВЫЗОВ: psql -v ON_ERROR_STOP=1 -U postgres -d bem -f db/probe_final_ext_mutation.sql  (код ≠ 0 — норма)
\set ON_ERROR_STOP on
BEGIN;
DO $probe$
DECLARE
    d text := pg_get_functiondef('bem_control.claim_outbox_batch(integer, interval, text)'::regprocedure);
BEGIN
    IF position('AND NOT coalesce(o.send_policy_idempotent, false)' IN d) = 0 THEN
        RAISE EXCEPTION 'PROBE_ANCHOR_MISSING';
    END IF;
    EXECUTE replace(d, 'AND NOT coalesce(o.send_policy_idempotent, false)', 'AND false');
END
$probe$;
\ir 05_final_state_check_ext01.sql
ROLLBACK;
