-- ДОКУМЕНТ: db/02_zavod_ext_01.sql — СОБРАН db/build_ext.mjs, руками не править
-- ИСТОЧНИК H1.31 01: sha256 ce75f3c9978d9ef470ba4c9f9c9f84985c27b603f5d7576951d007492145a7e5
-- НЕИЗМЕННАЯ ЧАСТЬ: db/zavod_ext_01_static.sql sha256 0dfee08faf8ff98ed752149d8155597fe50eeab62078045b2b89a4ac832dda1d
\set ON_ERROR_STOP on
BEGIN;
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

-- Функции H1.31 дословно, заменены только условие области и условие сверки (build_ext.mjs, по одной замене).
CREATE OR REPLACE FUNCTION bem_control.publish_subject(
    p_tenant_id    uuid,
    p_subject_id   uuid,
    p_work_item_id uuid,
    p_head_sha     text,
    p_criticality  text,
    p_scope        text,
    p_authors      text[],
    p_evidence     jsonb)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor     text;   -- выводится из контекста, не из настройки
    v_subject   bem_core.subject;
    v_author    text;
    v_provider  bem_core.provider;
    v_stored    text[];
    v_asked     text[];
    v_rows      integer;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);   -- граница заказчика, C-H17-R7-04
    SELECT out_actor_id INTO v_actor
      FROM bem_control.current_actor_checked(p_tenant_id);

    IF p_authors IS NULL OR cardinality(p_authors) = 0 THEN
        RAISE EXCEPTION 'SUBJECT_WITHOUT_AUTHOR';
    END IF;
    IF p_scope NOT IN ('WORKING', 'BEM954_PROTOCOL', 'ZAVOD_PRODUCT_RELEASE') THEN
        RAISE EXCEPTION 'BAD_SCOPE: %', p_scope;
    END IF;
    IF p_criticality NOT IN ('CRITICAL', 'NORMAL') THEN
        RAISE EXCEPTION 'BAD_CRITICALITY: %', p_criticality;
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 1. Единый порядок блокировок: сначала строка предмета.
    --        Выпуск и запись вердикта начинают так же, поэтому
    --        три операции больше не пересекаются (C-H17-R7-06).
    ---------------------------------------------------------------
    v_subject := bem_control.lock_subject(p_tenant_id, p_subject_id);

    IF v_subject.id IS NULL THEN
        ---------------------------------------------------------------
        -- ШАГ 2а. Новый предмет: сначала строка без отметки публикации,
        --         затем авторы, и только потом отметка — иначе сработает
        --         триггер заморозки авторов.
        ---------------------------------------------------------------
        INSERT INTO bem_core.subject
               (id, tenant_id, work_item_id, head_sha, criticality, scope)
        VALUES (p_subject_id, p_tenant_id, p_work_item_id, p_head_sha,
                p_criticality, p_scope);

        FOREACH v_author IN ARRAY p_authors
        LOOP
            SELECT a.provider INTO v_provider
              FROM bem_core.actor a
             WHERE a.actor_id = v_author AND a.is_active;
            IF v_provider IS NULL THEN
                RAISE EXCEPTION 'UNKNOWN_OR_INACTIVE_ACTOR: %', v_author;
            END IF;
            INSERT INTO bem_core.subject_author
                   (subject_id, actor_id, provider, tenant_id)
            VALUES (p_subject_id, v_author, v_provider, p_tenant_id);
        END LOOP;

        UPDATE bem_core.subject
           SET published_at = now()
         WHERE id = p_subject_id AND tenant_id = p_tenant_id;
    ELSE
        ---------------------------------------------------------------
        -- ШАГ 2б. Новая версия существующего предмета.
        --         H1.7 принимал работу, важность, область и авторов
        --         и молча их игнорировал (замечание M-H17-R7-15).
        --         Теперь каждое неизменяемое поле сверяется с тем,
        --         что уже записано, и расхождение отклоняется.
        ---------------------------------------------------------------
        IF v_subject.published_at IS NULL THEN
            RAISE EXCEPTION 'SUBJECT_ROW_WITHOUT_PUBLICATION: %', p_subject_id;
        END IF;
        IF v_subject.work_item_id <> p_work_item_id THEN
            RAISE EXCEPTION 'SUBJECT_WORK_ITEM_MISMATCH: stored=% argument=%',
                  v_subject.work_item_id, p_work_item_id;
        END IF;
        IF v_subject.criticality <> p_criticality THEN
            RAISE EXCEPTION 'SUBJECT_CRITICALITY_MISMATCH: stored=% argument=%',
                  v_subject.criticality, p_criticality;
        END IF;
        IF v_subject.scope <> p_scope THEN
            RAISE EXCEPTION 'SUBJECT_SCOPE_MISMATCH: stored=% argument=%',
                  v_subject.scope, p_scope;
        END IF;

        -- авторы заморожены: переданный список обязан совпасть с записанным
        SELECT array_agg(a.actor_id ORDER BY a.actor_id) INTO v_stored
          FROM bem_core.subject_author a
         WHERE a.subject_id = p_subject_id AND a.tenant_id = p_tenant_id;
        SELECT array_agg(x ORDER BY x) INTO v_asked
          FROM unnest(p_authors) AS x;
        IF v_stored IS DISTINCT FROM v_asked THEN
            RAISE EXCEPTION 'SUBJECT_AUTHORS_MISMATCH: stored=% argument=%',
                  v_stored, v_asked;
        END IF;

        IF v_subject.head_sha = p_head_sha THEN
            RETURN false;             -- та же версия: делать нечего
        END IF;

        -- новая версия: вердикты старой версии больше не действуют,
        -- пометка разногласия и отметка выпуска снимаются
        UPDATE bem_core.subject
           SET head_sha            = p_head_sha,
               published_at        = now(),
               released_at         = NULL,
               released_by         = NULL,
               disagreement_at     = NULL,
               disagreement_reason = NULL
         WHERE id = p_subject_id AND tenant_id = p_tenant_id;
        GET DIAGNOSTICS v_rows = ROW_COUNT;
        IF v_rows <> 1 THEN
            RAISE EXCEPTION 'SUBJECT_UPDATE_LOST: %', p_subject_id;
        END IF;
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 3. Доказательство строится из ЗАПИСАННОЙ строки, а не из
    --        аргументов вызова: аргумент мог быть любым, а запись —
    --        это то, что действительно лежит в базе (M-H17-R7-15).
    ---------------------------------------------------------------
    SELECT * INTO v_subject
      FROM bem_core.subject s
     WHERE s.id = p_subject_id AND s.tenant_id = p_tenant_id;

    PERFORM bem_control.evidence_write(p_tenant_id, 'SUBJECT_PUBLISHED',
                                       COALESCE(p_evidence, '{}'::jsonb)
                                       || jsonb_build_object('subject_id',   v_subject.id,
                                       'work_item_id', v_subject.work_item_id,
                                       'head_sha',     v_subject.head_sha,
                                       'criticality',  v_subject.criticality,
                                       'scope',        v_subject.scope,
                                       'published_at', v_subject.published_at));
    RETURN true;
