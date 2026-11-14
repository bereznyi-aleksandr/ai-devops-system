-- ДОКУМЕНТ: db/08_zavod_ext_06.sql (расширение Z-EXT-06: печать аренды пробы без сессии, выпуск B10, шаг 3.5.5)
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-11-14 21:48 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 21:48 +02:00
-- ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 08» (32cd5105-15f9-40e6-8d25-a2f0c46066f1)
-- ОСНОВАНИЕ: проект DESIGN_B10_3_5_5_20261114_v0_17.md, раздел 4.2 (принят ChatGPT REL61 AGREED 0/0/1,
--   B10_CODE_ALLOWED=YES). Аудит кода — отдельно.
-- НАЗНАЧЕНИЕ: (1) таблица-признак bem_control.lease_seal: аренда пробы закрыта печатью «сессии не было»
--       (NO_SESSION_PRE_START) по файлу доказательств proof.json (его SHA-256);
--   (2) функция bem_control.lease_seal_unstarted — одной операцией: проверки по порядку договора 4.2, затем три
--       вставки с одним временем: lease_seal, session_start (START_FAILED), session_start_log (START_FAILED).
--       Ответы — слово: SEALED_NOW, ALREADY_SEALED, REFUSED_CALLER, REFUSED_ARGS, REFUSED_INCONSISTENT,
--       REFUSED_HAS_SESSION, REFUSED_NOT_OWN, REFUSED_HAS_LOG, REFUSED_HAS_GATE.
--   После печати lease_reserve_start по этой аренде навсегда отвечает ALREADY_STARTED (06_zavod_ext_04.sql).
-- ОГРАНИЧЕНИЯ: ставится после 07_zavod_ext_05.sql одной транзакцией (BEGIN … COMMIT); только CREATE новых
--   объектов, существующие таблицы, строки и функции не меняются (объект уже есть → ошибка и откат всего).
--   Вызвать функцию может только суперпользователь (на сервере — root через runuser -u postgres); EXECUTE не
--   выдаётся никому. Граница прав — root: функция защищает от ошибок и несогласованности, не от root.

-- (1) Таблица-признак печати. Одна строка на аренду; строки только добавляются (UPDATE и DELETE не выдаются).
CREATE TABLE bem_control.lease_seal (
    lease_id     uuid NOT NULL PRIMARY KEY REFERENCES bem_control.chat_lease (lease_id),
    series       text NOT NULL CHECK (series ~ '^[0-9A-Za-z_-]{1,40}$'),
    reason       text NOT NULL CHECK (reason = 'NO_SESSION_PRE_START'),
    proof_sha256 text NOT NULL CHECK (proof_sha256 ~ '^[0-9a-f]{64}$'),
    sealed_at    timestamptz NOT NULL,
    sealed_by    name NOT NULL DEFAULT session_user
);
ALTER TABLE bem_control.lease_seal OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.lease_seal FROM PUBLIC;
GRANT SELECT ON bem_control.lease_seal TO backup_reader;

