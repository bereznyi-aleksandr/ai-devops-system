-- Отказ вне транзакции. Курсор без WITH HOLD существует только внутри
-- транзакции: вне её PostgreSQL 16 возвращает ошибку 25P01
-- «DECLARE CURSOR can only be used in transaction blocks».
-- Так файл не даёт выполнить себя по одной команде за раз.
-- Транзакцию открывает обёртка ключом --single-transaction (раздел 25.7).
DECLARE bem_migration_guard CURSOR FOR SELECT 1;
CLOSE bem_migration_guard;

-- ---------------------------------------------------------------
-- Шаг 0. Досмотр до первого изменения.
--        PostgreSQL объединяет разрешающие политики через ИЛИ
--        (документация 16, CREATE POLICY). Поэтому одна лишняя
--        политика `USING (true)` с любым другим именем открывает
--        все строки, даже когда `tenant_isolation` правильна.
--        H1.8 проверял только политику с известным именем и такого
--        обхода не замечал (замечание C-H18-R8-02).
--        Здесь миграция останавливается ДО первого изменения:
--        чужую политику она не удаляет молча, а называет вслух.
-- ---------------------------------------------------------------
DO $$
DECLARE
    t     text;
    v_bad text;
BEGIN
    FOREACH t IN ARRAY ARRAY['work_item', 'evidence', 'subject', 'subject_author',
                             'audit_record', 'outbox', 'command_log', 'usage_record',
                             'handoff_packet', 'user_tenant_membership',
                             'audit_assignment']
    LOOP
        CONTINUE WHEN to_regclass('bem_core.' || t) IS NULL;

        SELECT string_agg(pol.policyname || ' (' || pol.cmd || ', ' ||
                          pol.permissive || ')', ', ' ORDER BY pol.policyname)
          INTO v_bad
          FROM pg_policies pol
         WHERE pol.schemaname = 'bem_core'
           AND pol.tablename  = t
           AND pol.policyname <> 'tenant_isolation';

        IF v_bad IS NOT NULL THEN
            -- ПОКРЫТИЕ: K-R8-02
            RAISE EXCEPTION
              'RLS_EXTRA_POLICY: на bem_core.% есть посторонние политики: %.'
              ' Миграция остановлена до первого изменения. Лишняя разрешающая'
              ' политика открывает все строки; удалите её под присмотром'
              ' и запустите файл заново', t, v_bad;
        END IF;
    END LOOP;
END
$$;

-- Досмотр 2. Колонки, которые этот файл считает существующими.
-- Их добавляет файл 02 (раздел 27). Если файл 01 запущен на старой
-- базе в одиночку, он обязан остановиться здесь, а не упасть на
-- середине создания функций, оставив половину работы.
DO $$
DECLARE
    r     record;
    v_bad text := '';
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('actor',          'db_role'),
            ('evidence',       'session_role'),
            ('evidence',       'identity_mode'),
            ('outbox',         'next_attempt_at'),
            ('command_log',    'fingerprint_version'),
            ('handoff_packet', 'accepted_by'),
            ('evidence',       'delegation_id'),
            ('evidence',       'identity_contract')
        ) AS t(tbl, col)
    LOOP
        CONTINUE WHEN to_regclass('bem_core.' || r.tbl) IS NULL;

        IF NOT EXISTS (SELECT 1
                         FROM pg_attribute a
                        WHERE a.attrelid = ('bem_core.' || r.tbl)::regclass
                          AND a.attname  = r.col
                          AND a.attnum   > 0
                          AND NOT a.attisdropped) THEN
            v_bad := v_bad || ' bem_core.' || r.tbl || '.' || r.col;
        END IF;
    END LOOP;

    IF v_bad <> '' THEN
        RAISE EXCEPTION
          'SCHEMA_UPGRADE_REQUIRED: в базе нет колонок:%.'
          ' Порядок один: сначала файл 02 (раздел 27), затем этот файл.'
          ' Ни одного изменения не сделано', v_bad;
    END IF;
END
$$;

-- ---------------------------------------------------------------
-- Шаг 1. Схемы. Роли уже созданы файлом 00, поэтому AUTHORIZATION
--        не падает на «роль не существует» — дефект прошлой редакции.
-- ---------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS bem_core    AUTHORIZATION bem_core_owner;
CREATE SCHEMA IF NOT EXISTS bem_engine  AUTHORIZATION bem_engine_owner;
CREATE SCHEMA IF NOT EXISTS bem_control AUTHORIZATION bem_control_owner;

-- ---------------------------------------------------------------
-- Шаг 2. Домен и перечисления
-- ---------------------------------------------------------------
SET ROLE bem_core_owner;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'actor_id' AND n.nspname = 'bem_core') THEN
        CREATE DOMAIN bem_core.actor_id AS text
          CHECK (VALUE ~ '^(claude|codex|human):[a-z0-9_.-]{1,64}$');
    -- H1.26, D1 (пробы R46, п. 16): домен есть, а его проверку сняли —
    -- повторный прогон возвращает её под прежним именем.
    ELSIF NOT EXISTS (SELECT 1 FROM pg_constraint c
                        JOIN pg_type t ON t.oid = c.contypid
                        JOIN pg_namespace n ON n.oid = t.typnamespace
                       WHERE n.nspname = 'bem_core' AND t.typname = 'actor_id'
                         AND c.conname = 'actor_id_check') THEN
        ALTER DOMAIN bem_core.actor_id ADD CONSTRAINT actor_id_check
          CHECK (VALUE ~ '^(claude|codex|human):[a-z0-9_.-]{1,64}$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'provider' AND n.nspname = 'bem_core') THEN
        CREATE TYPE bem_core.provider AS ENUM ('anthropic', 'openai', 'human');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'audit_verdict' AND n.nspname = 'bem_core') THEN
        CREATE TYPE bem_core.audit_verdict AS ENUM ('ACCEPT', 'REVISE', 'REJECT', 'BLOCKED');
    END IF;
END
$$;

-- ---------------------------------------------------------------
-- Шаг 3. Таблицы. Ссылка создаётся после своей цели.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bem_core.schema_migration (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now(),
    applied_by text NOT NULL DEFAULT current_user
);

