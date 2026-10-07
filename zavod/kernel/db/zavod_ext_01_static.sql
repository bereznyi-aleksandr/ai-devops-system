-- ДОКУМЕНТ: db/zavod_ext_01_static.sql (неизменная часть расширения Z-EXT-01)
-- ВЕРСИЯ: v0.5  СТАТУС: CANDIDATE
-- ДАТА СОЗДАНИЯ: 2026-10-07 14:18 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 19:05 +03:00 (v0.5: ответ на аудит Z5 —
--   M-Z5-01: ограждается вся единица исполнения (cgroup v2 / Job Object / контейнер), способ
--   «один процесс» запрещён; доказательство обязано показать пустую единицу;
--   M-Z5-02: запись ограждения требует полномочия OPERATOR (канон §16 «Оператор», как у сверки);
--   v0.4: ответ на аудит Z4 M-Z4-01 —
--   отметка привязана к экземпляру среды исполнения; ограждение принимается только от надзирателя
--   с доказательством наблюдённого завершения именно этого экземпляра; v0.3 — ответ на Z3)
-- ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
-- НАЗНАЧЕНИЕ: добавочное расширение схемы H1.31 для Завода:
--   (1) M-Z2-01: отдельная область ZAVOD_PRODUCT_RELEASE для выпуска продукта покупателю
--       с тем же серверным правилом, что у BEM954_PROTOCOL (ровно {anthropic, openai});
--   (2) M-Z2-02: отметка начала внешней отправки (send_started_epoch). Строка, чья аренда
--       истекла ПОСЛЕ начала отправки, у неидемпотентного вида не возвращается в очередь,
--       а переходит в UNKNOWN_OUTCOME до сверки;
--   (3) M-Z3-02: политика вида — версии только добавляются; первая отметка начала отправки
--       закрепляет за строкой версию и признак идемпотентности, и захват партии смотрит только
--       на закреплённое: новая версия политики на уже начатую отправку не действует;
--   (4) M-Z3-03: сверка CONFIRMED_NOT_SENT строки, у которой отправка начиналась, возможна только
--       после записи об ограждении исполнителя (процесс или контейнер завершён и не оживёт).
--       Условие вставлено в reconcile_unknown_outcome (делает db/build_ext.mjs, одной заменой).
--   (5) M-Z4-01: запись в базе сама по себе не ограждение. Каждая попытка отправки идёт в своём
--       экземпляре среды исполнения (send_runtime_instance, задаёт надзиратель src/fencer.mjs).
--       Ограждение записывает только надзиратель (роль bem_governance) ПОСЛЕ того, как сам
--       завершил этот экземпляр, дождался его выхода и проверил, что он не жив; база сверяет
--       экземпляр с отметкой и требует в доказательстве наблюдателя (не сам исполнитель),
--       exit_observed=true, время выхода и тот же экземпляр.
-- ОГРАНИЧЕНИЯ: не удаляет данных и объектов; не меняет существующие строки; ставится
--   после 01 одной транзакцией. Функции publish_subject, release_subject и reconcile_unknown_outcome
--   в итоговом файле взяты из 01 дословно с заменами, которые делает db/build_ext.mjs и сверяет
--   число замен. Парная дельта-проверка 05 и отпечатки тел функций — db/build_final_ext.mjs.

-- (1) Область выпуска продукта.
ALTER TABLE bem_core.subject DROP CONSTRAINT subject_scope_check;
ALTER TABLE bem_core.subject ADD CONSTRAINT subject_scope_check
    CHECK (scope IN ('WORKING', 'BEM954_PROTOCOL', 'ZAVOD_PRODUCT_RELEASE'));

-- (2), (3) Отметка начала отправки и закреплённая за строкой политика.
ALTER TABLE bem_core.outbox ADD COLUMN send_started_epoch bigint;
ALTER TABLE bem_core.outbox ADD COLUMN send_policy_version integer;
ALTER TABLE bem_core.outbox ADD COLUMN send_policy_idempotent boolean;
ALTER TABLE bem_core.outbox ADD COLUMN send_runtime_instance text;
-- Как у остальных колонок исхода в H1.31: право на правку колонки только у владельца функций.
GRANT UPDATE (send_started_epoch, send_policy_version, send_policy_idempotent, send_runtime_instance)
    ON bem_core.outbox TO bem_control_owner;