END;
$$;

ALTER FUNCTION bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)
       TO bem_kernel_rw;


CREATE OR REPLACE FUNCTION bem_control.release_subject(
    p_tenant_id  uuid,
    p_subject_id uuid,
    p_head_sha   text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor      text;   -- выводится из контекста, не из настройки
    v_subject    bem_core.subject;
    v_author_pr  bem_core.provider[];
    v_ok_pr      bem_core.provider[];
    v_bad_cnt    integer;
    v_bad_list   text;
    v_need       integer;
    v_rows       integer;
    v_required   bem_core.provider[] := ARRAY['anthropic', 'openai']::bem_core.provider[];
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);   -- граница заказчика, C-H17-R7-04
    SELECT out_actor_id INTO v_actor
      FROM bem_control.current_actor_checked(p_tenant_id);

    ---------------------------------------------------------------
    -- ШАГ 0. Блокировка строки предмета — первая и единственная точка
    --        синхронизации. Публикация новой версии и запись вердикта
    --        берут ту же блокировку тем же порядком, поэтому выпуск
    --        больше не может опереться на устаревшее чтение
    --        (замечание C-H17-R7-06).
    ---------------------------------------------------------------
    v_subject := bem_control.lock_subject(p_tenant_id, p_subject_id);
    IF v_subject.id IS NULL OR v_subject.published_at IS NULL THEN
        RAISE EXCEPTION 'SUBJECT_NOT_PUBLISHED';
    END IF;
    IF v_subject.head_sha <> p_head_sha THEN
        RAISE EXCEPTION 'HEAD_MISMATCH: subject=% asked=%',
              v_subject.head_sha, p_head_sha;
    END IF;
    IF v_subject.released_at IS NOT NULL THEN
        RETURN false;                 -- уже выпущено: повтор ничего не меняет
    END IF;

    SELECT array_agg(DISTINCT a.provider)
      INTO v_author_pr
      FROM bem_core.subject_author a
     WHERE a.subject_id = p_subject_id AND a.tenant_id = p_tenant_id;
    IF v_author_pr IS NULL THEN RAISE EXCEPTION 'SUBJECT_WITHOUT_AUTHOR'; END IF;

    ---------------------------------------------------------------
    -- ШАГ 1. ЛЮБОЙ отрицательный вердикт по ЭТОЙ версии закрывает
    --        выпуск. Уникальность (subject_id, head_sha, auditor_actor)
    --        гарантирует ровно один вердикт на проверяющего, поэтому
    --        «действующий» и «единственный» здесь совпадают.
    ---------------------------------------------------------------
    SELECT count(*),
           string_agg(r.auditor_actor || '=' || r.verdict, ', ' ORDER BY r.auditor_actor)
      INTO v_bad_cnt, v_bad_list
      FROM bem_core.audit_record r
     WHERE r.subject_id = p_subject_id
       AND r.tenant_id  = p_tenant_id
       AND r.head_sha   = p_head_sha
       AND r.verdict   <> 'ACCEPT';

    IF v_bad_cnt > 0 THEN
        UPDATE bem_core.subject
           SET disagreement_at     = now(),
               disagreement_reason = v_bad_list
         WHERE id = p_subject_id AND tenant_id = p_tenant_id;

        PERFORM bem_control.evidence_write(p_tenant_id, 'DISAGREEMENT_OPEN',
                                           jsonb_build_object('subject_id', p_subject_id,
                                           'head_sha',   p_head_sha,
                                           'scope',      v_subject.scope,
                                           'verdicts',   v_bad_list));
        -- транзакция НЕ прерывается: состояние разногласия должно сохраниться
        RETURN false;
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 2. Положительные вердикты по той же версии, от НАЗНАЧЕННЫХ
    --        проверяющих и не от авторов. H1.7 считал вердикт любого
    --        активного не-автора (замечание C-H17-R7-05).
    ---------------------------------------------------------------
    SELECT array_agg(DISTINCT r.auditor_provider)
      INTO v_ok_pr
      FROM bem_core.audit_record r
      JOIN bem_core.audit_assignment g
        ON g.subject_id    = r.subject_id
       AND g.tenant_id     = r.tenant_id
       AND g.auditor_actor = r.auditor_actor
       AND g.revoked_at   IS NULL
     WHERE r.subject_id = p_subject_id
       AND r.tenant_id  = p_tenant_id
       AND r.head_sha   = p_head_sha
       AND r.verdict    = 'ACCEPT'
       AND NOT EXISTS (SELECT 1 FROM bem_core.subject_author a
                        WHERE a.subject_id = r.subject_id
                          AND a.actor_id   = r.auditor_actor);

    ---------------------------------------------------------------
    -- ШАГ 3. Правило протокола BEM-954: ТОЧНОЕ множество компаний.
    --        Не «две разные», а именно Anthropic и OpenAI.
    --        Пары human+anthropic и human+openai больше не проходят
    --        (замечание C-H17-R7-05).
    ---------------------------------------------------------------
    IF v_subject.scope IN ('BEM954_PROTOCOL', 'ZAVOD_PRODUCT_RELEASE') THEN
        IF v_ok_pr IS NULL THEN
            RAISE EXCEPTION 'WAITING_AUDIT: need exactly {anthropic, openai}, have {}';
        END IF;
        IF NOT (v_ok_pr @> v_required AND v_required @> v_ok_pr) THEN
            RAISE EXCEPTION
              'BEM954_PROVIDER_SET_MISMATCH: need exactly {anthropic, openai}, have %',
              v_ok_pr;
        END IF;
        -- две компании — значит и два разных назначенных проверяющих
        IF (SELECT count(DISTINCT r.auditor_actor)
              FROM bem_core.audit_record r
              JOIN bem_core.audit_assignment g
                ON g.subject_id    = r.subject_id
               AND g.tenant_id     = r.tenant_id
               AND g.auditor_actor = r.auditor_actor
               AND g.revoked_at   IS NULL
             WHERE r.subject_id = p_subject_id
               AND r.tenant_id  = p_tenant_id
               AND r.head_sha   = p_head_sha
               AND r.verdict    = 'ACCEPT') < 2 THEN
            RAISE EXCEPTION 'BEM954_NEEDS_TWO_ASSIGNED_AUDITORS';
        END IF;
    ELSE
        ---------------------------------------------------------------
        -- Рабочее правило: одна или две разные компании по важности.
        ---------------------------------------------------------------
        IF cardinality(v_author_pr) >= 2 AND v_subject.criticality = 'CRITICAL' THEN
            v_need := 2;
        ELSE
            v_need := 1;
        END IF;

        IF v_ok_pr IS NULL OR cardinality(v_ok_pr) < v_need THEN
            RAISE EXCEPTION 'WAITING_AUDIT: need % distinct providers, have %',
                  v_need, COALESCE(cardinality(v_ok_pr), 0);
        END IF;

        IF v_need = 1 AND cardinality(v_author_pr) = 1
           AND v_author_pr[1] <> 'human'
           AND v_author_pr[1] = ANY(v_ok_pr) AND cardinality(v_ok_pr) = 1 THEN
            RAISE EXCEPTION 'WAITING_AUDIT_PROVIDER';
        END IF;
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 4. Выпуск. Условие включает ту же версию: если параллельная
    --        транзакция успела опубликовать новую версию, строк будет
    --        ноль и выпуск не состоится (замечание C-H17-R7-06).
    ---------------------------------------------------------------
    UPDATE bem_core.subject
       SET released_at         = now(),
           released_by         = v_actor,
           disagreement_at     = NULL,   -- отрицательных вердиктов по этой версии нет
           disagreement_reason = NULL
     WHERE id          = p_subject_id
       AND tenant_id   = p_tenant_id
       AND head_sha    = p_head_sha
       AND released_at IS NULL;
    GET DIAGNOSTICS v_rows = ROW_COUNT;

    IF v_rows <> 1 THEN
        RAISE EXCEPTION 'HEAD_CHANGED_DURING_RELEASE: % строк обновлено', v_rows;
    END IF;

    PERFORM bem_control.evidence_write(p_tenant_id, 'SUBJECT_RELEASED',
                                       jsonb_build_object('subject_id', p_subject_id,
                                       'head_sha',   p_head_sha,
                                       'scope',      v_subject.scope,
                                       'providers',  v_ok_pr));

    RETURN true;
