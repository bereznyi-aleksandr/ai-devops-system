-- ДОКУМЕНТ: db/07_zavod_ext_05.sql (расширение Z-EXT-05: привратник команд агента, карта 3.3.10.1–3.3.10.3)
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 22:56 +02:00
-- ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
-- ОСНОВАНИЕ: протокол v3.1 И.7а п.1–3 (привратник, только заранее написанные запросы, правила строк), ПБ-5 (повтор).
-- НАЗНАЧЕНИЕ: (1) входная роль zgate — её получает только служба привратника (peer, сопоставление zavod_gate);
--   (2) таблица команд агента bem_control.gate_command: одна строка на команду, одноразовый номер (nonce) — один
--       раз на всю базу; правила строк (RLS — какие строки видит запрос) включены с FORCE: строки видит только
--       тот, кто поставил номер заказчика своей аренды (app.tenant_id), даже владелец таблицы;
--   (3) журнал решений привратника bem_control.gate_command_log (и приём, и каждый отказ);
--   (4) gate_accept — одной операцией: формат значений, аренда команды = аренда собеседника (SO_PEERCRED),
--       сумма тела совпала, аренда открыта, сессия этой аренды работает, тело — JSON строгого вида из списка
--       видов, номер не встречался → запись. Номер заказчика берётся только из аренды. Ответ — слово;
--   (5) gate_command_status — если привратник не узнал итог записи (обрыв связи с базой), он сначала сверяет базу.
-- ОГРАНИЧЕНИЯ: ставится после 06_zavod_ext_04.sql и до итоговой проверки одной транзакцией; не меняет
--   существующие таблицы, строки и функции. Текст агента в запрос не вклеивается: тело приходит параметром
--   (bytea), разбирается здесь же. Список видов команд — допущение до описания команд ядра (вопрос аудитору).

-- (0) Входная роль привратника. Без пароля, без особых признаков, без членств.
CREATE ROLE zgate LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT;
GRANT CONNECT ON DATABASE bem TO zgate;
GRANT USAGE ON SCHEMA bem_control TO zgate;

-- (1) Команды агента. Строки только добавляются; читает ядро в рамках своего заказчика.
CREATE TABLE bem_control.gate_command (
    command_id  uuid NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL,
    lease_id    uuid NOT NULL REFERENCES bem_control.chat_lease (lease_id),
    nonce       text NOT NULL CHECK (nonce ~ '^[0-9a-f]{64}$'),
    body_sha256 text NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
    kind        text NOT NULL CHECK (kind IN ('HEARTBEAT', 'PROGRESS', 'QUESTION', 'ARCHIVE_READY')),
    args        jsonb NOT NULL CHECK (jsonb_typeof(args) = 'object'),
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT gate_command_nonce_once UNIQUE (nonce)
);
ALTER TABLE bem_control.gate_command OWNER TO bem_control_owner;
ALTER TABLE bem_control.gate_command ENABLE ROW LEVEL SECURITY;
ALTER TABLE bem_control.gate_command FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON bem_control.gate_command
    USING (tenant_id = bem_core.current_tenant()) WITH CHECK (tenant_id = bem_core.current_tenant());
REVOKE ALL ON bem_control.gate_command FROM PUBLIC;
GRANT SELECT ON bem_control.gate_command TO bem_kernel_rw;
GRANT SELECT ON bem_control.gate_command TO backup_reader;

