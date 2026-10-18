-- ДОКУМЕНТ: db/04_zavod_ext_03.sql (расширение Z-EXT-03: пакет Z-TRANSPORT-01, привратник)
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-10-18 10:24 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 10:38 +03:00 (пропуск истекает по аренде, закрытой после его выдачи)
-- ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
-- ОСНОВАНИЕ: проект ПРОЕКТ_Z_TRANSPORT_01_20261018.md v0.4 (ChatGPT R23 APPROVE 0/0/0), §3–§5.
-- НАЗНАЧЕНИЕ: (1) участник роли role_actor — пишет только путь управления (bem_governance), §4;
--   (2) выдача пропуска сессии: подготовка (prepare_session_enrollment) держателем той же роли, держателем
--       роли-начальника или по билету оператора (только входная роль bem_rules_gate), получение
--       (claim_session_enrollment) по одноразовому коду, §3.1;
--   (3) проверка пропуска (lookup_session_credential), §3.2; отзыв (revoke_session_credential), §3.1 шаг 3.
--   В базе только SHA-256 кода выдачи и пропуска; открытые значения сюда не попадают.
--   Отказы (§3.3): обычный отказ — код возврата без изменений базы; событие безопасности — ровно оговорённые
--   строки и одна строка доказательства SESSION_SECURITY_EVENT, тоже кодом возврата, без исключения.
-- ОГРАНИЧЕНИЯ: ставится после 03_zavod_ext_02.sql одной транзакцией; не удаляет данных и объектов, не меняет
--   существующие строки и функции H1.31/Z-EXT-01/Z-EXT-02. Отзыв при завершении аренды ядро вызывает в той же
--   транзакции, что и complete_chat_lease (функция Z-EXT-02 не меняется); проверка пропуска дополнительно
--   считает пропуск недействительным, если аренда этой сессии завершена.

-- (1) Участник роли (§4). Пропуск копирует участника при выдаче; смена действует с новой выдачи.
CREATE TABLE bem_control.role_actor (
    tenant_id   uuid NOT NULL,
    role_key    text NOT NULL CHECK (role_key ~ '^0[1-9]_[^/\\]{1,60}$' OR role_key = 'OPERATOR'),
    actor_id    text NOT NULL REFERENCES bem_core.actor (actor_id),
    set_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, role_key)
);
ALTER TABLE bem_control.role_actor OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.role_actor FROM PUBLIC;
GRANT SELECT ON bem_control.role_actor TO bem_kernel_rw;
GRANT SELECT ON bem_control.role_actor TO bem_rules_gate;
GRANT SELECT ON bem_control.role_actor TO backup_reader;

-- (2) Выдача пропуска (§3.1). Одна ожидающая на роль заказчика; одноразовый номер билета оператора — один раз.
CREATE TABLE bem_control.session_enrollment (
    enrollment_id       uuid NOT NULL PRIMARY KEY,
    tenant_id           uuid NOT NULL,
    role_key            text NOT NULL CHECK (role_key ~ '^0[1-9]_[^/\\]{1,60}$'),
    session             text NOT NULL CHECK (btrim(session) <> '' AND session <> 'OPERATOR' AND length(session) <= 200),
    claim_sha256        text NOT NULL CHECK (claim_sha256 ~ '^[0-9a-f]{64}$'),
    prepared_by         text NOT NULL CHECK (prepared_by IN ('SAME_ROLE', 'PARENT_ROLE', 'OPERATOR_TICKET')),
    prepared_by_session text,
    prepared_by_lease   uuid,
    ticket_nonce        text CHECK (ticket_nonce ~ '^[0-9a-f]{32,64}$'),
    status              text NOT NULL CHECK (status IN ('PENDING', 'CLAIMED', 'CONFLICT', 'EXPIRED')),
    created_at          timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz NOT NULL,
    claimed_at          timestamptz,
    credential_id       uuid,
    prepared_evidence_id uuid NOT NULL,
    CONSTRAINT session_enrollment_by_shape CHECK (
        (prepared_by = 'OPERATOR_TICKET' AND ticket_nonce IS NOT NULL AND prepared_by_session IS NULL
            AND prepared_by_lease IS NULL)
        OR (prepared_by <> 'OPERATOR_TICKET' AND ticket_nonce IS NULL AND prepared_by_session IS NOT NULL
            AND prepared_by_lease IS NOT NULL)),
    CONSTRAINT session_enrollment_claim_pair CHECK (
        (status IN ('CLAIMED', 'CONFLICT')) = (claimed_at IS NOT NULL AND credential_id IS NOT NULL))
);
CREATE UNIQUE INDEX session_enrollment_one_pending ON bem_control.session_enrollment (tenant_id, role_key)
    WHERE status = 'PENDING';