END;
$$;

ALTER FUNCTION bem_control.release_subject(uuid, uuid, text)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.release_subject(uuid, uuid, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.release_subject(uuid, uuid, text) TO bem_kernel_rw;


CREATE OR REPLACE FUNCTION bem_control.reconcile_unknown_outcome(
    p_tenant_id uuid,
    p_outbox_id uuid,
    p_outcome   text,
    p_evidence  jsonb)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor    text;
    v_status   text;
    v_new      text;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);

    -- Операторская калитка. H1.8 считал оператором любую строку,
    -- начинавшуюся на 'human:', а установить её может кто угодно:
    -- SET LOCAL прав не требует (замечание C-H18-R8-05). Теперь нужна
    -- связанная личность и действующее полномочие OPERATOR.
    v_actor := bem_control.assert_authority('OPERATOR', p_tenant_id);
    IF p_outcome NOT IN ('CONFIRMED_SENT', 'CONFIRMED_NOT_SENT', 'UNRESOLVED') THEN
        RAISE EXCEPTION 'BAD_RECONCILE_OUTCOME: %', p_outcome;
    END IF;

    SELECT o.status INTO v_status
      FROM bem_core.outbox o
     WHERE o.id = p_outbox_id AND o.tenant_id = p_tenant_id
       FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'NOT_FOUND'; END IF;
    IF v_status <> 'UNKNOWN_OUTCOME' THEN
        RAISE EXCEPTION 'RECONCILE_FROM_WRONG_STATUS: %', v_status;
    END IF;

    -- Z-EXT-01 (аудит Z3 M-Z3-03): строка, у которой отправка начиналась, возвращается в
    -- очередь только после записи об ограждении исполнителя этого поколения: иначе он может
    -- возобновиться после сверки и сделать второй внешний вызов.
    IF p_outcome = 'CONFIRMED_NOT_SENT' AND EXISTS (
        SELECT 1
          FROM bem_core.outbox o
         WHERE o.id = p_outbox_id
           AND o.send_started_epoch IS NOT NULL
           AND NOT EXISTS (SELECT 1
                             FROM bem_control.outbox_send_fence f
                            WHERE f.outbox_id        = o.id
                              AND f.lease_epoch      = o.send_started_epoch
                              AND f.runtime_instance = o.send_runtime_instance))
    THEN
        RAISE EXCEPTION 'RECONCILE_NOT_FENCED: исполнитель, начавший отправку, не огражден';
    END IF;

    v_new := CASE p_outcome
               WHEN 'CONFIRMED_SENT'     THEN 'SENT'
               WHEN 'CONFIRMED_NOT_SENT' THEN 'PENDING'
               ELSE 'DEAD_LETTER'
             END;

    UPDATE bem_core.outbox
       SET status = v_new,
           reconciled_at = now(),
           reconciled_outcome = p_outcome,
           dead_lettered_at = CASE WHEN v_new = 'DEAD_LETTER' THEN now() END,
           dead_letter_reason = CASE WHEN v_new = 'DEAD_LETTER'
                                     THEN 'исход не установлен человеком' END,
           finished_at = CASE WHEN v_new = 'SENT' THEN now() ELSE NULL END,
           -- Оператор подтвердил, что внешняя сторона ничего не получила:
           -- строка возвращается в очередь с чистым счётом попыток,
           -- и это записано в доказательстве.
           attempt_count = CASE WHEN v_new = 'PENDING' THEN 0
                                ELSE attempt_count END,
           next_attempt_at = CASE WHEN v_new = 'PENDING' THEN clock_timestamp()
                                  ELSE next_attempt_at END,
           leased_by = NULL,
           leased_until = NULL
     WHERE id = p_outbox_id AND tenant_id = p_tenant_id;

    PERFORM bem_control.evidence_write(p_tenant_id, 'OUTBOX_RECONCILED',
                                       COALESCE(p_evidence, '{}'::jsonb)
                                       || jsonb_build_object('outbox_id', p_outbox_id,
                                       'outcome',   p_outcome,
                                       'new_status', v_new));
    RETURN v_new;