-- (2) Журнал решений привратника. Строки только добавляются. Номер аренды и одноразовый номер пишутся, только
--     если они правильного вида: мусор агента в журнал не попадает.
CREATE TABLE bem_control.gate_command_log (
    log_id   uuid NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    lease_id uuid,
    nonce    text CHECK (nonce ~ '^[0-9a-f]{64}$'),
    outcome  text NOT NULL CHECK (outcome IN ('ACCEPTED', 'BAD_COMMAND', 'PEER_MISMATCH', 'SHA_MISMATCH', 'LEASE_NOT_OPEN',
                                              'SESSION_NOT_RUNNING', 'NONCE_REPLAY')),
    at       timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX gate_command_log_at ON bem_control.gate_command_log (at);
ALTER TABLE bem_control.gate_command_log OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.gate_command_log FROM PUBLIC;
GRANT SELECT ON bem_control.gate_command_log TO backup_reader;

-- (3) Приём команды. Ответы: 'ACCEPTED <command_id>' или слово отказа из журнала. Исключений наружу нет:
--     любой отказ записан в журнал и возвращён словом.
CREATE FUNCTION bem_control.gate_accept(p_lease_id uuid, p_peer_lease uuid, p_nonce text, p_sha256 text, p_body bytea)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_nonce  text := CASE WHEN p_nonce ~ '^[0-9a-f]{64}$' THEN p_nonce END;
    v_tenant uuid;
    v_status text;
    v_run    text;
    v_cmd    jsonb;
    v_keys   integer;
    v_id     uuid;
    v_out    text;
BEGIN
    IF p_lease_id IS NULL OR p_peer_lease IS NULL OR v_nonce IS NULL OR p_sha256 IS NULL
       OR p_sha256 !~ '^[0-9a-f]{64}$' OR p_body IS NULL OR length(p_body) NOT BETWEEN 2 AND 16384 THEN
        v_out := 'BAD_COMMAND';
    ELSIF p_lease_id <> p_peer_lease THEN
        v_out := 'PEER_MISMATCH';
    ELSIF encode(sha256(p_body), 'hex') <> p_sha256 THEN
        v_out := 'SHA_MISMATCH';
    END IF;
    IF v_out IS NULL THEN
        -- Строка аренды заперта до конца операции: закрыть аренду между проверкой и записью нельзя.
        SELECT tenant_id, status INTO v_tenant, v_status FROM bem_control.chat_lease WHERE lease_id = p_lease_id FOR SHARE;
        IF v_status IS DISTINCT FROM 'OPEN' THEN
            v_out := 'LEASE_NOT_OPEN';
        ELSE
            SELECT status INTO v_run FROM bem_control.session_start WHERE lease_id = p_lease_id FOR SHARE;
            IF v_run IS DISTINCT FROM 'RUNNING' THEN v_out := 'SESSION_NOT_RUNNING'; END IF;
        END IF;
    END IF;
    IF v_out IS NULL THEN
        -- Строгий вид: объект ровно с ключами kind и args, без повторов ключей (json хранит повторы, jsonb — нет),
        -- kind — строка из списка, args — объект. Ошибка разбора — тот же отказ.
        BEGIN
            v_cmd := convert_from(p_body, 'UTF8')::jsonb;
            SELECT count(*) INTO v_keys FROM json_object_keys(convert_from(p_body, 'UTF8')::json);
        EXCEPTION WHEN OTHERS THEN
            v_cmd := NULL;
        END;
        IF v_cmd IS NULL OR jsonb_typeof(v_cmd) <> 'object' OR v_keys <> 2
           OR NOT (v_cmd ? 'kind' AND v_cmd ? 'args')
           OR jsonb_typeof(v_cmd -> 'kind') <> 'string' OR jsonb_typeof(v_cmd -> 'args') <> 'object'
           OR (v_cmd ->> 'kind') NOT IN ('HEARTBEAT', 'PROGRESS', 'QUESTION', 'ARCHIVE_READY') THEN
            v_out := 'BAD_COMMAND';
        END IF;
    END IF;
    IF v_out IS NULL THEN
        -- Номер заказчика — только из аренды; правила строк проверяют его при записи (WITH CHECK).
        PERFORM set_config('app.tenant_id', v_tenant::text, true);
        INSERT INTO bem_control.gate_command (tenant_id, lease_id, nonce, body_sha256, kind, args)
        VALUES (v_tenant, p_lease_id, v_nonce, p_sha256, v_cmd ->> 'kind', v_cmd -> 'args')
        ON CONFLICT (nonce) DO NOTHING
        RETURNING command_id INTO v_id;
        PERFORM set_config('app.tenant_id', '', true);
        v_out := CASE WHEN v_id IS NULL THEN 'NONCE_REPLAY' ELSE 'ACCEPTED' END;
    END IF;
    INSERT INTO bem_control.gate_command_log (lease_id, nonce, outcome)
    VALUES (CASE WHEN v_out = 'BAD_COMMAND' AND v_status IS NULL THEN NULL ELSE p_lease_id END, v_nonce, v_out);
    RETURN CASE WHEN v_out = 'ACCEPTED' THEN 'ACCEPTED ' || v_id ELSE v_out END;
END;
$$;
ALTER FUNCTION bem_control.gate_accept(uuid, uuid, text, text, bytea) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.gate_accept(uuid, uuid, text, text, bytea) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.gate_accept(uuid, uuid, text, text, bytea) TO zgate;

-- (4) Сверка после обрыва: 'ACCEPTED <command_id>' — команда этой аренды с этим номером записана; 'NONE' — нет.
CREATE FUNCTION bem_control.gate_command_status(p_lease_id uuid, p_nonce text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_tenant uuid;
    v_id     uuid;
BEGIN
    IF p_lease_id IS NULL OR p_nonce IS NULL OR p_nonce !~ '^[0-9a-f]{64}$' THEN RETURN 'NONE'; END IF;
    SELECT tenant_id INTO v_tenant FROM bem_control.chat_lease WHERE lease_id = p_lease_id;
    IF v_tenant IS NULL THEN RETURN 'NONE'; END IF;
    PERFORM set_config('app.tenant_id', v_tenant::text, true);
    SELECT command_id INTO v_id FROM bem_control.gate_command WHERE lease_id = p_lease_id AND nonce = p_nonce;
    PERFORM set_config('app.tenant_id', '', true);
    RETURN CASE WHEN v_id IS NULL THEN 'NONE' ELSE 'ACCEPTED ' || v_id END;
END;
$$;
ALTER FUNCTION bem_control.gate_command_status(uuid, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.gate_command_status(uuid, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.gate_command_status(uuid, text) TO zgate;