CREATE UNIQUE INDEX session_enrollment_ticket_once ON bem_control.session_enrollment (tenant_id, ticket_nonce)
    WHERE ticket_nonce IS NOT NULL;
ALTER TABLE bem_control.session_enrollment OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.session_enrollment FROM PUBLIC;
GRANT SELECT ON bem_control.session_enrollment TO backup_reader;

-- (3) Пропуск сессии (§3). Одна живая на сессию. Открытый пропуск в базе не хранится.
CREATE TABLE bem_control.session_credential (
    credential_id  uuid NOT NULL PRIMARY KEY,
    tenant_id      uuid NOT NULL,
    role_key       text NOT NULL CHECK (role_key ~ '^0[1-9]_[^/\\]{1,60}$'),
    session        text NOT NULL CHECK (btrim(session) <> '' AND session <> 'OPERATOR' AND length(session) <= 200),
    actor_id       text NOT NULL REFERENCES bem_core.actor (actor_id),
    pass_sha256    text NOT NULL UNIQUE CHECK (pass_sha256 ~ '^[0-9a-f]{64}$'),
    enrollment_id  uuid NOT NULL REFERENCES bem_control.session_enrollment (enrollment_id),
    issued_at      timestamptz NOT NULL DEFAULT now(),
    revoked_at     timestamptz,
    revoke_reason  text CHECK (revoke_reason IN ('LEASE_COMPLETED', 'OPERATOR_TICKET', 'CLAIM_REPLAY')),
    CONSTRAINT session_credential_revoke_pair CHECK ((revoked_at IS NULL) = (revoke_reason IS NULL))
);
CREATE UNIQUE INDEX session_credential_one_live ON bem_control.session_credential (session)
    WHERE revoked_at IS NULL;
ALTER TABLE bem_control.session_credential OWNER TO bem_control_owner;
REVOKE ALL ON bem_control.session_credential FROM PUBLIC;
GRANT SELECT ON bem_control.session_credential TO backup_reader;