END;
$$;

ALTER FUNCTION bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)
       TO bem_governance;

-- Самопроверка расширения: при любом расхождении транзакция откатывается.
DO $chk$
DECLARE v int;
BEGIN
  SELECT count(*) INTO v FROM pg_constraint
   WHERE conname = 'subject_scope_check'
     AND pg_get_constraintdef(oid) LIKE '%ZAVOD_PRODUCT_RELEASE%';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: scope check'; END IF;
  SELECT count(*) INTO v FROM information_schema.columns
   WHERE table_schema = 'bem_core' AND table_name = 'outbox'
     AND column_name IN ('send_started_epoch', 'send_policy_version', 'send_policy_idempotent',
                         'send_runtime_instance');
  IF v <> 4 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: outbox columns'; END IF;
  SELECT count(*) INTO v FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'bem_control'
     AND p.proname IN ('mark_outbox_send_started', 'set_outbox_kind_policy', 'claim_outbox_batch',
                       'record_outbox_fence')
     AND p.prosecdef AND pg_get_userbyid(p.proowner) = 'bem_control_owner';
  IF v <> 4 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: functions'; END IF;
  SELECT count(*) INTO v FROM pg_proc
   WHERE oid = 'bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)'::regprocedure
     AND prosrc LIKE '%RECONCILE_NOT_FENCED%';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: reconcile fence'; END IF;
  IF has_function_privilege('bem_kernel_rw', 'bem_control.set_outbox_kind_policy(text, boolean, text, text, text)', 'EXECUTE')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may set policy'; END IF;
  IF has_function_privilege('bem_kernel_rw', 'bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)', 'EXECUTE')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may record fence'; END IF;
  IF has_table_privilege('bem_kernel_rw', 'bem_control.outbox_kind_policy', 'INSERT')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may write policy'; END IF;
  IF has_table_privilege('bem_kernel_rw', 'bem_control.outbox_send_fence', 'INSERT')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may write fence'; END IF;
  IF to_regprocedure('bem_control.mark_outbox_send_started(uuid, bigint, text)') IS NOT NULL
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: mark without runtime instance'; END IF;
  SELECT count(*) INTO v FROM pg_proc
   WHERE oid = 'bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)'::regprocedure
     AND prosrc LIKE '%FENCE_RUNTIME_MISMATCH%' AND prosrc LIKE '%FENCE_EVIDENCE_INCOMPLETE%'
     AND prosrc LIKE '%FENCE_SELF_REPORT%' AND prosrc LIKE '%FENCE_UNIT_NOT_EMPTY%'
     AND prosrc LIKE '%FENCE_METHOD_FORBIDDEN%'
     AND prosrc LIKE '%assert_authority(''OPERATOR'', p_tenant_id)%';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: fence checks'; END IF;
  -- M-Z5-02: точный список тех, кто может вызвать запись ограждения: владелец и bem_governance.
  SELECT count(*) INTO v FROM pg_proc p, aclexplode(p.proacl) a
   WHERE p.oid = 'bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)'::regprocedure
     AND a.privilege_type = 'EXECUTE'
     AND a.grantee NOT IN ('bem_control_owner'::regrole, 'bem_governance'::regrole);
  IF v <> 0 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: fence callers whitelist'; END IF;
END
$chk$;
COMMIT;