-- Версии политики только добавляются; правки и удаления строк функциями нет.
CREATE TABLE bem_control.outbox_kind_policy (
    kind               text NOT NULL CHECK (kind ~ '^[A-Za-z][A-Za-z0-9_.:-]{0,127}$'),
    version            integer NOT NULL CHECK (version >= 1),
    idempotent_adapter boolean NOT NULL,
    adapter_version    text NOT NULL CHECK (btrim(adapter_version) <> ''),
    key_scheme         text NOT NULL CHECK (btrim(key_scheme) <> ''),
    evidence           text NOT NULL CHECK (btrim(evidence) <> ''),
    registered_at      timestamptz NOT NULL DEFAULT now(),
    registered_by      text NOT NULL DEFAULT session_user,
    PRIMARY KEY (kind, version)
);
ALTER TABLE bem_control.outbox_kind_policy OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.outbox_kind_policy FROM PUBLIC;
GRANT SELECT ON bem_control.outbox_kind_policy TO bem_kernel_rw;
-- Как ALTER DEFAULT PRIVILEGES H1.31 для bem_control: копия базы читает каждую таблицу
-- (таблица создана не владельцем, поэтому право по умолчанию не сработало; найдено дельта-проверкой 05).
GRANT SELECT ON bem_control.outbox_kind_policy TO backup_reader;

-- Регистрация версии вида — путь управления, не Kernel: Kernel не может сам объявить свой
-- адаптер идемпотентным и тем разрешить себе повтор. Возвращает номер новой версии.
CREATE FUNCTION bem_control.set_outbox_kind_policy(
    p_kind text, p_idempotent boolean, p_adapter_version text, p_key_scheme text, p_evidence text)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_version integer;
BEGIN
    IF p_idempotent IS NULL THEN
        RAISE EXCEPTION 'POLICY_IDEMPOTENT_REQUIRED';
    END IF;
    -- Две регистрации одного вида идут по очереди: номер версии без пропусков и гонок.
    PERFORM pg_advisory_xact_lock(hashtext('zavod.outbox_kind_policy:' || coalesce(p_kind, '')));
    SELECT coalesce(max(p.version), 0) + 1 INTO v_version
      FROM bem_control.outbox_kind_policy p WHERE p.kind = p_kind;
    INSERT INTO bem_control.outbox_kind_policy
           (kind, version, idempotent_adapter, adapter_version, key_scheme, evidence)
    VALUES (p_kind, v_version, p_idempotent, p_adapter_version, p_key_scheme, p_evidence);
    RETURN v_version;
