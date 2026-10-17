-- ДОКУМЕНТ: db/03_zavod_ext_02.sql (расширение Z-EXT-02: пакеты Z-RULES-01 и Z-HANDOFF-01)
-- ВЕРСИЯ: v0.4  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-10-17 23:39 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 02:21 +03:00 (v0.4: ChatGPT R14B —
--   RG14-01 включение правил и подтверждение отчёта оператору — только отдельная входная роль bem_rules_gate
--   (у bem_kernel_rw права вызова activate_rules нет, путь оператора в acknowledge_lease_report сверяет
--   session_user); RG14-02 смена аренды адресата проверяется до повтора подтверждения; RG14-03 завершение
--   заново сверяет аренду, поколение и сессию адресата подтверждённого отчёта.
--   v0.3: проект v1.2 по ChatGPT R13 —
--   RG13-01 доказательства аренды пишет только держатель через record_lease_evidence в отдельную таблицу;
--   RG13-02 отчёт выше с адресатом, закреплённым при создании по иерархии ролей из подписанных правил;
--   RG13-03 порядок завершения и четыре номера в строке аренды; RG13-04 подробности каждой проверки GitHub
--   и назначенный источник; факты GitHub и подписи пишет сама activate_rules.
--   v0.2: одна действующая версия на заказчика, сессия держателя, ожидаемая версия правил, повтор завершения)
-- ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
-- ЗАМЕНЯЕТ: v0.3, SHA-256 f6440a2294a78bf2eb791f76dd610c5a35a4df3202461f136d4409b71553fe64
--   (копия — state/zavod_20261007/kernel_rules_handoff_20261017/03_zavod_ext_02_v0_3.SUPERSEDED.sql;
--   v0.2 — 03_zavod_ext_02_v0_2.SUPERSEDED.sql, 1da56fb21eb1404f…)
-- НАЗНАЧЕНИЕ: протокол Завода v2.5.
--   (1) Z-RULES-01 (П.3, Д.7, Е.2): действующая версия правил заказчика (полный номер коммита) и история
--       включений. Включение — одно действие activate_rules: факты GitHub (слияние в main, четыре обязательные
--       проверки от назначенного источника на проверенной версии), подписанный оператором билет и выпуск
--       проверенной аудитом версии. Факты GitHub и подписи функция записывает сама, поэтому заранее
--       подложенное доказательство ей не нужно и не принимается. Прежняя версия получает пометку
--       superseded_at/superseded_by; строки не удаляются.
--   (2) Z-HANDOFF-01 (Л.12): аренда чата роли с поколением, номером и сессией держателя; итог, память роли и
--       следующий шаг пишет только держатель (record_lease_evidence); отчёт выше получает адресата при
--       создании (file_lease_report) и подтверждается только им (acknowledge_lease_report); завершение
--       complete_chat_lease сверяет всё это по таблицам, а не по видам доказательств.
-- ОГРАНИЧЕНИЯ: ставится после 02_zavod_ext_01.sql одной транзакцией; не удаляет данных и объектов, не меняет
--   существующие строки и функции H1.31/Z-EXT-01. Текст правил в базе не хранится (П.3). GitHub, git и подпись
--   проверяет ядро (src/rules_gate.mjs); сессию вызывающего даёт посредник ядра (проект §3.2). Факты GitHub и
--   подпись оператора база принимает только от входной роли bem_rules_gate (RG14-01): общая роль ядра
--   bem_kernel_rw включить правила и подтвердить отчёт за оператора не может. Вход bem_rules_gate выдаётся
--   только изолированной проверке правил (строка pg_hba.conf и сертификат клиента — у администратора, как у
--   остальных входных ролей H1.31); пока этого нет, граница честно описана в проекте §1 и §7.

-- (0) Входная роль проверки правил (RG14-01). Без пароля, без особых признаков, без членств; права — ровно
--     подключение, схема bem_control, чтение rules_activation и вызов двух функций ниже.
CREATE ROLE bem_rules_gate LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT;
GRANT CONNECT ON DATABASE bem TO bem_rules_gate;
GRANT USAGE ON SCHEMA bem_control TO bem_rules_gate;

-- (1) Действующая версия правил и история включений.
CREATE TABLE bem_control.rules_activation (
    tenant_id              uuid NOT NULL,
    rules_commit           text NOT NULL CHECK (rules_commit ~ '^[0-9a-f]{40}$'),
    registry_digest        text NOT NULL CHECK (registry_digest ~ '^[0-9a-f]{64}$'),
    role_parents           jsonb NOT NULL CHECK (jsonb_typeof(role_parents) = 'object'),
    pr_number              integer NOT NULL CHECK (pr_number >= 1),
    pr_url                 text NOT NULL CHECK (pr_url ~ '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*$'),
    subject_id             uuid NOT NULL,
    head_sha               text NOT NULL CHECK (head_sha ~ '^[0-9a-f]{40}$'),
    key_fingerprint        text NOT NULL CHECK (key_fingerprint ~ '^SHA256:[A-Za-z0-9+/]{43}$'),
    merge_evidence_id      uuid NOT NULL,
    signature_evidence_id  uuid NOT NULL,
    activation_evidence_id uuid NOT NULL,
    activated_by           text NOT NULL CHECK (btrim(activated_by) <> ''),
    activated_at           timestamptz NOT NULL DEFAULT now(),
    superseded_at          timestamptz,
    superseded_by          text CHECK (superseded_by ~ '^[0-9a-f]{40}$'),
    PRIMARY KEY (tenant_id, rules_commit),
    CONSTRAINT rules_activation_superseded_pair CHECK ((superseded_at IS NULL) = (superseded_by IS NULL))
);
-- Одна действующая версия на заказчика: единственная его строка без пометки SUPERSEDED.
CREATE UNIQUE INDEX rules_activation_one_active ON bem_control.rules_activation (tenant_id) WHERE superseded_at IS NULL;
ALTER TABLE bem_control.rules_activation OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.rules_activation FROM PUBLIC;
GRANT SELECT ON bem_control.rules_activation TO bem_kernel_rw;
GRANT SELECT ON bem_control.rules_activation TO backup_reader;
GRANT SELECT ON bem_control.rules_activation TO bem_rules_gate;