-- (2) Печать аренды пробы без сессии. Порядок блокировок как в lease_reserve_start: сначала вся таблица
--     session_start (EXCLUSIVE), затем строка аренды FOR SHARE; бронь запуска ждёт конца печати, взаимной
--     блокировки нет. Исключения не перехватываются: любая ошибка откатывает всё.
CREATE FUNCTION bem_control.lease_seal_unstarted(p_series text, p_lease_id uuid, p_proof_sha256 text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_super  boolean;
    v_seal   bem_control.lease_seal;
    v_start  bem_control.session_start;
    v_lease  bem_control.chat_lease;
    v_failed integer;
    v_other  integer;
    v_now    timestamptz;
BEGIN
    -- 0) вызывающий: только суперпользователь (session_user — тот, кто вошёл, а не владелец функции).
    SELECT r.rolsuper INTO v_super FROM pg_catalog.pg_roles r WHERE r.rolname = session_user;
    IF v_super IS DISTINCT FROM true THEN
        RETURN 'REFUSED_CALLER';
    END IF;

    -- 1) аргументы.
    IF p_series IS NULL OR p_series !~ '^[0-9A-Za-z_-]{1,40}$'
       OR p_proof_sha256 IS NULL OR p_proof_sha256 !~ '^[0-9a-f]{64}$'
       OR p_lease_id IS NULL THEN
        RETURN 'REFUSED_ARGS';
    END IF;

    LOCK TABLE bem_control.session_start IN EXCLUSIVE MODE;
    SELECT l.* INTO v_lease FROM bem_control.chat_lease l WHERE l.lease_id = p_lease_id FOR SHARE;

    -- 2) печать уже есть: повтор с тем же доказательством и чистой «историей печати» → ALREADY_SEALED.
    SELECT s.* INTO v_seal FROM bem_control.lease_seal s WHERE s.lease_id = p_lease_id;
    IF FOUND THEN
        SELECT st.* INTO v_start FROM bem_control.session_start st WHERE st.lease_id = p_lease_id;
        IF NOT FOUND
           OR v_seal.series <> p_series
           OR v_seal.proof_sha256 <> p_proof_sha256
           OR v_start.status <> 'START_FAILED'
           OR v_start.running_at IS NOT NULL
           OR v_start.reserved_at <> v_seal.sealed_at
           OR v_start.ended_at IS DISTINCT FROM v_seal.sealed_at THEN
            RETURN 'REFUSED_INCONSISTENT';
        END IF;
        SELECT count(*) INTO v_failed FROM bem_control.session_start_log g
         WHERE g.lease_id = p_lease_id AND g.outcome = 'START_FAILED' AND g.at = v_seal.sealed_at;
        SELECT count(*) INTO v_other FROM bem_control.session_start_log g
         WHERE g.lease_id = p_lease_id
           AND NOT (g.outcome = 'START_FAILED' AND g.at = v_seal.sealed_at)
           AND NOT (g.outcome = 'ALREADY_STARTED' AND g.at >= v_seal.sealed_at);
        IF v_failed <> 1 OR v_other <> 0 THEN
            RETURN 'REFUSED_INCONSISTENT';
        END IF;
        RETURN 'ALREADY_SEALED';
    END IF;

    -- 3) у аренды есть строка запуска без печати (в том числе настоящий неудачный запуск).
    IF EXISTS (SELECT 1 FROM bem_control.session_start st WHERE st.lease_id = p_lease_id) THEN
        RETURN 'REFUSED_HAS_SESSION';
    END IF;

    -- 4) аренда своя: открыта бегунком пробы этой серии на роль установочной пробы.
    IF v_lease.lease_id IS NULL
       OR v_lease.status <> 'OPEN'
       OR v_lease.opened_by <> 'zprobe-run'
       OR v_lease.holder_session <> ('zprobe-' || p_series)
       OR v_lease.role_key <> '01_install_probe' THEN
        RETURN 'REFUSED_NOT_OWN';
    END IF;

    -- 5) у аренды нет следов журнала запуска и команд агента.
    IF EXISTS (SELECT 1 FROM bem_control.session_start_log g WHERE g.lease_id = p_lease_id) THEN
        RETURN 'REFUSED_HAS_LOG';
    END IF;
    IF EXISTS (SELECT 1 FROM bem_control.gate_command c WHERE c.lease_id = p_lease_id) THEN
        RETURN 'REFUSED_HAS_GATE';
    END IF;

    -- 6) три вставки с одним временем.
    v_now := pg_catalog.clock_timestamp();
    INSERT INTO bem_control.lease_seal (lease_id, series, reason, proof_sha256, sealed_at)
         VALUES (p_lease_id, p_series, 'NO_SESSION_PRE_START', p_proof_sha256, v_now);
    INSERT INTO bem_control.session_start (lease_id, status, reserved_at, running_at, ended_at)
         VALUES (p_lease_id, 'START_FAILED', v_now, NULL, v_now);
    INSERT INTO bem_control.session_start_log (lease_id, outcome, at)
         VALUES (p_lease_id, 'START_FAILED', v_now);
    RETURN 'SEALED_NOW';
END;
$$;
ALTER FUNCTION bem_control.lease_seal_unstarted(text, uuid, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.lease_seal_unstarted(text, uuid, text) FROM PUBLIC;
