-- ДОКУМЕНТ: db/probe_final_ext02_mutation.sql
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-10-18 00:08 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 00:08 +03:00
-- ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
-- НАЗНАЧЕНИЕ: проба Z-EXT-02 (проект v1.2 §6). Внутри транзакции подменяет activate_rules так, что правила
--   включаются без выпуска проверенной версии (убрана проверка RULES_AUDIT_NOT_RELEASED), и запускает
--   05_final_state_check_ext01.sql. Ожидаемо: отказ FINAL_ZAVOD_FN_BODY_MISMATCH: activate_rules; изменение не
--   фиксируется (ошибка обрывает транзакцию, сессия закрывается без COMMIT).
-- ВЫЗОВ: psql -v ON_ERROR_STOP=1 -U postgres -d bem -f db/probe_final_ext02_mutation.sql  (код ≠ 0 — норма)
\set ON_ERROR_STOP on
BEGIN;
DO $probe$
DECLARE
    d text := pg_get_functiondef('bem_control.activate_rules(uuid, text, text, integer, text, uuid, jsonb, jsonb, jsonb)'::regprocedure);
    a text := $a$IF v_subject.released_at IS NULL THEN RAISE EXCEPTION 'RULES_AUDIT_NOT_RELEASED'; END IF;$a$;
BEGIN
    IF position(a IN d) = 0 THEN
        RAISE EXCEPTION 'PROBE_ANCHOR_MISSING';
    END IF;
    EXECUTE replace(d, a, 'NULL;');
END
$probe$;
\ir 05_final_state_check_ext01.sql
ROLLBACK;