CREATE TABLE IF NOT EXISTS bem_core.tenant (
    id         uuid PRIMARY KEY,
    name       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bem_core.actor (
    actor_id   bem_core.actor_id PRIMARY KEY,
    provider   bem_core.provider NOT NULL,
    user_id    uuid,
    is_active  boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT actor_provider_prefix CHECK (
        (provider = 'anthropic' AND actor_id LIKE 'claude:%') OR
        (provider = 'openai'    AND actor_id LIKE 'codex:%')  OR
        (provider = 'human'     AND actor_id LIKE 'human:%')),
    CONSTRAINT actor_unique_pair UNIQUE (actor_id, provider),
    -- Связь участника с ролью входа в базу. NULL означает «работает
    -- через общую runtime-роль», и такой участник не может получить
    -- полномочие: оно требует связанной личности (замечание C-H18-R8-05).
    db_role    name,
    CONSTRAINT actor_db_role_uniq UNIQUE (db_role)
);

-- Полномочия участников. Это не членство в заказчике и не роль базы:
-- это право совершать чувствительные действия — операторский разбор
-- неизвестного исхода, назначение проверяющих, заведение заказчика.
-- Полномочие с пустым tenant_id действует во всём кластере.
-- Таблица не принадлежит заказчику и защиты строк не имеет: её читает
-- только владелец управляющих функций (замечания C-H18-R8-04, C-H18-R8-05).
CREATE TABLE IF NOT EXISTS bem_core.actor_authority (
    id         uuid PRIMARY KEY,
    tenant_id  uuid REFERENCES bem_core.tenant(id),
    actor_id   bem_core.actor_id NOT NULL REFERENCES bem_core.actor(actor_id),
    authority  text NOT NULL
               CHECK (authority IN ('OPERATOR', 'AUDIT_COORDINATOR',
                                    'TENANT_PROVISIONER')),
    granted_by bem_core.actor_id NOT NULL,
    granted_at timestamptz NOT NULL DEFAULT now(),
    revoked_by bem_core.actor_id,
    revoked_at timestamptz
);

CREATE TABLE IF NOT EXISTS bem_core.user_tenant_membership (
    id         uuid PRIMARY KEY,
    user_id    uuid NOT NULL,
    tenant_id  uuid NOT NULL REFERENCES bem_core.tenant(id),
    role       text NOT NULL CHECK (role IN ('tenant_admin', 'member', 'viewer')),
    granted_by bem_core.actor_id NOT NULL,
    granted_at timestamptz NOT NULL DEFAULT now(),
    revoked_by bem_core.actor_id,
    revoked_at timestamptz
);

CREATE TABLE IF NOT EXISTS bem_core.work_item (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES bem_core.tenant(id),
    status              text NOT NULL,
    revision            integer NOT NULL DEFAULT 1,
    criticality         text NOT NULL DEFAULT 'NORMAL'
                        CHECK (criticality IN ('CRITICAL', 'NORMAL')),
    -- Связь с экземпляром процесса в движке BPMN. Раздел 8.3 объявляет
    -- эту связь источником сопоставления, поэтому она хранится в базе,
    -- а не только в памяти движка (замечание M-H17-R7-13).
    process_instance_id text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT work_item_tenant_id_uniq UNIQUE (tenant_id, id),
    -- один экземпляр процесса принадлежит ровно одной работе;
    -- NULL не участвует в уникальности, поэтому работы без движка живут как раньше
    CONSTRAINT work_item_process_instance_uniq UNIQUE (process_instance_id)
);

-- Досмотра таблиц здесь нет, и это решение, а не пропуск. Таблицы
-- создаёт только этот файл — пункт 2 раздела 27.4, — и создаёт их
-- командой CREATE TABLE IF NOT EXISTS. Требовать таблицу заранее
-- значило бы требовать её от самого себя. В черновике редакции такой
-- досмотр стоял и требовал таблицу доверенностей от файла 02; он
-- останавливал обновление любой непустой базы насмерть, потому что
-- файл 02 таблиц не создаёт, а до строки, где её создаёт этот файл,
-- дело не доходило. Досмотр 2 выше остаётся и остаётся нужным:
-- столбец существующей таблицы CREATE TABLE IF NOT EXISTS добавить
-- не может, и добавляет его именно файл 02.

-- ---------------------------------------------------------------
-- Доверенности. Кто из ролей входа вправе говорить за участника.
--
-- H1.9 считала личностью строку в настройке app.actor_id: назвал имя —
-- получил его в доказательстве. Основания за этим не стояло никакого
-- (замечание C-H19-R9-01). Здесь основание становится строкой в базе:
-- доверенность выдаёт держатель полномочия OPERATOR, она принадлежит
-- паре «роль входа — участник», её видно и её можно отозвать.
--
-- Без живой строки в этой таблице режим DELEGATED невозможен:
-- current_actor_checked отказывает, а доказательство без ссылки на
-- доверенность не проходит ограничение evidence_delegation_basis.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bem_core.actor_delegation (
    id             uuid PRIMARY KEY,
    principal_role name NOT NULL,
    actor_id       bem_core.actor_id NOT NULL
                   REFERENCES bem_core.actor (actor_id),
    granted_by     bem_core.actor_id NOT NULL
                   REFERENCES bem_core.actor (actor_id),
    reason         text NOT NULL CHECK (length(btrim(reason)) BETWEEN 3 AND 500),
    granted_at     timestamptz NOT NULL DEFAULT now(),
    revoked_at     timestamptz,
    revoked_by     bem_core.actor_id REFERENCES bem_core.actor (actor_id),
    CONSTRAINT actor_delegation_revocation_pair CHECK (
        (revoked_at IS NULL     AND revoked_by IS NULL) OR
        (revoked_at IS NOT NULL AND revoked_by IS NOT NULL))
);

-- Одна живая доверенность на пару. Отозванных может быть сколько угодно:
-- они остаются как история, потому что доказательства на них ссылаются.
CREATE UNIQUE INDEX IF NOT EXISTS actor_delegation_live_uniq
    ON bem_core.actor_delegation (principal_role, actor_id)
 WHERE revoked_at IS NULL;

-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bem_core.evidence (
    id         uuid PRIMARY KEY,
    tenant_id  uuid NOT NULL REFERENCES bem_core.tenant(id),
    kind       text NOT NULL,
    actor_id   bem_core.actor_id NOT NULL,
    payload    jsonb NOT NULL,
    prev_hash  text,
    hash       text,
    -- Кто физически писал строку и как установлена личность.
    -- H1.8 верил строке `app.actor_id` и давал ядру прямой INSERT,
    -- поэтому доказательство можно было подписать чужим именем
    -- (замечание C-H18-R8-05). Значения проставляет триггер, а не
    -- вызывающий: подменить их из запроса нельзя.
    session_role  name NOT NULL DEFAULT session_user,
    identity_mode text NOT NULL DEFAULT 'DELEGATED'
                  CHECK (identity_mode IN ('BOUND', 'DELEGATED')),
    -- Основание доверенности. Для BOUND его нет и быть не должно:
    -- участник вошёл сам. Для DELEGATED это ссылка на выданную
    -- доверенность — ту самую строку, которую можно предъявить и
    -- отозвать (замечание C-H19-R9-01).
    delegation_id uuid,
    -- Номер договора личности. 1 — строки, написанные до H1.10, когда
    -- основания не требовалось. 2 — строки нового договора. Отдельный
    -- номер нужен потому, что обновлять старые строки нечем: основания
    -- у них не было, и выдумать его задним числом нельзя.
    identity_contract smallint NOT NULL DEFAULT 2
                      CONSTRAINT evidence_identity_contract_check
                      CHECK (identity_contract IN (1, 2)),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT evidence_tenant_id_uniq UNIQUE (tenant_id, id),
    CONSTRAINT evidence_actor_fk FOREIGN KEY (actor_id)
        REFERENCES bem_core.actor (actor_id),
    -- Имя задано вручную, а не оставлено на усмотрение сервера:
    -- на обновлённой базе это же ограничение добавляет шаг 4 ниже,
    -- и обе установки обязаны получить его под одним именем.
    CONSTRAINT evidence_delegation_fk FOREIGN KEY (delegation_id)
        REFERENCES bem_core.actor_delegation (id),
    CONSTRAINT evidence_delegation_basis CHECK (
        identity_contract = 1
        OR (identity_mode = 'BOUND'     AND delegation_id IS NULL)
        OR (identity_mode = 'DELEGATED' AND delegation_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS bem_core.subject (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES bem_core.tenant(id),
    work_item_id        uuid NOT NULL,
    head_sha            text NOT NULL,
    criticality         text NOT NULL CHECK (criticality IN ('CRITICAL', 'NORMAL')),
    scope               text NOT NULL DEFAULT 'WORKING'
                        CHECK (scope IN ('WORKING', 'BEM954_PROTOCOL')),
    published_at        timestamptz,
    released_at         timestamptz,
    released_by         bem_core.actor_id,
    disagreement_at     timestamptz,
    disagreement_reason text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT subject_tenant_id_uniq UNIQUE (tenant_id, id),
    CONSTRAINT subject_work_item_fk
        FOREIGN KEY (tenant_id, work_item_id)
        REFERENCES bem_core.work_item (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS bem_core.subject_author (
    subject_id uuid NOT NULL,
    actor_id   bem_core.actor_id NOT NULL,
    provider   bem_core.provider NOT NULL,
    tenant_id  uuid NOT NULL,
    added_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_id, actor_id),
    CONSTRAINT subject_author_actor_fk
        FOREIGN KEY (actor_id, provider) REFERENCES bem_core.actor (actor_id, provider),
    CONSTRAINT subject_author_subject_fk
        FOREIGN KEY (tenant_id, subject_id) REFERENCES bem_core.subject (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS bem_core.audit_record (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL,
    subject_id       uuid NOT NULL,
    head_sha         text NOT NULL,
    auditor_actor    bem_core.actor_id NOT NULL,
    auditor_provider bem_core.provider NOT NULL,
    verdict          bem_core.audit_verdict NOT NULL,
    evidence_id      uuid NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT audit_one_per_head_auditor UNIQUE (subject_id, head_sha, auditor_actor),
    CONSTRAINT audit_actor_fk
        FOREIGN KEY (auditor_actor, auditor_provider)
        REFERENCES bem_core.actor (actor_id, provider),
    CONSTRAINT audit_subject_fk
        FOREIGN KEY (tenant_id, subject_id) REFERENCES bem_core.subject (tenant_id, id),
    CONSTRAINT audit_evidence_fk
        FOREIGN KEY (tenant_id, evidence_id) REFERENCES bem_core.evidence (tenant_id, id)
);

-- Назначение проверяющего. H1.7 принимал вердикт любого активного
-- не-автора; теперь вердикт считается только у назначенного
-- проверяющего с действующим назначением (замечание C-H17-R7-05).
CREATE TABLE IF NOT EXISTS bem_core.audit_assignment (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL,
    subject_id       uuid NOT NULL,
    auditor_actor    bem_core.actor_id NOT NULL,
    auditor_provider bem_core.provider NOT NULL,
    assigned_by      bem_core.actor_id NOT NULL,
    assigned_at      timestamptz NOT NULL DEFAULT now(),
    revoked_at       timestamptz,
    CONSTRAINT audit_assignment_uniq UNIQUE (subject_id, auditor_actor),
    CONSTRAINT audit_assignment_actor_fk
        FOREIGN KEY (auditor_actor, auditor_provider)
        REFERENCES bem_core.actor (actor_id, provider),
    CONSTRAINT audit_assignment_subject_fk
        FOREIGN KEY (tenant_id, subject_id) REFERENCES bem_core.subject (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS bem_core.outbox (
    id              uuid PRIMARY KEY,
    tenant_id       uuid NOT NULL,
    work_item_id    uuid NOT NULL,
    command_id      uuid NOT NULL,
    kind            text NOT NULL,
    payload         jsonb NOT NULL,
    -- Ключ повтора для внешней стороны. H1.7 вставлял эту колонку,
    -- но не объявлял её — первый же переход падал с ошибкой
    -- «column does not exist» (замечание C-H17-R7-02).
    -- Формат закреплён: 64 знака шестнадцатеричной суммы SHA-256
    -- от текста command_id. Значение выводится из команды, поэтому
    -- повтор той же команды даёт тот же ключ.
    idempotency_key text NOT NULL
                    CHECK (idempotency_key ~ '^[0-9a-f]{64}$'),
    status          text NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING', 'LEASED', 'SENT', 'FAILED',
                                      'UNKNOWN_OUTCOME', 'DEAD_LETTER')),
    leased_by       text,
    leased_until    timestamptz,
    lease_epoch     bigint NOT NULL DEFAULT 0,
    attempt_count   integer NOT NULL DEFAULT 0,
    -- Время, раньше которого строку не берут в работу. H1.8 переводил
    -- неудачу в `FAILED` и больше её не захватывал: порог пяти попыток
    -- был недостижим по штатному пути (замечание C-H18-R8-03).
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    result          jsonb,
    finished_at     timestamptz,
    -- разбор исхода: перевод в тупик и закрытие неизвестного исхода
    -- (замечание M-H17-R7-14). NULL означает «разбора не было».
    dead_lettered_at   timestamptz,
    dead_letter_reason text,
    reconciled_at      timestamptz,
    reconciled_outcome text
                       CHECK (reconciled_outcome IN ('CONFIRMED_SENT',
                                                     'CONFIRMED_NOT_SENT',
                                                     'UNRESOLVED')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT outbox_command_uniq UNIQUE (command_id),
    -- Связь ключа с командой: один ключ на пару «заказчик + вид действия».
    -- Две разные команды одного вида у одного заказчика не могут
    -- предъявить внешней стороне один и тот же ключ.
    CONSTRAINT outbox_idem_uniq UNIQUE (tenant_id, kind, idempotency_key),
    CONSTRAINT outbox_work_item_fk
        FOREIGN KEY (tenant_id, work_item_id)
        REFERENCES bem_core.work_item (tenant_id, id)
);

-- Новая таблица этой редакции: резерв команды ДО изменения состояния
-- (раздел 8.5, замечание M-H16-R6-11)
CREATE TABLE IF NOT EXISTS bem_core.command_log (
    command_id      uuid PRIMARY KEY,
    tenant_id       uuid NOT NULL,
    work_item_id    uuid NOT NULL,
    -- Вид внешнего действия. NULL означает «переход без внешнего действия».
    -- В H1.7 колонка была NOT NULL, поэтому такой переход падал ещё до
    -- изменения состояния (замечание M-H17-R7-09).
    kind            text,
    has_outbox      boolean NOT NULL,
    payload_sha256  text NOT NULL,
    -- Версия кодировки отпечатка. Строковая склейка через `|` версии v1
    -- давала коллизии (замечание M-H18-R8-01). Строки версии 1 остаются
    -- в базе как есть, но повтор по ним отклоняется: доказать, что это
    -- та же команда, старая кодировка не позволяет.
    fingerprint_version smallint NOT NULL DEFAULT 2
                        CHECK (fingerprint_version IN (1, 2)),
    actor_id        bem_core.actor_id NOT NULL,
    result_revision integer,
    outbox_id       uuid,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT command_log_kind_agrees
        CHECK ((has_outbox AND kind IS NOT NULL) OR
               (NOT has_outbox AND kind IS NULL AND outbox_id IS NULL)),
    CONSTRAINT command_log_work_item_fk
        FOREIGN KEY (tenant_id, work_item_id)
        REFERENCES bem_core.work_item (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS bem_core.usage_record (
    id                   uuid PRIMARY KEY,
    tenant_id            uuid NOT NULL,
    work_item_id         uuid NOT NULL,
    attempt_no           integer NOT NULL,
    provider             text NOT NULL,
    model                text NOT NULL,
    input_tokens         integer,
    output_tokens        integer,
    cached_tokens        integer,
    tool_overhead_tokens integer,
    context_estimate     integer NOT NULL,
    context_limit        integer NOT NULL,
    measured_by          text NOT NULL
                         CHECK (measured_by IN ('PROVIDER_REPORTED', 'LOCAL_ESTIMATE')),
    outcome              text NOT NULL
                         CHECK (outcome IN ('OK', 'PROVIDER_ERROR', 'SOFT_LIMIT', 'HANDOFF')),
    created_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT usage_record_work_item_fk
        FOREIGN KEY (tenant_id, work_item_id)
        REFERENCES bem_core.work_item (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS bem_core.handoff_packet (
    id            uuid PRIMARY KEY,
    tenant_id     uuid NOT NULL,
    work_item_id  uuid NOT NULL,
    handoff_no    integer NOT NULL,
    payload       jsonb NOT NULL,
    packet_sha256 text NOT NULL,
    accepted_at   timestamptz,
    -- Кто принял пакет. Без этой колонки повторный приём нельзя
    -- отличить от приёма чужой сессией, а договор требует разного
    -- поведения в этих двух случаях (замечание M-H18-R8-05).
    accepted_by   bem_core.actor_id REFERENCES bem_core.actor(actor_id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT handoff_packet_accepted_pair CHECK (
        (accepted_at IS NULL     AND accepted_by IS NULL) OR
        (accepted_at IS NOT NULL AND accepted_by IS NOT NULL)),
    CONSTRAINT handoff_packet_work_item_fk
        FOREIGN KEY (tenant_id, work_item_id)
        REFERENCES bem_core.work_item (tenant_id, id),
    CONSTRAINT handoff_packet_no_uniq UNIQUE (work_item_id, handoff_no)
);

-- ---------------------------------------------------------------
-- Шаг 4. Полный список ограничений таблиц bem_core
-- ---------------------------------------------------------------
-- H1.26, D1 (пробы R46, п. 16): прежний шаг знал шесть ограничений
-- из семидесяти. Снятые вручную outbox_idem_uniq и составной FK
-- subject_author_subject_fk повторный прогон не вернул, а файл 05 этого
-- не заметил. Теперь здесь все ограничения таблиц bem_core в печатной
-- форме pg_get_constraintdef: первичные ключи, затем UNIQUE, затем FK,
-- затем CHECK, чтобы ссылка появлялась после своей цели.
-- Ограничения нет — оно добавляется. Есть, но с другой формой — отказ:
-- молча заменить чужую форму значит скрыть причину расхождения.
-- Форма сверяется при пути поиска pg_catalog: иначе имя таблицы в
-- REFERENCES печатается то со схемой, то без. Ограничения схемы
-- bem_control добавляет такой же блок после создания её таблиц, а
-- проверку домена — шаг 2. Точное множество сверяет файл 05.
DO $$
DECLARE
    r      record;
    v_def  text;
    v_path text;
BEGIN
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog', true);
    FOR r IN
        SELECT * FROM (VALUES
            -- Столбец delegation_id добавляет файл 02, но связать его
            -- с таблицей доверенностей он не может: таблицы тогда ещё
            -- нет. Связь evidence_delegation_fk ставится здесь
            -- (замечание C-H19-R9-01).
            ('bem_core.actor', 'actor_pkey', 'PRIMARY KEY (actor_id)'),
            ('bem_core.actor_authority', 'actor_authority_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.actor_delegation', 'actor_delegation_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.audit_assignment', 'audit_assignment_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.audit_record', 'audit_record_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.command_log', 'command_log_pkey', 'PRIMARY KEY (command_id)'),
            ('bem_core.evidence', 'evidence_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.handoff_packet', 'handoff_packet_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.outbox', 'outbox_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.schema_migration', 'schema_migration_pkey', 'PRIMARY KEY (version)'),
            ('bem_core.subject', 'subject_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.subject_author', 'subject_author_pkey', 'PRIMARY KEY (subject_id, actor_id)'),
            ('bem_core.tenant', 'tenant_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.usage_record', 'usage_record_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.user_tenant_membership', 'user_tenant_membership_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.work_item', 'work_item_pkey', 'PRIMARY KEY (id)'),
            ('bem_core.actor', 'actor_db_role_uniq', 'UNIQUE (db_role)'),
            ('bem_core.actor', 'actor_unique_pair', 'UNIQUE (actor_id, provider)'),
            ('bem_core.audit_assignment', 'audit_assignment_uniq', 'UNIQUE (subject_id, auditor_actor)'),
            ('bem_core.audit_record', 'audit_one_per_head_auditor', 'UNIQUE (subject_id, head_sha, auditor_actor)'),
            ('bem_core.evidence', 'evidence_tenant_id_uniq', 'UNIQUE (tenant_id, id)'),
            ('bem_core.handoff_packet', 'handoff_packet_no_uniq', 'UNIQUE (work_item_id, handoff_no)'),
            ('bem_core.outbox', 'outbox_command_uniq', 'UNIQUE (command_id)'),
            ('bem_core.outbox', 'outbox_idem_uniq', 'UNIQUE (tenant_id, kind, idempotency_key)'),
            ('bem_core.subject', 'subject_tenant_id_uniq', 'UNIQUE (tenant_id, id)'),
            ('bem_core.work_item', 'work_item_process_instance_uniq', 'UNIQUE (process_instance_id)'),
            ('bem_core.work_item', 'work_item_tenant_id_uniq', 'UNIQUE (tenant_id, id)'),
            ('bem_core.actor_authority', 'actor_authority_actor_id_fkey', 'FOREIGN KEY (actor_id) REFERENCES bem_core.actor(actor_id)'),
            ('bem_core.actor_authority', 'actor_authority_tenant_id_fkey', 'FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)'),
            ('bem_core.actor_delegation', 'actor_delegation_actor_id_fkey', 'FOREIGN KEY (actor_id) REFERENCES bem_core.actor(actor_id)'),
            ('bem_core.actor_delegation', 'actor_delegation_granted_by_fkey', 'FOREIGN KEY (granted_by) REFERENCES bem_core.actor(actor_id)'),
            ('bem_core.actor_delegation', 'actor_delegation_revoked_by_fkey', 'FOREIGN KEY (revoked_by) REFERENCES bem_core.actor(actor_id)'),
            ('bem_core.audit_assignment', 'audit_assignment_actor_fk', 'FOREIGN KEY (auditor_actor, auditor_provider) REFERENCES bem_core.actor(actor_id, provider)'),
            ('bem_core.audit_assignment', 'audit_assignment_subject_fk', 'FOREIGN KEY (tenant_id, subject_id) REFERENCES bem_core.subject(tenant_id, id)'),
            ('bem_core.audit_record', 'audit_actor_fk', 'FOREIGN KEY (auditor_actor, auditor_provider) REFERENCES bem_core.actor(actor_id, provider)'),
            ('bem_core.audit_record', 'audit_evidence_fk', 'FOREIGN KEY (tenant_id, evidence_id) REFERENCES bem_core.evidence(tenant_id, id)'),
            ('bem_core.audit_record', 'audit_subject_fk', 'FOREIGN KEY (tenant_id, subject_id) REFERENCES bem_core.subject(tenant_id, id)'),
            ('bem_core.command_log', 'command_log_work_item_fk', 'FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)'),
            ('bem_core.evidence', 'evidence_actor_fk', 'FOREIGN KEY (actor_id) REFERENCES bem_core.actor(actor_id)'),
            ('bem_core.evidence', 'evidence_delegation_fk', 'FOREIGN KEY (delegation_id) REFERENCES bem_core.actor_delegation(id)'),
            ('bem_core.evidence', 'evidence_tenant_id_fkey', 'FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)'),
            ('bem_core.handoff_packet', 'handoff_packet_accepted_by_fkey', 'FOREIGN KEY (accepted_by) REFERENCES bem_core.actor(actor_id)'),
            ('bem_core.handoff_packet', 'handoff_packet_work_item_fk', 'FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)'),
            ('bem_core.outbox', 'outbox_work_item_fk', 'FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)'),
            ('bem_core.subject', 'subject_tenant_id_fkey', 'FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)'),
            ('bem_core.subject', 'subject_work_item_fk', 'FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)'),
            ('bem_core.subject_author', 'subject_author_actor_fk', 'FOREIGN KEY (actor_id, provider) REFERENCES bem_core.actor(actor_id, provider)'),
            ('bem_core.subject_author', 'subject_author_subject_fk', 'FOREIGN KEY (tenant_id, subject_id) REFERENCES bem_core.subject(tenant_id, id)'),
            ('bem_core.usage_record', 'usage_record_work_item_fk', 'FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)'),
            ('bem_core.user_tenant_membership', 'user_tenant_membership_tenant_id_fkey', 'FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)'),
            ('bem_core.work_item', 'work_item_tenant_id_fkey', 'FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)'),
            ('bem_core.actor', 'actor_provider_prefix', 'CHECK ((((provider = ''anthropic''::bem_core.provider) AND ((actor_id)::text ~~ ''claude:%''::text)) OR ((provider = ''openai''::bem_core.provider) AND ((actor_id)::text ~~ ''codex:%''::text)) OR ((provider = ''human''::bem_core.provider) AND ((actor_id)::text ~~ ''human:%''::text))))'),
            ('bem_core.actor_authority', 'actor_authority_authority_check', 'CHECK ((authority = ANY (ARRAY[''OPERATOR''::text, ''AUDIT_COORDINATOR''::text, ''TENANT_PROVISIONER''::text])))'),
            ('bem_core.actor_delegation', 'actor_delegation_reason_check', 'CHECK (((length(btrim(reason)) >= 3) AND (length(btrim(reason)) <= 500)))'),
            ('bem_core.actor_delegation', 'actor_delegation_revocation_pair', 'CHECK ((((revoked_at IS NULL) AND (revoked_by IS NULL)) OR ((revoked_at IS NOT NULL) AND (revoked_by IS NOT NULL))))'),
            ('bem_core.command_log', 'command_log_fingerprint_version_check', 'CHECK ((fingerprint_version = ANY (ARRAY[1, 2])))'),
            ('bem_core.command_log', 'command_log_kind_agrees', 'CHECK (((has_outbox AND (kind IS NOT NULL)) OR ((NOT has_outbox) AND (kind IS NULL) AND (outbox_id IS NULL))))'),
            ('bem_core.evidence', 'evidence_delegation_basis', 'CHECK (((identity_contract = 1) OR ((identity_mode = ''BOUND''::text) AND (delegation_id IS NULL)) OR ((identity_mode = ''DELEGATED''::text) AND (delegation_id IS NOT NULL))))'),
            ('bem_core.evidence', 'evidence_identity_contract_check', 'CHECK ((identity_contract = ANY (ARRAY[1, 2])))'),
            ('bem_core.evidence', 'evidence_identity_mode_check', 'CHECK ((identity_mode = ANY (ARRAY[''BOUND''::text, ''DELEGATED''::text])))'),
            ('bem_core.handoff_packet', 'handoff_packet_accepted_pair', 'CHECK ((((accepted_at IS NULL) AND (accepted_by IS NULL)) OR ((accepted_at IS NOT NULL) AND (accepted_by IS NOT NULL))))'),
            ('bem_core.outbox', 'outbox_idempotency_key_check', 'CHECK ((idempotency_key ~ ''^[0-9a-f]{64}$''::text))'),
            ('bem_core.outbox', 'outbox_reconciled_outcome_check', 'CHECK ((reconciled_outcome = ANY (ARRAY[''CONFIRMED_SENT''::text, ''CONFIRMED_NOT_SENT''::text, ''UNRESOLVED''::text])))'),
            ('bem_core.outbox', 'outbox_status_check', 'CHECK ((status = ANY (ARRAY[''PENDING''::text, ''LEASED''::text, ''SENT''::text, ''FAILED''::text, ''UNKNOWN_OUTCOME''::text, ''DEAD_LETTER''::text])))'),
            ('bem_core.subject', 'subject_criticality_check', 'CHECK ((criticality = ANY (ARRAY[''CRITICAL''::text, ''NORMAL''::text])))'),
            ('bem_core.subject', 'subject_scope_check', 'CHECK ((scope = ANY (ARRAY[''WORKING''::text, ''BEM954_PROTOCOL''::text])))'),
            ('bem_core.usage_record', 'usage_record_measured_by_check', 'CHECK ((measured_by = ANY (ARRAY[''PROVIDER_REPORTED''::text, ''LOCAL_ESTIMATE''::text])))'),
            ('bem_core.usage_record', 'usage_record_outcome_check', 'CHECK ((outcome = ANY (ARRAY[''OK''::text, ''PROVIDER_ERROR''::text, ''SOFT_LIMIT''::text, ''HANDOFF''::text])))'),
            ('bem_core.user_tenant_membership', 'user_tenant_membership_role_check', 'CHECK ((role = ANY (ARRAY[''tenant_admin''::text, ''member''::text, ''viewer''::text])))'),
            ('bem_core.work_item', 'work_item_criticality_check', 'CHECK ((criticality = ANY (ARRAY[''CRITICAL''::text, ''NORMAL''::text])))')
        ) AS t(tbl, con, def)
    LOOP
        SELECT pg_get_constraintdef(c.oid) INTO v_def
          FROM pg_constraint c
         WHERE c.conname = r.con AND c.conrelid = r.tbl::regclass;
        IF NOT FOUND THEN
            EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', r.tbl, r.con, r.def);
        ELSIF v_def IS DISTINCT FROM r.def THEN
            RAISE EXCEPTION
              'MIGRATION_FAILED: CONSTRAINT_DEFINITION_MISMATCH: % %: ожидалось %, найдено %',
              r.tbl, r.con, r.def, v_def;
        END IF;
    END LOOP;
    PERFORM set_config('search_path', v_path, true);
END
$$;

-- ---------------------------------------------------------------
-- Шаг 5. Индексы
-- ---------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS user_tenant_membership_active_uniq
    ON bem_core.user_tenant_membership (user_id, tenant_id)
 WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS outbox_ready_idx
    ON bem_core.outbox (created_at)
 WHERE status IN ('PENDING', 'LEASED');

CREATE INDEX IF NOT EXISTS audit_record_subject_idx
    ON bem_core.audit_record (subject_id, head_sha);

CREATE INDEX IF NOT EXISTS evidence_tenant_created_idx
    ON bem_core.evidence (tenant_id, created_at);

CREATE INDEX IF NOT EXISTS command_log_work_item_idx
    ON bem_core.command_log (tenant_id, work_item_id);

-- Одно действующее полномочие на пару «участник — право». Отозванные
-- строки остаются историей и в уникальность не входят. Пустой tenant_id
-- (полномочие на весь кластер) заменяется нулевым: в уникальном индексе
-- два NULL считаются разными, и без замены одно и то же право можно
-- было бы выдать на кластер дважды.
CREATE UNIQUE INDEX IF NOT EXISTS actor_authority_active_uniq
    ON bem_core.actor_authority (
           actor_id, authority,
           coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid))
 WHERE revoked_at IS NULL;

-- ---------------------------------------------------------------
-- Шаг 6. Функция заказчика и триггерные функции — полные тела
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION bem_core.current_tenant()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = pg_catalog, pg_temp
AS $$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION bem_core.forbid_update_delete()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = bem_core, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION 'APPEND_ONLY_TABLE: % запрещает % ', TG_TABLE_NAME, TG_OP;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION bem_core.forbid_self_audit()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = bem_core, pg_temp
AS $$
BEGIN
    IF EXISTS (SELECT 1
                 FROM bem_core.subject_author sa
                WHERE sa.subject_id = NEW.subject_id
                  AND sa.tenant_id  = NEW.tenant_id
                  AND sa.actor_id   = NEW.auditor_actor) THEN
        RAISE EXCEPTION 'AUTHOR_CANNOT_AUDIT: % является автором предмета %',
                        NEW.auditor_actor, NEW.subject_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION bem_core.audit_head_matches_subject()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = bem_core, pg_temp
AS $$
DECLARE
    v_head text;
BEGIN
    SELECT s.head_sha INTO v_head
      FROM bem_core.subject s
     WHERE s.id = NEW.subject_id
       AND s.tenant_id = NEW.tenant_id;

    IF v_head IS NULL THEN
        RAISE EXCEPTION 'SUBJECT_NOT_FOUND: %', NEW.subject_id;
    END IF;
    IF v_head IS DISTINCT FROM NEW.head_sha THEN
        RAISE EXCEPTION 'AUDIT_HEAD_MISMATCH: вердикт по %, а у предмета %',
                        NEW.head_sha, v_head;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION bem_core.require_at_least_one_author()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = bem_core, pg_temp
AS $$
BEGIN
    IF NOT EXISTS (SELECT 1
                     FROM bem_core.subject_author sa
                    WHERE sa.subject_id = NEW.id
                      AND sa.tenant_id  = NEW.tenant_id) THEN
        RAISE EXCEPTION 'SUBJECT_WITHOUT_AUTHOR: предмет % опубликован без автора', NEW.id;
    END IF;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION bem_core.forbid_author_change_after_publish()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = bem_core, pg_temp
AS $$
DECLARE
    v_published timestamptz;
    v_subject   uuid := COALESCE(NEW.subject_id, OLD.subject_id);
    v_tenant    uuid := COALESCE(NEW.tenant_id,  OLD.tenant_id);
BEGIN
    SELECT s.published_at INTO v_published
      FROM bem_core.subject s
     WHERE s.id = v_subject
       AND s.tenant_id = v_tenant;

    IF v_published IS NOT NULL THEN
        RAISE EXCEPTION 'AUTHORS_FROZEN_AFTER_PUBLISH: предмет % опубликован %',
                        v_subject, v_published;
    END IF;
    RETURN NEW;
END;
$$;

-- Личность в доказательстве. Всё, что можно подделать из запроса,
-- перезаписывает сам сервер, поэтому обойти проверку нельзя ни одним
-- путём вставки (замечание C-H18-R8-05).
CREATE OR REPLACE FUNCTION bem_core.evidence_identity()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_active boolean;
    v_user   uuid;
BEGIN
    -- 1. Роль входа пишет сервер. SECURITY DEFINER её не меняет:
    --    session_user остаётся настоящей ролью, под которой вошли.
    NEW.session_role := session_user;

    -- 2. Участник обязан существовать и быть действующим.
    SELECT a.is_active, a.user_id
      INTO v_active, v_user
      FROM bem_core.actor a
     WHERE a.actor_id = NEW.actor_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'EVIDENCE_UNKNOWN_ACTOR: %', NEW.actor_id;
    END IF;
    IF NOT v_active THEN
        RAISE EXCEPTION 'EVIDENCE_INACTIVE_ACTOR: %', NEW.actor_id;
    END IF;

    -- 3. Участник с учётной записью обязан состоять в этом заказчике.
    --    Машинный участник без учётной записи работает во всех
    --    заказчиках, и такой проверки у него нет.
    IF v_user IS NOT NULL
       AND NOT EXISTS (
        SELECT 1
          FROM bem_core.user_tenant_membership m
         WHERE m.user_id   = v_user
           AND m.tenant_id = NEW.tenant_id
           AND m.revoked_at IS NULL)
       -- Держатель полномочия на весь кластер (оператор, координатор
       -- проверок, заводящий заказчиков) работает во всех заказчиках
       -- по должности. Кто именно писал, видно из session_role.
       AND NOT EXISTS (
        SELECT 1
          FROM bem_core.actor_authority aa
         WHERE aa.actor_id   = NEW.actor_id
           AND aa.tenant_id  IS NULL
           AND aa.revoked_at IS NULL)
    THEN
        RAISE EXCEPTION 'EVIDENCE_ACTOR_NOT_IN_TENANT: участник % не состоит в заказчике %',
                        NEW.actor_id, NEW.tenant_id;
    END IF;

    -- 4. Как установлена личность. BOUND — участник связан именно с
    --    этой ролью входа. DELEGATED — за него говорит общая роль.
    IF EXISTS (SELECT 1
                 FROM bem_core.actor a
                WHERE a.db_role  = session_user
                  AND a.actor_id = NEW.actor_id)
    THEN
        NEW.identity_mode := 'BOUND';
        IF NEW.delegation_id IS NOT NULL THEN
            RAISE EXCEPTION
              'EVIDENCE_BOUND_WITH_DELEGATION: участник % вошёл сам,'
              ' доверенность здесь лишняя', NEW.actor_id;
        END IF;
    ELSE
        NEW.identity_mode := 'DELEGATED';

        -- 5. Основание доверенности. Триггер не верит тому, что записал
        --    вызывающий: он сам сверяет ссылку с живой строкой
        --    доверенности для этой роли входа и этого участника.
        --    Проверка стоит здесь, а не только в writer, потому что
        --    прямой INSERT обязан упереться в то же самое.
        IF NEW.delegation_id IS NULL THEN
            RAISE EXCEPTION
              'EVIDENCE_DELEGATION_REQUIRED: роль % пишет за участника %'
              ' без ссылки на доверенность', session_user, NEW.actor_id;
        END IF;

        IF NOT EXISTS (
            SELECT 1
              FROM bem_core.actor_delegation d
             WHERE d.id             = NEW.delegation_id
               AND d.principal_role = session_user
               AND d.actor_id       = NEW.actor_id
               AND d.revoked_at     IS NULL)
        THEN
            RAISE EXCEPTION
              'EVIDENCE_DELEGATION_INVALID: доверенность % не выдана роли %'
              ' на участника % или отозвана',
              NEW.delegation_id, session_user, NEW.actor_id;
        END IF;
    END IF;

    -- 6. Новые строки пишутся только по договору 2. Единицу ставят
    --    старые строки, перенесённые файлом 02, и менять её нельзя.
    NEW.identity_contract := 2;

    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------
-- Шаг 7. Триггеры. Не «есть триггер с таким именем», а «есть триггер
--        с таким определением». Прежний шаг проверял только пару
--        «имя + таблица» и существующий триггер не трогал. Поэтому
--        триггер с правильным именем и неправильным поведением
--        переживал повторную миграцию и проходил итоговую проверку
--        (замечание C-H114-R14-01, подделка I-H114-01: BEFORE UPDATE
--        OR DELETE заменено на BEFORE UPDATE OF head_sha — защита
--        удаления и остальных столбцов исчезает, имя остаётся).
--
--        Теперь каждый управляемый триггер пересоздаётся из канона
--        безусловно и сразу сверяется по полям каталога. DROP + CREATE
--        внутри одной транзакции выбран вместо CREATE OR REPLACE
--        TRIGGER намеренно: замена не умеет превратить обычный триггер
--        в constraint-триггер и обратно, а подменить могли и так.
--        Пока транзакция не зафиксирована, другие сеансы таблицу
--        изменённой не видят: DROP берёт ACCESS EXCLUSIVE.
--
--        Ожидаемый tgtype — разрядная маска каталога, а не проза:
--        1 строка, 2 BEFORE, 4 INSERT, 8 DELETE, 16 UPDATE, 32
--        TRUNCATE, 64 INSTEAD. BEFORE UPDATE OR DELETE построчно даёт
--        1+2+8+16 = 27; BEFORE INSERT — 1+2+4 = 7; BEFORE DELETE —
--        1+2+8 = 11; AFTER INSERT OR UPDATE — 1+4+16 = 21. Подделка
--        I-H114-01 даёт 19 и непустой список столбцов, то есть
--        расходится сразу по двум полям.
--
--        R31 (замечание C-H115-R15-01). Отпечаток знал об условии
--        WHEN только «есть или нет». Подделка I-H115-01 меняла условие
--        constraint-триггера на WHEN (true), и эта сверка её
--        пропускала. Теперь у каждого триггера сверяются ещё текст
--        условия, байты аргументов и определение целиком — строка
--        pg_get_triggerdef(oid, true) с пробелами, сжатыми до одного.
--        Путь поиска на время блока закреплён: от него зависят имена
--        схем в этой строке и в приведении к regprocedure.
--
--        Условие берётся из строки определения, а не через
--        pg_get_expr(tgqual, tgrelid). В условии триггера NEW и OLD —
--        два разных отношения, а pg_get_expr строит контекст из
--        одного, и по разбору исходного текста PostgreSQL 16 на NEW
--        он отказывает («bogus varno»). Вживую (R43) проверено
--        сравнение tgqual::text ниже.
-- ---------------------------------------------------------------
DO $$
DECLARE
    r         record;
    v_problem text;
    v_attr    text;
    v_def     text;
    v_when    text;
    v_args    text;
    v_path    text;
    v_want_when text;
    v_want_def  text;
    v_tgqual_real text;
    v_tgqual_ref  text;
BEGIN
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog, pg_temp', true);

    FOR r IN
        SELECT * FROM (VALUES
            -- имя, таблица, тело CREATE TRIGGER, ожидаемый tgtype,
            -- ожидаемый список столбцов (имена через запятую; пусто —
            -- список не задан), ожидаемая функция с полной подписью,
            -- ожидаемое условие WHEN (пусто — условия нет) и ожидаемое
            -- определение — строка pg_get_triggerdef(oid, true) при
            -- пути поиска pg_catalog, с пробелами, сжатыми до одного
            ('audit_record_append_only', 'bem_core.audit_record',
             'BEFORE UPDATE OR DELETE ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',
             27::smallint, ''::text, 'bem_core.forbid_update_delete()'::text,
             ''::text,
             'CREATE TRIGGER audit_record_append_only BEFORE DELETE OR UPDATE ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()'::text),
            ('subject_author_append_only', 'bem_core.subject_author',
             'BEFORE UPDATE OR DELETE ON bem_core.subject_author FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',
             27::smallint, ''::text, 'bem_core.forbid_update_delete()'::text,
             ''::text,
             'CREATE TRIGGER subject_author_append_only BEFORE DELETE OR UPDATE ON bem_core.subject_author FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()'::text),
            ('evidence_append_only', 'bem_core.evidence',
             'BEFORE UPDATE OR DELETE ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',
             27::smallint, ''::text, 'bem_core.forbid_update_delete()'::text,
             ''::text,
             'CREATE TRIGGER evidence_append_only BEFORE DELETE OR UPDATE ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()'::text),
            ('evidence_identity', 'bem_core.evidence',
             'BEFORE INSERT ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.evidence_identity()',
             7::smallint, ''::text, 'bem_core.evidence_identity()'::text,
             ''::text,
             'CREATE TRIGGER evidence_identity BEFORE INSERT ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.evidence_identity()'::text),
            ('command_log_append_only', 'bem_core.command_log',
             'BEFORE DELETE ON bem_core.command_log FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',
             11::smallint, ''::text, 'bem_core.forbid_update_delete()'::text,
             ''::text,
             'CREATE TRIGGER command_log_append_only BEFORE DELETE ON bem_core.command_log FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()'::text),
            ('audit_record_no_self_audit', 'bem_core.audit_record',
             'BEFORE INSERT ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_self_audit()',
             7::smallint, ''::text, 'bem_core.forbid_self_audit()'::text,
             ''::text,
             'CREATE TRIGGER audit_record_no_self_audit BEFORE INSERT ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_self_audit()'::text),
            ('audit_record_head_match', 'bem_core.audit_record',
             'BEFORE INSERT ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.audit_head_matches_subject()',
             7::smallint, ''::text, 'bem_core.audit_head_matches_subject()'::text,
             ''::text,
             'CREATE TRIGGER audit_record_head_match BEFORE INSERT ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.audit_head_matches_subject()'::text),
            ('subject_author_frozen', 'bem_core.subject_author',
             'BEFORE INSERT ON bem_core.subject_author FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_author_change_after_publish()',
             7::smallint, ''::text, 'bem_core.forbid_author_change_after_publish()'::text,
             ''::text,
             'CREATE TRIGGER subject_author_frozen BEFORE INSERT ON bem_core.subject_author FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_author_change_after_publish()'::text)
        ) AS t(trg, tbl, body, want_type, want_attr, want_fn, want_when, want_def)
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %s', r.trg, r.tbl);
        EXECUTE format('CREATE TRIGGER %I %s', r.trg, r.body);

        -- Сверка сразу после создания. Она ловит расхождение между
        -- телом команды и объявленной маской: тот, кто поправил только
        -- тело, здесь и останавливается.
        SELECT string_agg(a.attname::text, ',' ORDER BY u.ord) INTO v_attr
          FROM pg_trigger tg
          CROSS JOIN LATERAL unnest(tg.tgattr::smallint[]) WITH ORDINALITY AS u(attnum, ord)
          JOIN pg_attribute a
            ON a.attrelid = r.tbl::regclass AND a.attnum = u.attnum
         WHERE tg.tgname = r.trg
           AND tg.tgrelid = r.tbl::regclass
           AND NOT tg.tgisinternal;

        SELECT td.d, COALESCE(substring(td.d FROM ' WHEN \((.*)\) EXECUTE FUNCTION '), ''), encode(tg.tgargs, 'hex')
          INTO v_def, v_when, v_args
          FROM pg_trigger tg
          CROSS JOIN LATERAL (SELECT regexp_replace(pg_get_triggerdef(tg.oid, true), '\s+', ' ', 'g') AS d) AS td
         WHERE tg.tgname = r.trg
           AND tg.tgrelid = r.tbl::regclass
           AND NOT tg.tgisinternal;

        SELECT CASE
                 WHEN tg.oid IS NULL
                   THEN 'триггер не создан'
                 WHEN tg.tgtype <> r.want_type
                   THEN 'tgtype ' || tg.tgtype || ' вместо ' || r.want_type
                 WHEN COALESCE(v_attr, '') <> r.want_attr
                   THEN 'список столбцов ' || COALESCE(v_attr, '<пусто>')
                        || ' вместо ' || COALESCE(NULLIF(r.want_attr, ''), '<пусто>')
                 WHEN tg.tgfoid::regprocedure::text <> r.want_fn
                   THEN 'функция ' || tg.tgfoid::regprocedure::text
                        || ' вместо ' || r.want_fn
                 WHEN tg.tgenabled <> 'O'
                   THEN 'триггер не в обычном режиме: tgenabled = ' || tg.tgenabled::text
                 WHEN tg.tgconstraint <> 0
                   THEN 'обычный триггер создан как constraint-триггер'
                 WHEN tg.tgdeferrable OR tg.tginitdeferred
                   THEN 'обычный триггер объявлен отложенным'
                 WHEN tg.tgqual IS NOT NULL
                   THEN 'у обычного триггера есть условие WHEN'
                 WHEN tg.tgnargs <> 0
                   THEN 'у триггера есть аргументы, а их быть не должно'
                 WHEN v_when <> r.want_when
                   THEN 'условие WHEN (' || v_when || ') вместо (' || r.want_when || ')'
                 WHEN v_args <> ''
                   THEN 'байты аргументов ' || v_args || ' вместо пустых'
                 WHEN v_def <> r.want_def
                   THEN 'определение ' || v_def || ' вместо ' || r.want_def
                 ELSE NULL
               END
          INTO v_problem
          FROM (SELECT 1) AS one
          LEFT JOIN pg_trigger tg
            ON tg.tgname = r.trg
           AND tg.tgrelid = r.tbl::regclass
           AND NOT tg.tgisinternal;

        IF v_problem IS NOT NULL THEN
            RAISE EXCEPTION 'TRIGGER_DEFINITION_MISMATCH: % на %: %',
                r.trg, r.tbl, v_problem;
        END IF;
    END LOOP;

    -- Constraint-триггер пересоздаётся так же безусловно. У него
    -- проверяются ещё четыре поля: признак ограничения, отложенность,
    -- начальная отложенность и условие WHEN.
    DROP TRIGGER IF EXISTS subject_requires_author ON bem_core.subject;
    CREATE CONSTRAINT TRIGGER subject_requires_author
        AFTER INSERT OR UPDATE OF published_at ON bem_core.subject
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        WHEN (NEW.published_at IS NOT NULL)
        EXECUTE FUNCTION bem_core.require_at_least_one_author();

    SELECT string_agg(a.attname::text, ',' ORDER BY u.ord) INTO v_attr
      FROM pg_trigger tg
      CROSS JOIN LATERAL unnest(tg.tgattr::smallint[]) WITH ORDINALITY AS u(attnum, ord)
      JOIN pg_attribute a
        ON a.attrelid = 'bem_core.subject'::regclass AND a.attnum = u.attnum
     WHERE tg.tgname = 'subject_requires_author'
       AND tg.tgrelid = 'bem_core.subject'::regclass
       AND NOT tg.tgisinternal;

    -- Ожидаемые условие и определение constraint-триггера. Это те же
    -- строки, что стоят в самопроверке (пункт 15а) и в файле 05;
    -- сверщик раздела 15.11 выводит их из команды выше и сверяет все
    -- три места.
    v_want_when := 'new.published_at IS NOT NULL';
    v_want_def  := 'CREATE CONSTRAINT TRIGGER subject_requires_author AFTER INSERT OR UPDATE OF published_at ON bem_core.subject DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (new.published_at IS NOT NULL) EXECUTE FUNCTION bem_core.require_at_least_one_author()';

    SELECT td.d, COALESCE(substring(td.d FROM ' WHEN \((.*)\) EXECUTE FUNCTION '), ''), encode(tg.tgargs, 'hex')
      INTO v_def, v_when, v_args
      FROM pg_trigger tg
      CROSS JOIN LATERAL (SELECT regexp_replace(pg_get_triggerdef(tg.oid, true), '\s+', ' ', 'g') AS d) AS td
     WHERE tg.tgname = 'subject_requires_author'
       AND tg.tgrelid = 'bem_core.subject'::regclass
       AND NOT tg.tgisinternal;

    SELECT CASE
             WHEN tg.oid IS NULL        THEN 'constraint-триггер не создан'
             WHEN tg.tgtype <> 21       THEN 'tgtype ' || tg.tgtype || ' вместо 21'
             WHEN COALESCE(v_attr, '') <> 'published_at'
               THEN 'список столбцов ' || COALESCE(v_attr, '<пусто>') || ' вместо published_at'
             WHEN tg.tgfoid::regprocedure::text <> 'bem_core.require_at_least_one_author()'
               THEN 'функция ' || tg.tgfoid::regprocedure::text
             WHEN tg.tgenabled <> 'O'  THEN 'tgenabled = ' || tg.tgenabled::text
             WHEN tg.tgconstraint = 0   THEN 'создан как обычный триггер, а не constraint'
             WHEN NOT tg.tgdeferrable   THEN 'не DEFERRABLE'
             WHEN NOT tg.tginitdeferred THEN 'не INITIALLY DEFERRED'
             WHEN tg.tgqual IS NULL     THEN 'потеряно условие WHEN'
             WHEN tg.tgnargs <> 0       THEN 'появились аргументы'
             WHEN v_when <> v_want_when
               THEN 'условие WHEN (' || v_when || ') вместо (' || v_want_when || ')'
             WHEN v_args <> ''         THEN 'байты аргументов ' || v_args
             WHEN v_def <> v_want_def
               THEN 'определение ' || v_def || ' вместо ' || v_want_def
             ELSE NULL
           END
      INTO v_problem
      FROM (SELECT 1) AS one
      LEFT JOIN pg_trigger tg
        ON tg.tgname = 'subject_requires_author'
       AND tg.tgrelid = 'bem_core.subject'::regclass
       AND NOT tg.tgisinternal;

    IF v_problem IS NOT NULL THEN
        RAISE EXCEPTION 'TRIGGER_DEFINITION_MISMATCH: subject_requires_author: %', v_problem;
    END IF;

    -- R33 (замечание L-H117-R17-01 = L-C-02, решение D-05). Проверка выше
    -- (строки с v_want_when/v_want_def) сравнивает настоящий триггер со
    -- строкой, набранной здесь же, в этом файле, — источник не независим от
    -- документа, который же и проверяется. Ниже — приём из решения D-05,
    -- которого не было в H1.17 (раздел 15.28, «Чего нет»): точное сравнение
    -- tgqual::text настоящего триггера с tgqual::text эталонного триггера
    -- той же формы. pg_get_expr(tgqual, tgrelid) не годится: NEW и OLD — два
    -- разных отношения, а pg_get_expr строит контекст для одного и отказывает
    -- («bogus varno: 2», строка K-R16-12); tgqual::text — печать разобранного
    -- дерева условия, а не деразбор в SQL-текст, и двух отношений не боится.
    --
    -- Эталон — временная таблица той же формы (LIKE копирует список столбцов
    -- в том же порядке, поэтому у published_at тот же порядковый номер), с
    -- триггером той же формы на ней. Сравниваются ДВА независимых чтения
    -- каталога pg_trigger — настоящей таблицы и временной, — а не текст со
    -- строкой-константой.
    --
    -- Честно: возможное служебное поле положения в исходной строке
    -- (:location) внутри tgqual зависит от длины команды CREATE TRIGGER, а не
    -- от условия; снято regexp_replace ниже, иначе отказ был бы и на верной
    -- базе. PostgreSQL 16.15 это поле пишет (и в VAR, и в NULLTEST); живой
    -- прогон R43: совпадение на верной базе, TRIGGER_TGQUAL_MISMATCH при
    -- изменённом условии (EVIDENCE_PG16_D05_20261005T064050Z).
    DROP TABLE IF EXISTS pg_temp.subject_reference_shape;
    CREATE TEMP TABLE subject_reference_shape (LIKE bem_core.subject);

    DROP TRIGGER IF EXISTS subject_requires_author_ref ON pg_temp.subject_reference_shape;
    CREATE CONSTRAINT TRIGGER subject_requires_author_ref
        AFTER INSERT OR UPDATE OF published_at ON pg_temp.subject_reference_shape
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        WHEN (NEW.published_at IS NOT NULL)
        EXECUTE FUNCTION bem_core.require_at_least_one_author();

    SELECT regexp_replace(tg.tgqual::text, ':location -?[0-9]+', ':location X', 'g')
      INTO v_tgqual_real
      FROM pg_trigger tg
     WHERE tg.tgname = 'subject_requires_author'
       AND tg.tgrelid = 'bem_core.subject'::regclass
       AND NOT tg.tgisinternal;

    SELECT regexp_replace(tg.tgqual::text, ':location -?[0-9]+', ':location X', 'g')
      INTO v_tgqual_ref
      FROM pg_trigger tg
     WHERE tg.tgname = 'subject_requires_author_ref'
       AND tg.tgrelid = 'pg_temp.subject_reference_shape'::regclass
       AND NOT tg.tgisinternal;

    IF v_tgqual_real IS DISTINCT FROM v_tgqual_ref THEN
        RAISE EXCEPTION 'TRIGGER_TGQUAL_MISMATCH: subject_requires_author: % вместо %',
            v_tgqual_real, v_tgqual_ref;
    END IF;

    DROP TRIGGER IF EXISTS subject_requires_author_ref ON pg_temp.subject_reference_shape;
    DROP TABLE IF EXISTS pg_temp.subject_reference_shape;

    -- Лишний триггер на управляемой таблице — тоже расхождение: рядом
    -- с правильным можно повесить второй, который тихо меняет строку.
    SELECT string_agg(tg.tgname || ' на ' || tg.tgrelid::regclass::text, ', ')
      INTO v_problem
      FROM pg_trigger tg
     WHERE NOT tg.tgisinternal
       AND tg.tgrelid IN ('bem_core.audit_record'::regclass,
                          'bem_core.subject_author'::regclass,
                          'bem_core.evidence'::regclass,
                          'bem_core.command_log'::regclass,
                          'bem_core.subject'::regclass)
       AND tg.tgname NOT IN (
             'audit_record_append_only', 'subject_author_append_only', 'evidence_append_only', 'evidence_identity',
             'command_log_append_only', 'audit_record_no_self_audit', 'audit_record_head_match', 'subject_author_frozen',
             'subject_requires_author');

    IF v_problem IS NOT NULL THEN
        RAISE EXCEPTION 'TRIGGER_SURPLUS: лишние триггеры: %', v_problem;
    END IF;

    PERFORM set_config('search_path', v_path, true);
END
$$;

-- ---------------------------------------------------------------
-- Шаг 8. Защита строк. Одна политика на таблицу, одно выражение —
--        функция bem_core.current_tenant() и никаких копий.
-- ---------------------------------------------------------------
DO $$
DECLARE
    t        text;
    v_qual   text;
    v_check  text;
    v_cmd    text;
    v_perm   text;
    v_roles  name[];
    v_expr   constant text := '(tenant_id = current_tenant())';
BEGIN
    FOREACH t IN ARRAY ARRAY['work_item', 'evidence', 'subject', 'subject_author',
                             'audit_record', 'outbox', 'command_log', 'usage_record',
                             'handoff_packet', 'user_tenant_membership',
                             'audit_assignment']
    LOOP
        EXECUTE format('ALTER TABLE bem_core.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE bem_core.%I FORCE  ROW LEVEL SECURITY', t);

        SELECT pol.qual, pol.with_check, pol.cmd, pol.permissive, pol.roles
          INTO v_qual, v_check, v_cmd, v_perm, v_roles
          FROM pg_policies pol
         WHERE pol.schemaname = 'bem_core'
           AND pol.tablename  = t
           AND pol.policyname = 'tenant_isolation';

        IF NOT FOUND THEN
            EXECUTE format(
                'CREATE POLICY tenant_isolation ON bem_core.%I'
                ' USING (tenant_id = bem_core.current_tenant())'
                ' WITH CHECK (tenant_id = bem_core.current_tenant())', t);
        ELSE
            -- H1.7 проверял только ИМЯ политики, поэтому ослабленная
            -- политика с тем же именем оставалась жить (M-H17-R7-08).
            -- Команду и режим ALTER POLICY изменить не может: если они
            -- другие — остановка ДО любых изменений, с точным именем.
            IF v_cmd <> 'ALL' OR v_perm <> 'PERMISSIVE' THEN
                -- ПОКРЫТИЕ: K-R7-30
                RAISE EXCEPTION
                  'POLICY_SHAPE_MISMATCH: bem_core.% cmd=% permissive=%'
                  ' — политику нужно пересоздать вручную под присмотром',
                  t, v_cmd, v_perm;
            END IF;

            -- Сравнение по тексту каталога с убранным именем схемы:
            -- PostgreSQL печатает вызов со схемой или без неё в
            -- зависимости от пути поиска, и это не различие.
            IF replace(coalesce(v_qual, ''),  'bem_core.', '') IS DISTINCT FROM v_expr
            OR replace(coalesce(v_check, ''), 'bem_core.', '') IS DISTINCT FROM v_expr
            OR v_roles IS DISTINCT FROM ARRAY['public']::name[] THEN
                EXECUTE format(
                    'ALTER POLICY tenant_isolation ON bem_core.%I TO public'
                    ' USING (tenant_id = bem_core.current_tenant())'
                    ' WITH CHECK (tenant_id = bem_core.current_tenant())', t);
            END IF;
        END IF;
    END LOOP;
END
$$;

-- ---------------------------------------------------------------
-- Шаг 9а. Права в схеме bem_core. Выдаёт владелец этой схемы.
--         Прошлая редакция выдавала права на чужие схемы из-под
--         bem_core_owner — команда падала на отсутствии прав.
-- ---------------------------------------------------------------
GRANT USAGE ON SCHEMA bem_core TO bem_kernel_rw, bem_control_owner, backup_reader;

-- Сначала отзыв, потом точная выдача. Без отзыва повторный прогон на базе
-- прошлой редакции оставил бы широкое право INSERT, UPDATE у ядра:
-- команда GRANT права не сужает, она их только добавляет.
REVOKE ALL ON ALL TABLES    IN SCHEMA bem_core
    FROM bem_kernel_rw, bem_control_owner, backup_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA bem_core
    FROM bem_kernel_rw, bem_control_owner, backup_reader;

-- Ядро: только чтение, запись доказательств и ничего больше (раздел 5.2)
GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA bem_core TO bem_kernel_rw;
-- Прямой записи доказательств у ядра больше нет. H1.8 её выдавал, и
-- общая runtime-роль могла подписать доказательство любым синтаксически
-- допустимым участником (замечание C-H18-R8-05). Теперь доказательства
-- пишет узкая функция bem_control.record_evidence, а личность проставляет
-- триггер bem_core.evidence_identity.
REVOKE INSERT ON bem_core.evidence FROM bem_kernel_rw;

-- Владелец функций: чтение всего (для подписи таблиц) плюс точечная запись.
--
-- Список выведен из тел функций, а не из памяти. H1.8 выдавал права на
-- восемь таблиц, а писали функции в двенадцать: приём пакета передачи,
-- запись расхода, назначение проверяющего и привязка процесса падали бы
-- на «нет прав» при первом же вызове. Отзыв выше снимает всё, поэтому
-- недостающее право не «донаследовалось» бы ниоткуда. Это дефект H1.8,
-- найденный сверх аудита C-линии: тела функций сверены со списком прав
-- построчно.
--
-- Правило для любой будущей правки: изменил тело функции — изменил
-- и эту строку. Проверка 16 раздела 26.9 сверяет их машинно.
GRANT SELECT ON ALL TABLES IN SCHEMA bem_core TO bem_control_owner;
GRANT INSERT ON bem_core.tenant        TO bem_control_owner;
GRANT INSERT ON bem_core.evidence      TO bem_control_owner;
GRANT INSERT ON bem_core.work_item     TO bem_control_owner;
GRANT UPDATE (status, revision, updated_at, process_instance_id)
              ON bem_core.work_item TO bem_control_owner;
GRANT INSERT ON bem_core.command_log   TO bem_control_owner;
GRANT UPDATE (result_revision, outbox_id)   ON bem_core.command_log TO bem_control_owner;
GRANT INSERT ON bem_core.outbox        TO bem_control_owner;
GRANT UPDATE (status, leased_by, leased_until, lease_epoch,
              attempt_count, result, finished_at, next_attempt_at,
              dead_lettered_at, dead_letter_reason,
              reconciled_at, reconciled_outcome) ON bem_core.outbox TO bem_control_owner;
GRANT INSERT ON bem_core.subject       TO bem_control_owner;
GRANT UPDATE (head_sha, published_at, released_at, released_by,
              disagreement_at, disagreement_reason) ON bem_core.subject TO bem_control_owner;
GRANT INSERT ON bem_core.subject_author TO bem_control_owner;
GRANT INSERT ON bem_core.audit_record   TO bem_control_owner;
GRANT INSERT ON bem_core.audit_assignment TO bem_control_owner;
GRANT UPDATE (revoked_at, assigned_at, assigned_by)
              ON bem_core.audit_assignment TO bem_control_owner;
GRANT INSERT ON bem_core.usage_record   TO bem_control_owner;
GRANT INSERT ON bem_core.handoff_packet TO bem_control_owner;
GRANT UPDATE (accepted_at, accepted_by) ON bem_core.handoff_packet TO bem_control_owner;
GRANT INSERT ON bem_core.user_tenant_membership TO bem_control_owner;
GRANT UPDATE (revoked_at, revoked_by) ON bem_core.user_tenant_membership TO bem_control_owner;
-- Жизненный цикл личности. H1.10 создала пять функций — завести
-- участника, выдать и отозвать полномочие, выдать и отозвать
-- доверенность — и не выдала их владельцу ни одного права записи.
-- Каждая из пяти останавливалась на первой же команде, то есть весь
-- путь чистой установки был неисполним (замечание C-H110-R10-01).
-- Права выданы точечно, по фактическим телам функций: ни одного ALL,
-- ни одного DELETE, обновление — по именам колонок.
GRANT INSERT ON bem_core.actor            TO bem_control_owner;
GRANT INSERT ON bem_core.actor_authority  TO bem_control_owner;
GRANT UPDATE (revoked_at) ON bem_core.actor_authority TO bem_control_owner;
GRANT INSERT ON bem_core.actor_delegation TO bem_control_owner;
GRANT UPDATE (revoked_at, revoked_by) ON bem_core.actor_delegation TO bem_control_owner;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA bem_core TO bem_control_owner;

-- Копирование: только чтение
GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO backup_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA bem_core TO backup_reader;

ALTER DEFAULT PRIVILEGES FOR ROLE bem_core_owner IN SCHEMA bem_core
    GRANT SELECT ON TABLES TO backup_reader, bem_kernel_rw, bem_control_owner;
ALTER DEFAULT PRIVILEGES FOR ROLE bem_core_owner IN SCHEMA bem_core
    GRANT SELECT ON SEQUENCES TO backup_reader, bem_kernel_rw, bem_control_owner;

-- Служебный заказчик для доказательств копирования (раздел 26.6)
INSERT INTO bem_core.tenant (id, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'service')
ON CONFLICT (id) DO NOTHING;

-- Первая связанная личность и её полномочия.
--
-- Без неё установка мертва. Полномочие выдаётся только связанной
-- личности, а выдать его может лишь тот, у кого полномочие уже есть;
-- первого администратора заказчика заводит create_tenant, а она сама
-- требует полномочия TENANT_PROVISIONER. Замкнутый круг разрывается
-- здесь, один раз, на чистой установке (замечание M-H18-R8-07).
--
-- Эта строка — не «учётная запись для всех». Она связана с ролью входа
-- bem_bootstrap_admin (файл 00), у которой нет пароля до тех пор, пока
-- оператор его не задаст. Первое, что делает оператор после установки:
-- заводит собственные роли входа, связывает их со своими участниками,
-- выдаёт им полномочия и отзывает полномочия этой строки. Проверки
-- K-R8-16 и K-R8-17 требуют ровно этого.
--
-- granted_by указывает на саму строку: выдающего ещё не существует,
-- и записывать сюда чужое имя было бы неправдой.
INSERT INTO bem_core.actor (actor_id, provider, user_id, is_active, db_role)
VALUES ('human:bootstrap', 'human', NULL, true, 'bem_bootstrap_admin')
ON CONFLICT (actor_id) DO NOTHING;

-- Сторож окна копирования. H1.9 писала доказательство от имени
-- 'human:backup-watchdog', не создав такой строки: внешний ключ
-- evidence_actor_fk и триггер evidence_identity отказали бы при первом
-- же вызове на чистой установке (замечание M-H19-R9-01).
--
-- Строка связана с ролью входа bem_backup_admin, поэтому личность
-- сторожа выходит BOUND сама собой, без доверенности и без настройки
-- app.actor_id. Учётной записи у него нет (user_id = NULL): это
-- служебный участник платформы, и в заказчиках он не состоит.
--
-- Префикс 'human:' здесь означает «не поставщик модели»: домен
-- bem_core.actor_id знает три префикса, и два из них — claude и codex —
-- заняты поставщиками. Заводить четвёртый ради одной строки значило бы
-- менять домен и набор поставщиков, который задание просит сохранить.
INSERT INTO bem_core.actor (actor_id, provider, user_id, is_active, db_role)
VALUES ('human:backup-watchdog', 'human', NULL, true, 'bem_backup_admin')
ON CONFLICT (actor_id) DO NOTHING;

INSERT INTO bem_core.actor_authority
       (id, tenant_id, actor_id, authority, granted_by)
SELECT gen_random_uuid(), NULL, 'human:bootstrap', a, 'human:bootstrap'
  FROM unnest(ARRAY['OPERATOR', 'AUDIT_COORDINATOR', 'TENANT_PROVISIONER']) AS a
 WHERE NOT EXISTS (SELECT 1
                     FROM bem_core.actor_authority x
                    WHERE x.actor_id   = 'human:bootstrap'
                      AND x.authority  = a
                      AND x.tenant_id  IS NULL
                      AND x.revoked_at IS NULL);

RESET ROLE;

-- ---------------------------------------------------------------
-- Шаг 9б. Права в схеме bem_engine. Выдаёт её владелец.
-- ---------------------------------------------------------------
SET ROLE bem_engine_owner;
-- Владелец свёрток тоже получает вход в схему движка и права на её
-- БУДУЩИЕ таблицы: без этого свёртка движка недоказуема (M-H17-R7-10).
GRANT USAGE  ON SCHEMA bem_engine TO bem_engine_rw, backup_reader, bem_control_owner;
GRANT SELECT ON ALL TABLES    IN SCHEMA bem_engine TO backup_reader, bem_control_owner;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA bem_engine TO backup_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE bem_engine_owner IN SCHEMA bem_engine
    GRANT SELECT ON TABLES TO backup_reader, bem_control_owner;
ALTER DEFAULT PRIVILEGES FOR ROLE bem_engine_owner IN SCHEMA bem_engine
    GRANT SELECT ON SEQUENCES TO backup_reader, bem_control_owner;
RESET ROLE;

-- ---------------------------------------------------------------
-- Шаг 9в. Права в схеме bem_control. Выдаёт её владелец.
-- ---------------------------------------------------------------
SET ROLE bem_control_owner;
GRANT USAGE  ON SCHEMA bem_control TO bem_kernel_rw, bem_backup_admin, backup_reader;
-- Управляющая группа: чувствительные функции исполняет она, а не общая
-- рабочая роль ядра (замечания C-H18-R8-04, C-H18-R8-05).
GRANT USAGE  ON SCHEMA bem_control TO bem_governance;
-- Право создавать объекты в этой схеме выдаётся владельцу функций окна
-- копирования на время их создания и отзывается сразу после (раздел 26.6).
GRANT USAGE  ON SCHEMA bem_control TO bem_backup_ctl_owner;
GRANT SELECT ON ALL TABLES    IN SCHEMA bem_control TO backup_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA bem_control TO backup_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE bem_control_owner IN SCHEMA bem_control
    GRANT SELECT ON TABLES TO backup_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE bem_control_owner IN SCHEMA bem_control
    GRANT SELECT ON SEQUENCES TO backup_reader;
RESET ROLE;

-- Все функции bem_control принадлежат bem_control_owner: именно его
-- правами они работают, потому что объявлены SECURITY DEFINER.
SET ROLE bem_control_owner;

-- Проверка 1. Аргумент заказчика обязан совпасть с контекстом транзакции.
-- Функция STABLE и ничего не пишет: её единственное действие — отказ.
CREATE OR REPLACE FUNCTION bem_control.assert_tenant(p_tenant_id uuid)
RETURNS void
LANGUAGE plpgsql
STABLE
SET search_path = bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_ctx uuid := bem_core.current_tenant();
BEGIN
    IF p_tenant_id IS NULL THEN
        RAISE EXCEPTION 'TENANT_ARGUMENT_NULL';
    END IF;
    IF v_ctx IS NULL THEN
        -- пустой контекст = отказ. То же правило, что и у защиты строк:
        -- «нет заказчика» означает «ничего не видно и ничего нельзя»
        RAISE EXCEPTION 'NO_TENANT_CONTEXT';
    END IF;
    IF v_ctx <> p_tenant_id THEN
        RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH: context=% argument=%',
              v_ctx, p_tenant_id;
    END IF;
END;
$$;

ALTER FUNCTION bem_control.assert_tenant(uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.assert_tenant(uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.assert_tenant(uuid) TO bem_kernel_rw;

-- Проверка 3. Личность вызывающего и способ её установления.
CREATE OR REPLACE FUNCTION bem_control.current_actor_checked(
    p_tenant_id            uuid,
    OUT out_actor_id       text,
    OUT out_identity_mode  text,
    OUT out_delegation_id  uuid)
RETURNS record
LANGUAGE plpgsql
STABLE
SET search_path = bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_claim  text := NULLIF(current_setting('app.actor_id', true), '');
    v_cnt    integer;
    v_bound  text;
    v_active boolean;
    v_user   uuid;
    v_deleg  uuid;
BEGIN
    -- Граница заказчика ставится здесь, а не только у вызывающего:
    -- право на исполнение этой функции есть и у рабочей роли, значит
    -- проверку обязана делать она сама (замечание M-H19-R9-03, находка
    -- смыслового сверщика сверх списка аудита). Пустой аргумент —
    -- общесистемный вызов без заказчика, там границей служит полномочие.
    IF p_tenant_id IS NOT NULL THEN
        PERFORM bem_control.assert_tenant(p_tenant_id);
    END IF;

    -- 1. Связанная личность. session_user — настоящая роль входа:
    --    SECURITY DEFINER меняет current_user, но не её.
    SELECT count(*), min(a.actor_id) INTO v_cnt, v_bound
      FROM bem_core.actor a
     WHERE a.db_role = session_user;

    -- Ограничение actor_db_role_uniq делает эту ветку недостижимой на
    -- целой схеме. Она оставлена намеренно: если ограничение когда-нибудь
    -- снимут, вход должен остановиться, а не выбрать участника наугад.
    IF v_cnt > 1 THEN
        RAISE EXCEPTION
          'ACTOR_BINDING_AMBIGUOUS: роль % связана с % участниками', session_user, v_cnt;
    END IF;

    IF v_cnt = 1 THEN
        SELECT a.is_active INTO v_active
          FROM bem_core.actor a WHERE a.actor_id = v_bound;
        IF NOT v_active THEN
            RAISE EXCEPTION 'INACTIVE_ACTOR: %', v_bound;
        END IF;
        IF v_claim IS NOT NULL AND v_claim <> v_bound THEN
            RAISE EXCEPTION
              'ACTOR_CLAIM_MISMATCH: сессия связана с %, а заявлен %', v_bound, v_claim;
        END IF;
        out_actor_id      := v_bound;
        out_identity_mode := 'BOUND';
        out_delegation_id := NULL;     -- участник вошёл сам, основание не нужно
        RETURN;
    END IF;

    -- 2. Личность по доверенности: за участника говорит общая роль.
    IF v_claim IS NULL THEN
        RAISE EXCEPTION 'NO_ACTOR_CONTEXT';
    END IF;

    SELECT a.is_active, a.user_id INTO v_active, v_user
      FROM bem_core.actor a
     WHERE a.actor_id = v_claim;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'UNKNOWN_ACTOR: %', v_claim;
    END IF;
    IF NOT v_active THEN
        RAISE EXCEPTION 'INACTIVE_ACTOR: %', v_claim;
    END IF;

    IF v_user IS NOT NULL AND p_tenant_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
          FROM bem_core.user_tenant_membership m
         WHERE m.user_id    = v_user
           AND m.tenant_id  = p_tenant_id
           AND m.revoked_at IS NULL)
    THEN
        RAISE EXCEPTION
          'ACTOR_NOT_IN_TENANT: участник % не состоит в заказчике %', v_claim, p_tenant_id;
    END IF;

    -- Основание доверенности. H1.9 здесь заканчивала проверку: строка
    -- в настройке app.actor_id считалась личностью сама по себе, и
    -- сессия ядра могла назвать любого действующего участника
    -- (замечание C-H19-R9-01). Теперь за словом обязана стоять
    -- выданная доверенность: пара «роль входа — участник», живая на
    -- момент вызова. Выдаёт её держатель полномочия OPERATOR, и
    -- отозвать её можно одной строкой.
    SELECT d.id INTO v_deleg
      FROM bem_core.actor_delegation d
     WHERE d.principal_role = session_user
       AND d.actor_id       = v_claim
       AND d.revoked_at     IS NULL;

    IF v_deleg IS NULL THEN
        RAISE EXCEPTION
          'DELEGATION_NOT_GRANTED: роли % не выдана доверенность говорить'
          ' за участника %', session_user, v_claim;
    END IF;

    out_actor_id      := v_claim;
    out_identity_mode := 'DELEGATED';
    out_delegation_id := v_deleg;
    RETURN;
END;
$$;

ALTER FUNCTION bem_control.current_actor_checked(uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.current_actor_checked(uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.current_actor_checked(uuid) TO bem_kernel_rw;

-- Проверка 4. Полномочие. Полномочие есть только у связанной личности:
-- строка в настройке полномочием не является никогда
-- (замечания C-H18-R8-04, C-H18-R8-05).
CREATE OR REPLACE FUNCTION bem_control.assert_authority(
    p_authority text,
    p_tenant_id uuid DEFAULT NULL)
RETURNS text
LANGUAGE plpgsql
STABLE
SET search_path = bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor text;
    v_mode  text;
BEGIN
    -- Граница заказчика ставится здесь, а не только у вызывающего:
    -- право на исполнение этой функции есть и у рабочей роли, значит
    -- проверку обязана делать она сама (замечание M-H19-R9-03, находка
    -- смыслового сверщика сверх списка аудита). Пустой аргумент —
    -- общесистемный вызов без заказчика, там границей служит полномочие.
    IF p_tenant_id IS NOT NULL THEN
        PERFORM bem_control.assert_tenant(p_tenant_id);
    END IF;

    SELECT out_actor_id, out_identity_mode INTO v_actor, v_mode
      FROM bem_control.current_actor_checked(p_tenant_id);

    IF v_mode <> 'BOUND' THEN
        RAISE EXCEPTION
          'AUTHORITY_REQUIRES_BOUND_IDENTITY: полномочие % требует собственного входа;'
          ' роль % говорит за участника % по доверенности',
          p_authority, session_user, v_actor;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM bem_core.actor_authority aa
         WHERE aa.actor_id   = v_actor
           AND aa.authority  = p_authority
           AND aa.revoked_at IS NULL
           AND (aa.tenant_id IS NULL OR aa.tenant_id = p_tenant_id))
    THEN
        RAISE EXCEPTION
          'AUTHORITY_REQUIRED: у участника % нет действующего полномочия %',
          v_actor, p_authority;
    END IF;

    RETURN v_actor;
END;
$$;

ALTER FUNCTION bem_control.assert_authority(text, uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.assert_authority(text, uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.assert_authority(text, uuid) TO bem_kernel_rw;

-- Служебный заказчик. H1.10 повторяла этот номер шесть раз внутри шести
-- разных функций: «одно место» существовало только на словах. Теперь
-- место одно, и оно здесь.
--
-- Это не обычный заказчик. У него нет людей, работ и предметов; в нём
-- живут доказательства о самой установке — заведение участника, выдача
-- и отзыв полномочия и доверенности, окно копирования. Строку с этим
-- номером создаёт шаг 8 (раздел 26.4), а проверка 17 раздела 26.9
-- сверяет, что номер строки и ответ этой функции — одно и то же.
CREATE OR REPLACE FUNCTION bem_control.service_tenant()
RETURNS uuid
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog, pg_temp
AS $$ SELECT '00000000-0000-0000-0000-000000000001'::uuid $$;

ALTER FUNCTION bem_control.service_tenant() OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.service_tenant() FROM PUBLIC;

-- Одна очередь на кластерное полномочие OPERATOR.
--
-- H1.10 считала оставшихся операторов обычным запросом, а потом
-- обновляла строку. Две сессии, отзывающие двух разных операторов,
-- обе видели второго в своём снимке, обе проходили проверку — и
-- операторов не оставалось ни одного (замечание M-H110-R10-04).
--
-- Ключ один и тот же для выдачи и для отзыва, поэтому обе операции
-- стоят в одной очереди. Блокировка транзакционная: она снимается
-- сама при фиксации и при откате, и забыть её снять нельзя.
-- Значение ключа считается от постоянной строки. Оно обязано быть
-- одинаковым во всех сессиях одного кластера — этого достаточно:
-- блокировка живёт внутри одного работающего сервера и в файлы не
-- попадает.
CREATE OR REPLACE FUNCTION bem_control.operator_lock_key()
RETURNS bigint
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog, pg_temp
AS $$ SELECT hashtextextended('bem954:cluster-operator', 0) $$;

ALTER FUNCTION bem_control.operator_lock_key() OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.operator_lock_key() FROM PUBLIC;

-- Строка-охранник кластерного полномочия OPERATOR.
--
-- H1.11 брала очередь правильным ключом, но поздно: assert_authority()
-- успевал прочитать три таблицы, а при REPEATABLE READ снимок данных
-- создаётся первым же запросом и дальше не меняется. Вторая сессия
-- дожидалась очереди, считала операторов по старому снимку, видела там
-- живого A и отзывала B. Обе фиксировались, операторов не оставалось
-- (замечание M-H111-R11-01). Очередь упорядочивает сессии; снимок она
-- не обновляет, и обещать обратное нельзя.
--
-- Барьер здесь другой. Обе функции первым действием обновляют одну и ту
-- же строку этой таблицы. Такое обновление не зависит от возраста
-- снимка: PostgreSQL обязан либо дождаться чужой транзакции и взять
-- новую версию строки, либо отказать. Что происходит дальше, зависит от
-- уровня изоляции, и оба исхода безопасны:
--
--   READ COMMITTED  — вторая сессия ждёт, берёт новую версию строки и
--                     считает операторов уже по результату первой;
--   REPEATABLE READ,
--   SERIALIZABLE    — вторая сессия получает SQLSTATE 40001 и обязана
--                     повторить транзакцию целиком; ничего неверного
--                     зафиксировано не будет.
--
-- Ошибочного исхода нет ни на одном из трёх уровней, и ни один из них
-- не требуется задавать клиенту заранее. Проверки K-R11-01…K-R11-06.
--
-- Таблица принадлежит bem_control_owner — тому же владельцу, чьими
-- правами работают функции полномочий. Поэтому права на неё никому не
-- выдаются: владелец пишет в свою таблицу своими правами, а выданных
-- прав, которые нужно было бы сверять договором, здесь нет вовсе.
CREATE TABLE IF NOT EXISTS bem_control.authority_guard (
    scope      text PRIMARY KEY,
    revision   bigint      NOT NULL DEFAULT 0,
    changed_at timestamptz NOT NULL DEFAULT now(),
    changed_by name
);
-- H1.26, D1 (пробы R46, п. 16): ограничения таблицы bem_control.authority_guard — тем же
-- порядком, что шаг 4 для bem_core, и до первой вставки с ON CONFLICT:
-- без первичного ключа она падает раньше, чем ключ успеют вернуть.
DO $$
DECLARE
    r      record;
    v_def  text;
    v_path text;
BEGIN
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog', true);
    FOR r IN
        SELECT * FROM (VALUES
            ('bem_control.authority_guard', 'authority_guard_pkey', 'PRIMARY KEY (scope)')
        ) AS t(tbl, con, def)
    LOOP
        SELECT pg_get_constraintdef(c.oid) INTO v_def
          FROM pg_constraint c
         WHERE c.conname = r.con AND c.conrelid = r.tbl::regclass;
        IF NOT FOUND THEN
            EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', r.tbl, r.con, r.def);
        ELSIF v_def IS DISTINCT FROM r.def THEN
            RAISE EXCEPTION
              'MIGRATION_FAILED: CONSTRAINT_DEFINITION_MISMATCH: % %: ожидалось %, найдено %',
              r.tbl, r.con, r.def, v_def;
        END IF;
    END LOOP;
    PERFORM set_config('search_path', v_path, true);
END
$$;
INSERT INTO bem_control.authority_guard (scope)
VALUES ('cluster_operator')
ON CONFLICT (scope) DO NOTHING;

-- Барьер. Возвращает новый номер правки — он попадает в доказательство,
-- поэтому «барьер был взят» становится проверяемым фактом, а не
-- обещанием кода.
CREATE OR REPLACE FUNCTION bem_control.authority_barrier(p_scope text)
RETURNS bigint
LANGUAGE plpgsql
SET search_path = bem_control, pg_catalog, pg_temp
AS $$
DECLARE
    v_rev bigint;
BEGIN
    -- Первое обращение к данным во всей цепочке. Ни одна пользовательская
    -- таблица до него не читается: иначе снимок окажется старше барьера,
    -- и вернётся ровно тот дефект, который закрывает эта функция.
    UPDATE bem_control.authority_guard
       SET revision   = revision + 1,
           changed_at = now(),
           changed_by = session_user
     WHERE scope = p_scope
    RETURNING revision INTO v_rev;

    IF v_rev IS NULL THEN
        RAISE EXCEPTION 'UNKNOWN_AUTHORITY_SCOPE: %', p_scope;
    END IF;

    -- Очередь берётся после барьера и только ради порядка ожидания:
    -- доказательством безопасности она не является.
    PERFORM pg_advisory_xact_lock(bem_control.operator_lock_key());
    RETURN v_rev;
END;
$$;

ALTER FUNCTION bem_control.authority_barrier(text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.authority_barrier(text) FROM PUBLIC;

-- Проверка 5. Единственная дверь для записи доказательства.
--
-- H1.9 объявляла эту дверь, но двадцать функций писали в таблицу
-- напрямую, и пять из них брали участника прямо из настройки
-- app.actor_id (замечание C-H19-R9-01). Здесь дверь одна на самом деле:
-- ниже стоит единственный во всём пакете INSERT INTO bem_core.evidence,
-- и найти это может не человек, а программа — сверщик раздела 15.9
-- считает вставки и отказывает, если их больше одной.
--
-- Участника writer не принимает аргументом вовсе. Он выводит его сам
-- из проверенного контекста, поэтому «написать от чужого имени» нечем:
-- подменить можно только то, что передают.
CREATE OR REPLACE FUNCTION bem_control.evidence_write(
    p_tenant_id uuid,
    p_kind      text,
    p_payload   jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_temp
AS $$
DECLARE
    v_actor text;
    v_mode  text;
    v_deleg uuid;
    v_id    uuid := gen_random_uuid();
BEGIN
    IF p_tenant_id IS NULL THEN
        RAISE EXCEPTION 'EVIDENCE_TENANT_REQUIRED';
    END IF;
    IF p_kind IS NULL OR btrim(p_kind) = '' THEN
        RAISE EXCEPTION 'EVIDENCE_KIND_REQUIRED';
    END IF;

    -- Служебная запись. У служебного заказчика контекста сессии нет и
    -- быть не может: участника заводят до всякого заказчика, окно
    -- копирования открывают помимо заказчиков вовсе. H1.10 требовала
    -- контекст и здесь, поэтому весь путь установки был недостижим:
    -- каждая из шести функций упиралась в NO_TENANT_CONTEXT
    -- (замечание C-H110-R10-01, факт 5, и M-H110-R10-01).
    --
    -- Послабление узкое, и узость его проверяема. Оно действует ровно
    -- для одного номера — служебного — и ни для какого другого: для
    -- любого настоящего заказчика граница остаётся прежней. Права на
    -- исполнение этой функции нет ни у одной рабочей роли; ядро пишет
    -- доказательства через record_evidence, а та требует совпадения
    -- заказчика с контекстом всегда. Личность проверяется так же
    -- строго: связанная по роли входа или по живой доверенности.
    -- Общего обхода границы здесь нет — есть один служебный номер.
    IF p_tenant_id = bem_control.service_tenant() THEN
        SELECT out_actor_id, out_identity_mode, out_delegation_id
          INTO v_actor, v_mode, v_deleg
          FROM bem_control.current_actor_checked(NULL);
    ELSE
        SELECT out_actor_id, out_identity_mode, out_delegation_id
          INTO v_actor, v_mode, v_deleg
          FROM bem_control.current_actor_checked(p_tenant_id);
    END IF;

    -- EVIDENCE_WRITE_MARKER: единственная разрешённая вставка
    -- доказательства во всём пакете. Сверщик раздела 15.9 и
    -- самопроверка 26.9 опираются на эту метку.
    INSERT INTO bem_core.evidence
           (id, tenant_id, kind, actor_id, payload, delegation_id, created_at)
    VALUES (v_id, p_tenant_id, p_kind, v_actor,
            coalesce(p_payload, '{}'::jsonb), v_deleg, now());

    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.evidence_write(uuid, text, jsonb) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.evidence_write(uuid, text, jsonb) FROM PUBLIC;
-- Ядру прямой доступ к writer не нужен: у него есть record_evidence,
-- которая вдобавок сверяет заказчика с контекстом сессии.
GRANT  EXECUTE ON FUNCTION bem_control.evidence_write(uuid, text, jsonb) TO bem_control_owner;

-- Публичная дверь ядра. Отличается от writer ровно одним: она требует,
-- чтобы заказчик в аргументе совпал с заказчиком сессии.
CREATE OR REPLACE FUNCTION bem_control.record_evidence(
    p_tenant_id uuid,
    p_kind      text,
    p_payload   jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_temp
AS $$
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    RETURN bem_control.evidence_write(p_tenant_id, p_kind, p_payload);
END;
$$;

ALTER FUNCTION bem_control.record_evidence(uuid, text, jsonb) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.record_evidence(uuid, text, jsonb) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.record_evidence(uuid, text, jsonb) TO bem_kernel_rw;

-- Проверка 2. Канонический отпечаток команды, версия формата 2.
-- Склейки нет: каждое поле лежит в объекте jsonb под своим именем
-- и со своим типом, поэтому знак | внутри значения ничего не сдвигает.
CREATE OR REPLACE FUNCTION bem_control.command_fingerprint(
    p_tenant_id         uuid,
    p_work_item_id      uuid,
    p_actor_id          text,
    p_expected_revision integer,
    p_allowed_from      text[],
    p_new_status        text,
    p_outbox_kind       text,
    p_outbox_payload    jsonb,
    p_evidence          jsonb)
RETURNS text
LANGUAGE sql
STABLE
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT encode(sha256(convert_to(jsonb_build_object(
               'v',                 2,
               'tenant_id',         coalesce(to_jsonb(p_tenant_id),         'null'::jsonb),
               'work_item_id',      coalesce(to_jsonb(p_work_item_id),      'null'::jsonb),
               'actor_id',          coalesce(to_jsonb(p_actor_id),          'null'::jsonb),
               'expected_revision', coalesce(to_jsonb(p_expected_revision), 'null'::jsonb),
               'allowed_from',      coalesce(to_jsonb(p_allowed_from),      'null'::jsonb),
               'new_status',        coalesce(to_jsonb(p_new_status),        'null'::jsonb),
               'outbox_kind',       coalesce(to_jsonb(p_outbox_kind),       'null'::jsonb),
               'outbox_payload',    coalesce(p_outbox_payload,              'null'::jsonb),
               'evidence',          coalesce(p_evidence,                    'null'::jsonb)
           )::text, 'UTF8')), 'hex');
$$;

ALTER FUNCTION bem_control.command_fingerprint(uuid, uuid, text, integer, text[],
                                               text, text, jsonb, jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.command_fingerprint(uuid, uuid, text, integer,
                                                           text[], text, text, jsonb, jsonb)
       FROM PUBLIC;

-- Проверка 3. Полная сверка личности команды. Любое расхождение
-- прерывает всю транзакцию: «похоже» здесь не считается.
CREATE OR REPLACE FUNCTION bem_control.assert_command_identity(
    p_prev         bem_core.command_log,
    p_command_id   uuid,
    p_tenant_id    uuid,
    p_work_item_id uuid,
    p_fingerprint  text,
    p_actor_id     text,
    p_has_outbox   boolean,
    p_outbox_kind  text)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    -- Отпечаток версии 1 сравнивать нельзя: та кодировка допускала
    -- коллизии, поэтому совпадение сумм ничего не доказывает
    -- (замечание M-H18-R8-01). Такая строка закрывает повтор отказом.
    IF p_prev.fingerprint_version IS DISTINCT FROM 2 THEN
        RAISE EXCEPTION
          'COMMAND_FINGERPRINT_VERSION_LEGACY: команда % записана отпечатком версии %;'
          ' доказать повтор старой кодировкой нельзя',
          p_prev.command_id, p_prev.fingerprint_version;
    END IF;

    IF p_prev.command_id     IS DISTINCT FROM p_command_id
    OR p_prev.tenant_id      IS DISTINCT FROM p_tenant_id
    OR p_prev.work_item_id   IS DISTINCT FROM p_work_item_id
    OR p_prev.payload_sha256 IS DISTINCT FROM p_fingerprint
    OR p_prev.actor_id       IS DISTINCT FROM p_actor_id
    OR p_prev.has_outbox     IS DISTINCT FROM p_has_outbox
    OR p_prev.kind           IS DISTINCT FROM p_outbox_kind THEN
        RAISE EXCEPTION
          'COMMAND_ID_REUSED_WITH_DIFFERENT_PAYLOAD: %', p_command_id;
    END IF;
END;
$$;

ALTER FUNCTION bem_control.assert_command_identity(bem_core.command_log, uuid, uuid,
                                                   uuid, text, text, boolean, text)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.assert_command_identity(bem_core.command_log,
                            uuid, uuid, uuid, text, text, boolean, text) FROM PUBLIC;

-- Проверка 4. Единый порядок блокировок: сначала строка предмета,
-- потом всё остальное. Функция возвращает заблокированную строку,
-- поэтому вызывающий не может «забыть» взять блокировку.
CREATE OR REPLACE FUNCTION bem_control.lock_subject(
    p_tenant_id  uuid,
    p_subject_id uuid)
RETURNS bem_core.subject
LANGUAGE plpgsql
SET search_path = bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_row bem_core.subject;
BEGIN
    SELECT * INTO v_row
      FROM bem_core.subject s
     WHERE s.id = p_subject_id AND s.tenant_id = p_tenant_id
       FOR UPDATE;              -- вторая транзакция ждёт здесь, а не гонится
    RETURN v_row;               -- NULL-строка означает «предмета нет»
END;
$$;

ALTER FUNCTION bem_control.lock_subject(uuid, uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.lock_subject(uuid, uuid) FROM PUBLIC;

CREATE OR REPLACE FUNCTION bem_control.create_work_item(
    p_tenant_id    uuid,
    p_work_item_id uuid,
    p_status       text,
    p_criticality  text,
    p_evidence     jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor  text;   -- выводится из контекста, не из настройки
    v_rows   integer;
    v_tenant uuid;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);   -- граница заказчика, C-H17-R7-04
    SELECT out_actor_id INTO v_actor
      FROM bem_control.current_actor_checked(p_tenant_id);
    IF p_criticality NOT IN ('CRITICAL', 'NORMAL') THEN
        RAISE EXCEPTION 'BAD_CRITICALITY: %', p_criticality;
    END IF;

    INSERT INTO bem_core.work_item (id, tenant_id, status, revision, criticality)
    VALUES (p_work_item_id, p_tenant_id, p_status, 1, p_criticality)
    ON CONFLICT (id) DO NOTHING;
    GET DIAGNOSTICS v_rows = ROW_COUNT;

    IF v_rows = 0 THEN
        -- работа с таким идентификатором уже есть: повтор допустим,
        -- но только внутри того же заказчика
        SELECT w.tenant_id INTO v_tenant
          FROM bem_core.work_item w WHERE w.id = p_work_item_id;
        IF v_tenant IS DISTINCT FROM p_tenant_id THEN
            RAISE EXCEPTION 'WORK_ITEM_BELONGS_TO_OTHER_TENANT: %', p_work_item_id;
        END IF;
        RETURN p_work_item_id;
    END IF;

    PERFORM bem_control.evidence_write(p_tenant_id, 'WORK_ITEM_CREATED',
                                       COALESCE(p_evidence, '{}'::jsonb)
                                       || jsonb_build_object('work_item_id', p_work_item_id,
                                       'status', p_status,
                                       'criticality', p_criticality));

    RETURN p_work_item_id;
END;
$$;

ALTER FUNCTION bem_control.create_work_item(uuid, uuid, text, text, jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.create_work_item(uuid, uuid, text, text, jsonb)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.create_work_item(uuid, uuid, text, text, jsonb)
       TO bem_kernel_rw;

-- Первый заказчик и его первый администратор. H1.8 обещал такую
-- возможность в тексте, но функции не было ни одной, а
-- set_tenant_membership требует уже существующего администратора —
-- то есть первого администратора создать было нечем
-- (замечание M-H18-R8-07).
-- Здесь нет вызова assert_tenant: заказчика ещё не существует,
-- и контекста у него быть не может. Право даёт полномочие на весь
-- кластер, а не членство.
CREATE OR REPLACE FUNCTION bem_control.create_tenant(
    p_tenant_id      uuid,
    p_name           text,
    p_admin_actor_id text,
    p_admin_user_id  uuid,
    p_evidence       jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor  text;
    v_user   uuid;
    v_active boolean;
    v_id     uuid := coalesce(p_tenant_id, gen_random_uuid());
BEGIN
    v_actor := bem_control.assert_authority('TENANT_PROVISIONER', NULL);

    IF p_name IS NULL OR btrim(p_name) = '' THEN
        RAISE EXCEPTION 'TENANT_NAME_REQUIRED';
    END IF;
    IF p_admin_user_id IS NULL THEN
        RAISE EXCEPTION 'TENANT_ADMIN_USER_REQUIRED';
    END IF;

    SELECT a.is_active, a.user_id INTO v_active, v_user
      FROM bem_core.actor a
     WHERE a.actor_id = p_admin_actor_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'UNKNOWN_ACTOR: %', p_admin_actor_id;
    END IF;
    IF NOT v_active THEN
        RAISE EXCEPTION 'INACTIVE_ACTOR: %', p_admin_actor_id;
    END IF;
    IF v_user IS DISTINCT FROM p_admin_user_id THEN
        RAISE EXCEPTION
          'TENANT_ADMIN_USER_MISMATCH: у участника % учётная запись %, передана %',
          p_admin_actor_id, v_user, p_admin_user_id;
    END IF;

    -- Заказчик и его первый администратор появляются одной транзакцией
    -- или не появляются вовсе.
    INSERT INTO bem_core.tenant (id, name) VALUES (v_id, p_name);

    INSERT INTO bem_core.user_tenant_membership
           (id, user_id, tenant_id, role, granted_by, granted_at)
    VALUES (gen_random_uuid(), p_admin_user_id, v_id, 'tenant_admin', v_actor, now());

    -- Доказательство о заведении заказчика принадлежит служебному
    -- заказчику, а не новому. Причина не вкусовая: в момент записи
    -- нового заказчика нет ни в чьём контексте сессии, а при вызове с
    -- пустым номером его номер рождается внутри этой функции — и
    -- вызывающий не мог бы заранее установить контекст на то, чего не
    -- знал. В H1.10 эта ветка откатывалась всегда (замечание
    -- C-H110-R10-01). Номер нового заказчика записан в самом
    -- доказательстве, поэтому найти его по нему можно.
    PERFORM bem_control.evidence_write(bem_control.service_tenant(), 'TENANT_CREATED',
                                       coalesce(p_evidence, '{}'::jsonb)
                                       || jsonb_build_object('tenant_id',          v_id,
                                       'name',               p_name,
                                       'first_admin_actor',  p_admin_actor_id,
                                       'first_admin_user',   p_admin_user_id));

    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.create_tenant(uuid, text, text, uuid, jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.create_tenant(uuid, text, text, uuid, jsonb)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.create_tenant(uuid, text, text, uuid, jsonb)
       TO bem_governance;

-- Функция 25. Завести участника.
--
-- Это и есть недостающее звено чистой установки. Участник со связью
-- db_role отвечает за себя сам; участник без связи работает только по
-- доверенности и полномочия получить не может.
CREATE OR REPLACE FUNCTION bem_control.create_actor(
    p_actor_id text,
    p_provider bem_core.provider,
    p_user_id  uuid,
    p_db_role  name)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_by      text;
    v_service uuid := bem_control.service_tenant();
BEGIN
    v_by := bem_control.assert_authority('OPERATOR', NULL);

    IF p_actor_id IS NULL OR btrim(p_actor_id) = '' THEN
        RAISE EXCEPTION 'ACTOR_ID_REQUIRED';
    END IF;

    -- Роль входа обязана существовать в кластере. Связь с несуществующей
    -- ролью выглядела бы как связанная личность, но BOUND никогда бы не
    -- дала: session_user такого имени не бывает.
    IF p_db_role IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = p_db_role) THEN
        RAISE EXCEPTION 'ACTOR_DB_ROLE_UNKNOWN: роли % в кластере нет', p_db_role;
    END IF;

    INSERT INTO bem_core.actor (actor_id, provider, user_id, is_active, db_role)
    VALUES (p_actor_id, p_provider, p_user_id, true, p_db_role);

    PERFORM bem_control.evidence_write(v_service, 'ACTOR_CREATED',
            jsonb_build_object('actor_id', p_actor_id,
                               'provider', p_provider,
                               'user_id',  p_user_id,
                               'db_role',  p_db_role,
                               'created_by', v_by));

    RETURN p_actor_id;
END;
$$;

ALTER FUNCTION bem_control.create_actor(text, bem_core.provider, uuid, name)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.create_actor(text, bem_core.provider, uuid, name)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.create_actor(text, bem_core.provider, uuid, name)
       TO bem_governance;

-- Функция 26. Выдать полномочие.
CREATE OR REPLACE FUNCTION bem_control.grant_authority(
    p_actor_id  text,
    p_authority text,
    p_tenant_id uuid)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_by      text;
    v_role    name;
    v_active  boolean;
    v_id      uuid := gen_random_uuid();
    v_service uuid;
    v_guard   bigint;
BEGIN
    -- Барьер стоит ПЕРВЫМ, до чтения любой пользовательской таблицы.
    -- Выдача и отзыв проходят через один и тот же барьер: иначе
    -- «выдали одного, отозвали другого» разошлось бы так, что проверка
    -- последнего оператора верна у обеих сессий и неверна по факту
    -- (замечания M-H110-R10-04 и M-H111-R11-01).
    IF p_authority = 'OPERATOR' AND p_tenant_id IS NULL THEN
        v_guard := bem_control.authority_barrier('cluster_operator');
    END IF;

    v_service := bem_control.service_tenant();
    v_by      := bem_control.assert_authority('OPERATOR', NULL);

    SELECT a.db_role, a.is_active INTO v_role, v_active
      FROM bem_core.actor a WHERE a.actor_id = p_actor_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'UNKNOWN_ACTOR: %', p_actor_id;
    END IF;
    IF NOT v_active THEN
        RAISE EXCEPTION 'INACTIVE_ACTOR: %', p_actor_id;
    END IF;

    -- Полномочие даётся только связанной личности. Это то же правило,
    -- что проверяет assert_authority при использовании; здесь оно
    -- стоит на выдаче, чтобы бесполезных строк не появлялось вовсе.
    IF v_role IS NULL THEN
        RAISE EXCEPTION
          'AUTHORITY_REQUIRES_BOUND_IDENTITY: у участника % нет своей роли входа',
          p_actor_id;
    END IF;

    IF EXISTS (SELECT 1 FROM bem_core.actor_authority aa
                WHERE aa.actor_id   = p_actor_id
                  AND aa.authority  = p_authority
                  AND aa.tenant_id  IS NOT DISTINCT FROM p_tenant_id
                  AND aa.revoked_at IS NULL) THEN
        RAISE EXCEPTION 'AUTHORITY_ALREADY_GRANTED: % уже есть у %', p_authority, p_actor_id;
    END IF;

    INSERT INTO bem_core.actor_authority (id, tenant_id, actor_id, authority, granted_by)
    VALUES (v_id, p_tenant_id, p_actor_id, p_authority, v_by);

    PERFORM bem_control.evidence_write(coalesce(p_tenant_id, v_service), 'AUTHORITY_GRANTED',
            jsonb_build_object('authority', p_authority,
                               'actor_id',  p_actor_id,
                               'tenant_id', p_tenant_id,
                               'isolation', current_setting('transaction_isolation'),
                               'guard_revision', v_guard,
                               'granted_by', v_by));

    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.grant_authority(text, text, uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.grant_authority(text, text, uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.grant_authority(text, text, uuid) TO bem_governance;

-- Функция 27. Отозвать полномочие.
--
-- Последнее живое полномочие OPERATOR на весь кластер отозвать нельзя:
-- иначе установка теряет управление навсегда, а вернуть его можно было
-- бы только суперпользователем в обход всех проверок.
CREATE OR REPLACE FUNCTION bem_control.revoke_authority(
    p_actor_id  text,
    p_authority text,
    p_tenant_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_by      text;
    v_left    integer;
    v_rows    integer;
    v_service uuid;
    v_guard   bigint;
BEGIN
    -- Барьер стоит ПЕРВЫМ действием функции, до assert_authority() и до
    -- любого чтения пользовательских таблиц. H1.11 ставила очередь
    -- после проверки прав, поэтому снимок данных оказывался старше
    -- очереди и при REPEATABLE READ вторая сессия считала операторов по
    -- устаревшим строкам (замечание M-H111-R11-01).
    IF p_authority = 'OPERATOR' AND p_tenant_id IS NULL THEN
        v_guard := bem_control.authority_barrier('cluster_operator');
    END IF;

    v_service := bem_control.service_tenant();
    v_by      := bem_control.assert_authority('OPERATOR', NULL);

    IF p_authority = 'OPERATOR' AND p_tenant_id IS NULL THEN
        -- Подсчёт идёт ПОСЛЕ барьера. На READ COMMITTED этот запрос
        -- берёт свежий снимок и видит чужой отзыв; на REPEATABLE READ и
        -- SERIALIZABLE сессия сюда не доходит — барьер уже ответил
        -- 40001. Проверки K-R11-01…K-R11-06.
        SELECT count(*) INTO v_left
          FROM bem_core.actor_authority aa
          JOIN bem_core.actor a ON a.actor_id = aa.actor_id
         WHERE aa.authority  = 'OPERATOR'
           AND aa.tenant_id  IS NULL
           AND aa.revoked_at IS NULL
           AND a.is_active
           AND a.db_role IS NOT NULL
           AND aa.actor_id <> p_actor_id;

        IF v_left = 0 THEN
            RAISE EXCEPTION
              'LAST_OPERATOR_AUTHORITY: у % последнее полномочие OPERATOR на кластер;'
              ' сначала выдайте OPERATOR другому связанному участнику', p_actor_id;
        END IF;
    END IF;

    UPDATE bem_core.actor_authority
       SET revoked_at = now()
     WHERE actor_id   = p_actor_id
       AND authority  = p_authority
       AND tenant_id  IS NOT DISTINCT FROM p_tenant_id
       AND revoked_at IS NULL;
    GET DIAGNOSTICS v_rows = ROW_COUNT;

    IF v_rows = 0 THEN
        RETURN false;                 -- отзывать нечего, и это не ошибка
    END IF;

    PERFORM bem_control.evidence_write(coalesce(p_tenant_id, v_service), 'AUTHORITY_REVOKED',
            jsonb_build_object('authority', p_authority,
                               'actor_id',  p_actor_id,
                               'tenant_id', p_tenant_id,
                               'isolation', current_setting('transaction_isolation'),
                               'guard_revision', v_guard,
                               'revoked_by', v_by));

    RETURN true;
END;
$$;

ALTER FUNCTION bem_control.revoke_authority(text, text, uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.revoke_authority(text, text, uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.revoke_authority(text, text, uuid) TO bem_governance;

-- Функция 28. Выдать доверенность: роль входа вправе говорить за
-- участника. Это и есть основание режима DELEGATED.
CREATE OR REPLACE FUNCTION bem_control.grant_delegation(
    p_principal_role name,
    p_actor_id       text,
    p_reason         text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_by      text;
    v_bound   name;
    v_id      uuid := gen_random_uuid();
    v_service uuid := bem_control.service_tenant();
BEGIN
    v_by := bem_control.assert_authority('OPERATOR', NULL);

    IF NOT EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = p_principal_role) THEN
        RAISE EXCEPTION 'DELEGATION_ROLE_UNKNOWN: роли % в кластере нет', p_principal_role;
    END IF;

    SELECT a.db_role INTO v_bound
      FROM bem_core.actor a WHERE a.actor_id = p_actor_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'UNKNOWN_ACTOR: %', p_actor_id;
    END IF;

    -- Участнику со своей ролью входа доверенность не нужна и вредна:
    -- она открыла бы второй путь говорить за того, кто отвечает сам.
    IF v_bound IS NOT NULL THEN
        RAISE EXCEPTION
          'DELEGATION_FOR_BOUND_ACTOR: участник % входит сам ролью %',
          p_actor_id, v_bound;
    END IF;

    INSERT INTO bem_core.actor_delegation
           (id, principal_role, actor_id, granted_by, reason)
    VALUES (v_id, p_principal_role, p_actor_id, v_by, p_reason);

    PERFORM bem_control.evidence_write(v_service, 'DELEGATION_GRANTED',
            jsonb_build_object('delegation_id',  v_id,
                               'principal_role', p_principal_role,
                               'actor_id',       p_actor_id,
                               'reason',         p_reason,
                               'granted_by',     v_by));

    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.grant_delegation(name, text, text) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.grant_delegation(name, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.grant_delegation(name, text, text) TO bem_governance;

-- Функция 29. Отозвать доверенность. Прежние доказательства на неё
-- по-прежнему ссылаются: строка остаётся, гаснет только её действие.
CREATE OR REPLACE FUNCTION bem_control.revoke_delegation(p_delegation_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_by      text;
    v_rows    integer;
    v_service uuid := bem_control.service_tenant();
BEGIN
    v_by := bem_control.assert_authority('OPERATOR', NULL);

    UPDATE bem_core.actor_delegation
       SET revoked_at = now(), revoked_by = v_by
     WHERE id         = p_delegation_id
       AND revoked_at IS NULL;
    GET DIAGNOSTICS v_rows = ROW_COUNT;

    IF v_rows = 0 THEN
        RETURN false;
    END IF;

    PERFORM bem_control.evidence_write(v_service, 'DELEGATION_REVOKED',
            jsonb_build_object('delegation_id', p_delegation_id,
                               'revoked_by',    v_by));

    RETURN true;
END;
$$;

ALTER FUNCTION bem_control.revoke_delegation(uuid) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.revoke_delegation(uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.revoke_delegation(uuid) TO bem_governance;

CREATE OR REPLACE FUNCTION bem_control.set_tenant_membership(
    p_target_user_id uuid,
    p_tenant_id      uuid,
    p_role           text,
    p_revoke         boolean)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_temp
AS $$
DECLARE
    v_actor  text;
    v_mode   text;
    v_admin  boolean;
    v_id     uuid;
BEGIN
    -- Граница заказчика — первой строкой, до любого чтения.
    -- H1.8 её здесь не вызывал: администратор заказчика B менял B
    -- из контекста A, и BYPASSRLS владельца функции это не ловил
    -- (замечание C-H18-R8-01).
    PERFORM bem_control.assert_tenant(p_tenant_id);

    SELECT out_actor_id, out_identity_mode INTO v_actor, v_mode
      FROM bem_control.current_actor_checked(p_tenant_id);

    IF p_role NOT IN ('tenant_admin', 'member', 'viewer') THEN
        RAISE EXCEPTION 'INVALID_ROLE';
    END IF;

    SELECT EXISTS (
        SELECT 1
          FROM bem_core.user_tenant_membership m
          JOIN bem_core.actor a ON a.actor_id = v_actor
         WHERE m.user_id    = a.user_id
           AND m.tenant_id  = p_tenant_id
           AND m.role       = 'tenant_admin'
           AND m.revoked_at IS NULL)
      INTO v_admin;

    IF NOT v_admin THEN
        RAISE EXCEPTION 'NOT_TENANT_ADMIN';
    END IF;

    IF p_revoke THEN
        UPDATE bem_core.user_tenant_membership
           SET revoked_at = now(), revoked_by = v_actor
         WHERE user_id = p_target_user_id
           AND tenant_id = p_tenant_id
           AND revoked_at IS NULL
        RETURNING id INTO v_id;
    ELSE
        INSERT INTO bem_core.user_tenant_membership
               (id, user_id, tenant_id, role, granted_by, granted_at)
        VALUES (gen_random_uuid(), p_target_user_id, p_tenant_id, p_role, v_actor, now())
        ON CONFLICT (user_id, tenant_id) WHERE revoked_at IS NULL DO NOTHING
        RETURNING id INTO v_id;
    END IF;

    IF v_id IS NULL THEN
        RAISE EXCEPTION 'MEMBERSHIP_NO_CHANGE';
    END IF;

    -- Evidence пишется той же функцией в той же транзакции
    PERFORM bem_control.evidence_write(p_tenant_id, 'MEMBERSHIP_CHANGE',
                                       jsonb_build_object('target', p_target_user_id,
                                       'role', p_role,
                                       'revoke', p_revoke,
                                       'membership_id', v_id));

    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.set_tenant_membership(uuid, uuid, text, boolean)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.set_tenant_membership(uuid, uuid, text, boolean)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.set_tenant_membership(uuid, uuid, text, boolean)
       TO bem_kernel_rw;

-- Предел попыток объявлен один раз и используется всеми: захватом,
-- фиксацией результата, ручным переводом в тупик и реестром тестов.
-- H1.8 держал его константой внутри одной функции, и остальные места
-- расходились с ней (замечание C-H18-R8-03).
CREATE OR REPLACE FUNCTION bem_control.outbox_retry_limit()
RETURNS integer
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog, pg_temp
AS $$ SELECT 5 $$;

ALTER FUNCTION bem_control.outbox_retry_limit() OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.outbox_retry_limit() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.outbox_retry_limit() TO bem_kernel_rw;

CREATE OR REPLACE FUNCTION bem_control.claim_outbox_batch(
    p_limit  integer,
    p_lease  interval,
    p_worker text)
RETURNS TABLE (outbox_id uuid, tenant_id uuid, work_item_id uuid,
               kind text, lease_epoch bigint)
LANGUAGE sql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_temp
AS $$
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
$$;

ALTER FUNCTION bem_control.claim_outbox_batch(integer, interval, text)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.claim_outbox_batch(integer, interval, text)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.claim_outbox_batch(integer, interval, text)
       TO bem_kernel_rw;

CREATE OR REPLACE FUNCTION bem_control.finish_outbox_row(
    p_outbox_id   uuid,
    p_lease_epoch bigint,
    p_worker      text,
    p_outcome     text,   -- SENT | FAILED | UNKNOWN_OUTCOME
    p_detail      jsonb)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_temp
AS $$
DECLARE
    v_attempt integer;
    v_new     text;
    v_wait    interval;
    v_tenant  uuid;
    v_kind    text;
BEGIN
    IF p_outcome NOT IN ('SENT', 'FAILED', 'UNKNOWN_OUTCOME') THEN
        RAISE EXCEPTION 'INVALID_OUTCOME';
    END IF;

    -- Строку берём под замок и вместе с числом уже сделанных попыток:
    -- по нему решается, пора ли в тупик. H1.8 ставил FAILED и больше
    -- строку не захватывал, поэтому порог не достигался никогда
    -- (замечание C-H18-R8-03).
    SELECT o.attempt_count, o.tenant_id, o.kind
      INTO v_attempt, v_tenant, v_kind
      FROM bem_core.outbox o
     WHERE o.id          = p_outbox_id
       AND o.lease_epoch = p_lease_epoch
       AND o.leased_by   = p_worker
       AND o.status      = 'LEASED'
       FOR UPDATE;

    IF NOT FOUND THEN
        -- аренда уже перехвачена или номер поколения другой:
        -- устаревший работник ничего не меняет и молчит
        RETURN false;
    END IF;

    v_new := CASE
                WHEN p_outcome = 'SENT'            THEN 'SENT'
                WHEN p_outcome = 'UNKNOWN_OUTCOME' THEN 'UNKNOWN_OUTCOME'
                WHEN v_attempt >= bem_control.outbox_retry_limit()
                                                   THEN 'DEAD_LETTER'
                ELSE 'FAILED'
             END;

    -- Выдержка удваивается: 30 секунд, минута, две, четыре, восемь;
    -- потолок — полчаса, чтобы очередь не засыпала насовсем.
    v_wait := least(interval '30 minutes',
                    make_interval(secs => 30 * power(2, greatest(v_attempt - 1, 0))));

    UPDATE bem_core.outbox o
       SET status          = v_new,
           result          = p_detail,
           leased_until    = NULL,
           leased_by       = NULL,
           finished_at     = CASE WHEN v_new IN ('SENT', 'DEAD_LETTER',
                                                 'UNKNOWN_OUTCOME')
                                  THEN clock_timestamp() END,
           next_attempt_at = CASE WHEN v_new = 'FAILED'
                                  THEN clock_timestamp() + v_wait
                                  ELSE o.next_attempt_at END,
           dead_lettered_at = CASE WHEN v_new = 'DEAD_LETTER'
                                   THEN clock_timestamp()
                                   ELSE o.dead_lettered_at END,
           dead_letter_reason = CASE WHEN v_new = 'DEAD_LETTER'
                                     THEN 'RETRY_LIMIT_REACHED'
                                     ELSE o.dead_letter_reason END
     WHERE o.id = p_outbox_id;

    -- Доказательство автоматического тупика. H1.9 обещала его текстом
    -- и строкой покрытия, но писала только отдельная ручная функция
    -- dead_letter_outbox_row, которую автоматический путь не зовёт
    -- (замечание M-H19-R9-02). Здесь запись идёт той же транзакцией:
    -- либо строка в тупике и доказательство есть, либо нет ни того,
    -- ни другого.
    --
    -- Ровно одно доказательство на строку. Повтор сюда не доходит:
    -- выборка выше требует статуса LEASED, а после тупика он другой,
    -- поэтому повторный вызов возвращает false ещё до UPDATE.
    IF v_new = 'DEAD_LETTER' THEN
        PERFORM bem_control.evidence_write(v_tenant, 'OUTBOX_DEAD_LETTER',
                jsonb_build_object('outbox_id', p_outbox_id,
                                   'kind',      v_kind,
                                   'attempts',  v_attempt,
                                   'reason',    'RETRY_LIMIT_REACHED',
                                   'automatic', true,
                                   'worker',    p_worker));
    END IF;

    RETURN true;
END;
$$;

ALTER FUNCTION bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)
       TO bem_kernel_rw;

CREATE OR REPLACE FUNCTION bem_control.apply_transition(
    p_tenant_id         uuid,
    p_work_item_id      uuid,
    p_expected_revision integer,
    p_allowed_from      text[],
    p_new_status        text,
    p_command_id        uuid,
    p_outbox_kind       text,
    p_outbox_payload    jsonb,
    p_evidence          jsonb)
RETURNS TABLE (work_item_id uuid, new_revision integer, outbox_id uuid)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor       text;   -- выводится из контекста, не из настройки
    v_rev         integer;
    v_rows        integer;
    v_outbox_id   uuid;
    v_cur_status  text;
    v_cur_rev     integer;
    v_hash        text;
    v_has_outbox  boolean := (p_outbox_kind IS NOT NULL);
    v_idem        text;
    v_prev        bem_core.command_log%ROWTYPE;
BEGIN
    -- Граница заказчика стоит первой во всех функциях без исключения:
    -- current_actor_checked сама читает членства, а любое чтение
    -- данных заказчика до assert_tenant — тот самый дефект, который
    -- закрывает проверка закрытого списка (замечание M-H19-R9-03).
    PERFORM bem_control.assert_tenant(p_tenant_id);   -- граница заказчика, C-H17-R7-04
    SELECT out_actor_id INTO v_actor
      FROM bem_control.current_actor_checked(p_tenant_id);

    -- вид действия и его содержимое приходят только вместе
    IF v_has_outbox AND p_outbox_payload IS NULL THEN
        RAISE EXCEPTION 'OUTBOX_KIND_WITHOUT_PAYLOAD';
    END IF;
    IF NOT v_has_outbox AND p_outbox_payload IS NOT NULL THEN
        RAISE EXCEPTION 'OUTBOX_PAYLOAD_WITHOUT_KIND';
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 1. Резерв команды ДО любого изменения состояния.
    --        Отпечаток считается по ВСЕМ значимым полям команды
    --        (замечание M-H17-R7-09), а личность сверяет одна и та же
    --        функция в обеих ветках (замечание C-H17-R7-07).
    ---------------------------------------------------------------
    v_hash := bem_control.command_fingerprint(
                  p_tenant_id, p_work_item_id, v_actor, p_expected_revision,
                  p_allowed_from, p_new_status, p_outbox_kind,
                  p_outbox_payload, p_evidence);

    SELECT * INTO v_prev
      FROM bem_core.command_log
     WHERE command_id = p_command_id;

    IF FOUND THEN
        PERFORM bem_control.assert_command_identity(
                    v_prev, p_command_id, p_tenant_id, p_work_item_id,
                    v_hash, v_actor, v_has_outbox, p_outbox_kind);
        RETURN QUERY SELECT v_prev.work_item_id, v_prev.result_revision, v_prev.outbox_id;
        RETURN;                       -- честный повтор: состояние не трогаем
    END IF;

    BEGIN
        INSERT INTO bem_core.command_log
               (command_id, tenant_id, work_item_id, kind, has_outbox,
                payload_sha256, actor_id, created_at)
        VALUES (p_command_id, p_tenant_id, p_work_item_id, p_outbox_kind, v_has_outbox,
                v_hash, v_actor, now());
    EXCEPTION WHEN unique_violation THEN
        -- параллельный вызов с тем же command_id успел зафиксироваться
        SELECT * INTO v_prev
          FROM bem_core.command_log
         WHERE command_id = p_command_id;
        PERFORM bem_control.assert_command_identity(
                    v_prev, p_command_id, p_tenant_id, p_work_item_id,
                    v_hash, v_actor, v_has_outbox, p_outbox_kind);
        RETURN QUERY SELECT v_prev.work_item_id, v_prev.result_revision, v_prev.outbox_id;
        RETURN;
    END;

    ---------------------------------------------------------------
    -- ШАГ 2. Переход состояния с проверкой ожидаемой версии
    ---------------------------------------------------------------
    UPDATE bem_core.work_item w
       SET status     = p_new_status,
           revision   = w.revision + 1,
           updated_at = now()
     WHERE w.id        = p_work_item_id
       AND w.tenant_id = p_tenant_id
       AND w.revision  = p_expected_revision
       AND w.status    = ANY(p_allowed_from)
    RETURNING w.revision INTO v_rev;
    GET DIAGNOSTICS v_rows = ROW_COUNT;

    IF v_rows <> 1 THEN
        SELECT w.status, w.revision INTO v_cur_status, v_cur_rev
          FROM bem_core.work_item w
         WHERE w.id = p_work_item_id AND w.tenant_id = p_tenant_id;

        IF v_cur_status IS NULL THEN
            RAISE EXCEPTION 'NOT_FOUND';
        ELSIF NOT (v_cur_status = ANY(p_allowed_from)) THEN
            RAISE EXCEPTION 'INVALID_TRANSITION: current=% allowed=%',
                  v_cur_status, p_allowed_from;
        ELSE
            RAISE EXCEPTION 'STALE_REVISION: current=% expected=%',
                  v_cur_rev, p_expected_revision;
        END IF;
        -- любая ветка возбуждает исключение и откатывает ВСЁ, включая резерв команды
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 3. Доказательство
    ---------------------------------------------------------------
    PERFORM bem_control.evidence_write(p_tenant_id, 'TRANSITION',
                                       p_evidence);

    ---------------------------------------------------------------
    -- ШАГ 4. Намерение внешнего действия
    ---------------------------------------------------------------
    IF v_has_outbox THEN
        -- Ключ повтора выводится из идентификатора команды: честный повтор
        -- даёт тот же ключ, другая команда — другой. Колонка теперь
        -- объявлена в таблице (замечание C-H17-R7-02).
        v_idem := encode(sha256(convert_to(p_command_id::text, 'UTF8')), 'hex');

        INSERT INTO bem_core.outbox
               (id, tenant_id, work_item_id, command_id, kind, payload,
                idempotency_key, status, lease_epoch, attempt_count, created_at)
        VALUES (gen_random_uuid(), p_tenant_id, p_work_item_id, p_command_id,
                p_outbox_kind, p_outbox_payload, v_idem,
                'PENDING', 0, 0, now())
        RETURNING id INTO v_outbox_id;
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 5. Итог команды и сигнал ТОЛЬКО при реальной вставке
    ---------------------------------------------------------------
    UPDATE bem_core.command_log
       SET result_revision = v_rev,
           outbox_id       = v_outbox_id
     WHERE command_id = p_command_id;

    IF v_outbox_id IS NOT NULL THEN
        PERFORM pg_notify('bem_outbox', '');
    END IF;

    RETURN QUERY SELECT p_work_item_id, v_rev, v_outbox_id;
END;
$$;

ALTER FUNCTION bem_control.apply_transition(uuid, uuid, integer, text[], text,
                                            uuid, text, jsonb, jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.apply_transition(uuid, uuid, integer, text[], text,
                                                        uuid, text, jsonb, jsonb)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.apply_transition(uuid, uuid, integer, text[], text,
                                                        uuid, text, jsonb, jsonb)
       TO bem_kernel_rw;

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
    IF p_scope NOT IN ('WORKING', 'BEM954_PROTOCOL') THEN
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

CREATE OR REPLACE FUNCTION bem_control.record_audit_verdict(
    p_tenant_id  uuid,
    p_subject_id uuid,
    p_head_sha   text,
    p_verdict    text,
    p_evidence   jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor       text;   -- выводится из контекста, не из настройки
    v_provider    bem_core.provider;
    v_subject     bem_core.subject;
    v_assigned    boolean;
    v_evidence_id uuid := gen_random_uuid();
    v_id          uuid := gen_random_uuid();
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);   -- граница заказчика, C-H17-R7-04
    SELECT out_actor_id INTO v_actor
      FROM bem_control.current_actor_checked(p_tenant_id);
    IF p_evidence IS NULL THEN RAISE EXCEPTION 'VERDICT_WITHOUT_EVIDENCE'; END IF;

    SELECT a.provider INTO v_provider
      FROM bem_core.actor a
     WHERE a.actor_id = v_actor AND a.is_active;
    IF v_provider IS NULL THEN
        RAISE EXCEPTION 'UNKNOWN_OR_INACTIVE_ACTOR: %', v_actor;
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 1. Тот же порядок блокировок, что и у публикации и выпуска:
    --        строка предмета берётся первой (C-H17-R7-06).
    ---------------------------------------------------------------
    v_subject := bem_control.lock_subject(p_tenant_id, p_subject_id);
    IF v_subject.id IS NULL THEN
        RAISE EXCEPTION 'SUBJECT_NOT_FOUND: %', p_subject_id;
    END IF;
    IF v_subject.published_at IS NULL THEN
        RAISE EXCEPTION 'SUBJECT_NOT_PUBLISHED: %', p_subject_id;
    END IF;
    IF v_subject.head_sha <> p_head_sha THEN
        -- вердикт по устаревшей версии не принимается: он не про то,
        -- что сейчас лежит в предмете
        RAISE EXCEPTION 'HEAD_MISMATCH: subject=% verdict=%',
              v_subject.head_sha, p_head_sha;
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 2. Проверяющий обязан быть назначен на этот предмет.
    --        H1.7 принимал вердикт любого активного не-автора
    --        (замечание C-H17-R7-05).
    ---------------------------------------------------------------
    SELECT true INTO v_assigned
      FROM bem_core.audit_assignment g
     WHERE g.subject_id    = p_subject_id
       AND g.tenant_id     = p_tenant_id
       AND g.auditor_actor = v_actor
       AND g.revoked_at IS NULL;
    IF v_assigned IS NULL THEN
        RAISE EXCEPTION 'AUDITOR_NOT_ASSIGNED: % subject=%', v_actor, p_subject_id;
    END IF;

    ---------------------------------------------------------------
    -- ШАГ 3. Доказательство пишется первым: вердикт без него не примет
    --        ни ограничение NOT NULL, ни внешний ключ.
    ---------------------------------------------------------------
    SELECT bem_control.evidence_write(p_tenant_id, 'AUDIT_EVIDENCE',
                                      p_evidence)
      INTO v_evidence_id;

    -- самопроверку и несовпадение версии отклонят триггеры таблицы
    INSERT INTO bem_core.audit_record
           (id, tenant_id, subject_id, head_sha,
            auditor_actor, auditor_provider, verdict, evidence_id)
    VALUES (v_id, p_tenant_id, p_subject_id, p_head_sha,
            v_actor, v_provider, p_verdict::bem_core.audit_verdict, v_evidence_id);

    ---------------------------------------------------------------
    -- ШАГ 4. Вердикт, пришедший ПОСЛЕ выпуска этой же версии.
    --        Поведение названо прямо, а не оставлено на удачу
    --        (замечание C-H17-R7-06).
    --        Запись вердикта не отменяет уже сделанный выпуск:
    --        журнал аудита только дополняется. Но отрицательный
    --        вердикт открывает разногласие и оставляет отдельное
    --        доказательство — решение об отзыве принимает оператор.
    ---------------------------------------------------------------
    IF v_subject.released_at IS NOT NULL
       AND p_verdict::bem_core.audit_verdict <> 'ACCEPT' THEN
        UPDATE bem_core.subject
           SET disagreement_at     = now(),
               disagreement_reason = v_actor || '=' || p_verdict || ' (после выпуска)'
         WHERE id = p_subject_id AND tenant_id = p_tenant_id;

        PERFORM bem_control.evidence_write(p_tenant_id, 'DISAGREEMENT_AFTER_RELEASE',
                                           jsonb_build_object('subject_id',  p_subject_id,
                                           'head_sha',    p_head_sha,
                                           'verdict',     p_verdict,
                                           'released_at', v_subject.released_at,
                                           'note', 'выпуск не отменён автоматически; решение оператора'));
    END IF;

    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)
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
    IF v_subject.scope = 'BEM954_PROTOCOL' THEN
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

CREATE OR REPLACE FUNCTION bem_control.schema_digest(p_table regclass)
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT encode(sha256(convert_to(
             coalesce(string_agg(line, E'\n' ORDER BY line), ''), 'UTF8')), 'hex')
      FROM (
        SELECT concat_ws('|', 'v2', 'table',
                         c.relkind::text,
                         c.relpersistence::text,
                         c.relrowsecurity::text,
                         c.relforcerowsecurity::text,
                         pg_get_userbyid(c.relowner),
                         coalesce((SELECT string_agg(x::text, ',' ORDER BY x::text)
                                     FROM unnest(c.relacl) x), '-')) AS line
          FROM pg_class c
         WHERE c.oid = p_table
        UNION ALL
        SELECT concat_ws('|', 'v2', 'column',
                         a.attnum::text,
                         a.attname,
                         format_type(a.atttypid, a.atttypmod),
                         a.attnotnull::text,
                         coalesce(cl.collname, '-'),
                         coalesce(pg_get_expr(d.adbin, d.adrelid), '-'),
                         coalesce((SELECT string_agg(x::text, ',' ORDER BY x::text)
                                     FROM unnest(a.attacl) x), '-'))
          FROM pg_attribute a
          LEFT JOIN pg_collation cl ON cl.oid = a.attcollation
          LEFT JOIN pg_attrdef   d  ON d.adrelid = a.attrelid AND d.adnum = a.attnum
         WHERE a.attrelid = p_table AND a.attnum > 0 AND NOT a.attisdropped
        UNION ALL
        SELECT concat_ws('|', 'v2', 'constraint',
                         con.conname, pg_get_constraintdef(con.oid))
          FROM pg_constraint con
         WHERE con.conrelid = p_table
        UNION ALL
        SELECT concat_ws('|', 'v2', 'index',
                         ci.relname, pg_get_indexdef(i.indexrelid))
          FROM pg_index i JOIN pg_class ci ON ci.oid = i.indexrelid
         WHERE i.indrelid = p_table
        UNION ALL
        SELECT concat_ws('|', 'v2', 'policy',
                         pol.policyname, pol.permissive, pol.cmd,
                         coalesce(array_to_string(pol.roles, ','), '-'),
                         coalesce(pol.qual, '-'), coalesce(pol.with_check, '-'))
          FROM pg_policies pol
         -- H1.23, дефект D8 живого прогона R42: прежнее условие
         -- format(...)::regclass планировщик применял к каждой строке
         -- pg_class, включая pg_toast, куда у владельца функции нет входа,
         -- и свёртка падала у любой роли. Сравнение по имени схемы и таблицы.
         WHERE (pol.schemaname, pol.tablename) =
               (SELECT sn.nspname, sc.relname
                  FROM pg_class sc JOIN pg_namespace sn ON sn.oid = sc.relnamespace
                 WHERE sc.oid = p_table)
        UNION ALL
        -- Внутренние триггеры принадлежат ограничениям и уже учтены
        -- строками группы constraint; здесь только объявленные схемой.
        SELECT concat_ws('|', 'v2', 'trigger',
                         tg.tgname, tg.tgenabled::text, pg_get_triggerdef(tg.oid))
          FROM pg_trigger tg
         WHERE tg.tgrelid = p_table AND NOT tg.tgisinternal
      ) s(line);
$$;

ALTER FUNCTION bem_control.schema_digest(regclass) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.schema_digest(regclass) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.schema_digest(regclass)
       TO bem_kernel_rw, bem_backup_admin;

CREATE OR REPLACE FUNCTION bem_control.data_digest(p_table regclass)
RETURNS text
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
SET TimeZone           = 'UTC'
SET DateStyle          = 'ISO, YMD'
SET extra_float_digits = 3
SET bytea_output       = 'hex'
AS $$
DECLARE
    v_result text;
BEGIN
    EXECUTE format($q$
        SELECT encode(sha256(convert_to(
                 coalesce(string_agg(row_text, E'\n' ORDER BY row_text), ''), 'UTF8')), 'hex')
          FROM (SELECT jsonb_build_object(
                         'digest_schema', 2,
                         'table', %L,
                         'row',   to_jsonb(t.*))::text AS row_text
                  FROM %s t) s $q$, p_table::text, p_table::text)
      INTO v_result;

    RETURN v_result;
END;
$$;

ALTER FUNCTION bem_control.data_digest(regclass) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.data_digest(regclass) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.data_digest(regclass)
       TO bem_kernel_rw, bem_backup_admin;

CREATE OR REPLACE FUNCTION bem_control.database_digest()
RETURNS TABLE (table_name text, shape_sha256 text, data_sha256 text)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = bem_control, pg_catalog, pg_temp
AS $$
DECLARE
    r record;
BEGIN
    -- 'r' — обычная таблица, 'p' — секционированная. Вторую H1.8
    -- пропускал (замечание M-H18-R8-06).
    FOR r IN
        SELECT c.oid::regclass AS t
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname IN ('bem_core', 'bem_engine', 'bem_control')
           AND c.relkind IN ('r', 'p')
         ORDER BY n.nspname, c.relname
    LOOP
        table_name   := r.t::text;
        shape_sha256 := bem_control.schema_digest(r.t);
        data_sha256  := bem_control.data_digest(r.t);
        RETURN NEXT;
    END LOOP;

    -- Права на сами схемы и правила по умолчанию для будущих объектов.
    FOR r IN
        SELECT n.nspname AS s
          FROM pg_namespace n
         WHERE n.nspname IN ('bem_core', 'bem_engine', 'bem_control')
         ORDER BY n.nspname
    LOOP
        SELECT encode(sha256(convert_to(
                 coalesce(string_agg(line, E'\n' ORDER BY line), ''), 'UTF8')), 'hex')
          INTO shape_sha256
          FROM (
            SELECT concat_ws('|', 'v3', 'schema',
                             n.nspname,
                             pg_get_userbyid(n.nspowner),
                             coalesce((SELECT string_agg(a, ',' ORDER BY a)
                                         FROM (SELECT concat_ws(':',
                                                        CASE WHEN e.grantee = 0 THEN 'PUBLIC'
                                                             ELSE pg_get_userbyid(e.grantee) END,
                                                        e.privilege_type,
                                                        CASE WHEN e.is_grantable THEN 'grant' ELSE '-' END,
                                                        pg_get_userbyid(e.grantor)) AS a
                                                 FROM aclexplode(n.nspacl) e
                                                -- H1.24, M-R43-01 (аудит R43): из свёртки убирается
                                                -- ровно одно право: USAGE роли restore_verifier на
                                                -- bem_control без права передачи, которое выдаёт файл
                                                -- 03 после восстановления. Любое другое право этой роли
                                                -- на любую из трёх схем (CREATE, USAGE с правом
                                                -- передачи, вход в bem_core или bem_engine) остаётся в
                                                -- свёртке. H1.23 (D9) отбрасывал всю запись роли целиком.
                                                -- H1.25, L-R44-01 (аудит R44): убирается только запись,
                                                -- выданная владельцем схемы. То же USAGE от другой роли
                                                -- переживает REVOKE владельца и потому остаётся в свёртке.
                                                WHERE NOT (n.nspname = 'bem_control'
                                                           AND e.grantee <> 0
                                                           AND pg_get_userbyid(e.grantee) = 'restore_verifier'
                                                           AND e.privilege_type = 'USAGE'
                                                           AND NOT e.is_grantable
                                                           AND e.grantor = n.nspowner)) z), '-')) AS line
              FROM pg_namespace n
             WHERE n.nspname = r.s
            UNION ALL
            SELECT concat_ws('|', 'v2', 'default_acl',
                             pg_get_userbyid(d.defaclrole),
                             d.defaclobjtype::text,
                             coalesce((SELECT string_agg(x::text, ',' ORDER BY x::text)
                                         FROM unnest(d.defaclacl) x), '-'))
              FROM pg_default_acl d
              JOIN pg_namespace n2 ON n2.oid = d.defaclnamespace
             WHERE n2.nspname = r.s
          ) q(line);

        table_name  := 'schema:' || r.s;
        data_sha256 := NULL;
        RETURN NEXT;
    END LOOP;
END;
$$;

ALTER FUNCTION bem_control.database_digest() OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.database_digest() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.database_digest()
       TO bem_kernel_rw, bem_backup_admin;

CREATE OR REPLACE FUNCTION bem_control.record_backup_evidence(p_payload jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_id      uuid := gen_random_uuid();
    v_service uuid := bem_control.service_tenant();
    v_key     text;
    v_session text := session_user;      -- кто подключился на самом деле
    v_system  text;                      -- кем его признал способ входа
    v_owner   text := current_user;      -- чьими правами работает функция
BEGIN
    IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'BACKUP_EVIDENCE_MUST_BE_OBJECT';
    END IF;

    -- H1.7 записывал current_user и получал имя ВЛАДЕЛЬЦА функции, а не
    -- того, кто её вызвал: у SECURITY DEFINER current_user — это владелец
    -- (замечание M-H17-R7-16). Фактического вызывающего даёт session_user,
    -- а system_user говорит, каким способом он вошёл.
    -- system_user есть начиная с PostgreSQL 16 и возвращает пару
    -- «способ входа : предъявленная личность». При входе по доверию
    -- он пуст — это нормально, и подменять пустоту выдумкой нельзя.
    v_system := system_user;

    IF v_session <> 'bem_backup_admin' THEN
        RAISE EXCEPTION 'BACKUP_EVIDENCE_WRONG_CALLER: %', v_session;
    END IF;

    -- отказ при признаке секрета: доказательство копии не место для
    -- пароля, ключа или токена, и «почистить частично» здесь нельзя
    FOREACH v_key IN ARRAY ARRAY(SELECT jsonb_object_keys(p_payload))
    LOOP
        IF lower(v_key) ~ '(password|passwd|secret|token|api_key|private_key|cookie)' THEN
            RAISE EXCEPTION 'SECRET_IN_BACKUP_EVIDENCE: поле %', v_key;
        END IF;
    END LOOP;

    SELECT bem_control.evidence_write(v_service, 'BACKUP_WINDOW',
                                      p_payload || jsonb_build_object('session_user',    v_session,
                                      'system_user',     coalesce(v_system, '-'),
                                      'effective_owner', v_owner))
      INTO v_id;

    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.record_backup_evidence(jsonb) OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.record_backup_evidence(jsonb) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.record_backup_evidence(jsonb) TO bem_backup_admin;

CREATE OR REPLACE FUNCTION bem_control.assign_auditor(
    p_tenant_id  uuid,
    p_subject_id uuid,
    p_auditor    text,
    p_evidence   jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor    text;
    v_provider bem_core.provider;
    v_subject  bem_core.subject;
    v_id       uuid := gen_random_uuid();
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);

    -- Назначает не автор и не общая рабочая роль, а связанная личность
    -- с полномочием координатора. H1.8 проверял только «не сам себя»,
    -- поэтому автор спокойно назначал проверяющим коллегу своей линии
    -- (замечание C-H18-R8-04).
    v_actor := bem_control.assert_authority('AUDIT_COORDINATOR', p_tenant_id);

    v_subject := bem_control.lock_subject(p_tenant_id, p_subject_id);
    IF v_subject.id IS NULL THEN
        RAISE EXCEPTION 'SUBJECT_NOT_FOUND: %', p_subject_id;
    END IF;

    SELECT a.provider INTO v_provider
      FROM bem_core.actor a
     WHERE a.actor_id = p_auditor AND a.is_active;
    IF v_provider IS NULL THEN
        RAISE EXCEPTION 'UNKNOWN_OR_INACTIVE_ACTOR: %', p_auditor;
    END IF;

    -- назначающий не может назначить проверяющим самого себя:
    -- иначе сторона приводит «своего» проверяющего сама
    IF p_auditor = v_actor THEN
        RAISE EXCEPTION 'SELF_ASSIGNMENT_FORBIDDEN: %', p_auditor;
    END IF;

    -- автор не может быть назначен проверяющим собственной работы:
    -- запрет действует уже при назначении, а не только при вердикте
    IF EXISTS (SELECT 1 FROM bem_core.subject_author a
                WHERE a.subject_id = p_subject_id AND a.actor_id = p_auditor) THEN
        RAISE EXCEPTION 'SELF_AUDIT_FORBIDDEN: %', p_auditor;
    END IF;

    -- координатор не может быть автором этого же предмета: иначе
    -- полномочие превращается в право выбрать себе проверяющего
    IF EXISTS (SELECT 1 FROM bem_core.subject_author a
                WHERE a.subject_id = p_subject_id AND a.actor_id = v_actor) THEN
        RAISE EXCEPTION 'COORDINATOR_IS_AUTHOR: %', v_actor;
    END IF;

    -- H1.26, D2 (пробы R46, п. 20): прежний запрет «проверяющий из той же
    -- компании, что любой из авторов» убран. Он противоречил пункту 1
    -- раздела 13.5: при авторе-модели одна из двух обязательных компаний
    -- не могла дать проверяющего, и предмет BEM-954 не выпускался никогда.
    -- Замечание C-H18-R8-04 («автор приводит коллегу своей линии») закрыто
    -- проверками выше: назначает только координатор с полномочием, сам
    -- координатор не автор, проверяющий не автор. Выпуск требует точного
    -- множества {anthropic, openai} среди назначенных не-авторов.

    INSERT INTO bem_core.audit_assignment
           (id, tenant_id, subject_id, auditor_actor, auditor_provider, assigned_by)
    VALUES (v_id, p_tenant_id, p_subject_id, p_auditor, v_provider, v_actor)
    ON CONFLICT (subject_id, auditor_actor) DO UPDATE
       SET revoked_at = NULL, assigned_at = now(), assigned_by = v_actor
    RETURNING id INTO v_id;

    PERFORM bem_control.evidence_write(p_tenant_id, 'AUDITOR_ASSIGNED',
                                       COALESCE(p_evidence, '{}'::jsonb)
                                       || jsonb_build_object('subject_id', p_subject_id,
                                       'auditor',    p_auditor,
                                       'provider',   v_provider));
    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.assign_auditor(uuid, uuid, text, jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.assign_auditor(uuid, uuid, text, jsonb) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.assign_auditor(uuid, uuid, text, jsonb)
       TO bem_governance;

-- Отзыв назначения требует того же полномочия, что и назначение:
-- иначе автор снимал бы неудобного проверяющего (замечание C-H18-R8-04).
CREATE OR REPLACE FUNCTION bem_control.revoke_auditor(
    p_tenant_id  uuid,
    p_subject_id uuid,
    p_auditor    text,
    p_evidence   jsonb)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor text;
    v_rows  integer;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    v_actor := bem_control.assert_authority('AUDIT_COORDINATOR', p_tenant_id);
    PERFORM bem_control.lock_subject(p_tenant_id, p_subject_id);

    UPDATE bem_core.audit_assignment
       SET revoked_at = now()
     WHERE subject_id    = p_subject_id
       AND tenant_id     = p_tenant_id
       AND auditor_actor = p_auditor
       AND revoked_at   IS NULL;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    IF v_rows = 0 THEN RETURN false; END IF;

    PERFORM bem_control.evidence_write(p_tenant_id, 'AUDITOR_REVOKED',
                                       COALESCE(p_evidence, '{}'::jsonb)
                                       || jsonb_build_object('subject_id', p_subject_id, 'auditor', p_auditor));
    RETURN true;
END;
$$;

ALTER FUNCTION bem_control.revoke_auditor(uuid, uuid, text, jsonb)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.revoke_auditor(uuid, uuid, text, jsonb) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.revoke_auditor(uuid, uuid, text, jsonb)
       TO bem_governance;

CREATE OR REPLACE FUNCTION bem_control.bind_process_instance(
    p_tenant_id          uuid,
    p_work_item_id       uuid,
    p_process_instance_id text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor text;   -- выводится из контекста, не из настройки
    v_cur   text;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    SELECT out_actor_id INTO v_actor
      FROM bem_control.current_actor_checked(p_tenant_id);
    IF p_process_instance_id IS NULL THEN
        RAISE EXCEPTION 'PROCESS_INSTANCE_NULL';
    END IF;

    SELECT w.process_instance_id INTO v_cur
      FROM bem_core.work_item w
     WHERE w.id = p_work_item_id AND w.tenant_id = p_tenant_id
       FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'NOT_FOUND'; END IF;

    IF v_cur IS NOT NULL THEN
        IF v_cur = p_process_instance_id THEN
            RETURN false;                       -- честный повтор
        END IF;
        RAISE EXCEPTION 'PROCESS_INSTANCE_ALREADY_BOUND: stored=% asked=%',
              v_cur, p_process_instance_id;
    END IF;

    UPDATE bem_core.work_item
       SET process_instance_id = p_process_instance_id, updated_at = now()
     WHERE id = p_work_item_id AND tenant_id = p_tenant_id;

    PERFORM bem_control.evidence_write(p_tenant_id, 'PROCESS_INSTANCE_BOUND',
                                       jsonb_build_object('work_item_id', p_work_item_id,
                                       'process_instance_id', p_process_instance_id));
    RETURN true;
END;
$$;

ALTER FUNCTION bem_control.bind_process_instance(uuid, uuid, text)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.bind_process_instance(uuid, uuid, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.bind_process_instance(uuid, uuid, text)
       TO bem_kernel_rw;

CREATE OR REPLACE FUNCTION bem_control.record_usage(
    p_tenant_id       uuid,
    p_work_item_id    uuid,
    p_attempt_no      integer,
    p_provider        text,
    p_model           text,
    p_input_tokens    integer,
    p_output_tokens   integer,
    p_cached_tokens   integer,
    p_tool_overhead   integer,
    p_context_estimate integer,
    p_context_limit   integer,
    p_measured_by     text,
    p_outcome         text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor text;   -- выводится из контекста, не из настройки
    v_id    uuid := gen_random_uuid();
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    SELECT out_actor_id INTO v_actor
      FROM bem_control.current_actor_checked(p_tenant_id);

    INSERT INTO bem_core.usage_record
           (id, tenant_id, work_item_id, attempt_no, provider, model,
            input_tokens, output_tokens, cached_tokens, tool_overhead_tokens,
            context_estimate, context_limit, measured_by, outcome)
    VALUES (v_id, p_tenant_id, p_work_item_id, p_attempt_no, p_provider, p_model,
            p_input_tokens, p_output_tokens, p_cached_tokens, p_tool_overhead,
            p_context_estimate, p_context_limit, p_measured_by, p_outcome);

    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.record_usage(uuid, uuid, integer, text, text, integer,
                                        integer, integer, integer, integer, integer,
                                        text, text)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.record_usage(uuid, uuid, integer, text, text,
                                                    integer, integer, integer, integer,
                                                    integer, integer, text, text)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.record_usage(uuid, uuid, integer, text, text,
                                                    integer, integer, integer, integer,
                                                    integer, integer, text, text)
       TO bem_kernel_rw;

CREATE OR REPLACE FUNCTION bem_control.record_handoff(
    p_tenant_id     uuid,
    p_work_item_id  uuid,
    p_handoff_no    integer,
    p_payload       jsonb,
    p_packet_sha256 text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor text;   -- выводится из контекста, не из настройки
    v_id    uuid := gen_random_uuid();
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    SELECT out_actor_id INTO v_actor
      FROM bem_control.current_actor_checked(p_tenant_id);
    IF p_packet_sha256 !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'HANDOFF_SHA_FORMAT: %', p_packet_sha256;
    END IF;
    IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'HANDOFF_PAYLOAD_MUST_BE_OBJECT';
    END IF;

    INSERT INTO bem_core.handoff_packet
           (id, tenant_id, work_item_id, handoff_no, payload, packet_sha256)
    VALUES (v_id, p_tenant_id, p_work_item_id, p_handoff_no, p_payload, p_packet_sha256);

    PERFORM bem_control.evidence_write(p_tenant_id, 'HANDOFF_WRITTEN',
                                       jsonb_build_object('work_item_id', p_work_item_id,
                                       'handoff_no',   p_handoff_no,
                                       'packet_sha256', p_packet_sha256));
    RETURN v_id;
END;
$$;

ALTER FUNCTION bem_control.record_handoff(uuid, uuid, integer, jsonb, text)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.record_handoff(uuid, uuid, integer, jsonb, text)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.record_handoff(uuid, uuid, integer, jsonb, text)
       TO bem_kernel_rw;

CREATE OR REPLACE FUNCTION bem_control.accept_handoff(
    p_tenant_id    uuid,
    p_work_item_id uuid,
    p_handoff_no   integer,
    p_packet_sha256 text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor  text;
    v_mode   text;
    v_sha    text;
    v_at     timestamptz;
    v_by     text;
    v_facts  jsonb;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);

    SELECT out_actor_id, out_identity_mode INTO v_actor, v_mode
      FROM bem_control.current_actor_checked(p_tenant_id);

    SELECT h.packet_sha256, h.accepted_at, h.accepted_by
      INTO v_sha, v_at, v_by
      FROM bem_core.handoff_packet h
     WHERE h.tenant_id    = p_tenant_id
       AND h.work_item_id = p_work_item_id
       AND h.handoff_no   = p_handoff_no
       FOR UPDATE;

    -- Пакета нет: записывать доказательство не о чем, и это ошибка
    -- вызывающего, а не событие приёма.
    IF NOT FOUND THEN RAISE EXCEPTION 'HANDOFF_NOT_FOUND'; END IF;

    v_facts := jsonb_build_object('work_item_id',  p_work_item_id,
                                  'handoff_no',    p_handoff_no,
                                  'packet_sha256', p_packet_sha256,
                                  'identity_mode', v_mode);

    -- Правило 2: сумма проверяется первой.
    IF v_sha <> p_packet_sha256 THEN
        -- Отказ, а не исключение: исключение откатило бы транзакцию
        -- вместе с этой строкой доказательства (замечание M-H18-R8-05).
        PERFORM bem_control.evidence_write(p_tenant_id, 'HANDOFF_REJECTED',
                                           v_facts || jsonb_build_object('stored_sha256', v_sha));

        -- Журнал сервера откат не отменяет.
        RAISE WARNING 'HANDOFF_REJECTED: пакет %/% сумма в базе %, предъявлена %',
                      p_work_item_id, p_handoff_no, v_sha, p_packet_sha256;
        RETURN false;
    END IF;

    -- Правило 3: повтор тем же участником ничего не добавляет.
    IF v_at IS NOT NULL THEN
        IF v_by = v_actor THEN
            RETURN true;
        END IF;

        PERFORM bem_control.evidence_write(p_tenant_id, 'HANDOFF_ACCEPT_CONFLICT',
                                           v_facts || jsonb_build_object('accepted_by', v_by,
                                           'accepted_at', v_at));

        RAISE WARNING 'HANDOFF_ACCEPT_CONFLICT: пакет %/% уже принят участником %',
                      p_work_item_id, p_handoff_no, v_by;
        RETURN false;
    END IF;

    -- Первый приём. Строка взята FOR UPDATE выше, поэтому второй
    -- вызывающий ждёт здесь и увидит уже принятый пакет.
    UPDATE bem_core.handoff_packet
       SET accepted_at = now(),
           accepted_by = v_actor
     WHERE tenant_id    = p_tenant_id
       AND work_item_id = p_work_item_id
       AND handoff_no   = p_handoff_no;

    PERFORM bem_control.evidence_write(p_tenant_id, 'HANDOFF_ACCEPTED',
                                       v_facts);

    RETURN true;
END;
$$;

ALTER FUNCTION bem_control.accept_handoff(uuid, uuid, integer, text)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.accept_handoff(uuid, uuid, integer, text)
       FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.accept_handoff(uuid, uuid, integer, text)
       TO bem_kernel_rw;

CREATE OR REPLACE FUNCTION bem_control.dead_letter_outbox_row(
    p_tenant_id uuid,
    p_outbox_id uuid,
    p_reason    text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = bem_control, bem_core, pg_catalog, pg_temp
AS $$
DECLARE
    v_actor    text;
    v_status   text;
    v_attempts integer;
BEGIN
    PERFORM bem_control.assert_tenant(p_tenant_id);
    -- Ручной перевод в тупик — решение оператора, а не рабочей роли.
    -- Автоматический перевод по порогу делает finish_outbox_row.
    v_actor := bem_control.assert_authority('OPERATOR', p_tenant_id);

    SELECT o.status, o.attempt_count INTO v_status, v_attempts
      FROM bem_core.outbox o
     WHERE o.id = p_outbox_id AND o.tenant_id = p_tenant_id
       FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'NOT_FOUND'; END IF;

    IF v_status = 'DEAD_LETTER' THEN RETURN false; END IF;      -- честный повтор
    -- Порога здесь нет: оператор вправе прекратить попытки раньше.
    -- Он обязан назвать причину, и она уходит в доказательство.
    IF v_status NOT IN ('FAILED', 'UNKNOWN_OUTCOME') THEN
        RAISE EXCEPTION 'DEAD_LETTER_FROM_WRONG_STATUS: %', v_status;
    END IF;
    IF p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'DEAD_LETTER_REASON_REQUIRED';
    END IF;

    UPDATE bem_core.outbox
       SET status = 'DEAD_LETTER',
           dead_lettered_at = now(),
           dead_letter_reason = p_reason
     WHERE id = p_outbox_id AND tenant_id = p_tenant_id;

    PERFORM bem_control.evidence_write(p_tenant_id, 'OUTBOX_DEAD_LETTER',
                                       jsonb_build_object('outbox_id', p_outbox_id,
                                       'attempts',  v_attempts,
                                       'reason',    p_reason));
    RETURN true;
END;
$$;

ALTER FUNCTION bem_control.dead_letter_outbox_row(uuid, uuid, text)
      OWNER TO bem_control_owner;
REVOKE EXECUTE ON FUNCTION bem_control.dead_letter_outbox_row(uuid, uuid, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.dead_letter_outbox_row(uuid, uuid, text)
       TO bem_governance;

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

-- Состояние окна создаёт владелец схемы управления: таблица общая,
-- а функции окна получают на неё только чтение и правку.
-- Строка ровно одна — окно у базы одно.
CREATE TABLE IF NOT EXISTS bem_control.backup_window (
    id          smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    locked_xid  xid8,
    locked_at   timestamptz,
    locked_by   name,
    zero_streak smallint NOT NULL DEFAULT 0,
    closed_at   timestamptz
);
-- H1.26, D1 (пробы R46, п. 16): ограничения таблицы bem_control.backup_window — тем же
-- порядком, что шаг 4 для bem_core, и до первой вставки с ON CONFLICT:
-- без первичного ключа она падает раньше, чем ключ успеют вернуть.
DO $$
DECLARE
    r      record;
    v_def  text;
    v_path text;
BEGIN
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog', true);
    FOR r IN
        SELECT * FROM (VALUES
            ('bem_control.backup_window', 'backup_window_pkey', 'PRIMARY KEY (id)'),
            ('bem_control.backup_window', 'backup_window_id_check', 'CHECK ((id = 1))')
        ) AS t(tbl, con, def)
    LOOP
        SELECT pg_get_constraintdef(c.oid) INTO v_def
          FROM pg_constraint c
         WHERE c.conname = r.con AND c.conrelid = r.tbl::regclass;
        IF NOT FOUND THEN
            EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', r.tbl, r.con, r.def);
        ELSIF v_def IS DISTINCT FROM r.def THEN
            RAISE EXCEPTION
              'MIGRATION_FAILED: CONSTRAINT_DEFINITION_MISMATCH: % %: ожидалось %, найдено %',
              r.tbl, r.con, r.def, v_def;
        END IF;
    END LOOP;
    PERFORM set_config('search_path', v_path, true);
END
$$;
INSERT INTO bem_control.backup_window (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
-- Право на запись здесь тоже по колонкам, а не на всю таблицу:
-- проверка 16 раздела 26.9 считает лишним любое право, которого не
-- требует ни одно тело функции. Сами функции создаёт файл 04: здесь
-- создаётся только их общее состояние.
GRANT SELECT ON bem_control.backup_window TO bem_backup_ctl_owner;
GRANT UPDATE (locked_xid, locked_at, locked_by, zero_streak, closed_at)
              ON bem_control.backup_window TO bem_backup_ctl_owner;


RESET ROLE;

INSERT INTO bem_core.schema_migration (version)
VALUES ('bem954-h1-10-baseline')
ON CONFLICT (version) DO NOTHING;

DO $$
DECLARE
    v_cnt   integer;
    v_name  text;
    v_row   text;
    v_who   text;
    v_obj   text;
    v_priv  text;
    v_okind text;
    v_oname text;
    v_sig   text;
    v_path  text;
    v_txt   text;
    v_tdef  text;
    v_oid   oid;
    v_ok    boolean;
    v_acl_got  text[];
    v_acl_want text[];
    v_got      text;
    -- Обязательное чтение. Каждая строка — «кому | объект | право».
    -- Список не написан здесь руками: его печатает сверщик раздела
    -- 15.11 ключом --print-selfcheck, и он же при каждой сверке
    -- требует, чтобы массив совпал с выведенным из канона. Строка
    -- роли проверки восстановления сюда не входит: её выдаёт файл 03
    -- в восстановленной копии, а не этот файл в базе bem.
    v_read  constant text[] := ARRAY[
        'backup_reader|ALLSEQUENCES:bem_control|SELECT',
        'backup_reader|ALLSEQUENCES:bem_core|SELECT',
        'backup_reader|ALLSEQUENCES:bem_engine|SELECT',
        'backup_reader|ALLTABLES:bem_control|SELECT',
        'backup_reader|ALLTABLES:bem_core|SELECT',
        'backup_reader|ALLTABLES:bem_engine|SELECT',
        'backup_reader|DATABASE:bem|CONNECT',
        'backup_reader|DEFSEQUENCES:bem_control|SELECT',
        'backup_reader|DEFSEQUENCES:bem_core|SELECT',
        'backup_reader|DEFSEQUENCES:bem_engine|SELECT',
        'backup_reader|DEFTABLES:bem_control|SELECT',
        'backup_reader|DEFTABLES:bem_core|SELECT',
        'backup_reader|DEFTABLES:bem_engine|SELECT',
        'backup_reader|SCHEMA:bem_control|USAGE',
        'backup_reader|SCHEMA:bem_core|USAGE',
        'backup_reader|SCHEMA:bem_engine|USAGE',
        'bem_backup_admin|DATABASE:bem|CONNECT',
        'bem_backup_admin|SCHEMA:bem_control|USAGE',
        'bem_backup_ctl_owner|SCHEMA:bem_control|USAGE',
        'bem_backup_ctl_owner|TABLE:bem_control.backup_window|SELECT',
        'bem_bootstrap_admin|DATABASE:bem|CONNECT',
        'bem_control_owner|ALLSEQUENCES:bem_core|SELECT',
        'bem_control_owner|ALLTABLES:bem_core|SELECT',
        'bem_control_owner|ALLTABLES:bem_engine|SELECT',
        'bem_control_owner|DEFSEQUENCES:bem_core|SELECT',
        'bem_control_owner|DEFSEQUENCES:bem_engine|SELECT',
        'bem_control_owner|DEFTABLES:bem_core|SELECT',
        'bem_control_owner|DEFTABLES:bem_engine|SELECT',
        'bem_control_owner|SCHEMA:bem_core|USAGE',
        'bem_control_owner|SCHEMA:bem_engine|USAGE',
        'bem_engine_rw|DATABASE:bem|CONNECT',
        'bem_engine_rw|SCHEMA:bem_engine|USAGE',
        'bem_governance|SCHEMA:bem_control|USAGE',
        'bem_kernel_rw|ALLSEQUENCES:bem_core|SELECT',
        'bem_kernel_rw|ALLTABLES:bem_core|SELECT',
        'bem_kernel_rw|DATABASE:bem|CONNECT',
        'bem_kernel_rw|DEFSEQUENCES:bem_core|SELECT',
        'bem_kernel_rw|DEFTABLES:bem_core|SELECT',
        'bem_kernel_rw|SCHEMA:bem_control|USAGE',
        'bem_kernel_rw|SCHEMA:bem_core|USAGE',
        'schema_migrator|DATABASE:bem|CONNECT'];
    -- Обязательные вызовы. Ключ — ПОЛНАЯ подпись и точный получатель
    -- (пункт 5 замечания M-H112-R12-01: короткое имя подписью не
    -- является). Список выводится тем же ключом сверщика.
    v_exec  constant text[] := ARRAY[
        'bem_control.accept_handoff(uuid, uuid, integer, text)|bem_kernel_rw',
        'bem_control.apply_transition(uuid, uuid, integer, text[], text, uuid, text, jsonb, jsonb)|bem_kernel_rw',
        'bem_control.assert_authority(text, uuid)|bem_kernel_rw',
        'bem_control.assert_tenant(uuid)|bem_kernel_rw',
        'bem_control.assign_auditor(uuid, uuid, text, jsonb)|bem_governance',
        'bem_control.bind_process_instance(uuid, uuid, text)|bem_kernel_rw',
        'bem_control.claim_outbox_batch(integer, interval, text)|bem_kernel_rw',
        'bem_control.create_actor(text, bem_core.provider, uuid, name)|bem_governance',
        'bem_control.create_tenant(uuid, text, text, uuid, jsonb)|bem_governance',
        'bem_control.create_work_item(uuid, uuid, text, text, jsonb)|bem_kernel_rw',
        'bem_control.current_actor_checked(uuid)|bem_kernel_rw',
        'bem_control.data_digest(regclass)|bem_backup_admin',
        'bem_control.data_digest(regclass)|bem_kernel_rw',
        'bem_control.database_digest()|bem_backup_admin',
        'bem_control.database_digest()|bem_kernel_rw',
        'bem_control.dead_letter_outbox_row(uuid, uuid, text)|bem_governance',
        'bem_control.evidence_write(uuid, text, jsonb)|bem_control_owner',
        'bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)|bem_kernel_rw',
        'bem_control.grant_authority(text, text, uuid)|bem_governance',
        'bem_control.grant_delegation(name, text, text)|bem_governance',
        'bem_control.outbox_retry_limit()|bem_kernel_rw',
        'bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)|bem_kernel_rw',
        'bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)|bem_governance',
        'bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)|bem_kernel_rw',
        'bem_control.record_backup_evidence(jsonb)|bem_backup_admin',
        'bem_control.record_evidence(uuid, text, jsonb)|bem_kernel_rw',
        'bem_control.record_handoff(uuid, uuid, integer, jsonb, text)|bem_kernel_rw',
        'bem_control.record_usage(uuid, uuid, integer, text, text, integer, integer, integer, integer, integer, integer, text, text)|bem_kernel_rw',
        'bem_control.release_subject(uuid, uuid, text)|bem_kernel_rw',
        'bem_control.revoke_auditor(uuid, uuid, text, jsonb)|bem_governance',
        'bem_control.revoke_authority(text, text, uuid)|bem_governance',
        'bem_control.revoke_delegation(uuid)|bem_governance',
        'bem_control.schema_digest(regclass)|bem_backup_admin',
        'bem_control.schema_digest(regclass)|bem_kernel_rw',
        'bem_control.set_tenant_membership(uuid, uuid, text, boolean)|bem_kernel_rw'];
    -- Полный договор записи. Каждая строка — «кому | таблица | право |
    -- колонка», и каждая выведена из тела конкретной функции, а не
    -- написана по памяти. Пустая колонка означает право на всю
    -- таблицу. Список сверяется в обе стороны: проверка 17 требует,
    -- чтобы всё перечисленное было выдано, проверка 18 — чтобы ничего
    -- сверх перечисленного выдано не было. Полноту самого списка
    -- доказывает сверщик раздела 15.11: он читает тела всех функций
    -- канонического раздела и сравнивает выведенное с этим текстом.
    v_dml   constant text[] := ARRAY[
        'bem_backup_ctl_owner|bem_control.backup_window|UPDATE|closed_at',
        'bem_backup_ctl_owner|bem_control.backup_window|UPDATE|locked_at',
        'bem_backup_ctl_owner|bem_control.backup_window|UPDATE|locked_by',
        'bem_backup_ctl_owner|bem_control.backup_window|UPDATE|locked_xid',
        'bem_backup_ctl_owner|bem_control.backup_window|UPDATE|zero_streak',
        'bem_control_owner|bem_core.actor_authority|INSERT|',
        'bem_control_owner|bem_core.actor_authority|UPDATE|revoked_at',
        'bem_control_owner|bem_core.actor_delegation|INSERT|',
        'bem_control_owner|bem_core.actor_delegation|UPDATE|revoked_at',
        'bem_control_owner|bem_core.actor_delegation|UPDATE|revoked_by',
        'bem_control_owner|bem_core.actor|INSERT|',
        'bem_control_owner|bem_core.audit_assignment|INSERT|',
        'bem_control_owner|bem_core.audit_assignment|UPDATE|assigned_at',
        'bem_control_owner|bem_core.audit_assignment|UPDATE|assigned_by',
        'bem_control_owner|bem_core.audit_assignment|UPDATE|revoked_at',
        'bem_control_owner|bem_core.audit_record|INSERT|',
        'bem_control_owner|bem_core.command_log|INSERT|',
        'bem_control_owner|bem_core.command_log|UPDATE|outbox_id',
        'bem_control_owner|bem_core.command_log|UPDATE|result_revision',
        'bem_control_owner|bem_core.evidence|INSERT|',
        'bem_control_owner|bem_core.handoff_packet|INSERT|',
        'bem_control_owner|bem_core.handoff_packet|UPDATE|accepted_at',
        'bem_control_owner|bem_core.handoff_packet|UPDATE|accepted_by',
        'bem_control_owner|bem_core.outbox|INSERT|',
        'bem_control_owner|bem_core.outbox|UPDATE|attempt_count',
        'bem_control_owner|bem_core.outbox|UPDATE|dead_letter_reason',
        'bem_control_owner|bem_core.outbox|UPDATE|dead_lettered_at',
        'bem_control_owner|bem_core.outbox|UPDATE|finished_at',
        'bem_control_owner|bem_core.outbox|UPDATE|lease_epoch',
        'bem_control_owner|bem_core.outbox|UPDATE|leased_by',
        'bem_control_owner|bem_core.outbox|UPDATE|leased_until',
        'bem_control_owner|bem_core.outbox|UPDATE|next_attempt_at',
        'bem_control_owner|bem_core.outbox|UPDATE|reconciled_at',
        'bem_control_owner|bem_core.outbox|UPDATE|reconciled_outcome',
        'bem_control_owner|bem_core.outbox|UPDATE|result',
        'bem_control_owner|bem_core.outbox|UPDATE|status',
        'bem_control_owner|bem_core.subject_author|INSERT|',
        'bem_control_owner|bem_core.subject|INSERT|',
        'bem_control_owner|bem_core.subject|UPDATE|disagreement_at',
        'bem_control_owner|bem_core.subject|UPDATE|disagreement_reason',
        'bem_control_owner|bem_core.subject|UPDATE|head_sha',
        'bem_control_owner|bem_core.subject|UPDATE|published_at',
        'bem_control_owner|bem_core.subject|UPDATE|released_at',
        'bem_control_owner|bem_core.subject|UPDATE|released_by',
        'bem_control_owner|bem_core.tenant|INSERT|',
        'bem_control_owner|bem_core.usage_record|INSERT|',
        'bem_control_owner|bem_core.user_tenant_membership|INSERT|',
        'bem_control_owner|bem_core.user_tenant_membership|UPDATE|revoked_at',
        'bem_control_owner|bem_core.user_tenant_membership|UPDATE|revoked_by',
        'bem_control_owner|bem_core.work_item|INSERT|',
        'bem_control_owner|bem_core.work_item|UPDATE|process_instance_id',
        'bem_control_owner|bem_core.work_item|UPDATE|revision',
        'bem_control_owner|bem_core.work_item|UPDATE|status',
        'bem_control_owner|bem_core.work_item|UPDATE|updated_at'];
    -- Права целиком (R32, замечание M-H116-R16-02). Строка — «вид |
    -- объект | получатель | право[*] | выдавший»; у записи прав по
    -- умолчанию: DEFAULT | роль | схема | вид | получатель | право |
    -- выдавший. Выдавший — последнее поле. Списки не написаны здесь
    -- руками: их печатает сверщик раздела 15.11 из модели прав
    -- PostgreSQL 16, и он же при каждой сверке требует совпадения с
    -- каноном в обе стороны с учётом повторов. v_acl — состояние после
    -- этого файла; v_acl_04 — восемь строк прав четырёх функций окна
    -- резервного копирования: их создаёт файл 04, то есть позже, и
    -- проверка 21 принимает их по правилу «все или ни одной».
    v_acl    constant text[] := ARRAY[
        'COLUMN|bem_control.backup_window.closed_at|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_control.backup_window.locked_at|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_control.backup_window.locked_by|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_control.backup_window.locked_xid|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_control.backup_window.zero_streak|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_core.actor_authority.revoked_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.actor_delegation.revoked_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.actor_delegation.revoked_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.audit_assignment.assigned_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.audit_assignment.assigned_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.audit_assignment.revoked_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.command_log.outbox_id|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.command_log.result_revision|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.handoff_packet.accepted_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.handoff_packet.accepted_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.attempt_count|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.dead_letter_reason|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.dead_lettered_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.finished_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.lease_epoch|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.leased_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.leased_until|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.next_attempt_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.reconciled_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.reconciled_outcome|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.result|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.status|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.disagreement_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.disagreement_reason|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.head_sha|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.published_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.released_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.released_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.user_tenant_membership.revoked_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.user_tenant_membership.revoked_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.work_item.process_instance_id|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.work_item.revision|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.work_item.status|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.work_item.updated_at|bem_control_owner|UPDATE|bem_core_owner',
        'DATABASE|bem|backup_reader|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_backup_admin|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_bootstrap_admin|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_core_owner|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_core_owner|CREATE|bem_core_owner',
        'DATABASE|bem|bem_core_owner|TEMPORARY|bem_core_owner',
        'DATABASE|bem|bem_engine_rw|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_kernel_rw|CONNECT|bem_core_owner',
        'DATABASE|bem|schema_migrator|CONNECT|bem_core_owner',
        'DEFAULT|bem_control_owner|bem_control|S|backup_reader|SELECT|bem_control_owner',
        'DEFAULT|bem_control_owner|bem_control|r|backup_reader|SELECT|bem_control_owner',
        'DEFAULT|bem_core_owner|bem_core|S|backup_reader|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|S|bem_control_owner|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|S|bem_kernel_rw|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|r|backup_reader|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|r|bem_control_owner|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|r|bem_kernel_rw|SELECT|bem_core_owner',
        'DEFAULT|bem_engine_owner|bem_engine|S|backup_reader|SELECT|bem_engine_owner',
        'DEFAULT|bem_engine_owner|bem_engine|S|bem_control_owner|SELECT|bem_engine_owner',
        'DEFAULT|bem_engine_owner|bem_engine|r|backup_reader|SELECT|bem_engine_owner',
        'DEFAULT|bem_engine_owner|bem_engine|r|bem_control_owner|SELECT|bem_engine_owner',
        'FUNCTION|bem_control.accept_handoff(uuid, uuid, integer, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.accept_handoff(uuid, uuid, integer, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.apply_transition(uuid, uuid, integer, text[], text, uuid, text, jsonb, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.apply_transition(uuid, uuid, integer, text[], text, uuid, text, jsonb, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_authority(text, uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_authority(text, uuid)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_command_identity(bem_core.command_log, uuid, uuid, uuid, text, text, boolean, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_tenant(uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_tenant(uuid)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assign_auditor(uuid, uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assign_auditor(uuid, uuid, text, jsonb)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.authority_barrier(text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.bind_process_instance(uuid, uuid, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.bind_process_instance(uuid, uuid, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.claim_outbox_batch(integer, interval, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.claim_outbox_batch(integer, interval, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.command_fingerprint(uuid, uuid, text, integer, text[], text, text, jsonb, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_actor(text, bem_core.provider, uuid, name)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_actor(text, bem_core.provider, uuid, name)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_tenant(uuid, text, text, uuid, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_tenant(uuid, text, text, uuid, jsonb)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_work_item(uuid, uuid, text, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_work_item(uuid, uuid, text, text, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.current_actor_checked(uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.current_actor_checked(uuid)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.data_digest(regclass)|bem_backup_admin|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.data_digest(regclass)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.data_digest(regclass)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.database_digest()|bem_backup_admin|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.database_digest()|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.database_digest()|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.dead_letter_outbox_row(uuid, uuid, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.dead_letter_outbox_row(uuid, uuid, text)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.evidence_write(uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.grant_authority(text, text, uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.grant_authority(text, text, uuid)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.grant_delegation(name, text, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.grant_delegation(name, text, text)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.lock_subject(uuid, uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.operator_lock_key()|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.outbox_retry_limit()|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.outbox_retry_limit()|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_backup_evidence(jsonb)|bem_backup_admin|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_backup_evidence(jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_evidence(uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_evidence(uuid, text, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_handoff(uuid, uuid, integer, jsonb, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_handoff(uuid, uuid, integer, jsonb, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_usage(uuid, uuid, integer, text, text, integer, integer, integer, integer, integer, integer, text, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_usage(uuid, uuid, integer, text, text, integer, integer, integer, integer, integer, integer, text, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.release_subject(uuid, uuid, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.release_subject(uuid, uuid, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_auditor(uuid, uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_auditor(uuid, uuid, text, jsonb)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_authority(text, text, uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_authority(text, text, uuid)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_delegation(uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_delegation(uuid)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.schema_digest(regclass)|bem_backup_admin|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.schema_digest(regclass)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.schema_digest(regclass)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.service_tenant()|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.set_tenant_membership(uuid, uuid, text, boolean)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.set_tenant_membership(uuid, uuid, text, boolean)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'SCHEMA|bem_control|backup_reader|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_backup_admin|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_backup_ctl_owner|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_control_owner|CREATE|bem_control_owner',
        'SCHEMA|bem_control|bem_control_owner|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_governance|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_kernel_rw|USAGE|bem_control_owner',
        'SCHEMA|bem_core|backup_reader|USAGE|bem_core_owner',
        'SCHEMA|bem_core|bem_control_owner|USAGE|bem_core_owner',
        'SCHEMA|bem_core|bem_core_owner|CREATE|bem_core_owner',
        'SCHEMA|bem_core|bem_core_owner|USAGE|bem_core_owner',
        'SCHEMA|bem_core|bem_kernel_rw|USAGE|bem_core_owner',
        'SCHEMA|bem_engine|backup_reader|USAGE|bem_engine_owner',
        'SCHEMA|bem_engine|bem_control_owner|USAGE|bem_engine_owner',
        'SCHEMA|bem_engine|bem_engine_owner|CREATE|bem_engine_owner',
        'SCHEMA|bem_engine|bem_engine_owner|USAGE|bem_engine_owner',
        'SCHEMA|bem_engine|bem_engine_rw|USAGE|bem_engine_owner',
        'SCHEMA|public|pg_database_owner|CREATE|pg_database_owner',
        'SCHEMA|public|pg_database_owner|USAGE|pg_database_owner',
        'TABLE|bem_control.authority_guard|backup_reader|SELECT|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|DELETE|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|INSERT|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|REFERENCES|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|SELECT|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|TRIGGER|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|TRUNCATE|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|UPDATE|bem_control_owner',
        'TABLE|bem_control.backup_window|backup_reader|SELECT|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_backup_ctl_owner|SELECT|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|DELETE|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|INSERT|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|REFERENCES|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|SELECT|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|TRIGGER|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|TRUNCATE|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|UPDATE|bem_control_owner',
        'TABLE|bem_core.actor_authority|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.actor|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.actor|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.actor|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_record|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.command_log|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.command_log|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.evidence|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.outbox|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.outbox|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.schema_migration|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.subject_author|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.subject|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.subject|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.subject|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.subject|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.tenant|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.tenant|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.usage_record|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.work_item|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.work_item|bem_kernel_rw|SELECT|bem_core_owner'];
    v_acl_04 constant text[] := ARRAY[
        'FUNCTION|bem_control.backup_window_assert_closed()|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_assert_closed()|bem_backup_ctl_owner|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_drain()|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_drain()|bem_backup_ctl_owner|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_lock()|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_lock()|bem_backup_ctl_owner|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_open(integer)|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_open(integer)|bem_backup_ctl_owner|EXECUTE|bem_backup_ctl_owner'];
    v_expr  constant text := '(tenant_id = current_tenant())';
    v_fns   constant text[] := ARRAY[
        'accept_handoff',
        'apply_transition',
        'assert_authority',
        'assert_command_identity',
        'assert_tenant',
        'assign_auditor',
        'authority_barrier',
        'backup_window_assert_closed',
        'backup_window_drain',
        'backup_window_lock',
        'backup_window_open',
        'bind_process_instance',
        'claim_outbox_batch',
        'command_fingerprint',
        'create_actor',
        'create_tenant',
        'create_work_item',
        'current_actor_checked',
        'data_digest',
        'database_digest',
        'dead_letter_outbox_row',
        'evidence_write',
        'finish_outbox_row',
        'grant_authority',
        'grant_delegation',
        'lock_subject',
        'operator_lock_key',
        'outbox_retry_limit',
        'publish_subject',
        'reconcile_unknown_outcome',
        'record_audit_verdict',
        'record_backup_evidence',
        'record_evidence',
        'record_handoff',
        'record_usage',
        'release_subject',
        'revoke_auditor',
        'revoke_authority',
        'revoke_delegation',
        'schema_digest',
        'service_tenant',
        'set_tenant_membership'];
    v_bw     integer;
    v_bw_all integer;
    v_fns_want integer;
BEGIN
    -- 1. У ядра нет прямых прав записи нигде, включая доказательства.
    --    H1.8 делал здесь исключение для evidence, и оно позволяло
    --    ядру записать доказательство от любого имени (C-H18-R8-05).
    --    Теперь запись идёт только через record_evidence.
    SELECT count(*) INTO v_cnt
      FROM information_schema.table_privileges
     WHERE grantee = 'bem_kernel_rw'
       AND table_schema = 'bem_core'
       AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE');
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: у ядра % прав прямой записи', v_cnt;
    END IF;

    -- 2. Никто не получил DELETE в bem_core
    SELECT count(*) INTO v_cnt
      FROM information_schema.table_privileges
     WHERE table_schema = 'bem_core' AND privilege_type = 'DELETE'
       AND grantee <> 'bem_core_owner';
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: право DELETE выдано % раз', v_cnt;
    END IF;

    -- 3. Одиннадцать политик, и у каждой сверено ПОЛНОЕ определение:
    --    выражение чтения, выражение записи, команда, режим и роли.
    --    Сравнение идёт по тексту из каталога с убранным именем схемы:
    --    PostgreSQL печатает вызов функции со схемой или без неё в
    --    зависимости от пути поиска, и это не является различием.
    SELECT count(*) INTO v_cnt
      FROM pg_policies pol
     WHERE pol.schemaname = 'bem_core'
       AND pol.policyname = 'tenant_isolation'
       AND pol.cmd        = 'ALL'
       AND pol.permissive = 'PERMISSIVE'
       AND pol.roles      = ARRAY['public']::name[]
       AND replace(coalesce(pol.qual, ''),       'bem_core.', '') = v_expr
       AND replace(coalesce(pol.with_check, ''), 'bem_core.', '') = v_expr;
    IF v_cnt <> 11 THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: политик с точным определением % вместо 11', v_cnt;
    END IF;

    -- 4. Все функции управляющего слоя на месте — поимённо, а не числом.
    --    Четыре функции окна копирования создаёт файл 04, и он идёт
    --    после 01 (H1.22, дефект D2 живого прогона R41). Для них правило
    --    то же, что для их прав: все или ни одной. Ни одной — первая
    --    установка; все — повтор 01 на базе, где 04 уже применён.
    SELECT count(*) INTO v_bw_all FROM unnest(v_fns) AS f WHERE f LIKE 'backup\_window\_%';
    SELECT count(DISTINCT p.proname) INTO v_bw
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'bem_control' AND p.proname LIKE 'backup\_window\_%';
    IF v_bw NOT IN (0, v_bw_all) THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: функций окна копирования % из % — нужно все или ни одной',
              v_bw, v_bw_all;
    END IF;
    FOREACH v_name IN ARRAY v_fns
    LOOP
        CONTINUE WHEN v_bw = 0 AND v_name LIKE 'backup\_window\_%';
        IF NOT EXISTS (SELECT 1 FROM pg_proc p
                         JOIN pg_namespace n ON n.oid = p.pronamespace
                        WHERE n.nspname = 'bem_control' AND p.proname = v_name) THEN
            RAISE EXCEPTION 'MIGRATION_FAILED: нет функции bem_control.%', v_name;
        END IF;
    END LOOP;

    SELECT count(DISTINCT p.proname) INTO v_cnt
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'bem_control';
    -- Число считается до IF: слово THEN внутри CASE оборвало бы условие IF.
    v_fns_want := cardinality(v_fns) - CASE WHEN v_bw = 0 THEN v_bw_all ELSE 0 END;
    IF v_cnt <> v_fns_want THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: в bem_control % имён функций вместо %',
              v_cnt, v_fns_want;
    END IF;

    -- 5. У каждой функции управляющего слоя фиксирован путь поиска
    SELECT count(*) INTO v_cnt
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'bem_control'
       AND (p.proconfig IS NULL
            OR NOT EXISTS (SELECT 1 FROM unnest(p.proconfig) c
                            WHERE c LIKE 'search\_path=%'));
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: у % функций не задан путь поиска', v_cnt;
    END IF;

    -- 6. Ни одна функция управляющего слоя не доступна всем подряд
    SELECT count(*) INTO v_cnt
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'bem_control'
       AND has_function_privilege('public', p.oid, 'EXECUTE');
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: % функций доступны PUBLIC', v_cnt;
    END IF;

    -- 7. Защита строк включена и распространена на владельца
    SELECT count(*) INTO v_cnt
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'bem_core' AND c.relkind = 'r'
       AND c.relname IN ('work_item', 'evidence', 'subject', 'subject_author',
                         'audit_record', 'outbox', 'command_log', 'usage_record',
                         'handoff_packet', 'user_tenant_membership',
                         'audit_assignment')
       AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity);
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: у % таблиц защита строк не полная', v_cnt;
    END IF;

    -- 8. Форма ящика согласована с функцией перехода: колонка ключа
    --    повтора существует, обязательна и имеет проверку формата
    SELECT count(*) INTO v_cnt
      FROM information_schema.columns
     WHERE table_schema = 'bem_core' AND table_name = 'outbox'
       AND column_name = 'idempotency_key' AND is_nullable = 'NO';
    IF v_cnt <> 1 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: колонка idempotency_key не в форме';
    END IF;

    -- 9. Сторож копирования не имеет ни членства, ни системного права
    SELECT count(*) INTO v_cnt
      FROM pg_auth_members m
      JOIN pg_roles member ON member.oid = m.member
     WHERE member.rolname = 'bem_backup_admin';
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: у сторожа % членств вместо 0', v_cnt;
    END IF;

    -- 10. Владелец функций окна копирования не умеет входить
    SELECT count(*) INTO v_cnt
      FROM pg_roles WHERE rolname = 'bem_backup_ctl_owner' AND rolcanlogin;
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: владелец окна копирования умеет входить';
    END IF;

    -- 11. Роль восстановления видит схему движка и её будущие таблицы
    IF NOT has_schema_privilege('bem_control_owner', 'bem_engine', 'USAGE') THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: нет USAGE на bem_engine у владельца свёрток';
    END IF;

    -- 12. Чувствительные функции не выданы общей рабочей роли ядра.
    --     Их исполняет управляющая группа (C-H18-R8-04, C-H18-R8-05).
    SELECT count(*) INTO v_cnt
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'bem_control'
       AND p.proname IN ('assign_auditor', 'revoke_auditor', 'create_tenant',
                         'dead_letter_outbox_row', 'reconcile_unknown_outcome')
       AND has_function_privilege('bem_kernel_rw', p.oid, 'EXECUTE');
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: % чувствительных функций доступны ядру', v_cnt;
    END IF;

    -- 13. Первая связанная личность на месте, и полномочий у неё ровно три
    SELECT count(*) INTO v_cnt
      FROM bem_core.actor a
     WHERE a.actor_id = 'human:bootstrap'
       AND a.db_role  = 'bem_bootstrap_admin'
       AND a.is_active;
    IF v_cnt <> 1 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: нет связанной личности установки';
    END IF;

    SELECT count(*) INTO v_cnt
      FROM bem_core.actor_authority aa
     WHERE aa.actor_id   = 'human:bootstrap'
       AND aa.tenant_id  IS NULL
       AND aa.revoked_at IS NULL;
    IF v_cnt <> 3 THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: полномочий установки % вместо 3', v_cnt;
    END IF;

    -- 14. В трёх схемах нет отношений, которых не видит свёртка базы.
    --     Она обходит 'r' и 'p'; представление, материализованное
    --     представление или внешняя таблица прошли бы мимо неё
    --     (замечание M-H18-R8-06).
    SELECT count(*) INTO v_cnt
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname IN ('bem_core', 'bem_engine', 'bem_control')
       AND c.relkind NOT IN ('r', 'p', 'i', 'I', 'S', 'c', 't');
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: % отношений не попадают в свёртку базы', v_cnt;
    END IF;

    -- 15. Все девять управляемых триггеров целиком, а не один и не
    --     по имени. Прежний пункт проверял только включённость
    --     триггера личности. Поэтому триггер с правильным именем и
    --     неправильным определением проходил самопроверку насквозь
    --     (замечание C-H114-R14-01).
    --
    --     Сверяется отпечаток из одиннадцати полей каталога:
    --     схема с таблицей, имя, маска событий, список столбцов,
    --     функция с полной подписью, режим работы, признак
    --     ограничения, отложенность, начальная отложенность,
    --     наличие условия WHEN и число аргументов. Имена схем берутся
    --     из pg_namespace, а не приведением к regclass: приведение
    --     зависит от search_path и на разных сеансах даёт разный текст.
    SELECT COALESCE(string_agg(fp, E'\n' ORDER BY fp COLLATE "C"), '')
      INTO v_txt
      FROM (
        SELECT tn.nspname || '.' || tc.relname || '|' || tg.tgname
               || '|' || tg.tgtype
               || '|' || COALESCE((
                        SELECT string_agg(a.attname::text, ',' ORDER BY u.ord)
                          FROM unnest(tg.tgattr::smallint[]) WITH ORDINALITY AS u(attnum, ord)
                          JOIN pg_attribute a
                            ON a.attrelid = tg.tgrelid AND a.attnum = u.attnum
                      ), '')
               || '|' || fn.nspname || '.' || fp.proname || '()'
               || '|' || tg.tgenabled::text
               || '|' || CASE WHEN tg.tgconstraint <> 0 THEN 't' ELSE 'f' END
               || '|' || CASE WHEN tg.tgdeferrable     THEN 't' ELSE 'f' END
               || '|' || CASE WHEN tg.tginitdeferred   THEN 't' ELSE 'f' END
               || '|' || CASE WHEN tg.tgqual IS NOT NULL THEN 't' ELSE 'f' END
               || '|' || tg.tgnargs AS fp
          FROM pg_trigger tg
          JOIN pg_class     tc ON tc.oid = tg.tgrelid
          JOIN pg_namespace tn ON tn.oid = tc.relnamespace
          JOIN pg_proc      fp ON fp.oid = tg.tgfoid
          JOIN pg_namespace fn ON fn.oid = fp.pronamespace
         WHERE NOT tg.tgisinternal
           AND tn.nspname = 'bem_core'
           AND tc.relname IN ('audit_record', 'command_log', 'evidence',
                              'subject', 'subject_author')
      ) q;

    IF v_txt <> 
            'bem_core.audit_record|audit_record_append_only|27||bem_core.forbid_update_delete()|O|f|f|f|f|0' || E'\n' ||
            'bem_core.audit_record|audit_record_head_match|7||bem_core.audit_head_matches_subject()|O|f|f|f|f|0' || E'\n' ||
            'bem_core.audit_record|audit_record_no_self_audit|7||bem_core.forbid_self_audit()|O|f|f|f|f|0' || E'\n' ||
            'bem_core.command_log|command_log_append_only|11||bem_core.forbid_update_delete()|O|f|f|f|f|0' || E'\n' ||
            'bem_core.evidence|evidence_append_only|27||bem_core.forbid_update_delete()|O|f|f|f|f|0' || E'\n' ||
            'bem_core.evidence|evidence_identity|7||bem_core.evidence_identity()|O|f|f|f|f|0' || E'\n' ||
            'bem_core.subject_author|subject_author_append_only|27||bem_core.forbid_update_delete()|O|f|f|f|f|0' || E'\n' ||
            'bem_core.subject_author|subject_author_frozen|7||bem_core.forbid_author_change_after_publish()|O|f|f|f|f|0' || E'\n' ||
            'bem_core.subject|subject_requires_author|21|published_at|bem_core.require_at_least_one_author()|O|t|t|t|t|0'
    THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: определения триггеров разошлись с договором; получено: %s', v_txt;
    END IF;

    -- 15а. Определения тех же девяти триггеров целиком (замечание
    --      C-H115-R15-01). Отпечаток пункта 15 знает об условии WHEN
    --      только «есть или нет», поэтому WHEN (true) его проходил.
    --      Здесь сверяются текст условия, байты аргументов и строка
    --      pg_get_triggerdef при закреплённом пути поиска: без него
    --      имена схем в строке зависят от сеанса. Строки литерала
    --      печатает сверщик раздела 15.11 и сверяет их с каноном.
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog, pg_temp', true);
    SELECT COALESCE(string_agg(fp, E'\n' ORDER BY fp COLLATE "C"), '')
      INTO v_tdef
      FROM (
        SELECT tn.nspname || '.' || tc.relname || '|' || tg.tgname
               || '|' || COALESCE(substring(td.d FROM ' WHEN \((.*)\) EXECUTE FUNCTION '), '')
               || '|' || encode(tg.tgargs, 'hex')
               || '|' || td.d AS fp
          FROM pg_trigger tg
          JOIN pg_class     tc ON tc.oid = tg.tgrelid
          JOIN pg_namespace tn ON tn.oid = tc.relnamespace
          CROSS JOIN LATERAL (SELECT regexp_replace(pg_get_triggerdef(tg.oid, true), '\s+', ' ', 'g') AS d) AS td
         WHERE NOT tg.tgisinternal
           AND tn.nspname = 'bem_core'
           AND tc.relname IN ('audit_record', 'command_log', 'evidence',
                              'subject', 'subject_author')
      ) q;
    PERFORM set_config('search_path', v_path, true);

    IF v_tdef <>
            'bem_core.audit_record|audit_record_append_only|||CREATE TRIGGER audit_record_append_only BEFORE DELETE OR UPDATE ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()' || E'\n' ||
            'bem_core.audit_record|audit_record_head_match|||CREATE TRIGGER audit_record_head_match BEFORE INSERT ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.audit_head_matches_subject()' || E'\n' ||
            'bem_core.audit_record|audit_record_no_self_audit|||CREATE TRIGGER audit_record_no_self_audit BEFORE INSERT ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_self_audit()' || E'\n' ||
            'bem_core.command_log|command_log_append_only|||CREATE TRIGGER command_log_append_only BEFORE DELETE ON bem_core.command_log FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()' || E'\n' ||
            'bem_core.evidence|evidence_append_only|||CREATE TRIGGER evidence_append_only BEFORE DELETE OR UPDATE ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()' || E'\n' ||
            'bem_core.evidence|evidence_identity|||CREATE TRIGGER evidence_identity BEFORE INSERT ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.evidence_identity()' || E'\n' ||
            'bem_core.subject_author|subject_author_append_only|||CREATE TRIGGER subject_author_append_only BEFORE DELETE OR UPDATE ON bem_core.subject_author FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()' || E'\n' ||
            'bem_core.subject_author|subject_author_frozen|||CREATE TRIGGER subject_author_frozen BEFORE INSERT ON bem_core.subject_author FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_author_change_after_publish()' || E'\n' ||
            'bem_core.subject|subject_requires_author|new.published_at IS NOT NULL||CREATE CONSTRAINT TRIGGER subject_requires_author AFTER INSERT OR UPDATE OF published_at ON bem_core.subject DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (new.published_at IS NOT NULL) EXECUTE FUNCTION bem_core.require_at_least_one_author()'
    THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: определения триггеров целиком разошлись с договором; получено: %', v_tdef;
    END IF;

    -- 16. Роль проверки восстановления не имеет доступа к рабочей базе.
    --     Сама роль общая на весь кластер, поэтому проверяется доступ,
    --     а не отсутствие имени (раздел 25.8, пункт 4.8 задания).
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'restore_verifier') THEN
        IF has_database_privilege('restore_verifier', current_database(), 'CONNECT')
           OR has_schema_privilege('restore_verifier', 'bem_control', 'USAGE')
           OR has_schema_privilege('restore_verifier', 'bem_core',    'USAGE') THEN
            RAISE EXCEPTION
              'MIGRATION_FAILED: у роли restore_verifier есть доступ к базе %',
              current_database();
        END IF;
    END IF;

    -- 17. Договор записи выполнен целиком: всё, что нужно телам
    --     функций, действительно выдано. H1.10 проверяла здесь один
    --     список из двенадцати таблиц и не знала ни про участника, ни
    --     про полномочие, ни про доверенность — поэтому пропустила
    --     критический дефект (замечание C-H110-R10-01, факт 4).
    FOREACH v_row IN ARRAY v_dml
    LOOP
        IF split_part(v_row, '|', 4) = '' THEN
            IF NOT has_table_privilege(split_part(v_row, '|', 1),
                                       split_part(v_row, '|', 2),
                                       split_part(v_row, '|', 3)) THEN
                RAISE EXCEPTION
                  'MIGRATION_FAILED: нет права по договору записи: %', v_row;
            END IF;
        ELSE
            IF NOT has_column_privilege(split_part(v_row, '|', 1),
                                        split_part(v_row, '|', 2),
                                        split_part(v_row, '|', 4),
                                        split_part(v_row, '|', 3)) THEN
                RAISE EXCEPTION
                  'MIGRATION_FAILED: нет права по договору записи: %', v_row;
            END IF;
        END IF;
    END LOOP;

    -- 18. И ни одного права записи сверх договора. Владелец таблицы в
    --     счёт не идёт: у него права не выданы, а свои. Права на
    --     колонку и права на всю таблицу считаются отдельно, потому
    --     что в каталоге они лежат в разных местах.
    SELECT count(*) INTO v_cnt
      FROM information_schema.table_privileges p
      JOIN pg_tables t ON t.schemaname = p.table_schema
                      AND t.tablename  = p.table_name
     WHERE p.table_schema   IN ('bem_core', 'bem_control', 'bem_engine')
       AND p.privilege_type IN ('INSERT', 'UPDATE', 'DELETE')
       AND p.grantee <> t.tableowner
       AND (p.grantee || '|' || p.table_schema || '.' || p.table_name
            || '|' || p.privilege_type || '|') <> ALL (v_dml);
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: % прав записи на таблицу сверх договора', v_cnt;
    END IF;

    SELECT count(*) INTO v_cnt
      FROM information_schema.column_privileges c
      JOIN pg_tables t ON t.schemaname = c.table_schema
                      AND t.tablename  = c.table_name
     WHERE c.table_schema   IN ('bem_core', 'bem_control', 'bem_engine')
       AND c.privilege_type IN ('INSERT', 'UPDATE', 'DELETE')
       AND c.grantee <> t.tableowner
       AND (c.grantee || '|' || c.table_schema || '.' || c.table_name
            || '|' || c.privilege_type || '|' || c.column_name) <> ALL (v_dml)
       AND (c.grantee || '|' || c.table_schema || '.' || c.table_name
            || '|' || c.privilege_type || '|') <> ALL (v_dml);
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: % прав записи на колонку сверх договора', v_cnt;
    END IF;

    -- 19. Служебный заказчик один и тот же в функции и в строке.
    --     H1.10 держала этот номер в шести местах, и разойтись им
    --     ничто не мешало (замечание C-H110-R10-01).
    IF NOT EXISTS (SELECT 1 FROM bem_core.tenant
                    WHERE id = bem_control.service_tenant()
                      AND name = 'service') THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: строки служебного заказчика нет или у неё другое имя';
    END IF;

    -- 20. Права доступа целиком: что стоит в каталоге сейчас (R32,
    --     замечание M-H116-R16-02). Проверки 17 и 18 знают только три
    --     права записи. Прежние пункты 20–22 сверяли получателя и право,
    --     но не выдавшего и не число повторов: одно и то же право,
    --     выданное двумя ролями, или строка договора, записанная дважды,
    --     проходили молча. Теперь каталог читается целиком в шести
    --     списках: база, схемы, таблицы и последовательности, столбцы,
    --     функции и процедуры, права по умолчанию. Строка — «вид |
    --     объект | получатель | право | выдавший»; у записи прав по
    --     умолчанию перед получателем стоят роль и схема. Звёздочка
    --     после права означает право передавать его дальше: в каноне
    --     такой выдачи нет, и любая звёздочка — лишнее право.
    --
    --     Системные схемы исключены, а рабочие НЕ перечислены поимённо:
    --     право, выданное в неожиданной схеме, обязано попасть в
    --     разницу, а не выпасть из рассмотрения вместе со схемой. Запрос
    --     тот же, что в шаге 10 файла 05, слово в слово: сверщик
    --     раздела 15.11 требует, чтобы они совпадали.
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog', true);
    WITH nsp AS (
        SELECT oid, nspname FROM pg_namespace
         WHERE nspname NOT IN ('pg_catalog', 'information_schema')
           AND nspname NOT LIKE 'pg\_toast%'
           AND nspname NOT LIKE 'pg\_temp%'
    ), got AS (
        SELECT 'SCHEMA|' || n.nspname || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text) AS r
          FROM nsp n
          JOIN pg_namespace pn ON pn.oid = n.oid
          CROSS JOIN LATERAL aclexplode(pn.nspacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
        UNION ALL
        SELECT 'DATABASE|' || d.datname || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_database d
          CROSS JOIN LATERAL aclexplode(d.datacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
         WHERE d.datname = current_database()
        UNION ALL
        SELECT CASE WHEN c.relkind = 'S' THEN 'SEQUENCE|' ELSE 'TABLE|' END
               || n.nspname || '.' || c.relname || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_class c
          JOIN nsp n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(c.relacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
         WHERE c.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
        UNION ALL
        SELECT 'COLUMN|' || n.nspname || '.' || c.relname || '.' || att.attname || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_attribute att
          JOIN pg_class c ON c.oid = att.attrelid
          JOIN nsp n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(att.attacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
        UNION ALL
        SELECT 'FUNCTION|' || n.nspname || '.' || p.proname
               || '(' || oidvectortypes(p.proargtypes) || ')|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_proc p
          JOIN nsp n ON n.oid = p.pronamespace
          CROSS JOIN LATERAL aclexplode(p.proacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
        UNION ALL
        SELECT 'DEFAULT|' || o.rolname || '|' || coalesce(dn.nspname, '-') || '|'
               || d.defaclobjtype::text || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_default_acl d
          JOIN pg_roles o ON o.oid = d.defaclrole
          LEFT JOIN pg_namespace dn ON dn.oid = d.defaclnamespace
          CROSS JOIN LATERAL aclexplode(d.defaclacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
    )
    SELECT coalesce(array_agg(r ORDER BY r COLLATE "C"), ARRAY[]::text[])
      INTO v_acl_got FROM got;
    PERFORM set_config('search_path', v_path, true);

    -- 21. Восемь строк прав четырёх функций окна резервного копирования
    --     — «все или ни одной». Эти функции создаёт файл 04, то есть
    --     после этой проверки, а файл 01 можно прогнать повторно и после
    --     него (раздел 26.8). До файла 04 строк нет совсем, после него
    --     они есть целиком. Часть строк — расхождение: окно наполовину
    --     выдано или наполовину снято.
    SELECT count(*) INTO v_cnt
      FROM unnest(v_acl_04) AS r
     WHERE r = ANY (v_acl_got);
    IF v_cnt NOT IN (0, cardinality(v_acl_04)) THEN
        RAISE EXCEPTION
          'MIGRATION_FAILED: права функций окна выданы не целиком: % из %',
          v_cnt, cardinality(v_acl_04);
    END IF;
    IF v_cnt = 0 THEN
        v_acl_want := v_acl;
    ELSE
        v_acl_want := v_acl || v_acl_04;
    END IF;

    -- 22. Сравнение с учётом повторов: у каждой строки считается, сколько
    --     раз она стоит в каталоге и сколько в договоре. Лишнее — где в
    --     каталоге больше, недостающее — где больше в договоре. Число
    --     после x в отказе — на сколько разошлись. EXCEPT сводил
    --     одинаковые строки в одну, и повтор проходил молча.
    SELECT count(*), left(coalesce(string_agg(x.r || ' x' || (x.n_got - x.n_want), ', '
                                              ORDER BY x.r COLLATE "C"), ''), 600)
      INTO v_cnt, v_got
      FROM (SELECT coalesce(g.r, w.r) AS r, coalesce(g.n, 0) AS n_got, coalesce(w.n, 0) AS n_want
              FROM (SELECT r, count(*) AS n FROM unnest(v_acl_got) AS r GROUP BY r) g
              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl_want) AS r GROUP BY r) w
                ON w.r = g.r) x
     WHERE x.n_got > x.n_want;
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: прав сверх договора %: %', v_cnt, v_got;
    END IF;
    SELECT count(*), left(coalesce(string_agg(x.r || ' x' || (x.n_want - x.n_got), ', '
                                              ORDER BY x.r COLLATE "C"), ''), 600)
      INTO v_cnt, v_got
      FROM (SELECT coalesce(g.r, w.r) AS r, coalesce(g.n, 0) AS n_got, coalesce(w.n, 0) AS n_want
              FROM (SELECT r, count(*) AS n FROM unnest(v_acl_got) AS r GROUP BY r) g
              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl_want) AS r GROUP BY r) w
                ON w.r = g.r) x
     WHERE x.n_want > x.n_got;
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: объявленных прав нет %: %', v_cnt, v_got;
    END IF;

    -- 22а. Кто выдал право (замечание M-H115-R15-01). До раунда R32
    --      пункты 20–22 не смотрели, КТО право выдал; теперь выдавший
    --      стоит в каждой строке договора, а этот пункт остаётся
    --      отдельным правилом и от содержимого договора не зависит.
    --      В каноне каждое право выдаёт владелец объекта: выдачу и
    --      суперпользователем, и членом роли-владельца сервер
    --      записывает от имени владельца, а смена владельца переписывает
    --      выдавшего. Иной выдавший появляется только через право
    --      передавать право дальше, а его в каноне нет ни одного.
    --      Поэтому правило одно на все шесть видов списков прав: база,
    --      схемы, таблицы и последовательности, столбцы, функции и права
    --      по умолчанию. Выдавший равен владельцу, у записи прав по
    --      умолчанию — роли, для которой запись заведена, и права
    --      передавать дальше нет ни у кого.
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog, pg_temp', true);
    WITH nsp AS (
        SELECT oid, nspname, nspowner, nspacl FROM pg_namespace
         WHERE nspname NOT IN ('pg_catalog', 'information_schema')
           AND nspname NOT LIKE 'pg\_toast%'
           AND nspname NOT LIKE 'pg\_temp%'
    ), items AS (
        SELECT 'база ' || d.datname AS obj, d.datdba AS owner, a.grantor, a.is_grantable
          FROM pg_database d
          CROSS JOIN LATERAL aclexplode(d.datacl) a
         WHERE d.datname = current_database()
        UNION ALL
        SELECT 'схема ' || n.nspname, n.nspowner, a.grantor, a.is_grantable
          FROM nsp n
          CROSS JOIN LATERAL aclexplode(n.nspacl) a
        UNION ALL
        SELECT 'отношение ' || n.nspname || '.' || c.relname, c.relowner, a.grantor, a.is_grantable
          FROM pg_class c
          JOIN nsp n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(c.relacl) a
        UNION ALL
        SELECT 'столбец ' || n.nspname || '.' || c.relname || '.' || att.attname,
               c.relowner, a.grantor, a.is_grantable
          FROM pg_attribute att
          JOIN pg_class c ON c.oid = att.attrelid
          JOIN nsp n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(att.attacl) a
        UNION ALL
        SELECT 'функция ' || n.nspname || '.' || p.proname
               || '(' || oidvectortypes(p.proargtypes) || ')',
               p.proowner, a.grantor, a.is_grantable
          FROM pg_proc p
          JOIN nsp n ON n.oid = p.pronamespace
          CROSS JOIN LATERAL aclexplode(p.proacl) a
        UNION ALL
        SELECT 'права по умолчанию ' || r.rolname || ' ' || coalesce(dn.nspname, '-')
               || ' ' || d.defaclobjtype::text,
               d.defaclrole, a.grantor, a.is_grantable
          FROM pg_default_acl d
          JOIN pg_roles r ON r.oid = d.defaclrole
          LEFT JOIN pg_namespace dn ON dn.oid = d.defaclnamespace
          CROSS JOIN LATERAL aclexplode(d.defaclacl) a
    )
    SELECT i.obj || ' | выдал ' || coalesce(g.rolname, i.grantor::text)
           || ' | владелец ' || coalesce(o.rolname, i.owner::text)
           || CASE WHEN i.is_grantable THEN ' | с правом передачи' ELSE '' END
      INTO v_row
      FROM items i
      LEFT JOIN pg_roles g ON g.oid = i.grantor
      LEFT JOIN pg_roles o ON o.oid = i.owner
     WHERE i.grantor <> i.owner OR i.is_grantable
     ORDER BY 1
     LIMIT 1;
    PERFORM set_config('search_path', v_path, true);
    IF v_row IS NOT NULL THEN
        RAISE EXCEPTION 'MIGRATION_FAILED: право выдано не владельцем: %', v_row;
    END IF;

    -- 23. Каждая обязательная строка чтения действительно выдана.
    --     H1.12 использовала договор чтения только как разрешающий
    --     набор: лишнее ловилось, снятое — нет. Поздний REVOKE снимал
    --     чтение, и живая проверка молчала (замечание M-H112-R12-01).
    FOREACH v_row IN ARRAY v_read LOOP
        v_who   := split_part(v_row, '|', 1);
        v_obj   := split_part(v_row, '|', 2);
        v_priv  := split_part(v_row, '|', 3);
        v_okind := split_part(v_obj, ':', 1);
        v_oname := split_part(v_obj, ':', 2);
        IF v_okind = 'DATABASE' THEN
            v_ok := has_database_privilege(v_who, v_oname, v_priv);
        ELSIF v_okind = 'SCHEMA' THEN
            v_ok := has_schema_privilege(v_who, v_oname, v_priv);
        ELSIF v_okind = 'TABLE' THEN
            v_ok := has_table_privilege(v_who, v_oname::regclass, v_priv);
        ELSIF v_okind = 'DEFTABLES' OR v_okind = 'DEFSEQUENCES' THEN
            v_ok := EXISTS (
                SELECT 1 FROM pg_default_acl d
                  JOIN pg_namespace n ON n.oid = d.defaclnamespace
                  CROSS JOIN LATERAL aclexplode(d.defaclacl) a
                  JOIN pg_roles r ON r.oid = a.grantee
                 WHERE n.nspname = v_oname
                   AND d.defaclobjtype = CASE WHEN v_okind = 'DEFTABLES'
                                              THEN 'r' ELSE 'S' END
                   AND r.rolname = v_who
                   AND a.privilege_type = v_priv);
        ELSIF v_okind = 'ALLTABLES' OR v_okind = 'ALLSEQUENCES' THEN
            -- Право «на все таблицы» в пустой схеме не доказывает
            -- ничего: проверять нечего, и строка прошла бы сама собой.
            -- Схема bem_engine на этот момент пуста именно так. Для
            -- пустой схемы требуется отложенное право: оно и есть
            -- единственная защита её будущих таблиц.
            SELECT count(*) INTO v_cnt
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = v_oname
               AND ((v_okind = 'ALLTABLES'    AND c.relkind IN ('r', 'p'))
                 OR (v_okind = 'ALLSEQUENCES' AND c.relkind = 'S'));
            IF v_cnt = 0 THEN
                v_ok := EXISTS (
                    SELECT 1 FROM pg_default_acl d
                      JOIN pg_namespace n ON n.oid = d.defaclnamespace
                      CROSS JOIN LATERAL aclexplode(d.defaclacl) a
                      JOIN pg_roles r ON r.oid = a.grantee
                     WHERE n.nspname = v_oname
                       AND d.defaclobjtype = CASE WHEN v_okind = 'ALLTABLES'
                                                  THEN 'r' ELSE 'S' END
                       AND r.rolname = v_who
                       AND a.privilege_type = v_priv);
            ELSE
                v_ok := NOT EXISTS (
                    SELECT 1 FROM pg_class c
                      JOIN pg_namespace n ON n.oid = c.relnamespace
                     WHERE n.nspname = v_oname
                       AND ((v_okind = 'ALLTABLES'    AND c.relkind IN ('r', 'p'))
                         OR (v_okind = 'ALLSEQUENCES' AND c.relkind = 'S'))
                       AND NOT (CASE WHEN v_okind = 'ALLTABLES'
                                     THEN has_table_privilege(v_who, c.oid, v_priv)
                                     ELSE has_sequence_privilege(v_who, c.oid, v_priv)
                                END));
            END IF;
        ELSE
            v_ok := false;
        END IF;
        IF NOT v_ok THEN
            RAISE EXCEPTION
              'MIGRATION_FAILED: обязательного права чтения нет: %', v_row;
        END IF;
    END LOOP;

    -- 24. Каждый обязательный вызов выдан точному получателю, и
    --     функция найдена по ПОЛНОЙ подписи, а не по имени. Две
    --     функции с одним именем и разными аргументами — разные
    --     функции, и подменённая проходила бы проверку по имени.
    --     Путь поиска на время сверки сведён к системному каталогу:
    --     иначе собственный тип печатается без схемы и подпись не
    --     совпадает с договором.
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog', true);
    FOREACH v_row IN ARRAY v_exec LOOP
        v_sig := split_part(v_row, '|', 1);
        v_who := split_part(v_row, '|', 2);
        SELECT p.oid INTO v_oid
          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname || '.' || p.proname || '('
               || oidvectortypes(p.proargtypes) || ')' = v_sig;
        IF v_oid IS NULL THEN
            RAISE EXCEPTION
              'MIGRATION_FAILED: функции с такой подписью нет: %', v_sig;
        END IF;
        IF NOT has_function_privilege(v_who, v_oid, 'EXECUTE') THEN
            RAISE EXCEPTION
              'MIGRATION_FAILED: обязательного вызова нет: % -> %', v_sig, v_who;
        END IF;
    END LOOP;
    PERFORM set_config('search_path', v_path, true);
END
$$;

-- BEM954-FINAL-SECURITY-CHECKPOINT: 01_database_migration.sql
-- Ниже этой строки не должно быть ни одной команды, меняющей роль,
-- членство, владельца или право. Это проверяет статический сверщик
-- раздела 15.11: команда после маркера — расхождение, а не мелочь.

