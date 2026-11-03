-- ДОКУМЕНТ: db/probe_final_ext05_mutation.sql
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 22:56 +02:00
-- ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
-- НАЗНАЧЕНИЕ: проба Z-EXT-05 (карта 3.3.10.3) — таблица команд агента без принудительных правил строк (владелец
--   читал бы её мимо политики) ловится итоговой проверкой (FINAL_RLS_MISMATCH: bem_control.gate_command).
--   Подмена в транзакции и не фиксируется.
\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE bem_control.gate_command NO FORCE ROW LEVEL SECURITY;
\ir 05_final_state_check_ext01.sql
ROLLBACK;