-- Контекст заказчика и участника для доказательства пишет сама функция из своих строк (не из запроса):
-- новая сессия до получения пропуска участника не знает. SET LOCAL — до конца транзакции.
CREATE FUNCTION bem_control.transport_context(p_tenant_id uuid, p_actor_id text)
RETURNS void
LANGUAGE sql
SET search_path = pg_catalog, pg_temp
AS $$ SELECT set_config('app.tenant_id', p_tenant_id::text, true), set_config('app.actor_id', p_actor_id, true) $$;
ALTER FUNCTION bem_control.transport_context(uuid, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.transport_context(uuid, text) FROM PUBLIC;

-- Участник роли — только путь управления (§4).
CREATE FUNCTION bem_control.set_role_actor(p_tenant_id uuid, p_role_key text, p_actor_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
BEGIN
    IF p_tenant_id IS NULL THEN RAISE EXCEPTION 'ROLE_ACTOR_TENANT_REQUIRED'; END IF;
    IF p_role_key IS NULL OR NOT (p_role_key ~ '^0[1-9]_[^/\\]{1,60}$' OR p_role_key = 'OPERATOR') THEN
        RAISE EXCEPTION 'ROLE_ACTOR_BAD_ROLE';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM bem_core.actor WHERE actor_id = p_actor_id AND is_active) THEN
        RAISE EXCEPTION 'ROLE_ACTOR_UNKNOWN';
    END IF;
    INSERT INTO bem_control.role_actor (tenant_id, role_key, actor_id) VALUES (p_tenant_id, p_role_key, p_actor_id)
    ON CONFLICT (tenant_id, role_key) DO UPDATE SET actor_id = EXCLUDED.actor_id, set_at = now();
END;
$$;
ALTER FUNCTION bem_control.set_role_actor(uuid, text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.set_role_actor(uuid, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.set_role_actor(uuid, text, text) TO bem_governance;

-- Подготовка выдачи (§3.1 шаг 1). Держатель той же роли или роли-начальника — ролью ядра, со своей проверенной
-- сессией (её даёт посредник), с открытой арендой и живым пропуском. Роль под оператором — только по билету
-- оператора, только входной ролью bem_rules_gate (подпись проверяет ядро, src/rules_gate.mjs).
CREATE FUNCTION bem_control.prepare_session_enrollment(
    p_tenant_id uuid, p_role_key text, p_session text, p_claim_sha256 text, p_by_session text,
    p_ticket_nonce text, p_ticket_expires timestamptz)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_parents jsonb;
    v_parent  text;
    v_by      text;
    v_by_role text;
    v_lease   uuid;
    v_id      uuid := gen_random_uuid();
    v_ev      uuid;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    PERFORM bem_control.current_actor_checked(p_tenant_id);
    IF p_role_key IS NULL OR p_role_key !~ '^0[1-9]_[^/\\]{1,60}$' THEN RAISE EXCEPTION 'ENROLL_BAD_ROLE'; END IF;
    IF p_session IS NULL OR btrim(p_session) = '' OR p_session = 'OPERATOR' OR length(p_session) > 200 THEN
        RAISE EXCEPTION 'ENROLL_BAD_SESSION';
    END IF;
    IF p_claim_sha256 IS NULL OR p_claim_sha256 !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'ENROLL_BAD_CODE_HASH'; END IF;
    PERFORM pg_advisory_xact_lock(hashtext('bem_control.session_enrollment:' || p_tenant_id::text || ':' || p_role_key));

    SELECT role_parents INTO v_parents FROM bem_control.rules_activation
     WHERE tenant_id = p_tenant_id AND superseded_at IS NULL;
    IF v_parents IS NULL THEN RAISE EXCEPTION 'ENROLL_NO_ACTIVE_RULES'; END IF;
    IF NOT (v_parents ? p_role_key) THEN RAISE EXCEPTION 'ENROLL_ROLE_NOT_IN_RULES: %', p_role_key; END IF;
    v_parent := v_parents ->> p_role_key;

    IF p_ticket_nonce IS NOT NULL THEN
        IF session_user IS DISTINCT FROM 'bem_rules_gate' THEN RAISE EXCEPTION 'ENROLL_TICKET_UNTRUSTED'; END IF;
        IF v_parent IS DISTINCT FROM 'OPERATOR' THEN RAISE EXCEPTION 'ENROLL_TICKET_NOT_FOR_ROLE'; END IF;
        IF p_ticket_nonce !~ '^[0-9a-f]{32,64}$' THEN RAISE EXCEPTION 'ENROLL_TICKET_BAD_NONCE'; END IF;
        IF p_ticket_expires IS NULL OR p_ticket_expires <= now() OR p_ticket_expires > now() + interval '24 hours' THEN
            RAISE EXCEPTION 'ENROLL_TICKET_EXPIRED';
        END IF;
        IF EXISTS (SELECT 1 FROM bem_control.session_enrollment
                    WHERE tenant_id = p_tenant_id AND ticket_nonce = p_ticket_nonce) THEN
            RAISE EXCEPTION 'ENROLL_TICKET_REUSED';
        END IF;
        v_by := 'OPERATOR_TICKET';
    ELSE
        IF session_user IS DISTINCT FROM 'bem_kernel_rw' THEN RAISE EXCEPTION 'ENROLL_UNTRUSTED'; END IF;
        IF p_by_session IS NULL OR btrim(p_by_session) = '' THEN RAISE EXCEPTION 'ENROLL_NOT_AUTHORIZED'; END IF;
        -- Разрешивший: живой пропуск и открытая аренда той же сессии, роль та же или роль-начальник.
        SELECT c.role_key INTO v_by_role FROM bem_control.session_credential c
         WHERE c.tenant_id = p_tenant_id AND c.session = p_by_session AND c.revoked_at IS NULL;
        IF v_by_role IS NULL THEN RAISE EXCEPTION 'ENROLL_NOT_AUTHORIZED'; END IF;
        SELECT l.lease_id INTO v_lease FROM bem_control.chat_lease l
         WHERE l.tenant_id = p_tenant_id AND l.role_key = v_by_role AND l.holder_session = p_by_session
           AND l.status = 'OPEN';
        IF v_lease IS NULL THEN RAISE EXCEPTION 'ENROLL_NOT_AUTHORIZED'; END IF;
        IF v_by_role = p_role_key THEN
            v_by := 'SAME_ROLE';
        ELSIF v_by_role = v_parent THEN
            v_by := 'PARENT_ROLE';
        ELSE
            RAISE EXCEPTION 'ENROLL_NOT_AUTHORIZED';
        END IF;
        IF p_by_session = p_session THEN RAISE EXCEPTION 'ENROLL_SELF'; END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM bem_control.session_credential WHERE session = p_session AND revoked_at IS NULL) THEN
        RAISE EXCEPTION 'ENROLL_SESSION_HAS_PASS';
    END IF;
    -- Истёкшая ожидающая освобождает место; живая — одна на роль.
    UPDATE bem_control.session_enrollment SET status = 'EXPIRED'
     WHERE tenant_id = p_tenant_id AND role_key = p_role_key AND status = 'PENDING' AND expires_at <= now();
    IF EXISTS (SELECT 1 FROM bem_control.session_enrollment
                WHERE tenant_id = p_tenant_id AND role_key = p_role_key AND status = 'PENDING') THEN
        RAISE EXCEPTION 'ENROLL_BUSY';
    END IF;

    v_ev := bem_control.evidence_write(p_tenant_id, 'SESSION_ENROLLMENT_PREPARED', jsonb_build_object(
        'enrollment_id', v_id, 'role_key', p_role_key, 'session', p_session, 'prepared_by', v_by,
        'prepared_by_session', CASE WHEN v_by = 'OPERATOR_TICKET' THEN NULL ELSE p_by_session END,
        'prepared_by_lease', v_lease, 'ticket_nonce', p_ticket_nonce));
    INSERT INTO bem_control.session_enrollment
           (enrollment_id, tenant_id, role_key, session, claim_sha256, prepared_by, prepared_by_session,
            prepared_by_lease, ticket_nonce, status, expires_at, prepared_evidence_id)
    VALUES (v_id, p_tenant_id, p_role_key, p_session, p_claim_sha256, v_by,
            CASE WHEN v_by = 'OPERATOR_TICKET' THEN NULL ELSE p_by_session END,
            CASE WHEN v_by = 'OPERATOR_TICKET' THEN NULL ELSE v_lease END,
            p_ticket_nonce, 'PENDING', now() + interval '10 minutes', v_ev);
    RETURN v_id;
END;
$$;
ALTER FUNCTION bem_control.prepare_session_enrollment(uuid, text, text, text, text, text, timestamptz) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.prepare_session_enrollment(uuid, text, text, text, text, text, timestamptz) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.prepare_session_enrollment(uuid, text, text, text, text, text, timestamptz) TO bem_kernel_rw;
GRANT  EXECUTE ON FUNCTION bem_control.prepare_session_enrollment(uuid, text, text, text, text, text, timestamptz) TO bem_rules_gate;

-- Получение пропуска (§3.1 шаг 2, §3.3). Возвращает код, без исключений:
--   OK — пропуск создан, запись «получена», доказательство SESSION_ENROLLED;
--   ENROLL_NOT_FOUND / ENROLL_EXPIRED / ENROLL_BAD_CODE / ENROLL_NO_ROLE_ACTOR / ENROLL_SESSION_HAS_PASS —
--     обычный отказ, база не меняется (неверный код ничего не отзывает, RG21-01);
--   ENROLL_REPLAY — верный код после выдачи (событие безопасности): пропуск этой записи отозван, запись
--     «конфликт», одна строка SESSION_SECURITY_EVENT.
CREATE FUNCTION bem_control.claim_session_enrollment(p_session text, p_claim_sha256 text, p_pass_sha256 text)
RETURNS TABLE (out_code text, out_tenant_id uuid, out_role_key text, out_actor_id text, out_credential_id uuid)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_en    bem_control.session_enrollment;
    v_cred  bem_control.session_credential;
    v_actor text;
    v_id    uuid := gen_random_uuid();
    v_ev    uuid;
BEGIN
    IF session_user IS DISTINCT FROM 'bem_kernel_rw' THEN RAISE EXCEPTION 'ENROLL_UNTRUSTED'; END IF;
    IF p_session IS NULL OR btrim(p_session) = '' OR p_claim_sha256 IS NULL OR p_claim_sha256 !~ '^[0-9a-f]{64}$'
       OR p_pass_sha256 IS NULL OR p_pass_sha256 !~ '^[0-9a-f]{64}$' THEN
        RETURN QUERY SELECT 'ENROLL_BAD_REQUEST'::text, NULL::uuid, NULL::text, NULL::text, NULL::uuid; RETURN;
    END IF;
    SELECT * INTO v_en FROM bem_control.session_enrollment
     WHERE session = p_session AND status IN ('PENDING', 'CLAIMED')
     ORDER BY created_at DESC LIMIT 1 FOR UPDATE;
    IF v_en.enrollment_id IS NULL THEN
        RETURN QUERY SELECT 'ENROLL_NOT_FOUND'::text, NULL::uuid, NULL::text, NULL::text, NULL::uuid; RETURN;
    END IF;
    IF v_en.claim_sha256 IS DISTINCT FROM p_claim_sha256 THEN
        RETURN QUERY SELECT 'ENROLL_BAD_CODE'::text, NULL::uuid, NULL::text, NULL::text, NULL::uuid; RETURN;
    END IF;

    IF v_en.status = 'CLAIMED' THEN
        -- Верный код второй раз: его знает кто-то третий. Отзыв пропуска этой записи и тревога.
        SELECT * INTO v_cred FROM bem_control.session_credential WHERE credential_id = v_en.credential_id FOR UPDATE;
        PERFORM bem_control.transport_context(v_en.tenant_id, v_cred.actor_id);
        v_ev := bem_control.evidence_write(v_en.tenant_id, 'SESSION_SECURITY_EVENT', jsonb_build_object(
            'event', 'CLAIM_REPLAY', 'enrollment_id', v_en.enrollment_id, 'role_key', v_en.role_key,
            'session', v_en.session, 'credential_id', v_en.credential_id));
        UPDATE bem_control.session_credential SET revoked_at = now(), revoke_reason = 'CLAIM_REPLAY'
         WHERE credential_id = v_en.credential_id AND revoked_at IS NULL;
        UPDATE bem_control.session_enrollment SET status = 'CONFLICT' WHERE enrollment_id = v_en.enrollment_id;
        RETURN QUERY SELECT 'ENROLL_REPLAY'::text, NULL::uuid, NULL::text, NULL::text, NULL::uuid; RETURN;
    END IF;

    IF v_en.expires_at <= now() THEN
        RETURN QUERY SELECT 'ENROLL_EXPIRED'::text, NULL::uuid, NULL::text, NULL::text, NULL::uuid; RETURN;
    END IF;
    SELECT actor_id INTO v_actor FROM bem_control.role_actor WHERE tenant_id = v_en.tenant_id AND role_key = v_en.role_key;
    IF v_actor IS NULL THEN
        RETURN QUERY SELECT 'ENROLL_NO_ROLE_ACTOR'::text, NULL::uuid, NULL::text, NULL::text, NULL::uuid; RETURN;
    END IF;
    IF EXISTS (SELECT 1 FROM bem_control.session_credential WHERE session = p_session AND revoked_at IS NULL)
       OR EXISTS (SELECT 1 FROM bem_control.session_credential WHERE pass_sha256 = p_pass_sha256) THEN
        RETURN QUERY SELECT 'ENROLL_SESSION_HAS_PASS'::text, NULL::uuid, NULL::text, NULL::text, NULL::uuid; RETURN;
    END IF;

    PERFORM bem_control.transport_context(v_en.tenant_id, v_actor);
    v_ev := bem_control.evidence_write(v_en.tenant_id, 'SESSION_ENROLLED', jsonb_build_object(
        'enrollment_id', v_en.enrollment_id, 'credential_id', v_id, 'role_key', v_en.role_key,
        'session', v_en.session, 'actor_id', v_actor, 'prepared_by', v_en.prepared_by));
    INSERT INTO bem_control.session_credential
           (credential_id, tenant_id, role_key, session, actor_id, pass_sha256, enrollment_id)
    VALUES (v_id, v_en.tenant_id, v_en.role_key, v_en.session, v_actor, p_pass_sha256, v_en.enrollment_id);
    UPDATE bem_control.session_enrollment SET status = 'CLAIMED', claimed_at = now(), credential_id = v_id
     WHERE enrollment_id = v_en.enrollment_id;
    RETURN QUERY SELECT 'OK'::text, v_en.tenant_id, v_en.role_key, v_actor, v_id;
END;
$$;
ALTER FUNCTION bem_control.claim_session_enrollment(text, text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.claim_session_enrollment(text, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.claim_session_enrollment(text, text, text) TO bem_kernel_rw;

-- Проверка пропуска (§3.2). Возвращает код, без исключений:
--   OK — заказчик, роль, участник и сессия из записи пропуска (не из запроса);
--   PASS_UNKNOWN / PASS_EXPIRED — обычный отказ, база не меняется;
--   PASS_REVOKED — предъявлен отозванный пропуск (событие безопасности): только одна строка доказательства.
-- Недействителен и пропуск сессии, чья аренда завершена (страховка к отзыву в CompleteChatLease), и пропуск
-- старше 30 суток без открытой аренды этой сессии.
CREATE FUNCTION bem_control.lookup_session_credential(p_session text, p_pass_sha256 text)
RETURNS TABLE (out_code text, out_tenant_id uuid, out_role_key text, out_actor_id text, out_session text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_cred bem_control.session_credential;
BEGIN
    IF session_user IS DISTINCT FROM 'bem_kernel_rw' THEN RAISE EXCEPTION 'PASS_UNTRUSTED'; END IF;
    IF p_session IS NULL OR p_pass_sha256 IS NULL OR p_pass_sha256 !~ '^[0-9a-f]{64}$' THEN
        RETURN QUERY SELECT 'PASS_UNKNOWN'::text, NULL::uuid, NULL::text, NULL::text, NULL::text; RETURN;
    END IF;
    SELECT * INTO v_cred FROM bem_control.session_credential WHERE pass_sha256 = p_pass_sha256;
    IF v_cred.credential_id IS NULL OR v_cred.session IS DISTINCT FROM p_session THEN
        RETURN QUERY SELECT 'PASS_UNKNOWN'::text, NULL::uuid, NULL::text, NULL::text, NULL::text; RETURN;
    END IF;
    IF v_cred.revoked_at IS NOT NULL THEN
        PERFORM bem_control.transport_context(v_cred.tenant_id, v_cred.actor_id);
        PERFORM bem_control.evidence_write(v_cred.tenant_id, 'SESSION_SECURITY_EVENT', jsonb_build_object(
            'event', 'REVOKED_PASS_PRESENTED', 'credential_id', v_cred.credential_id, 'role_key', v_cred.role_key,
            'session', v_cred.session, 'revoke_reason', v_cred.revoke_reason));
        RETURN QUERY SELECT 'PASS_REVOKED'::text, NULL::uuid, NULL::text, NULL::text, NULL::text; RETURN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM bem_control.chat_lease l
                    WHERE l.tenant_id = v_cred.tenant_id AND l.holder_session = v_cred.session AND l.status = 'OPEN')
       AND (EXISTS (SELECT 1 FROM bem_control.chat_lease l
                     WHERE l.tenant_id = v_cred.tenant_id AND l.holder_session = v_cred.session
                       AND l.status = 'COMPLETED' AND l.closed_at >= v_cred.issued_at)
            OR v_cred.issued_at < now() - interval '30 days') THEN
        RETURN QUERY SELECT 'PASS_EXPIRED'::text, NULL::uuid, NULL::text, NULL::text, NULL::text; RETURN;
    END IF;
    RETURN QUERY SELECT 'OK'::text, v_cred.tenant_id, v_cred.role_key, v_cred.actor_id, v_cred.session;
END;
$$;
ALTER FUNCTION bem_control.lookup_session_credential(text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.lookup_session_credential(text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.lookup_session_credential(text, text) TO bem_kernel_rw;

-- Отзыв (§3.1 шаг 3). LEASE_COMPLETED — ядро в транзакции CompleteChatLease, только если аренда этой сессии
-- завершена и открытой нет; OPERATOR_TICKET — только входная роль bem_rules_gate по проверенному билету.
-- Возвращает число отозванных (0 или 1); отозванный пропуск не оживает.
CREATE FUNCTION bem_control.revoke_session_credential(p_tenant_id uuid, p_session text, p_reason text)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_cred bem_control.session_credential;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    PERFORM bem_control.current_actor_checked(p_tenant_id);
    IF p_reason = 'LEASE_COMPLETED' THEN
        IF session_user IS DISTINCT FROM 'bem_kernel_rw' THEN RAISE EXCEPTION 'REVOKE_UNTRUSTED'; END IF;
        IF NOT EXISTS (SELECT 1 FROM bem_control.chat_lease
                        WHERE tenant_id = p_tenant_id AND holder_session = p_session AND status = 'COMPLETED')
           OR EXISTS (SELECT 1 FROM bem_control.chat_lease
                       WHERE tenant_id = p_tenant_id AND holder_session = p_session AND status = 'OPEN') THEN
            RAISE EXCEPTION 'REVOKE_LEASE_NOT_COMPLETED';
        END IF;
    ELSIF p_reason = 'OPERATOR_TICKET' THEN
        IF session_user IS DISTINCT FROM 'bem_rules_gate' THEN RAISE EXCEPTION 'REVOKE_UNTRUSTED'; END IF;
    ELSE
        RAISE EXCEPTION 'REVOKE_BAD_REASON';
    END IF;
    SELECT * INTO v_cred FROM bem_control.session_credential
     WHERE tenant_id = p_tenant_id AND session = p_session AND revoked_at IS NULL FOR UPDATE;
    IF v_cred.credential_id IS NULL THEN RETURN 0; END IF;
    PERFORM bem_control.evidence_write(p_tenant_id, 'SESSION_PASS_REVOKED', jsonb_build_object(
        'credential_id', v_cred.credential_id, 'role_key', v_cred.role_key, 'session', v_cred.session,
        'reason', p_reason));
    UPDATE bem_control.session_credential SET revoked_at = now(), revoke_reason = p_reason
     WHERE credential_id = v_cred.credential_id;
    RETURN 1;
END;
$$;
ALTER FUNCTION bem_control.revoke_session_credential(uuid, text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.revoke_session_credential(uuid, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.revoke_session_credential(uuid, text, text) TO bem_kernel_rw;
GRANT  EXECUTE ON FUNCTION bem_control.revoke_session_credential(uuid, text, text) TO bem_rules_gate;
