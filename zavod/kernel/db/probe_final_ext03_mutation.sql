-- ДОКУМЕНТ: db/probe_final_ext03_mutation.sql
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-10-18 10:38 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 10:38 +03:00
-- ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
-- НАЗНАЧЕНИЕ: проба Z-EXT-03 (пакет Z-TRANSPORT-01). Внутри транзакции подменяет lookup_session_credential так,
--   что отозванный пропуск снова принимается (убрана проверка revoked_at), и запускает
--   05_final_state_check_ext01.sql. Ожидаемо: отказ FINAL_ZAVOD_FN_BODY_MISMATCH: lookup_session_credential;
--   изменение не фиксируется (ошибка обрывает транзакцию, сессия закрывается без COMMIT).
-- ВЫЗОВ: psql -v ON_ERROR_STOP=1 -U postgres -d bem -f db/probe_final_ext03_mutation.sql  (код ≠ 0 — норма)
\set ON_ERROR_STOP on
BEGIN;
DO $probe$
DECLARE
    d text := pg_get_functiondef('bem_control.lookup_session_credential(text, text)'::regprocedure);
    a text := 'IF v_cred.revoked_at IS NOT NULL THEN';
BEGIN
    IF position(a IN d) = 0 THEN
        RAISE EXCEPTION 'PROBE_ANCHOR_MISSING';
    END IF;
    EXECUTE replace(d, a, 'IF false THEN');
END
$probe$;
\ir 05_final_state_check_ext01.sql
ROLLBACK;
