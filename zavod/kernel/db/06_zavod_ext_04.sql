-- ДОКУМЕНТ: db/06_zavod_ext_04.sql (расширение Z-EXT-04: запуск сессий агента, карта 3.3.8.5)
-- ВЕРСИЯ: v0.6  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-11-01 13:47 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 21:03 +02:00 (v0.6: аудит M33-R2-01 — lease_stop_check запирает строку аренды до конца транзакции; v0.5: срок аренды — LEASE_EXPIRED через 30 минут, сеанс 4 часа; v0.4: аудит M33-06 — тревоги клетки в таблице cell_alert с доставкой оператору; v0.3: аудит M33-02 — остановка только при открытой аренде; v0.2: аудит C33-01 — живая служба место не освобождает)
-- ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
-- ОСНОВАНИЕ: протокол v3.1 И.12а (zagent-start, lease_reserve_start, lease_mark_running, после перезагрузки).
-- НАЗНАЧЕНИЕ: (1) входная роль zstarter — её получает только root ячейки (peer, сопоставление zavod_cell);
--   (2) состояние запуска аренды bem_control.session_start: ЗАПУСКАЕТСЯ (STARTING) → РАБОТАЕТ (RUNNING);
--       ЗАПУСК_НЕ_УДАЛСЯ (START_FAILED) — нет отметки «работает» за 2 минуты или перезагрузка;
--       ПРЕРВАНА (INTERRUPTED) — служба не жива, аренда открыта; ЗАВЕРШЕНА (ENDED) — служба не жива, аренда закрыта;
--   (3) журнал bem_control.session_start_log — по нему считается предел 6 запусков в минуту;
--   (3а) срок аренды (вопрос аудитора «а»): запуск не позже 30 минут после открытия (LEASE_EXPIRED), сеанс не дольше 4 часов;
--   (4) lease_reserve_start — одной операцией: аренда открыта, запуска у неё не было, нет другой сессии в
--       STARTING или RUNNING, предел минуты не превышен → STARTING и строка журнала. Ответ — слово, без исключений;
--   (5) lease_mark_running — STARTING → RUNNING не позже 2 минут, иначе TOO_LATE без смены состояния (вызывает ядро);
--   (6) lease_start_reconcile — сверка с живыми службами (вызывает zagent-start каждый проход);
--   (7) lease_start_overdue — брони STARTING старше 2 минут: их живые службы zagent-start останавливает;
--   (8) lease_stop_check — остановка по заявке ядра только при открытой аренде (И.12 п.4, аудит M33-02);
--       строка аренды заперта до конца транзакции: закрыть аренду, пока идёт остановка, нельзя (M33-R2-01);
--   (9) тревоги клетки bem_control.cell_alert: запись из местной очереди, доставка оператору с квитанцией,
--       повтор при ошибке канала, счёт недоставленных (аудит M33-06).
--   Правило аудита C33-01: сессия из списка живых служб место не освобождает никогда.
-- ОГРАНИЧЕНИЯ: ставится после 04_zavod_ext_03.sql и до итоговой проверки одной транзакцией; не меняет
--   существующие таблицы, строки и функции. Срока у аренды bem_control.chat_lease нет — условие протокола
--   «аренда не истекла» проверяется сроком: 30 минут на запуск от opened_at, 4 часа на сеанс. Повторный запуск той же аренды не
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
    outcome  text NOT NULL CHECK (outcome IN ('RESERVED', 'ALREADY_STARTED', 'LEASE_NOT_OPEN', 'LEASE_EXPIRED', 'RUNNING',
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
    -- Срок аренды (вопрос аудитора «а»): запуск — не позже 30 минут после открытия аренды.
    IF (SELECT opened_at FROM bem_control.chat_lease WHERE lease_id = p_lease_id) <= clock_timestamp() - interval '30 minutes' THEN
        INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (p_lease_id, 'LEASE_EXPIRED');
        RETURN 'LEASE_EXPIRED';
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

-- (4) Отметка «сессия работает». Ответы: RUNNING; TOO_LATE (прошло 2 минуты; бронь остаётся STARTING, пока
--     zagent-start не остановит службу, — аудит C33-01);
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

-- (5) Сверка с живыми службами zagent@. Сессия из p_live не меняется никогда (аудит C33-01). Без живой службы:
--     STARTING → START_FAILED в первый проход после загрузки (p_boot) или если бронь старше 2 минут (раньше
--     служба может ещё стоять в очереди systemd); RUNNING → ENDED, если аренда закрыта, иначе INTERRUPTED.
--     Возвращает число изменённых строк.
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
        IF r.lease_id = ANY (p_live) THEN
            v_new := NULL;
        ELSIF r.status = 'STARTING' AND (p_boot OR r.reserved_at <= clock_timestamp() - interval '2 minutes') THEN
            v_new := 'START_FAILED';
        ELSIF r.status = 'RUNNING' THEN
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

-- (6) Зависшие запуски (аудит C33-01): брони STARTING старше 2 минут; сеансы RUNNING дольше 4 часов 5 минут
--     (срок сеанса — 4 часа, RuntimeMaxSec службы; вопрос аудитора «а»). zagent-start останавливает их живые
--     службы; место освобождает только сверка (5), когда службы уже нет в списке живых.
CREATE FUNCTION bem_control.lease_start_overdue()
RETURNS uuid[]
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
BEGIN
    RETURN coalesce((SELECT array_agg(lease_id ORDER BY lease_id) FROM bem_control.session_start
                      WHERE (status = 'STARTING' AND reserved_at <= clock_timestamp() - interval '2 minutes')
                         OR (status = 'RUNNING' AND running_at <= clock_timestamp() - interval '4 hours 5 minutes')),
                    '{}'::uuid[]);
END;
$$;
ALTER FUNCTION bem_control.lease_start_overdue() OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.lease_start_overdue() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.lease_start_overdue() TO zstarter;

-- (7) Можно ли остановить сеанс по заявке (протокол И.12 п.4, аудит M33-02): OPEN — аренда открыта, остановить;
--     LEASE_NOT_OPEN — аренды нет или она закрыта: заявка в архив без остановки (сеанс гаснет по RuntimeMaxSec).
--     Аудит M33-R2-01: строка аренды запирается (FOR SHARE) до конца транзакции вызывающего. zagent-start
--     держит транзакцию открытой, пока systemctl stop не закончит; закрытие аренды (UPDATE) в это время ждёт.
CREATE FUNCTION bem_control.lease_stop_check(p_lease_id uuid)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_status text;
BEGIN
    SELECT status INTO v_status FROM bem_control.chat_lease WHERE lease_id = p_lease_id FOR SHARE;
    IF v_status = 'OPEN' THEN
        RETURN 'OPEN';
    END IF;
    RETURN 'LEASE_NOT_OPEN';
END;
$$;
ALTER FUNCTION bem_control.lease_stop_check(uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.lease_stop_check(uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.lease_stop_check(uuid) TO zstarter;

-- (8) Тревоги клетки (аудит M33-06, И.12 п.7). Тревога сначала ложится файлом в местную очередь
--     /var/lib/zavod/alerts/spool (переживает отказ базы), затем zagent-start переносит её сюда; ключ очереди
--     не даёт записать одну тревогу дважды. Служба zavod-alert-notify передаёт строку оператору и отмечает
--     квитанцию канала или ошибку со следующей попыткой. Строки не удаляются.
CREATE TABLE bem_control.cell_alert (
    alert_id        uuid NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    spool_key       text NOT NULL UNIQUE CHECK (spool_key ~ '^[0-9a-f]{32}$'),
    source          text NOT NULL CHECK (source ~ '^[a-z][a-z0-9-]{0,31}$'),
    message         text NOT NULL CHECK (length(message) BETWEEN 1 AND 2000),
    raised_at       timestamptz NOT NULL,
    stored_at       timestamptz NOT NULL DEFAULT clock_timestamp(),
    attempts        integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_error      text CHECK (length(last_error) <= 300),
    delivered_at    timestamptz,
    receipt         text CHECK (length(receipt) BETWEEN 1 AND 200),
    CONSTRAINT cell_alert_delivery_pair CHECK ((delivered_at IS NULL) = (receipt IS NULL))
);
CREATE INDEX cell_alert_pending ON bem_control.cell_alert (next_attempt_at) WHERE delivered_at IS NULL;
ALTER TABLE bem_control.cell_alert OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.cell_alert FROM PUBLIC;
GRANT SELECT ON bem_control.cell_alert TO backup_reader;

-- (9) Запись тревоги из местной очереди. STORED — записана; DUPLICATE — этот ключ уже записан (повтор переноса);
--     INVALID — запись не проходит проверки таблицы: файл уходит в отказ очереди, чтобы не стоять вечно.
CREATE FUNCTION bem_control.cell_alert_store(p_key text, p_source text, p_message text, p_raised_at timestamptz)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
BEGIN
    INSERT INTO bem_control.cell_alert (spool_key, source, message, raised_at)
    VALUES (p_key, p_source, p_message, p_raised_at)
    ON CONFLICT (spool_key) DO NOTHING;
    IF FOUND THEN
        RETURN 'STORED';
    END IF;
    RETURN 'DUPLICATE';
EXCEPTION WHEN check_violation OR not_null_violation THEN
    RETURN 'INVALID';
END;
$$;
ALTER FUNCTION bem_control.cell_alert_store(text, text, text, timestamptz) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.cell_alert_store(text, text, text, timestamptz) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.cell_alert_store(text, text, text, timestamptz) TO zstarter;

-- (10) Тревоги к доставке: не доставлены и срок следующей попытки наступил; старые первыми, не больше 50.
CREATE FUNCTION bem_control.cell_alert_due(p_limit integer)
RETURNS TABLE (alert_id uuid, source text, message text, raised_at timestamptz, attempts integer)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
BEGIN
    RETURN QUERY
    SELECT a.alert_id, a.source, a.message, a.raised_at, a.attempts FROM bem_control.cell_alert a
     WHERE a.delivered_at IS NULL AND a.next_attempt_at <= clock_timestamp()
     ORDER BY a.raised_at, a.alert_id
     LIMIT greatest(1, least(coalesce(p_limit, 1), 50));
END;
$$;
ALTER FUNCTION bem_control.cell_alert_due(integer) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.cell_alert_due(integer) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.cell_alert_due(integer) TO zstarter;

-- (11) Итог попытки доставки. Квитанция канала → DELIVERED; ошибка → RETRY, следующая попытка через
--      1, 2, 4 … но не больше 60 минут. ALREADY_DELIVERED — квитанция уже есть, ничего не меняется; UNKNOWN — нет строки.
CREATE FUNCTION bem_control.cell_alert_result(p_alert_id uuid, p_receipt text, p_error text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_row bem_control.cell_alert%ROWTYPE;
BEGIN
    IF (p_receipt IS NULL) = (p_error IS NULL) THEN
        RAISE EXCEPTION 'CELL_ALERT_RESULT_SHAPE';
    END IF;
    SELECT * INTO v_row FROM bem_control.cell_alert WHERE alert_id = p_alert_id FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'UNKNOWN';
    END IF;
    IF v_row.delivered_at IS NOT NULL THEN
        RETURN 'ALREADY_DELIVERED';
    END IF;
    IF p_receipt IS NOT NULL THEN
        UPDATE bem_control.cell_alert SET delivered_at = clock_timestamp(), receipt = p_receipt,
               attempts = v_row.attempts + 1
         WHERE alert_id = p_alert_id;
        RETURN 'DELIVERED';
    END IF;
    UPDATE bem_control.cell_alert SET attempts = v_row.attempts + 1, last_error = left(p_error, 300),
           next_attempt_at = clock_timestamp() + interval '1 minute' * least(power(2, least(v_row.attempts, 6)), 60)
     WHERE alert_id = p_alert_id;
    RETURN 'RETRY';
END;
$$;
ALTER FUNCTION bem_control.cell_alert_result(uuid, text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.cell_alert_result(uuid, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.cell_alert_result(uuid, text, text) TO zstarter;

-- (12) Сколько тревог не доставлено дольше p_age: больше нуля — канал оператора не работает, служба
--      доставки поднимает аварийную строку журнала и отметку /run/zavod/alert-channel-down.
CREATE FUNCTION bem_control.cell_alert_stale(p_age interval)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
BEGIN
    RETURN (SELECT count(*)::integer FROM bem_control.cell_alert
             WHERE delivered_at IS NULL AND stored_at <= clock_timestamp() - p_age);
END;
$$;
ALTER FUNCTION bem_control.cell_alert_stale(interval) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.cell_alert_stale(interval) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.cell_alert_stale(interval) TO zstarter;
