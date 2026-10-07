-- ДОКУМЕНТ: db/02_zavod_ext_01.sql — СОБРАН db/build_ext.mjs, руками не править
-- ИСТОЧНИК H1.31 01: sha256 ce75f3c9978d9ef470ba4c9f9c9f84985c27b603f5d7576951d007492145a7e5
-- НЕИЗМЕННАЯ ЧАСТЬ: db/zavod_ext_01_static.sql sha256 1d30292fa4d5dab0eb709df510bf42231670e09cb3d54e10bfe546fcf3b59395
\set ON_ERROR_STOP on
BEGIN;
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

-- Функции H1.31 дословно, замена только условия области (build_ext.mjs, по одной замене).
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


-- Самопроверка расширения: при любом расхождении транзакция откатывается.
DO $chk$
DECLARE v int;
BEGIN
  SELECT count(*) INTO v FROM pg_constraint
   WHERE conname = 'subject_scope_check'
     AND pg_get_constraintdef(oid) LIKE '%ZAVOD_PRODUCT_RELEASE%';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: scope check'; END IF;
  SELECT count(*) INTO v FROM information_schema.columns
   WHERE table_schema = 'bem_core' AND table_name = 'outbox' AND column_name = 'send_started_epoch';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: send_started_epoch'; END IF;
  SELECT count(*) INTO v FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'bem_control'
     AND p.proname IN ('mark_outbox_send_started', 'set_outbox_kind_policy', 'claim_outbox_batch')
     AND p.prosecdef AND pg_get_userbyid(p.proowner) = 'bem_control_owner';
  IF v <> 3 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: functions'; END IF;
  IF has_function_privilege('bem_kernel_rw', 'bem_control.set_outbox_kind_policy(text, boolean, text)', 'EXECUTE')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may set policy'; END IF;
  IF has_table_privilege('bem_kernel_rw', 'bem_control.outbox_kind_policy', 'INSERT')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may write policy'; END IF;
END
$chk$;
COMMIT;
