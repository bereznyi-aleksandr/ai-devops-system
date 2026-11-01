-- ДОКУМЕНТ: db/06_zavod_ext_04.sql (расширение Z-EXT-04: запуск сессий агента, карта 3.3.8.5)
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-11-01 13:47 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 13:47 +02:00
-- ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
-- ОСНОВАНИЕ: протокол v3.1 И.12а (zagent-start, lease_reserve_start, lease_mark_running, после перезагрузки).
-- НАЗНАЧЕНИЕ: (1) входная роль zstarter — её получает только root ячейки (peer, сопоставление zavod_cell);
--   (2) состояние запуска аренды bem_control.session_start: ЗАПУСКАЕТСЯ (STARTING) → РАБОТАЕТ (RUNNING);
--       ЗАПУСК_НЕ_УДАЛСЯ (START_FAILED) — нет отметки «работает» за 2 минуты или перезагрузка;
--       ПРЕРВАНА (INTERRUPTED) — служба не жива, аренда открыта; ЗАВЕРШЕНА (ENDED) — служба не жива, аренда закрыта;
--   (3) журнал bem_control.session_start_log — по нему считается предел 6 запусков в минуту;
--   (4) lease_reserve_start — одной операцией: аренда открыта, запуска у неё не было, нет другой сессии в
--       STARTING или RUNNING, предел минуты не превышен → STARTING и строка журнала. Ответ — слово, без исключений;
--   (5) lease_mark_running — STARTING → RUNNING не позже 2 минут, иначе START_FAILED (вызывает ядро от сессии);
--   (6) lease_start_reconcile — сверка с живыми службами (вызывает zagent-start каждый проход).
-- ОГРАНИЧЕНИЯ: ставится после 04_zavod_ext_03.sql и до итоговой проверки одной транзакцией; не меняет
--   существующие таблицы, строки и функции. Срока у аренды bem_control.chat_lease нет — условие протокола
--   «аренда не истекла» сведено к «аренда OPEN» (вопрос аудитору). Повторный запуск той же аренды не
--   разрешён: новая сессия — новая аренда.

-- (0) Входная роль запуска. Без пароля, без особых признаков, без членств.
CREATE ROLE zstarter LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT;
GRANT CONNECT ON DATABASE bem TO zstarter;
GRANT USAGE ON SCHEMA bem_control TO zstarter;

-- (1) Состояние запуска: одна строка на аренду, живая (STARTING или RUNNING) — одна на всю ячейку.
CREATE TABLE bem_control.session_start (
    lease_id    uuid NOT NULL PRIMARY KEY REFERENCES bem_control.chat_lease (lease_id),
    status      text NOT NULL CHECK (status IN ('STARTING', 'RUNNING', 'START_FAILED', 'INTERRUPTED', 'ENDED')),
    reserved_at timestamptz NOT NULL DEFAULT now(),
    running_at  timestamptz,
    ended_at    timestamptz,
    CONSTRAINT session_start_shape CHECK (
           (status = 'STARTING'     AND running_at IS NULL     AND ended_at IS NULL)
        OR (status = 'RUNNING'      AND running_at IS NOT NULL AND ended_at IS NULL)
        OR (status = 'START_FAILED' AND running_at IS NULL     AND ended_at IS NOT NULL)
        OR (status IN ('INTERRUPTED', 'ENDED') AND running_at IS NOT NULL AND ended_at IS NOT NULL))
);
CREATE UNIQUE INDEX session_start_one_live ON bem_control.session_start ((true))
    WHERE status IN ('STARTING', 'RUNNING');
ALTER TABLE bem_control.session_start OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.session_start FROM PUBLIC;
GRANT SELECT ON bem_control.session_start TO backup_reader;