-- Включение версии правил одним действием. Возвращает номер доказательства RULES_ACTIVATED.
--   p_role_parents — иерархия ролей из реестра правил: роль -> вышестоящая роль или 'OPERATOR'.
--   p_github       — факты, которые ядро прочитало из GitHub (проект §3.1): base, merged, merge_commit,
--                    head_sha, pr_number, pr_url, required_checks [{context, app_id}] из защиты ветки main,
--                    check_runs [{name, check_run_id, app_id, head_sha, conclusion, completed_at}].
--   p_signature    — проверенная ядром подпись: namespace, key_fingerprint, signed_ticket_sha256, ticket.
CREATE FUNCTION bem_control.activate_rules(
    p_tenant_id uuid, p_commit text, p_head_sha text, p_pr_number integer, p_registry_digest text,
    p_subject_id uuid, p_role_parents jsonb, p_github jsonb, p_signature jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor   text;
    v_subject bem_core.subject;
    v_prev    text;
    v_check   text;
    v_field   text;
    v_want    jsonb;
    v_run     jsonb;
    v_app     text;
    v_n       integer;
    v_cur     text;
    v_steps   integer;
    v_total   integer;
    r         record;
    v_issued  timestamptz;
    v_merge   uuid;
    v_sig     uuid;
    v_ev      uuid;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    SELECT out_actor_id INTO v_actor FROM bem_control.current_actor_checked(p_tenant_id);
    IF p_commit IS NULL OR p_commit !~ '^[0-9a-f]{40}$' THEN RAISE EXCEPTION 'RULES_BAD_COMMIT'; END IF;
    IF p_head_sha IS NULL OR p_head_sha !~ '^[0-9a-f]{40}$' THEN RAISE EXCEPTION 'RULES_BAD_HEAD'; END IF;
    IF p_registry_digest IS NULL OR p_registry_digest !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RULES_BAD_DIGEST'; END IF;
    IF p_pr_number IS NULL OR p_pr_number < 1 THEN RAISE EXCEPTION 'RULES_BAD_PR'; END IF;
    IF p_subject_id IS NULL THEN RAISE EXCEPTION 'RULES_SUBJECT_MISSING'; END IF;

    -- Иерархия ролей: каждая роль ведёт к 'OPERATOR' без петель; у каждой — ровно одна вышестоящая.
    IF p_role_parents IS NULL OR jsonb_typeof(p_role_parents) <> 'object' OR p_role_parents = '{}'::jsonb THEN
        RAISE EXCEPTION 'RULES_BAD_ROLE_PARENTS';
    END IF;
    SELECT count(*) INTO v_total FROM jsonb_object_keys(p_role_parents);
    FOR r IN SELECT key, value FROM jsonb_each(p_role_parents) LOOP
        IF r.key !~ '^0[1-9]_[^/\\]{1,60}$' OR jsonb_typeof(r.value) <> 'string' THEN
            RAISE EXCEPTION 'RULES_BAD_ROLE_PARENTS: %', r.key;
        END IF;
        v_cur := r.key;
        v_steps := 0;
        WHILE v_cur <> 'OPERATOR' LOOP
            v_cur := p_role_parents->>v_cur;
            v_steps := v_steps + 1;
            IF v_cur IS NULL OR v_steps > v_total THEN RAISE EXCEPTION 'RULES_BAD_ROLE_PARENTS: %', r.key; END IF;
        END LOOP;
    END LOOP;

    -- Включения одного заказчика идут строго по одному.
    PERFORM pg_advisory_xact_lock(hashtext('bem_control.rules_activation:' || p_tenant_id::text));
    IF EXISTS (SELECT 1 FROM bem_control.rules_activation WHERE tenant_id = p_tenant_id AND rules_commit = p_commit) THEN
        RAISE EXCEPTION 'RULES_ALREADY_ACTIVE: %', p_commit;
    END IF;

    -- Шаги Е.2 «машинная проверка» и «слияние»: факты GitHub, прочитанные ядром (RG13-04).
    IF p_github IS NULL OR jsonb_typeof(p_github) <> 'object' THEN RAISE EXCEPTION 'RULES_MERGE_EVIDENCE_MISSING'; END IF;
    IF p_github->>'base' IS DISTINCT FROM 'main' THEN RAISE EXCEPTION 'RULES_MERGE_EVIDENCE_MISMATCH: base'; END IF;
    IF p_github->'merged' IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'RULES_MERGE_EVIDENCE_MISMATCH: merged'; END IF;
    IF p_github->>'merge_commit' IS DISTINCT FROM p_commit THEN RAISE EXCEPTION 'RULES_MERGE_EVIDENCE_MISMATCH: merge_commit'; END IF;
    IF p_github->>'head_sha' IS DISTINCT FROM p_head_sha THEN RAISE EXCEPTION 'RULES_MERGE_EVIDENCE_MISMATCH: head_sha'; END IF;
    IF p_github->'pr_number' IS DISTINCT FROM to_jsonb(p_pr_number) THEN RAISE EXCEPTION 'RULES_MERGE_EVIDENCE_MISMATCH: pr_number'; END IF;
    IF coalesce(p_github->>'pr_url', '') !~ ('^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/' || p_pr_number || '$') THEN
        RAISE EXCEPTION 'RULES_MERGE_EVIDENCE_MISMATCH: pr_url';
    END IF;
    IF jsonb_typeof(p_github->'required_checks') IS DISTINCT FROM 'array'
       OR jsonb_typeof(p_github->'check_runs') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'RULES_MERGE_EVIDENCE_MISMATCH: checks';
    END IF;
    FOREACH v_check IN ARRAY ARRAY['static', 'pg16', 'engine-pg', 'engine-pg-probes'] LOOP
        -- Назначенный источник обязательной проверки — из защиты ветки main; без источника проверку
        -- может подставить любое приложение, поэтому такая защита не принимается.
        SELECT count(*), min(x->>'app_id') INTO v_n, v_app
          FROM jsonb_array_elements(p_github->'required_checks') x WHERE x->>'context' = v_check;
        IF v_n <> 1 OR coalesce(v_app, '') !~ '^[1-9][0-9]*$' THEN
            RAISE EXCEPTION 'RULES_CHECK_SOURCE_UNASSIGNED: %', v_check;
        END IF;
        SELECT count(*) INTO v_n FROM jsonb_array_elements(p_github->'check_runs') x WHERE x->>'name' = v_check;
        IF v_n <> 1 THEN RAISE EXCEPTION 'RULES_CHECK_NOT_PASSED: %', v_check; END IF;
        SELECT x INTO v_run FROM jsonb_array_elements(p_github->'check_runs') x WHERE x->>'name' = v_check;
        IF v_run->>'app_id' IS DISTINCT FROM v_app THEN RAISE EXCEPTION 'RULES_CHECK_WRONG_SOURCE: %', v_check; END IF;
        IF v_run->>'head_sha' IS DISTINCT FROM p_head_sha THEN RAISE EXCEPTION 'RULES_CHECK_WRONG_HEAD: %', v_check; END IF;
        IF v_run->>'conclusion' IS DISTINCT FROM 'success' THEN RAISE EXCEPTION 'RULES_CHECK_NOT_PASSED: %', v_check; END IF;
        IF coalesce(v_run->>'check_run_id', '') !~ '^[1-9][0-9]*$'
           OR coalesce(v_run->>'completed_at', '') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$' THEN
            RAISE EXCEPTION 'RULES_CHECK_BAD_RUN: %', v_check;
        END IF;
    END LOOP;

    -- Шаг Е.2 «утверждение владельцем уровня»: билет, подписанный ключом оператора с телефона (проверило ядро).
    v_want := jsonb_build_object('tenant_id', p_tenant_id::text, 'merge_commit', p_commit, 'head_sha', p_head_sha,
        'pr_number', p_pr_number, 'registry_digest', p_registry_digest, 'subject_id', p_subject_id::text,
        'role_parents', p_role_parents);
    IF p_signature IS NULL OR jsonb_typeof(p_signature) <> 'object'
       OR p_signature->>'namespace' IS DISTINCT FROM 'zavod-rules-activation@v1'
       OR coalesce(p_signature->>'key_fingerprint', '') !~ '^SHA256:[A-Za-z0-9+/]{43}$'
       OR coalesce(p_signature->>'signed_ticket_sha256', '') !~ '^[0-9a-f]{64}$'
       OR jsonb_typeof(p_signature->'ticket') IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'RULES_SIGNATURE_MISSING';
    END IF;
    FOR v_field IN SELECT jsonb_object_keys(v_want) LOOP
        IF p_signature->'ticket'->v_field IS DISTINCT FROM v_want->v_field THEN
            RAISE EXCEPTION 'RULES_SIGNATURE_MISMATCH: %', v_field;
        END IF;
    END LOOP;
    IF coalesce(p_signature->'ticket'->>'issued_at', '') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$' THEN
        RAISE EXCEPTION 'RULES_SIGNATURE_EXPIRED';
    END IF;
    v_issued := (p_signature->'ticket'->>'issued_at')::timestamptz;
    IF v_issued > now() + interval '5 minutes' OR v_issued < now() - interval '24 hours' THEN
        RAISE EXCEPTION 'RULES_SIGNATURE_EXPIRED';
    END IF;

    -- Шаг Е.2 «независимый аудит»: проверенная версия выпущена (вердикт другого поставщика, H1.31 §9.4).
    SELECT * INTO v_subject FROM bem_core.subject WHERE id = p_subject_id AND tenant_id = p_tenant_id;
    IF v_subject.id IS NULL THEN RAISE EXCEPTION 'RULES_SUBJECT_MISSING'; END IF;
    IF v_subject.head_sha IS DISTINCT FROM p_head_sha THEN RAISE EXCEPTION 'RULES_SUBJECT_HEAD_MISMATCH'; END IF;
    IF v_subject.released_at IS NULL THEN RAISE EXCEPTION 'RULES_AUDIT_NOT_RELEASED'; END IF;

    -- Все проверки пройдены: факты записываются здесь же, одной транзакцией с включением.
    v_merge := bem_control.evidence_write(p_tenant_id, 'RULES_PR_MERGED',
        p_github || jsonb_build_object('tenant_id', p_tenant_id::text));
    v_sig := bem_control.evidence_write(p_tenant_id, 'RULES_OPERATOR_SIGNATURE', p_signature);
    SELECT rules_commit INTO v_prev FROM bem_control.rules_activation
     WHERE tenant_id = p_tenant_id AND superseded_at IS NULL FOR UPDATE;
    v_ev := bem_control.evidence_write(p_tenant_id, 'RULES_ACTIVATED', v_want || jsonb_build_object(
        'previous_rules_commit', v_prev, 'merge_evidence_id', v_merge, 'signature_evidence_id', v_sig,
        'pr_url', p_github->>'pr_url', 'key_fingerprint', p_signature->>'key_fingerprint'));
    UPDATE bem_control.rules_activation SET superseded_at = now(), superseded_by = p_commit
     WHERE tenant_id = p_tenant_id AND rules_commit = v_prev;
    INSERT INTO bem_control.rules_activation
           (tenant_id, rules_commit, registry_digest, role_parents, pr_number, pr_url, subject_id, head_sha,
            key_fingerprint, merge_evidence_id, signature_evidence_id, activation_evidence_id, activated_by)
    VALUES (p_tenant_id, p_commit, p_registry_digest, p_role_parents, p_pr_number, p_github->>'pr_url', p_subject_id,
            p_head_sha, p_signature->>'key_fingerprint', v_merge, v_sig, v_ev, v_actor);
    RETURN v_ev;
END;
$$;
ALTER FUNCTION bem_control.activate_rules(uuid, text, text, integer, text, uuid, jsonb, jsonb, jsonb) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.activate_rules(uuid, text, text, integer, text, uuid, jsonb, jsonb, jsonb) FROM PUBLIC;
-- RG14-01: вызывает только bem_rules_gate; у общей роли ядра права нет.
GRANT  EXECUTE ON FUNCTION bem_control.activate_rules(uuid, text, text, integer, text, uuid, jsonb, jsonb, jsonb) TO bem_rules_gate;

-- (2) Аренда чата роли.
CREATE TABLE bem_control.chat_lease (
    lease_id               uuid NOT NULL,
    tenant_id              uuid NOT NULL,
    role_key               text NOT NULL CHECK (role_key ~ '^0[1-9]_[^/\\]{1,60}$'),
    chat_number            text NOT NULL CHECK (chat_number ~ '^[A-Z][0-9]{5}$' AND substr(chat_number, 2) <> '00000'),
    generation             integer NOT NULL CHECK (generation >= 1),
    work_item_id           uuid NOT NULL,
    holder_session         text NOT NULL CHECK (btrim(holder_session) <> '' AND holder_session <> 'OPERATOR'),
    rules_commit           text NOT NULL CHECK (rules_commit ~ '^[0-9a-f]{40}$'),
    code_commit            text NOT NULL CHECK (code_commit ~ '^[0-9a-f]{40}$'),
    status                 text NOT NULL CHECK (status IN ('OPEN', 'COMPLETED')),
    opened_by              text NOT NULL CHECK (btrim(opened_by) <> ''),
    opened_at              timestamptz NOT NULL DEFAULT now(),
    closed_at              timestamptz,
    completion_evidence_id uuid,
    result_evidence_id     uuid,
    memory_evidence_id     uuid,
    next_evidence_id       uuid,
    report_id              uuid,
    PRIMARY KEY (lease_id),
    CONSTRAINT chat_lease_closed_pair CHECK ((status = 'COMPLETED') = (
        closed_at IS NOT NULL AND completion_evidence_id IS NOT NULL AND result_evidence_id IS NOT NULL
        AND memory_evidence_id IS NOT NULL AND next_evidence_id IS NOT NULL AND report_id IS NOT NULL)),
    CONSTRAINT chat_lease_number_unique UNIQUE (tenant_id, role_key, chat_number),
    CONSTRAINT chat_lease_generation_unique UNIQUE (tenant_id, role_key, generation)
);
-- Одна открытая аренда на роль и одна на работу у каждого заказчика.
CREATE UNIQUE INDEX chat_lease_one_open_per_role ON bem_control.chat_lease (tenant_id, role_key) WHERE status = 'OPEN';
CREATE UNIQUE INDEX chat_lease_one_open_per_work ON bem_control.chat_lease (tenant_id, work_item_id) WHERE status = 'OPEN';
ALTER TABLE bem_control.chat_lease OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.chat_lease FROM PUBLIC;
GRANT SELECT ON bem_control.chat_lease TO bem_kernel_rw;
GRANT SELECT ON bem_control.chat_lease TO backup_reader;

-- Итог, память роли и следующий шаг аренды (RG13-01). Пишет только record_lease_evidence.
CREATE TABLE bem_control.chat_lease_evidence (
    evidence_id     uuid NOT NULL PRIMARY KEY,
    tenant_id       uuid NOT NULL,
    lease_id        uuid NOT NULL REFERENCES bem_control.chat_lease (lease_id),
    generation      integer NOT NULL CHECK (generation >= 1),
    work_item_id    uuid NOT NULL,
    kind            text NOT NULL CHECK (kind IN ('TASK_RESULT', 'ROLE_MEMORY', 'NEXT_STEP')),
    holder_session  text NOT NULL CHECK (btrim(holder_session) <> ''),
    content_sha256  text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    created_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE bem_control.chat_lease_evidence OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.chat_lease_evidence FROM PUBLIC;
GRANT SELECT ON bem_control.chat_lease_evidence TO bem_kernel_rw;
GRANT SELECT ON bem_control.chat_lease_evidence TO backup_reader;

-- Отчёт выше (RG13-02). Адресат закрепляется при создании и потом не меняется.
CREATE TABLE bem_control.lease_report (
    report_id            uuid NOT NULL PRIMARY KEY,
    tenant_id            uuid NOT NULL,
    lease_id             uuid NOT NULL REFERENCES bem_control.chat_lease (lease_id),
    generation           integer NOT NULL CHECK (generation >= 1),
    work_item_id         uuid NOT NULL,
    from_role_key        text NOT NULL,
    from_session         text NOT NULL CHECK (btrim(from_session) <> ''),
    recipient_role_key   text NOT NULL,
    recipient_lease_id   uuid,
    recipient_generation integer,
    recipient_session    text,
    report_sha256        text NOT NULL CHECK (report_sha256 ~ '^[0-9a-f]{64}$'),
    filed_evidence_id    uuid NOT NULL,
    filed_at             timestamptz NOT NULL DEFAULT now(),
    ack_evidence_id      uuid,
    ack_session          text,
    acked_at             timestamptz,
    -- Адресат — либо открытая аренда вышестоящей роли, либо оператор (подтверждает подписью с телефона).
    CONSTRAINT lease_report_recipient_shape CHECK (
        (recipient_role_key = 'OPERATOR' AND recipient_lease_id IS NULL AND recipient_generation IS NULL
            AND recipient_session IS NULL)
        OR (recipient_role_key ~ '^0[1-9]_[^/\\]{1,60}$' AND recipient_lease_id IS NOT NULL
            AND recipient_generation IS NOT NULL AND recipient_session IS NOT NULL)),
    CONSTRAINT lease_report_ack_triple CHECK (
        (ack_evidence_id IS NULL) = (ack_session IS NULL) AND (ack_session IS NULL) = (acked_at IS NULL))
);
ALTER TABLE bem_control.lease_report OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.lease_report FROM PUBLIC;
GRANT SELECT ON bem_control.lease_report TO bem_kernel_rw;
GRANT SELECT ON bem_control.lease_report TO backup_reader;

-- Выдача аренды. Номер чата и поколение выдаёт база под блокировкой роли заказчика; версия правил — из
-- действующей записи и обязана совпасть с той, которую ядро сверило с рабочей копией (иначе LEASE_RULES_CHANGED).
CREATE FUNCTION bem_control.open_chat_lease(
    p_tenant_id uuid, p_role_key text, p_work_item_id uuid, p_holder_session text, p_code_commit text,
    p_expected_rules_commit text)
RETURNS TABLE (out_lease_id uuid, out_generation integer, out_chat_number text, out_rules_commit text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor   text;
    v_rules   text;
    v_parents jsonb;
    v_status  text;
    v_last    text;
    v_num     text;
    v_gen     integer;
    v_n       integer;
    v_id      uuid := gen_random_uuid();
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    SELECT out_actor_id INTO v_actor FROM bem_control.current_actor_checked(p_tenant_id);
    IF p_role_key IS NULL OR p_role_key !~ '^0[1-9]_[^/\\]{1,60}$' THEN RAISE EXCEPTION 'LEASE_BAD_ROLE'; END IF;
    IF p_code_commit IS NULL OR p_code_commit !~ '^[0-9a-f]{40}$' THEN RAISE EXCEPTION 'LEASE_BAD_CODE_COMMIT'; END IF;
    IF p_holder_session IS NULL OR btrim(p_holder_session) = '' OR p_holder_session = 'OPERATOR' THEN
        RAISE EXCEPTION 'LEASE_BAD_SESSION';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext('bem_control.chat_lease:' || p_tenant_id::text || ':' || p_role_key));

    SELECT rules_commit, role_parents INTO v_rules, v_parents FROM bem_control.rules_activation
     WHERE tenant_id = p_tenant_id AND superseded_at IS NULL;
    IF v_rules IS NULL THEN RAISE EXCEPTION 'LEASE_NO_ACTIVE_RULES'; END IF;
    IF p_expected_rules_commit IS DISTINCT FROM v_rules THEN RAISE EXCEPTION 'LEASE_RULES_CHANGED'; END IF;
    IF NOT (v_parents ? p_role_key) THEN RAISE EXCEPTION 'LEASE_ROLE_NOT_IN_RULES: %', p_role_key; END IF;
    SELECT status INTO v_status FROM bem_core.work_item WHERE id = p_work_item_id AND tenant_id = p_tenant_id;
    IF v_status IS NULL THEN RAISE EXCEPTION 'LEASE_WORK_NOT_FOUND'; END IF;
    IF v_status IN ('RELEASED', 'CANCELLED') THEN RAISE EXCEPTION 'LEASE_WORK_CLOSED: %', v_status; END IF;
    IF EXISTS (SELECT 1 FROM bem_control.chat_lease
                WHERE tenant_id = p_tenant_id AND role_key = p_role_key AND status = 'OPEN') THEN
        RAISE EXCEPTION 'LEASE_ROLE_BUSY';
    END IF;
    IF EXISTS (SELECT 1 FROM bem_control.chat_lease
                WHERE tenant_id = p_tenant_id AND work_item_id = p_work_item_id AND status = 'OPEN') THEN
        RAISE EXCEPTION 'LEASE_WORK_BUSY';
    END IF;

    -- Номер всегда шесть знаков, поэтому порядок строк совпадает с порядком номеров.
    SELECT chat_number INTO v_last FROM bem_control.chat_lease
     WHERE tenant_id = p_tenant_id AND role_key = p_role_key ORDER BY chat_number DESC LIMIT 1;
    IF v_last IS NULL THEN
        v_num := 'A00001';
    ELSE
        v_n := substr(v_last, 2)::integer;
        IF v_n < 99999 THEN
            v_num := substr(v_last, 1, 1) || lpad((v_n + 1)::text, 5, '0');
        ELSIF substr(v_last, 1, 1) < 'Z' THEN
            v_num := chr(ascii(substr(v_last, 1, 1)) + 1) || '00001';
        ELSE
            RAISE EXCEPTION 'CHAT_NUMBER_EXHAUSTED';
        END IF;
    END IF;
    SELECT coalesce(max(generation), 0) + 1 INTO v_gen FROM bem_control.chat_lease
     WHERE tenant_id = p_tenant_id AND role_key = p_role_key;

    INSERT INTO bem_control.chat_lease
           (lease_id, tenant_id, role_key, chat_number, generation, work_item_id, holder_session, rules_commit,
            code_commit, status, opened_by)
    VALUES (v_id, p_tenant_id, p_role_key, v_num, v_gen, p_work_item_id, p_holder_session, v_rules,
            p_code_commit, 'OPEN', v_actor);
    PERFORM bem_control.evidence_write(p_tenant_id, 'CHAT_LEASE_OPENED', jsonb_build_object(
        'lease_id', v_id, 'role_key', p_role_key, 'chat_number', v_num, 'generation', v_gen,
        'work_item_id', p_work_item_id, 'holder_session', p_holder_session, 'rules_commit', v_rules,
        'code_commit', p_code_commit));
    RETURN QUERY SELECT v_id, v_gen, v_num, v_rules;
END;
$$;
ALTER FUNCTION bem_control.open_chat_lease(uuid, text, uuid, text, text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.open_chat_lease(uuid, text, uuid, text, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.open_chat_lease(uuid, text, uuid, text, text, text) TO bem_kernel_rw;

-- Итог, память роли или следующий шаг (RG13-01). Аренда ищется строго по (заказчик, номер аренды) под
-- блокировкой; поколение и сессия держателя сверяются с проверенной посредником сессией вызывающего.
-- Поля аренды в доказательство кладёт база; одноимённые поля из p_payload перекрываются.
CREATE FUNCTION bem_control.record_lease_evidence(
    p_tenant_id uuid, p_lease_id uuid, p_generation integer, p_caller_session text, p_kind text,
    p_content_sha256 text, p_payload jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_lease bem_control.chat_lease;
    v_ev    uuid;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    PERFORM bem_control.current_actor_checked(p_tenant_id);
    IF p_kind IS NULL OR p_kind NOT IN ('TASK_RESULT', 'ROLE_MEMORY', 'NEXT_STEP') THEN
        RAISE EXCEPTION 'LEASE_EVIDENCE_BAD_KIND';
    END IF;
    IF p_content_sha256 IS NULL OR p_content_sha256 !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'LEASE_EVIDENCE_BAD_SHA'; END IF;
    IF p_payload IS NOT NULL AND jsonb_typeof(p_payload) <> 'object' THEN RAISE EXCEPTION 'LEASE_EVIDENCE_BAD_PAYLOAD'; END IF;
    SELECT * INTO v_lease FROM bem_control.chat_lease
     WHERE tenant_id = p_tenant_id AND lease_id = p_lease_id FOR UPDATE;
    IF v_lease.lease_id IS NULL THEN RAISE EXCEPTION 'LEASE_NOT_FOUND'; END IF;
    IF p_caller_session IS DISTINCT FROM v_lease.holder_session THEN RAISE EXCEPTION 'LEASE_NOT_HOLDER'; END IF;
    IF p_generation IS DISTINCT FROM v_lease.generation THEN RAISE EXCEPTION 'LEASE_GENERATION_MISMATCH'; END IF;
    IF v_lease.status <> 'OPEN' THEN RAISE EXCEPTION 'LEASE_NOT_OPEN'; END IF;

    v_ev := bem_control.evidence_write(p_tenant_id, p_kind, coalesce(p_payload, '{}'::jsonb) || jsonb_build_object(
        'lease_id', v_lease.lease_id, 'role_key', v_lease.role_key, 'generation', v_lease.generation,
        'work_item_id', v_lease.work_item_id, 'session', v_lease.holder_session, 'content_sha256', p_content_sha256));
    INSERT INTO bem_control.chat_lease_evidence
           (evidence_id, tenant_id, lease_id, generation, work_item_id, kind, holder_session, content_sha256)
    VALUES (v_ev, p_tenant_id, v_lease.lease_id, v_lease.generation, v_lease.work_item_id, p_kind,
            v_lease.holder_session, p_content_sha256);
    RETURN v_ev;
END;
$$;
ALTER FUNCTION bem_control.record_lease_evidence(uuid, uuid, integer, text, text, text, jsonb) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.record_lease_evidence(uuid, uuid, integer, text, text, text, jsonb) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.record_lease_evidence(uuid, uuid, integer, text, text, text, jsonb) TO bem_kernel_rw;

-- Отчёт выше (RG13-02). Подаёт держатель аренды. Адресата выбирает база по иерархии ролей той версии правил,
-- с которой открыта аренда: вышестоящая роль — её открытая аренда (номер, поколение, сессия держателя) или
-- оператор. Возвращает номер отчёта.
CREATE FUNCTION bem_control.file_lease_report(
    p_tenant_id uuid, p_lease_id uuid, p_generation integer, p_caller_session text, p_report_sha256 text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_lease  bem_control.chat_lease;
    v_parent text;
    v_up     bem_control.chat_lease;
    v_id     uuid := gen_random_uuid();
    v_ev     uuid;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    PERFORM bem_control.current_actor_checked(p_tenant_id);
    IF p_report_sha256 IS NULL OR p_report_sha256 !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'REPORT_BAD_SHA'; END IF;
    SELECT * INTO v_lease FROM bem_control.chat_lease
     WHERE tenant_id = p_tenant_id AND lease_id = p_lease_id FOR UPDATE;
    IF v_lease.lease_id IS NULL THEN RAISE EXCEPTION 'LEASE_NOT_FOUND'; END IF;
    IF p_caller_session IS DISTINCT FROM v_lease.holder_session THEN RAISE EXCEPTION 'LEASE_NOT_HOLDER'; END IF;
    IF p_generation IS DISTINCT FROM v_lease.generation THEN RAISE EXCEPTION 'LEASE_GENERATION_MISMATCH'; END IF;
    IF v_lease.status <> 'OPEN' THEN RAISE EXCEPTION 'LEASE_NOT_OPEN'; END IF;

    SELECT role_parents->>v_lease.role_key INTO v_parent FROM bem_control.rules_activation
     WHERE tenant_id = p_tenant_id AND rules_commit = v_lease.rules_commit;
    IF v_parent IS NULL THEN RAISE EXCEPTION 'REPORT_ROLE_NOT_IN_HIERARCHY: %', v_lease.role_key; END IF;
    IF v_parent <> 'OPERATOR' THEN
        SELECT * INTO v_up FROM bem_control.chat_lease
         WHERE tenant_id = p_tenant_id AND role_key = v_parent AND status = 'OPEN' FOR SHARE;
        IF v_up.lease_id IS NULL THEN RAISE EXCEPTION 'REPORT_RECIPIENT_NOT_AVAILABLE: %', v_parent; END IF;
    END IF;

    v_ev := bem_control.evidence_write(p_tenant_id, 'REPORT_FILED', jsonb_build_object(
        'report_id', v_id, 'lease_id', v_lease.lease_id, 'generation', v_lease.generation,
        'work_item_id', v_lease.work_item_id, 'from_role_key', v_lease.role_key,
        'from_session', v_lease.holder_session, 'recipient_role_key', v_parent,
        'recipient_lease_id', v_up.lease_id, 'recipient_generation', v_up.generation,
        'recipient_session', v_up.holder_session, 'report_sha256', p_report_sha256));
    INSERT INTO bem_control.lease_report
           (report_id, tenant_id, lease_id, generation, work_item_id, from_role_key, from_session,
            recipient_role_key, recipient_lease_id, recipient_generation, recipient_session, report_sha256,
            filed_evidence_id)
    VALUES (v_id, p_tenant_id, v_lease.lease_id, v_lease.generation, v_lease.work_item_id, v_lease.role_key,
            v_lease.holder_session, v_parent, v_up.lease_id, v_up.generation, v_up.holder_session, p_report_sha256,
            v_ev);
    RETURN v_id;
END;
$$;
ALTER FUNCTION bem_control.file_lease_report(uuid, uuid, integer, text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.file_lease_report(uuid, uuid, integer, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.file_lease_report(uuid, uuid, integer, text, text) TO bem_kernel_rw;

-- Подтверждение отчёта адресатом (RG13-02). Отчёт ищется строго по (заказчик, номер отчёта) под блокировкой;
-- сумма отчёта и проверенный посредником вызывающий сверяются с закреплённым адресатом. Для адресата
-- 'OPERATOR' вызывающий — 'OPERATOR', а p_operator_signature — проверенная ядром подпись билета
-- {tenant_id, report_id, report_sha256} в пространстве имён zavod-report-ack@v1. Повтор тем же адресатом
-- возвращает прежнее подтверждение без записи. Путь оператора принимается только от входной роли
-- bem_rules_gate (RG14-01). Смена аренды адресата проверяется раньше повтора (RG14-02).
CREATE FUNCTION bem_control.acknowledge_lease_report(
    p_tenant_id uuid, p_report_id uuid, p_report_sha256 text, p_caller_role_key text, p_caller_session text,
    p_operator_signature jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_rep  bem_control.lease_report;
    v_up   bem_control.chat_lease;
    v_sess text;
    v_ev   uuid;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    PERFORM bem_control.current_actor_checked(p_tenant_id);
    SELECT * INTO v_rep FROM bem_control.lease_report
     WHERE tenant_id = p_tenant_id AND report_id = p_report_id FOR UPDATE;
    IF v_rep.report_id IS NULL THEN RAISE EXCEPTION 'REPORT_NOT_FOUND'; END IF;
    IF p_report_sha256 IS DISTINCT FROM v_rep.report_sha256 THEN RAISE EXCEPTION 'REPORT_SHA_MISMATCH'; END IF;
    IF p_caller_role_key IS DISTINCT FROM v_rep.recipient_role_key THEN RAISE EXCEPTION 'REPORT_NOT_RECIPIENT'; END IF;
    IF v_rep.recipient_role_key = 'OPERATOR' THEN
        IF session_user IS DISTINCT FROM 'bem_rules_gate' THEN RAISE EXCEPTION 'REPORT_OPERATOR_ACK_UNTRUSTED'; END IF;
        IF p_caller_session IS DISTINCT FROM 'OPERATOR'
           OR p_operator_signature IS NULL OR jsonb_typeof(p_operator_signature) <> 'object'
           OR p_operator_signature->>'namespace' IS DISTINCT FROM 'zavod-report-ack@v1'
           OR coalesce(p_operator_signature->>'key_fingerprint', '') !~ '^SHA256:[A-Za-z0-9+/]{43}$'
           OR coalesce(p_operator_signature->>'signed_ticket_sha256', '') !~ '^[0-9a-f]{64}$'
           OR p_operator_signature->'ticket' IS DISTINCT FROM jsonb_build_object(
                'tenant_id', p_tenant_id::text, 'report_id', p_report_id::text, 'report_sha256', v_rep.report_sha256) THEN
            RAISE EXCEPTION 'REPORT_NOT_RECIPIENT';
        END IF;
        v_sess := 'OPERATOR';
    ELSE
        IF p_caller_session IS DISTINCT FROM v_rep.recipient_session THEN RAISE EXCEPTION 'REPORT_NOT_RECIPIENT'; END IF;
        v_sess := v_rep.recipient_session;
    END IF;
    IF v_rep.recipient_role_key <> 'OPERATOR' THEN
        -- Адресат обязан всё ещё держать ту же аренду того же поколения; сменился чат — отчёт подаётся заново.
        -- Проверка стоит до повтора: подтверждение ушедшего чата не возвращается (RG14-02).
        SELECT * INTO v_up FROM bem_control.chat_lease
         WHERE tenant_id = p_tenant_id AND lease_id = v_rep.recipient_lease_id FOR SHARE;
        IF v_up.status IS DISTINCT FROM 'OPEN' OR v_up.generation IS DISTINCT FROM v_rep.recipient_generation
           OR v_up.holder_session IS DISTINCT FROM v_rep.recipient_session THEN
            RAISE EXCEPTION 'REPORT_RECIPIENT_CHANGED';
        END IF;
    END IF;
    IF v_rep.ack_evidence_id IS NOT NULL THEN
        IF v_rep.ack_session = v_sess THEN RETURN v_rep.ack_evidence_id; END IF;   -- честный повтор
        RAISE EXCEPTION 'REPORT_ALREADY_ACKNOWLEDGED';
    END IF;

    v_ev := bem_control.evidence_write(p_tenant_id, 'REPORT_ACKNOWLEDGED', jsonb_build_object(
        'report_id', v_rep.report_id, 'lease_id', v_rep.lease_id, 'generation', v_rep.generation,
        'recipient_role_key', v_rep.recipient_role_key, 'ack_session', v_sess,
        'report_sha256', v_rep.report_sha256, 'operator_signature', p_operator_signature));
    UPDATE bem_control.lease_report SET ack_evidence_id = v_ev, ack_session = v_sess, acked_at = now()
     WHERE report_id = v_rep.report_id;
    RETURN v_ev;
END;
$$;
ALTER FUNCTION bem_control.acknowledge_lease_report(uuid, uuid, text, text, text, jsonb) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.acknowledge_lease_report(uuid, uuid, text, text, text, jsonb) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.acknowledge_lease_report(uuid, uuid, text, text, text, jsonb) TO bem_kernel_rw;
GRANT  EXECUTE ON FUNCTION bem_control.acknowledge_lease_report(uuid, uuid, text, text, text, jsonb) TO bem_rules_gate;

-- Завершение задачи (Л.12, RG13-03). Возвращает номер доказательства CHAT_LEASE_COMPLETED — квитанцию.
-- Порядок: блокировка аренды по (заказчик, номер аренды) -> сессия держателя -> поколение (старое поколение —
-- отказ в обоих случаях) -> COMPLETED: те же четыре номера — прежняя квитанция без записи, иначе отказ;
-- OPEN: работа завершена, три записи держателя и подтверждённый отчёт этой аренды и поколения, адресат которого
-- всё ещё держит ту же аренду того же поколения той же сессией (RG14-03) -> одна запись.
CREATE FUNCTION bem_control.complete_chat_lease(
    p_tenant_id uuid, p_lease_id uuid, p_generation integer, p_caller_session text,
    p_result_evidence uuid, p_memory_evidence uuid, p_next_evidence uuid, p_report_id uuid)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_lease  bem_control.chat_lease;
    v_status text;
    v_rep    bem_control.lease_report;
    v_up     bem_control.chat_lease;
    r        record;
    v_ev     uuid;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    PERFORM bem_control.current_actor_checked(p_tenant_id);
    SELECT * INTO v_lease FROM bem_control.chat_lease
     WHERE tenant_id = p_tenant_id AND lease_id = p_lease_id FOR UPDATE;
    IF v_lease.lease_id IS NULL THEN RAISE EXCEPTION 'LEASE_NOT_FOUND'; END IF;
    IF p_caller_session IS DISTINCT FROM v_lease.holder_session THEN RAISE EXCEPTION 'LEASE_NOT_HOLDER'; END IF;
    IF p_generation IS DISTINCT FROM v_lease.generation THEN RAISE EXCEPTION 'LEASE_GENERATION_MISMATCH'; END IF;
    IF v_lease.status = 'COMPLETED' THEN
        IF v_lease.result_evidence_id = p_result_evidence AND v_lease.memory_evidence_id = p_memory_evidence
           AND v_lease.next_evidence_id = p_next_evidence AND v_lease.report_id = p_report_id THEN
            RETURN v_lease.completion_evidence_id;   -- честный повтор: та же квитанция, новой записи нет
        END IF;
        RAISE EXCEPTION 'LEASE_COMPLETION_MISMATCH';
    END IF;

    SELECT status INTO v_status FROM bem_core.work_item WHERE id = v_lease.work_item_id AND tenant_id = p_tenant_id;
    IF v_status IS NULL OR v_status NOT IN ('ACCEPTED', 'RELEASED', 'CANCELLED') THEN
        RAISE EXCEPTION 'LEASE_WORK_NOT_DONE: %', v_status;
    END IF;
    FOR r IN SELECT * FROM (VALUES
        ('TASK_RESULT', p_result_evidence), ('ROLE_MEMORY', p_memory_evidence), ('NEXT_STEP', p_next_evidence))
        AS x(kind, id) LOOP
        IF NOT EXISTS (SELECT 1 FROM bem_control.chat_lease_evidence e
                        WHERE e.evidence_id = r.id AND e.tenant_id = p_tenant_id AND e.lease_id = p_lease_id
                          AND e.generation = v_lease.generation AND e.kind = r.kind
                          AND e.holder_session = v_lease.holder_session) THEN
            RAISE EXCEPTION 'LEASE_EVIDENCE_MISSING: %', r.kind;
        END IF;
    END LOOP;
    SELECT * INTO v_rep FROM bem_control.lease_report
     WHERE tenant_id = p_tenant_id AND report_id = p_report_id;
    IF v_rep.report_id IS NULL OR v_rep.lease_id IS DISTINCT FROM p_lease_id
       OR v_rep.generation IS DISTINCT FROM v_lease.generation OR v_rep.from_session IS DISTINCT FROM v_lease.holder_session THEN
        RAISE EXCEPTION 'LEASE_EVIDENCE_MISSING: REPORTED_UP';
    END IF;
    IF v_rep.ack_evidence_id IS NULL THEN RAISE EXCEPTION 'LEASE_REPORT_NOT_ACKNOWLEDGED'; END IF;
    IF v_rep.recipient_role_key <> 'OPERATOR' THEN
        -- Подтвердивший чат сменился — подтверждение больше не действует, нужен новый отчёт (RG14-03).
        SELECT * INTO v_up FROM bem_control.chat_lease
         WHERE tenant_id = p_tenant_id AND lease_id = v_rep.recipient_lease_id FOR SHARE;
        IF v_up.status IS DISTINCT FROM 'OPEN' OR v_up.generation IS DISTINCT FROM v_rep.recipient_generation
           OR v_up.holder_session IS DISTINCT FROM v_rep.recipient_session THEN
            RAISE EXCEPTION 'LEASE_REPORT_RECIPIENT_CHANGED';
        END IF;
    END IF;

    v_ev := bem_control.evidence_write(p_tenant_id, 'CHAT_LEASE_COMPLETED', jsonb_build_object(
        'lease_id', p_lease_id, 'role_key', v_lease.role_key, 'chat_number', v_lease.chat_number,
        'generation', v_lease.generation, 'work_item_id', v_lease.work_item_id, 'work_status', v_status,
        'holder_session', v_lease.holder_session, 'rules_commit', v_lease.rules_commit,
        'result_evidence_id', p_result_evidence, 'memory_evidence_id', p_memory_evidence,
        'next_evidence_id', p_next_evidence, 'report_id', p_report_id,
        'report_ack_evidence_id', v_rep.ack_evidence_id, 'report_recipient', v_rep.recipient_role_key));
    UPDATE bem_control.chat_lease
       SET status = 'COMPLETED', closed_at = now(), completion_evidence_id = v_ev,
           result_evidence_id = p_result_evidence, memory_evidence_id = p_memory_evidence,
           next_evidence_id = p_next_evidence, report_id = p_report_id
     WHERE tenant_id = p_tenant_id AND lease_id = p_lease_id;
    RETURN v_ev;
END;
$$;
ALTER FUNCTION bem_control.complete_chat_lease(uuid, uuid, integer, text, uuid, uuid, uuid, uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.complete_chat_lease(uuid, uuid, integer, text, uuid, uuid, uuid, uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.complete_chat_lease(uuid, uuid, integer, text, uuid, uuid, uuid, uuid) TO bem_kernel_rw;
