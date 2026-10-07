-- ДОКУМЕНТ: db/zavod_ext_01_static.sql (неизменная часть расширения Z-EXT-01)
-- ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
-- ДАТА СОЗДАНИЯ: 2026-10-07 14:18 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 14:18 +03:00
-- ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
-- НАЗНАЧЕНИЕ: добавочное расширение схемы H1.31 для Завода (ответ на аудит Z2):
--   (1) M-Z2-01: отдельная область ZAVOD_PRODUCT_RELEASE для выпуска продукта покупателю
--       с тем же серверным правилом, что у BEM954_PROTOCOL (ровно {anthropic, openai});
--   (2) M-Z2-02: отметка начала внешней отправки (send_started_epoch). Строка, чья аренда
--       истекла ПОСЛЕ начала отправки, у неидемпотентного вида действия не возвращается
--       в очередь, а переходит в UNKNOWN_OUTCOME до сверки; повтор — только у вида,
--       который управление зарегистрировало как идемпотентный.
-- ОГРАНИЧЕНИЯ: не удаляет данных и объектов; не меняет существующие строки; ставится
--   после 01 одной транзакцией. Функции publish_subject и release_subject в итоговом файле
--   взяты из 01 дословно с двумя заменами (их делает db/build_ext.mjs и сверяет число замен).
--   Регистр функций 05_final_state_check.sql расширение не знает: для пакета H1.31 нужна
--   парная дельта-проверка (вынесено в протокол v1.2, раздел 6.3).

-- (1) Область выпуска продукта.
ALTER TABLE bem_core.subject DROP CONSTRAINT subject_scope_check;
ALTER TABLE bem_core.subject ADD CONSTRAINT subject_scope_check
    CHECK (scope IN ('WORKING', 'BEM954_PROTOCOL', 'ZAVOD_PRODUCT_RELEASE'));

-- (2) Отметка начала отправки и политика видов действий.
ALTER TABLE bem_core.outbox ADD COLUMN send_started_epoch bigint;
-- Как у остальных колонок исхода в H1.31: право на правку колонки только у владельца функций.
GRANT UPDATE (send_started_epoch) ON bem_core.outbox TO bem_control_owner;

CREATE TABLE bem_control.outbox_kind_policy (
    kind               text PRIMARY KEY CHECK (kind ~ '^[A-Za-z][A-Za-z0-9_.:-]{0,127}$'),
    idempotent_adapter boolean NOT NULL,
    evidence           text NOT NULL CHECK (btrim(evidence) <> ''),
    registered_at      timestamptz NOT NULL DEFAULT now(),
    registered_by      text NOT NULL DEFAULT session_user
);
ALTER TABLE bem_control.outbox_kind_policy OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.outbox_kind_policy FROM PUBLIC;
GRANT SELECT ON bem_control.outbox_kind_policy TO bem_kernel_rw;

-- Регистрация вида действия — путь управления, не Kernel: Kernel не может сам
-- объявить свой адаптер идемпотентным и тем разрешить себе повтор.
CREATE FUNCTION bem_control.set_outbox_kind_policy(
    p_kind text, p_idempotent boolean, p_evidence text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
BEGIN
    IF p_idempotent IS NULL THEN
        RAISE EXCEPTION 'POLICY_IDEMPOTENT_REQUIRED';
    END IF;
    INSERT INTO bem_control.outbox_kind_policy (kind, idempotent_adapter, evidence)
    VALUES (p_kind, p_idempotent, p_evidence)
    ON CONFLICT (kind) DO UPDATE
       SET idempotent_adapter = EXCLUDED.idempotent_adapter,
           evidence           = EXCLUDED.evidence,
           registered_at      = now(),
           registered_by      = session_user;
END;
$$;
ALTER FUNCTION bem_control.set_outbox_kind_policy(text, boolean, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.set_outbox_kind_policy(text, boolean, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.set_outbox_kind_policy(text, boolean, text) TO bem_governance;

-- Исполнитель отправки ставит отметку ДО внешнего вызова. Отметка возможна только
-- в живой аренде своего поколения; false — отправлять нельзя.
CREATE FUNCTION bem_control.mark_outbox_send_started(
    p_outbox_id uuid, p_lease_epoch bigint, p_worker text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
BEGIN
    UPDATE bem_core.outbox o
       SET send_started_epoch = o.lease_epoch
     WHERE o.id           = p_outbox_id
       AND o.lease_epoch  = p_lease_epoch
       AND o.leased_by    = p_worker
       AND o.status       = 'LEASED'
       AND o.leased_until > clock_timestamp();
    RETURN FOUND;
END;
$$;
ALTER FUNCTION bem_control.mark_outbox_send_started(uuid, bigint, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.mark_outbox_send_started(uuid, bigint, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.mark_outbox_send_started(uuid, bigint, text) TO bem_kernel_rw;

-- Захват партии: сначала строки с истёкшей арендой после начала отправки у
-- неидемпотентного вида — в UNKNOWN_OUTCOME (сверка reconcile решает исход);
-- затем прежний выбор H1.31 §7.6. Подпись и права прежние.
CREATE OR REPLACE FUNCTION bem_control.claim_outbox_batch(
    p_limit  integer,
    p_lease  interval,
    p_worker text)
RETURNS TABLE (outbox_id uuid, tenant_id uuid, work_item_id uuid,
               kind text, lease_epoch bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_temp
AS $$
BEGIN
    UPDATE bem_core.outbox o
       SET status       = 'UNKNOWN_OUTCOME',
           result       = jsonb_build_object(
                            'reason',      'LEASE_EXPIRED_AFTER_SEND_START',
                            'lease_epoch', o.lease_epoch,
                            'leased_by',   o.leased_by,
                            'detected_by', p_worker),
           leased_until = NULL,
           leased_by    = NULL,
           finished_at  = clock_timestamp()
     WHERE o.status = 'LEASED'
       AND o.leased_until < clock_timestamp()
       AND o.send_started_epoch = o.lease_epoch
       AND NOT coalesce((SELECT p.idempotent_adapter
                           FROM bem_control.outbox_kind_policy p
                          WHERE p.kind = o.kind), false);

    RETURN QUERY
    WITH picked AS (
        SELECT o.id
          FROM bem_core.outbox o
         WHERE (o.status = 'PENDING'
                AND o.next_attempt_at <= clock_timestamp())
            OR (o.status = 'FAILED'
                AND o.attempt_count   <  bem_control.outbox_retry_limit()
                AND o.next_attempt_at <= clock_timestamp())
            OR (o.status = 'LEASED' AND o.leased_until < clock_timestamp())
         ORDER BY o.created_at
         FOR UPDATE SKIP LOCKED
         LIMIT p_limit)
    UPDATE bem_core.outbox o
       SET status        = 'LEASED',
           leased_until  = clock_timestamp() + p_lease,
           leased_by     = p_worker,
           lease_epoch   = o.lease_epoch + 1,
           attempt_count = o.attempt_count + 1
      FROM picked
     WHERE o.id = picked.id
    RETURNING o.id, o.tenant_id, o.work_item_id, o.kind, o.lease_epoch;
END;
$$;
ALTER FUNCTION bem_control.claim_outbox_batch(integer, interval, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.claim_outbox_batch(integer, interval, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.claim_outbox_batch(integer, interval, text) TO bem_kernel_rw;