-- (2) Журнал запуска. Строки только добавляются.
CREATE TABLE bem_control.session_start_log (
    log_id   uuid NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    lease_id uuid NOT NULL,
    outcome  text NOT NULL CHECK (outcome IN ('RESERVED', 'ALREADY_STARTED', 'LEASE_NOT_OPEN', 'RUNNING',
                                              'START_FAILED', 'INTERRUPTED', 'ENDED')),
    at       timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX session_start_log_at ON bem_control.session_start_log (at) WHERE outcome = 'RESERVED';
ALTER TABLE bem_control.session_start_log OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.session_start_log FROM PUBLIC;
GRANT SELECT ON bem_control.session_start_log TO backup_reader;

-- (3) Бронь запуска. Ответы: RESERVED, ALREADY_STARTED, LEASE_NOT_OPEN (запрос в архив без запуска),
--     BUSY, RATE_LIMITED (запрос остаётся до следующего прохода). Таблица запирается целиком на время
--     решения: два прохода zagent-start не могут занять две живые сессии.
CREATE FUNCTION bem_control.lease_reserve_start(p_lease_id uuid)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_status text;
BEGIN
    IF p_lease_id IS NULL THEN RETURN 'LEASE_NOT_OPEN'; END IF;
    LOCK TABLE bem_control.session_start IN EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM bem_control.session_start WHERE lease_id = p_lease_id) THEN
        INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (p_lease_id, 'ALREADY_STARTED');
        RETURN 'ALREADY_STARTED';
    END IF;
    SELECT status INTO v_status FROM bem_control.chat_lease WHERE lease_id = p_lease_id FOR SHARE;
    IF v_status IS DISTINCT FROM 'OPEN' THEN
        INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (p_lease_id, 'LEASE_NOT_OPEN');
        RETURN 'LEASE_NOT_OPEN';
    END IF;
    IF EXISTS (SELECT 1 FROM bem_control.session_start WHERE status IN ('STARTING', 'RUNNING')) THEN
        RETURN 'BUSY';
    END IF;
    IF (SELECT count(*) FROM bem_control.session_start_log
         WHERE outcome = 'RESERVED' AND at > clock_timestamp() - interval '60 seconds') >= 6 THEN
        RETURN 'RATE_LIMITED';
    END IF;
    INSERT INTO bem_control.session_start (lease_id, status, reserved_at) VALUES (p_lease_id, 'STARTING', clock_timestamp());
    INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (p_lease_id, 'RESERVED');
    RETURN 'RESERVED';
END;
$$;
ALTER FUNCTION bem_control.lease_reserve_start(uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.lease_reserve_start(uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.lease_reserve_start(uuid) TO zstarter;

-- (4) Отметка «сессия работает». Ответы: RUNNING; TOO_LATE (прошло 2 минуты — START_FAILED);
--     NOT_STARTING (нет брони в STARTING).
CREATE FUNCTION bem_control.lease_mark_running(p_lease_id uuid)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_row bem_control.session_start;
BEGIN
    SELECT * INTO v_row FROM bem_control.session_start WHERE lease_id = p_lease_id FOR UPDATE;
    IF NOT FOUND OR v_row.status <> 'STARTING' THEN RETURN 'NOT_STARTING'; END IF;
    IF v_row.reserved_at <= clock_timestamp() - interval '2 minutes' THEN
        UPDATE bem_control.session_start SET status = 'START_FAILED', ended_at = clock_timestamp()
         WHERE lease_id = p_lease_id;
        INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (p_lease_id, 'START_FAILED');
        RETURN 'TOO_LATE';
    END IF;
    UPDATE bem_control.session_start SET status = 'RUNNING', running_at = clock_timestamp()
     WHERE lease_id = p_lease_id;
    INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (p_lease_id, 'RUNNING');
    RETURN 'RUNNING';
END;
$$;
ALTER FUNCTION bem_control.lease_mark_running(uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.lease_mark_running(uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.lease_mark_running(uuid) TO bem_kernel_rw;

-- (5) Сверка с живыми службами zagent@. p_boot — первый проход после загрузки: всё STARTING → START_FAILED.
--     Иначе STARTING старше 2 минут → START_FAILED. RUNNING без живой службы → ENDED, если аренда закрыта,
--     иначе INTERRUPTED. Возвращает число изменённых строк.
CREATE FUNCTION bem_control.lease_start_reconcile(p_live uuid[], p_boot boolean)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    r     record;
    v_n   integer := 0;
    v_new text;
BEGIN
    IF p_live IS NULL OR p_boot IS NULL THEN RAISE EXCEPTION 'RECONCILE_ARGS_REQUIRED'; END IF;
    LOCK TABLE bem_control.session_start IN EXCLUSIVE MODE;
    FOR r IN SELECT s.lease_id, s.status, s.reserved_at, l.status AS lease_status
               FROM bem_control.session_start s
               JOIN bem_control.chat_lease l ON l.lease_id = s.lease_id
              WHERE s.status IN ('STARTING', 'RUNNING')
    LOOP
        v_new := NULL;
        IF r.status = 'STARTING' AND (p_boot OR r.reserved_at <= clock_timestamp() - interval '2 minutes') THEN
            v_new := 'START_FAILED';
        ELSIF r.status = 'RUNNING' AND (p_boot OR NOT (r.lease_id = ANY (p_live))) THEN
            v_new := CASE WHEN r.lease_status = 'COMPLETED' THEN 'ENDED' ELSE 'INTERRUPTED' END;
        END IF;
        IF v_new IS NOT NULL THEN
            UPDATE bem_control.session_start SET status = v_new, ended_at = clock_timestamp()
             WHERE lease_id = r.lease_id;
            INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (r.lease_id, v_new);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    RETURN v_n;
END;
$$;
ALTER FUNCTION bem_control.lease_start_reconcile(uuid[], boolean) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.lease_start_reconcile(uuid[], boolean) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.lease_start_reconcile(uuid[], boolean) TO zstarter;