END;
$$;
ALTER FUNCTION bem_control.set_outbox_kind_policy(text, boolean, text, text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.set_outbox_kind_policy(text, boolean, text, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.set_outbox_kind_policy(text, boolean, text, text, text) TO bem_governance;

-- Исполнитель отправки ставит отметку ДО внешнего вызова. Отметка возможна только
-- в живой аренде своего поколения; false — отправлять нельзя. Первая отметка строки
-- закрепляет последнюю версию политики её вида (нет версии — неидемпотентный);
-- последующие отметки закреплённое не меняют. Отметка запоминает экземпляр среды исполнения
-- попытки (M-Z4-01); в одном поколении аренды повторная отметка другим экземпляром — false.
CREATE FUNCTION bem_control.mark_outbox_send_started(
    p_outbox_id uuid, p_lease_epoch bigint, p_worker text, p_runtime_instance text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_version    integer;
    v_idempotent boolean;
BEGIN
    IF p_runtime_instance IS NULL OR btrim(p_runtime_instance) = '' THEN
        RAISE EXCEPTION 'RUNTIME_INSTANCE_REQUIRED';
    END IF;
    SELECT p.version, p.idempotent_adapter INTO v_version, v_idempotent
      FROM bem_core.outbox o
      JOIN bem_control.outbox_kind_policy p ON p.kind = o.kind
     WHERE o.id = p_outbox_id
     ORDER BY p.version DESC
     LIMIT 1;
    UPDATE bem_core.outbox o
       SET send_started_epoch     = o.lease_epoch,
           send_policy_version    = CASE WHEN o.send_started_epoch IS NULL
                                         THEN v_version ELSE o.send_policy_version END,
           send_policy_idempotent = CASE WHEN o.send_started_epoch IS NULL
                                         THEN coalesce(v_idempotent, false)
                                         ELSE o.send_policy_idempotent END,
           send_runtime_instance  = p_runtime_instance
     WHERE o.id           = p_outbox_id
       AND o.lease_epoch  = p_lease_epoch
       AND o.leased_by    = p_worker
       AND o.status       = 'LEASED'
       AND o.leased_until > clock_timestamp()
       AND (o.send_started_epoch IS DISTINCT FROM o.lease_epoch
            OR o.send_runtime_instance = p_runtime_instance);
    RETURN FOUND;
END;
$$;
ALTER FUNCTION bem_control.mark_outbox_send_started(uuid, bigint, text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.mark_outbox_send_started(uuid, bigint, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.mark_outbox_send_started(uuid, bigint, text, text) TO bem_kernel_rw;

-- Захват партии: сначала строки с истёкшей арендой после начала отправки, у которых
-- ЗАКРЕПЛЁННЫЙ признак не идемпотентный, — в UNKNOWN_OUTCOME (сверка reconcile решает исход);
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
                            'reason',         'LEASE_EXPIRED_AFTER_SEND_START',
                            'lease_epoch',    o.lease_epoch,
                            'leased_by',      o.leased_by,
                            'runtime_instance', o.send_runtime_instance,
                            'policy_version', o.send_policy_version,
                            'detected_by',    p_worker),
           leased_until = NULL,
           leased_by    = NULL,
           finished_at  = clock_timestamp()
     WHERE o.status = 'LEASED'
       AND o.leased_until < clock_timestamp()
       AND o.send_started_epoch = o.lease_epoch
       AND NOT coalesce(o.send_policy_idempotent, false);

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

-- (4), (5) Ограждение исполнителя. Запись делает только надзиратель рабочих (src/fencer.mjs)
-- под входом с полномочием OPERATOR (канон H1.31 §16: «Оператор»; роль bem_governance) после того,
-- как сам завершил ВСЮ единицу исполнения (cgroup v2 / Job Object / контейнер) экземпляра среды,
-- начавшего отправку в этом поколении, и увидел, что в единице не осталось ни одного процесса.
-- Завершение одного процесса не принимается (M-Z5-01): потомок мог пережить родителя.
-- Без записи сверка не вернёт строку в очередь (reconcile_unknown_outcome).
CREATE TABLE bem_control.outbox_send_fence (
    outbox_id   uuid NOT NULL,
    lease_epoch bigint NOT NULL,
    tenant_id   uuid NOT NULL,
    worker      text NOT NULL CHECK (btrim(worker) <> ''),
    runtime_instance text NOT NULL CHECK (btrim(runtime_instance) <> ''),
    method      text NOT NULL CHECK (method IN ('CGROUP_KILLED', 'JOB_OBJECT_TERMINATED', 'CONTAINER_TERMINATED')),
    evidence_id uuid NOT NULL,
    fenced_at   timestamptz NOT NULL DEFAULT now(),
    fenced_by   text NOT NULL DEFAULT session_user,
    PRIMARY KEY (outbox_id, lease_epoch)
);
ALTER TABLE bem_control.outbox_send_fence OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.outbox_send_fence FROM PUBLIC;
GRANT SELECT ON bem_control.outbox_send_fence TO backup_reader;

CREATE FUNCTION bem_control.record_outbox_fence(
    p_tenant_id uuid, p_outbox_id uuid, p_lease_epoch bigint,
    p_worker text, p_runtime_instance text, p_method text, p_evidence jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_status text;
    v_epoch  bigint;
    v_result jsonb;
    v_rt     text;
    v_ev     uuid;
    v_kind   text;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    -- M-Z5-02: ограждение открывает сверке путь CONFIRMED_NOT_SENT — это акт оператора (§16).
    PERFORM bem_control.assert_authority('OPERATOR', p_tenant_id);
    IF p_method IS NULL OR p_method NOT IN ('CGROUP_KILLED', 'JOB_OBJECT_TERMINATED', 'CONTAINER_TERMINATED') THEN
        RAISE EXCEPTION 'FENCE_METHOD_FORBIDDEN: %', p_method;
    END IF;
    IF p_evidence IS NULL OR p_evidence = '{}'::jsonb THEN
        RAISE EXCEPTION 'FENCE_EVIDENCE_REQUIRED';
    END IF;
    SELECT o.status, o.send_started_epoch, o.result, o.send_runtime_instance
      INTO v_status, v_epoch, v_result, v_rt
      FROM bem_core.outbox o
     WHERE o.id = p_outbox_id AND o.tenant_id = p_tenant_id
       FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'NOT_FOUND'; END IF;
    IF v_status <> 'UNKNOWN_OUTCOME' THEN
        RAISE EXCEPTION 'FENCE_FROM_WRONG_STATUS: %', v_status;
    END IF;
    IF v_epoch IS DISTINCT FROM p_lease_epoch THEN
        RAISE EXCEPTION 'FENCE_EPOCH_MISMATCH: send_started_epoch=% argument=%', v_epoch, p_lease_epoch;
    END IF;
    IF v_result ? 'leased_by' AND (v_result ->> 'leased_by') IS DISTINCT FROM p_worker THEN
        RAISE EXCEPTION 'FENCE_WORKER_MISMATCH: %', v_result ->> 'leased_by';
    END IF;
    -- M-Z4-01: ограждается именно тот экземпляр, который поставил отметку.
    IF v_rt IS NULL OR v_rt IS DISTINCT FROM p_runtime_instance THEN
        RAISE EXCEPTION 'FENCE_RUNTIME_MISMATCH: marked=% argument=%', v_rt, p_runtime_instance;
    END IF;
    -- Доказательство — наблюдение надзирателя: выход этого экземпляра увиден со стороны.
    -- Самоотчёт исполнителя («я остановился») не принимается.
    IF jsonb_typeof(p_evidence -> 'exit_observed') IS DISTINCT FROM 'boolean'
       OR NOT (p_evidence ->> 'exit_observed')::boolean
       OR coalesce(btrim(p_evidence ->> 'observer'), '') = ''
       OR coalesce(btrim(p_evidence ->> 'exit_observed_at'), '') = ''
       OR (p_evidence ->> 'runtime_instance') IS DISTINCT FROM p_runtime_instance THEN
        RAISE EXCEPTION 'FENCE_EVIDENCE_INCOMPLETE';
    END IF;
    -- M-Z5-01: единица исполнения целиком пуста — вид единицы совпадает со способом.
    v_kind := CASE p_method WHEN 'CGROUP_KILLED' THEN 'CGROUP_V2'
                            WHEN 'JOB_OBJECT_TERMINATED' THEN 'JOB_OBJECT'
                            WHEN 'CONTAINER_TERMINATED' THEN 'CONTAINER' END;
    IF coalesce(btrim(p_evidence ->> 'unit_id'), '') = ''
       OR (p_evidence ->> 'unit_kind') IS DISTINCT FROM v_kind
       OR jsonb_typeof(p_evidence -> 'unit_empty_observed') IS DISTINCT FROM 'boolean'
       OR NOT (p_evidence ->> 'unit_empty_observed')::boolean THEN
        RAISE EXCEPTION 'FENCE_UNIT_NOT_EMPTY';
    END IF;
    IF (p_evidence ->> 'observer') IN (p_worker, p_runtime_instance) THEN
        RAISE EXCEPTION 'FENCE_SELF_REPORT';
    END IF;
    v_ev := bem_control.evidence_write(p_tenant_id, 'OUTBOX_SEND_FENCED',
              p_evidence || jsonb_build_object('outbox_id', p_outbox_id, 'lease_epoch', p_lease_epoch,
                                               'worker', p_worker, 'runtime_instance', p_runtime_instance,
                                               'method', p_method));
    INSERT INTO bem_control.outbox_send_fence
           (outbox_id, lease_epoch, tenant_id, worker, runtime_instance, method, evidence_id)
    VALUES (p_outbox_id, p_lease_epoch, p_tenant_id, p_worker, p_runtime_instance, p_method, v_ev);
    RETURN v_ev;
END;
$$;
ALTER FUNCTION bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb) TO bem_governance;
