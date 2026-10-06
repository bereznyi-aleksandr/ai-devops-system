-- 02_upgrade_to_h110.sql
-- Запуск: только через обёртку окна мигратора (раздел 25.7):
--   node run_migration.mjs --files 02_upgrade_to_h110.sql,01_database_migration.sql
-- Сам файл окна не открывает и не закрывает.
-- Своей транзакции у файла тоже нет: её открывает psql ключом
-- --single-transaction, и она общая с файлом 01. Поэтому успешный 02
-- при отказавшем 01 не оставляет базу в промежуточной форме
-- (пункт 4.3 задания).

-- Отказ вне транзакции: курсор без WITH HOLD вне транзакции даёт
-- ошибку 25P01 «DECLARE CURSOR can only be used in transaction blocks».
DECLARE bem_upgrade_guard CURSOR FOR SELECT 1;
CLOSE bem_upgrade_guard;

-- ---------------------------------------------------------------
-- Шаг 0. Предусловие: база действительно в одной из прошлых форм
-- ---------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM bem_core.schema_migration
                    WHERE version IN ('bem954-h1-6-baseline',
                                      'bem954-h1-7-baseline',
                                      'bem954-h1-7-shape',
                                      'bem954-h1-8-baseline',
                                      'bem954-h1-8-shape',
                                      'bem954-h1-9-baseline',
                                      'bem954-h1-9-shape')) THEN
        RAISE EXCEPTION
          'UPGRADE_REFUSED: нет отметки прошлой формы; для пустой базы нужен раздел 26';
    END IF;
END
$$;

SET ROLE bem_core_owner;

-- ---------------------------------------------------------------
-- Шаг 1. Столбцы прошлой редакции. IF NOT EXISTS делает шаг
--        повторяемым и безвредным для базы, где они уже есть.
-- ---------------------------------------------------------------
ALTER TABLE bem_core.subject
    ADD COLUMN IF NOT EXISTS disagreement_at     timestamptz,
    ADD COLUMN IF NOT EXISTS disagreement_reason text;

ALTER TABLE bem_core.handoff_packet
    ADD COLUMN IF NOT EXISTS packet_sha256 text,
    ADD COLUMN IF NOT EXISTS accepted_at   timestamptz;

ALTER TABLE bem_core.work_item
    ADD COLUMN IF NOT EXISTS process_instance_id text;

-- ---------------------------------------------------------------
-- Шаг 2. Новые столбцы ящика исходящих
-- ---------------------------------------------------------------
ALTER TABLE bem_core.outbox
    ADD COLUMN IF NOT EXISTS idempotency_key    text,
    ADD COLUMN IF NOT EXISTS dead_lettered_at   timestamptz,
    ADD COLUMN IF NOT EXISTS dead_letter_reason text,
    ADD COLUMN IF NOT EXISTS reconciled_at      timestamptz,
    ADD COLUMN IF NOT EXISTS reconciled_outcome text;

-- ---------------------------------------------------------------
-- Шаг 3. Заполнение ключа повтора у существующих строк.
--
--        Значение НЕ выдумывается. Функция перехода вычисляет ключ
--        ровно так же — сумма SHA-256 от текста идентификатора
--        команды (раздел 26.5, шаг 4). Поэтому любой проверяющий
--        может пересчитать ключ любой строки и сверить его.
--
--        Защита строк временно снимается с владельца и тут же
--        возвращается. Иначе владелец не увидел бы ни одной строки:
--        у него нет признака BYPASSRLS, а заказчик в этом сеансе
--        не задан. Обратная команда стоит в том же шаге и в той же
--        транзакции, а файл 01 проверяет признак ещё раз.
-- ---------------------------------------------------------------
ALTER TABLE bem_core.outbox NO FORCE ROW LEVEL SECURITY;

UPDATE bem_core.outbox
   SET idempotency_key = encode(sha256(convert_to(command_id::text, 'UTF8')), 'hex')
 WHERE idempotency_key IS NULL;

ALTER TABLE bem_core.outbox FORCE ROW LEVEL SECURITY;

ALTER TABLE bem_core.outbox ALTER COLUMN idempotency_key SET NOT NULL;

-- ---------------------------------------------------------------
-- Шаг 4. Ограничения ящика. У ADD CONSTRAINT нет IF NOT EXISTS,
--        поэтому наличие проверяется по системному каталогу.
-- ---------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'outbox_idempotency_key_check'
                      AND conrelid = 'bem_core.outbox'::regclass) THEN
        ALTER TABLE bem_core.outbox
            ADD CONSTRAINT outbox_idempotency_key_check
            CHECK (idempotency_key ~ '^[0-9a-f]{64}$');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'outbox_idem_uniq'
                      AND conrelid = 'bem_core.outbox'::regclass) THEN
        ALTER TABLE bem_core.outbox
            ADD CONSTRAINT outbox_idem_uniq
            UNIQUE (tenant_id, kind, idempotency_key);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'outbox_reconciled_outcome_check'
                      AND conrelid = 'bem_core.outbox'::regclass) THEN
        ALTER TABLE bem_core.outbox
            ADD CONSTRAINT outbox_reconciled_outcome_check
            CHECK (reconciled_outcome IN ('CONFIRMED_SENT', 'CONFIRMED_NOT_SENT',
                                         'UNRESOLVED'));
    END IF;

    -- Список состояний расширяется двумя новыми. Старая проверка
    -- снимается и тут же заменяется более широкой, в той же
    -- транзакции: ни одна строка при этом не теряется и ни на
    -- мгновение таблица не остаётся без проверки состояния.
    IF EXISTS (SELECT 1 FROM pg_constraint
                WHERE conname = 'outbox_status_check'
                  AND conrelid = 'bem_core.outbox'::regclass
                  AND pg_get_constraintdef(oid) NOT LIKE '%DEAD_LETTER%') THEN
        ALTER TABLE bem_core.outbox DROP CONSTRAINT outbox_status_check;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'outbox_status_check'
                      AND conrelid = 'bem_core.outbox'::regclass) THEN
        ALTER TABLE bem_core.outbox
            ADD CONSTRAINT outbox_status_check
            CHECK (status IN ('PENDING', 'LEASED', 'SENT', 'FAILED',
                              'UNKNOWN_OUTCOME', 'DEAD_LETTER'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'work_item_process_instance_uniq'
                      AND conrelid = 'bem_core.work_item'::regclass) THEN
        ALTER TABLE bem_core.work_item
            ADD CONSTRAINT work_item_process_instance_uniq
            UNIQUE (process_instance_id);
    END IF;
END
$$;

-- ---------------------------------------------------------------
-- Шаг 5. Журнал команд. Таблицы здесь не создаются: если её ещё
--        нет, её создаст файл 01 уже в новой форме. Менять форму
--        нужно только у таблицы, которая существует.
-- ---------------------------------------------------------------
DO $$
DECLARE
    v_exists boolean := to_regclass('bem_core.command_log') IS NOT NULL;
BEGIN
    IF NOT v_exists THEN
        RETURN;
    END IF;

    ALTER TABLE bem_core.command_log ADD COLUMN IF NOT EXISTS has_outbox boolean;

    -- Значение выводится из самой строки: внешнее действие было
    -- тогда и только тогда, когда у команды есть ссылка на ящик.
    ALTER TABLE bem_core.command_log NO FORCE ROW LEVEL SECURITY;
    UPDATE bem_core.command_log
       SET has_outbox = (outbox_id IS NOT NULL)
     WHERE has_outbox IS NULL;
    ALTER TABLE bem_core.command_log FORCE ROW LEVEL SECURITY;

    ALTER TABLE bem_core.command_log ALTER COLUMN has_outbox SET NOT NULL;

    -- Вид внешнего действия перестаёт быть обязательным: переход
    -- без внешнего действия его не имеет (замечание M-H17-R7-09).
    ALTER TABLE bem_core.command_log ALTER COLUMN kind DROP NOT NULL;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'command_log_kind_agrees'
                      AND conrelid = 'bem_core.command_log'::regclass) THEN
        ALTER TABLE bem_core.command_log
            ADD CONSTRAINT command_log_kind_agrees
            CHECK ((has_outbox AND kind IS NOT NULL) OR
                   (NOT has_outbox AND kind IS NULL AND outbox_id IS NULL));
    END IF;
END
$$;

-- ---------------------------------------------------------------
-- Шаг 6. Функция заказчика. Без неё следующий шаг не выполнится.
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION bem_core.current_tenant()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = pg_catalog, pg_temp
AS $$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$;

-- ---------------------------------------------------------------
-- Шаг 7. Сумма пакета передачи.
--        Пересчитать её у старых строк нельзя: сумма считается по
--        файлу заметок, а файла в базе нет. Поэтому порядок такой.
--        Сначала триггер: он запрещает НОВУЮ строку без суммы
--        и на старые строки не смотрит. Затем проверка: если строк
--        без суммы нет, столбец становится обязательным, и форма
--        обновлённой базы совпадает с чистой установкой раздела 26.
--        Тогда же снимается и сам триггер вместе с его функцией:
--        при обязательном столбце он не нужен, а лишний триггер
--        и лишняя функция — это уже другая форма базы.
--        Если строки без суммы есть, столбец остаётся
--        необязательным, а триггер — на месте. Это одно из двух
--        известных расхождений формы между обновлённой и чистой
--        базой; второе — необязательные session_role и identity_mode
--        у доказательств, написанных до H1.9 (шаг 10, предупреждение
--        EVIDENCE_IDENTITY_LEGACY_ROWS); второе видно вживую (R43, отчёт 107).
--        базой. Молча оно не проходит: миграция печатает
--        предупреждение с числом таких строк.
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION bem_core.handoff_requires_sha()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF NEW.packet_sha256 IS NULL THEN
        RAISE EXCEPTION 'HANDOFF_SHA_REQUIRED: пакет передачи без суммы не принимается';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS handoff_requires_sha ON bem_core.handoff_packet;
CREATE TRIGGER handoff_requires_sha
    BEFORE INSERT ON bem_core.handoff_packet
    FOR EACH ROW EXECUTE FUNCTION bem_core.handoff_requires_sha();

-- FORCE RLS распространяется и на владельца, поэтому счётный запрос
-- временно снимается с принудительного режима — ровно как в шаге 3.
-- Всё это одна транзакция: открытого окна не возникает.
ALTER TABLE bem_core.handoff_packet NO FORCE ROW LEVEL SECURITY;

DO $$
DECLARE
    v_nulls bigint;
BEGIN
    SELECT count(*) INTO v_nulls
      FROM bem_core.handoff_packet
     WHERE packet_sha256 IS NULL;

    IF v_nulls = 0 THEN
        ALTER TABLE bem_core.handoff_packet
            ALTER COLUMN packet_sha256 SET NOT NULL;

        DROP TRIGGER IF EXISTS handoff_requires_sha ON bem_core.handoff_packet;
        DROP FUNCTION IF EXISTS bem_core.handoff_requires_sha();
    ELSE
        RAISE WARNING 'HANDOFF_SHA_LEGACY_ROWS: % строк пакетов передачи без суммы; столбец остаётся необязательным, новые строки без суммы запрещены триггером', v_nulls;
    END IF;
END
$$;

ALTER TABLE bem_core.handoff_packet FORCE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------
-- Шаг 8. Перевод политик на одно выражение.
--        ALTER POLICY меняет условие и НЕ удаляет политику:
--        промежутка, когда таблица открыта, не возникает.
--        Таблицы, которых ещё нет, пропускаются: их создаст
--        файл 01 и сам же заведёт им политику.
-- ---------------------------------------------------------------
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['work_item', 'evidence', 'subject', 'subject_author',
                             'audit_record', 'outbox', 'command_log', 'usage_record',
                             'handoff_packet', 'user_tenant_membership',
                             'audit_assignment']
    LOOP
        CONTINUE WHEN to_regclass('bem_core.' || t) IS NULL;

        EXECUTE format('ALTER TABLE bem_core.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE bem_core.%I FORCE  ROW LEVEL SECURITY', t);

        IF EXISTS (SELECT 1 FROM pg_policies
                    WHERE schemaname = 'bem_core' AND tablename = t
                      AND policyname = 'tenant_isolation') THEN
            EXECUTE format(
                'ALTER POLICY tenant_isolation ON bem_core.%I TO public'
                ' USING (tenant_id = bem_core.current_tenant())'
                ' WITH CHECK (tenant_id = bem_core.current_tenant())', t);
        ELSE
            EXECUTE format(
                'CREATE POLICY tenant_isolation ON bem_core.%I'
                ' USING (tenant_id = bem_core.current_tenant())'
                ' WITH CHECK (tenant_id = bem_core.current_tenant())', t);
        END IF;
    END LOOP;
END
$$;

-- ---------------------------------------------------------------
-- Шаг 9. Отзыв широких прав ядра. GRANT права не сужает —
--        нужен именно REVOKE, иначе прошлое право останется.
-- ---------------------------------------------------------------
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA bem_core FROM bem_kernel_rw;

ALTER DEFAULT PRIVILEGES FOR ROLE bem_core_owner IN SCHEMA bem_core
    REVOKE INSERT, UPDATE ON TABLES FROM bem_kernel_rw;

-- H1.8 возвращал ядру право вставлять доказательства этой строкой.
-- Она убрана: право позволяло общей рабочей роли подписать
-- доказательство любым участником (замечание C-H18-R8-05).
-- Доказательства пишет функция bem_control.record_evidence, личность
-- проставляет триггер bem_core.evidence_identity.

-- ---------------------------------------------------------------
-- Шаг 10. Столбцы и ограничения редакции H1.9.
--         Таблиц здесь по-прежнему не создаётся: таблицу полномочий
--         создаёт файл 01, который идёт следом в той же транзакции.
-- ---------------------------------------------------------------
SET ROLE bem_core_owner;

-- 10.1. Связь участника с ролью входа (замечание C-H18-R8-05)
ALTER TABLE bem_core.actor ADD COLUMN IF NOT EXISTS db_role name;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname  = 'actor_db_role_uniq'
                      AND conrelid = 'bem_core.actor'::regclass) THEN
        ALTER TABLE bem_core.actor
              ADD CONSTRAINT actor_db_role_uniq UNIQUE (db_role);
    END IF;
END
$$;

-- 10.2. Личность в доказательстве: роль входа и способ её установления.
--       Старым строкам значения не выдумываются: откуда они взялись,
--       теперь не установить. Умолчание действует только для новых
--       строк, а обязательность включается, лишь когда пустых нет.
ALTER TABLE bem_core.evidence ADD COLUMN IF NOT EXISTS session_role  name;
ALTER TABLE bem_core.evidence ADD COLUMN IF NOT EXISTS identity_mode text;

ALTER TABLE bem_core.evidence ALTER COLUMN session_role  SET DEFAULT session_user;
ALTER TABLE bem_core.evidence ALTER COLUMN identity_mode SET DEFAULT 'DELEGATED';

DO $$
DECLARE
    v_cnt integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname  = 'evidence_identity_mode_check'
                      AND conrelid = 'bem_core.evidence'::regclass) THEN
        ALTER TABLE bem_core.evidence
              ADD CONSTRAINT evidence_identity_mode_check
              CHECK (identity_mode IN ('BOUND', 'DELEGATED'));
    END IF;

    -- Защита строк снимается с владельца ровно на один подсчёт и
    -- возвращается в том же блоке: без этого владелец не увидел бы
    -- ни одной строки (у него нет BYPASSRLS, заказчик не задан).
    ALTER TABLE bem_core.evidence NO FORCE ROW LEVEL SECURITY;

    SELECT count(*) INTO v_cnt
      FROM bem_core.evidence
     WHERE session_role IS NULL OR identity_mode IS NULL;

    IF v_cnt = 0 THEN
        ALTER TABLE bem_core.evidence ALTER COLUMN session_role  SET NOT NULL;
        ALTER TABLE bem_core.evidence ALTER COLUMN identity_mode SET NOT NULL;
    ELSE
        RAISE WARNING
          'EVIDENCE_IDENTITY_LEGACY_ROWS: % строк доказательств написаны до H1.9;'
          ' у них нет роли входа и способа установления личности.'
          ' Столбцы остаются необязательными, у новых строк их проставляет'
          ' триггер evidence_identity. Чистая установка получает их сразу'
          ' обязательными (раздел 26)', v_cnt;
    END IF;

    -- Связь доказательства с участником. Если в старых строках есть
    -- имена, которых нет в справочнике участников, связь добавляется
    -- непроверенной: она действует для новых строк, а старые остаются
    -- как есть и видны в каталоге признаком NOT VALID.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname  = 'evidence_actor_fk'
                      AND conrelid = 'bem_core.evidence'::regclass) THEN
        SELECT count(*) INTO v_cnt
          FROM bem_core.evidence e
         WHERE NOT EXISTS (SELECT 1 FROM bem_core.actor a
                            WHERE a.actor_id = e.actor_id);

        IF v_cnt = 0 THEN
            ALTER TABLE bem_core.evidence
                  ADD CONSTRAINT evidence_actor_fk FOREIGN KEY (actor_id)
                  REFERENCES bem_core.actor (actor_id);
        ELSE
            ALTER TABLE bem_core.evidence
                  ADD CONSTRAINT evidence_actor_fk FOREIGN KEY (actor_id)
                  REFERENCES bem_core.actor (actor_id) NOT VALID;
            RAISE WARNING
              'EVIDENCE_ACTOR_UNKNOWN_ROWS: % строк доказательств ссылаются на'
              ' участников, которых нет в справочнике. Связь добавлена как'
              ' NOT VALID: новые строки проверяются, старые остаются.'
              ' Когда участники будут заведены, выполните'
              ' ALTER TABLE bem_core.evidence VALIDATE CONSTRAINT evidence_actor_fk',
              v_cnt;
        END IF;
    END IF;

    ALTER TABLE bem_core.evidence FORCE ROW LEVEL SECURITY;
END
$$;

-- 10.3. Время следующей попытки в ящике (замечание C-H18-R8-03).
--       Значение не выдумывается: у существующих строк оно равно
--       времени создания, то есть «готова к отправке немедленно».
ALTER TABLE bem_core.outbox ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz;
ALTER TABLE bem_core.outbox ALTER COLUMN next_attempt_at SET DEFAULT now();

ALTER TABLE bem_core.outbox NO FORCE ROW LEVEL SECURITY;

UPDATE bem_core.outbox
   SET next_attempt_at = created_at
 WHERE next_attempt_at IS NULL;

ALTER TABLE bem_core.outbox FORCE ROW LEVEL SECURITY;

ALTER TABLE bem_core.outbox ALTER COLUMN next_attempt_at SET NOT NULL;

-- 10.4. Версия отпечатка команды (замечание M-H18-R8-01).
--       Старые строки посчитаны версией 1 — это факт, а не догадка:
--       другой кодировки на момент их записи не существовало.
DO $$
BEGIN
    -- Таблицы может не быть: на форме H1.6 её не существовало.
    IF to_regclass('bem_core.command_log') IS NULL THEN RETURN; END IF;

    ALTER TABLE bem_core.command_log
          ADD COLUMN IF NOT EXISTS fingerprint_version smallint;
    ALTER TABLE bem_core.command_log
          ALTER COLUMN fingerprint_version SET DEFAULT 2;

    ALTER TABLE bem_core.command_log NO FORCE ROW LEVEL SECURITY;

    UPDATE bem_core.command_log
       SET fingerprint_version = 1
     WHERE fingerprint_version IS NULL;

    ALTER TABLE bem_core.command_log FORCE ROW LEVEL SECURITY;

    ALTER TABLE bem_core.command_log
          ALTER COLUMN fingerprint_version SET NOT NULL;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname  = 'command_log_fingerprint_version_check'
                      AND conrelid = 'bem_core.command_log'::regclass) THEN
        ALTER TABLE bem_core.command_log
              ADD CONSTRAINT command_log_fingerprint_version_check
              CHECK (fingerprint_version IN (1, 2));
    END IF;
END
$$;

-- 10.5. Кто принял пакет передачи (замечание M-H18-R8-05).
--       Значение выводится из уже записанного доказательства
--       HANDOFF_ACCEPTED, а не придумывается. Если доказательства нет,
--       поле остаётся пустым, и парное ограничение добавляется
--       непроверенным.
ALTER TABLE bem_core.handoff_packet
      ADD COLUMN IF NOT EXISTS accepted_by bem_core.actor_id;

DO $$
DECLARE
    v_cnt integer;
BEGIN
    ALTER TABLE bem_core.handoff_packet NO FORCE ROW LEVEL SECURITY;
    ALTER TABLE bem_core.evidence       NO FORCE ROW LEVEL SECURITY;

    UPDATE bem_core.handoff_packet h
       SET accepted_by = e.actor_id
      FROM bem_core.evidence e
     WHERE h.accepted_at IS NOT NULL
       AND h.accepted_by IS NULL
       AND e.kind        = 'HANDOFF_ACCEPTED'
       AND e.tenant_id   = h.tenant_id
       AND e.payload->>'work_item_id' ~ '^[0-9a-fA-F-]{36}$'
       AND e.payload->>'handoff_no'   ~ '^[0-9]+$'
       AND (e.payload->>'work_item_id')::uuid    = h.work_item_id
       AND (e.payload->>'handoff_no')::integer   = h.handoff_no;

    SELECT count(*) INTO v_cnt
      FROM bem_core.handoff_packet
     WHERE accepted_at IS NOT NULL AND accepted_by IS NULL;

    ALTER TABLE bem_core.evidence       FORCE ROW LEVEL SECURITY;
    ALTER TABLE bem_core.handoff_packet FORCE ROW LEVEL SECURITY;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname  = 'handoff_packet_accepted_pair'
                      AND conrelid = 'bem_core.handoff_packet'::regclass) THEN
        IF v_cnt = 0 THEN
            ALTER TABLE bem_core.handoff_packet
                  ADD CONSTRAINT handoff_packet_accepted_pair CHECK (
                      (accepted_at IS NULL     AND accepted_by IS NULL) OR
                      (accepted_at IS NOT NULL AND accepted_by IS NOT NULL));
        ELSE
            ALTER TABLE bem_core.handoff_packet
                  ADD CONSTRAINT handoff_packet_accepted_pair CHECK (
                      (accepted_at IS NULL     AND accepted_by IS NULL) OR
                      (accepted_at IS NOT NULL AND accepted_by IS NOT NULL)) NOT VALID;
            RAISE WARNING
              'HANDOFF_ACCEPTED_BY_UNKNOWN: у % принятых пакетов не нашлось'
              ' доказательства HANDOFF_ACCEPTED, поэтому принявший неизвестен.'
              ' Парное ограничение добавлено как NOT VALID и действует для'
              ' новых строк', v_cnt;
        END IF;
    END IF;

    -- H1.24, дефект D12 живого прогона R43: чистая установка (раздел 26)
    -- объявляет accepted_by со ссылкой на участника, а шаг 10.5 добавлял
    -- столбец без неё. Имена вне справочника в старых строках не
    -- выдумываются и не стираются: тогда связь добавляется NOT VALID.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname  = 'handoff_packet_accepted_by_fkey'
                      AND conrelid = 'bem_core.handoff_packet'::regclass) THEN
        ALTER TABLE bem_core.handoff_packet NO FORCE ROW LEVEL SECURITY;
        SELECT count(*) INTO v_cnt
          FROM bem_core.handoff_packet h
         WHERE h.accepted_by IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM bem_core.actor a
                            WHERE a.actor_id = h.accepted_by);
        ALTER TABLE bem_core.handoff_packet FORCE ROW LEVEL SECURITY;
        IF v_cnt = 0 THEN
            ALTER TABLE bem_core.handoff_packet
                  ADD CONSTRAINT handoff_packet_accepted_by_fkey
                  FOREIGN KEY (accepted_by) REFERENCES bem_core.actor(actor_id);
        ELSE
            ALTER TABLE bem_core.handoff_packet
                  ADD CONSTRAINT handoff_packet_accepted_by_fkey
                  FOREIGN KEY (accepted_by) REFERENCES bem_core.actor(actor_id) NOT VALID;
            RAISE WARNING
              'HANDOFF_ACCEPTED_BY_ORPHAN: у % пакетов принявший не найден'
              ' в справочнике участников; связь добавлена NOT VALID и'
              ' действует для новых строк', v_cnt;
        END IF;
    END IF;
END
$$;

-- ---------------------------------------------------------------
-- Шаг 10А. Столбцы и ограничения редакции H1.10.
--          Таблицу доверенностей bem_core.actor_delegation создаёт
--          файл 01 — он идёт следом в той же транзакции. Здесь
--          только то, чего CREATE TABLE IF NOT EXISTS сделать не
--          может: столбцы уже существующей таблицы доказательств.
--          Без этого шага файл 01 остановится на досмотре 2.
-- ---------------------------------------------------------------
SET ROLE bem_core_owner;

-- 10А.1. Основание, по которому роль входа говорит за участника
--        (замечание C-H19-R9-01). Ссылка на таблицу доверенностей
--        здесь не ставится: таблицы ещё нет. Её добавляет файл 01
--        шагом «ограничения, которые могли не появиться».
ALTER TABLE bem_core.evidence ADD COLUMN IF NOT EXISTS delegation_id uuid;

-- 10А.2. Номер договора личности. Значение 1 у существующих строк —
--        не выдумка, а факт: они написаны тогда, когда основания не
--        требовалось вовсе, и другого значения у них быть не может.
--        Умолчание 2 ставится следом и действует только для новых
--        строк. Порядок именно такой: сначала столбец приходит со
--        старым умолчанием и сразу обязателен, потом умолчание
--        меняется. Существующие строки при этом не переписываются.
ALTER TABLE bem_core.evidence
    ADD COLUMN IF NOT EXISTS identity_contract smallint NOT NULL DEFAULT 1;

ALTER TABLE bem_core.evidence
    ALTER COLUMN identity_contract SET DEFAULT 2;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname  = 'evidence_identity_contract_check'
                      AND conrelid = 'bem_core.evidence'::regclass) THEN
        ALTER TABLE bem_core.evidence
              ADD CONSTRAINT evidence_identity_contract_check
              CHECK (identity_contract IN (1, 2));
    END IF;

    -- 10А.3. Связь договора с основанием. Строки договора 1 проходят
    --        первой ветвью: у них ни роли входа, ни способа, ни
    --        основания, и требовать их задним числом нельзя.
    --        Проверять ограничение на существующих строках безопасно
    --        именно поэтому — NOT VALID здесь не нужен.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname  = 'evidence_delegation_basis'
                      AND conrelid = 'bem_core.evidence'::regclass) THEN
        ALTER TABLE bem_core.evidence
              ADD CONSTRAINT evidence_delegation_basis CHECK (
                  identity_contract = 1
                  OR (identity_mode = 'BOUND'     AND delegation_id IS NULL)
                  OR (identity_mode = 'DELEGATED' AND delegation_id IS NOT NULL));
    END IF;
END
$$;

-- ---------------------------------------------------------------
-- Шаг 11. Отметка новой версии формы
-- ---------------------------------------------------------------
RESET ROLE;

INSERT INTO bem_core.schema_migration (version)
VALUES ('bem954-h1-10-shape')
ON CONFLICT (version) DO NOTHING;

-- ---------------------------------------------------------------
-- Шаг 12. Проверка результата. Любая несостыковка откатывает
--         не только этот файл, но и файл 01: транзакция общая.
-- ---------------------------------------------------------------
DO $$
DECLARE
    v_cnt      integer;
    v_expected integer;
BEGIN
    -- 1. Столбцы разногласия на месте
    SELECT count(*) INTO v_cnt
      FROM information_schema.columns
     WHERE table_schema = 'bem_core' AND table_name = 'subject'
       AND column_name IN ('disagreement_at', 'disagreement_reason');
    IF v_cnt <> 2 THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: колонок разногласия % вместо 2', v_cnt;
    END IF;

    -- 2. Ключ повтора есть, обязателен и заполнен у всех строк
    SELECT count(*) INTO v_cnt
      FROM information_schema.columns
     WHERE table_schema = 'bem_core' AND table_name = 'outbox'
       AND column_name = 'idempotency_key' AND is_nullable = 'NO';
    IF v_cnt <> 1 THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: ключ повтора не обязателен или отсутствует';
    END IF;

    -- 3. Новые состояния ящика разрешены проверкой
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'outbox_status_check'
                      AND conrelid = 'bem_core.outbox'::regclass
                      AND pg_get_constraintdef(oid) LIKE '%DEAD_LETTER%') THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: список состояний ящика не расширен';
    END IF;

    -- 4. Журнал команд, если он есть, приведён к новой форме
    IF to_regclass('bem_core.command_log') IS NOT NULL THEN
        SELECT count(*) INTO v_cnt
          FROM information_schema.columns
         WHERE table_schema = 'bem_core' AND table_name = 'command_log'
           AND ((column_name = 'has_outbox' AND is_nullable = 'NO')
             OR (column_name = 'kind'       AND is_nullable = 'YES'));
        IF v_cnt <> 2 THEN
            RAISE EXCEPTION 'UPGRADE_FAILED: журнал команд не в новой форме (%)', v_cnt;
        END IF;
    END IF;

    -- 5. Политика есть у каждой существующей таблицы из списка,
    --    и её выражение переведено на функцию заказчика
    SELECT count(*) INTO v_expected
      FROM unnest(ARRAY['work_item', 'evidence', 'subject', 'subject_author',
                        'audit_record', 'outbox', 'command_log', 'usage_record',
                        'handoff_packet', 'user_tenant_membership',
                        'audit_assignment']) AS t(name)
     WHERE to_regclass('bem_core.' || t.name) IS NOT NULL;

    SELECT count(*) INTO v_cnt
      FROM pg_policies
     WHERE schemaname = 'bem_core' AND policyname = 'tenant_isolation'
       AND qual LIKE '%current_tenant()%';
    IF v_cnt <> v_expected THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: переведено % политик вместо %', v_cnt, v_expected;
    END IF;

    -- 6. У ядра не осталось прямых прав записи вообще
    SELECT count(*) INTO v_cnt
      FROM information_schema.table_privileges
     WHERE grantee = 'bem_kernel_rw' AND table_schema = 'bem_core'
       AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE');
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: у ядра осталось % прямых прав записи', v_cnt;
    END IF;

    -- 7. Защита строк нигде не осталась снятой. Список шире прежнего:
    --    шаг 10 снимает её ещё с доказательств и пакетов передачи.
    SELECT count(*) INTO v_cnt
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'bem_core' AND c.relkind = 'r'
       AND c.relname IN ('outbox', 'command_log', 'evidence', 'handoff_packet')
       AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity);
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: у % таблиц защита строк осталась снятой', v_cnt;
    END IF;

    -- 8. Все столбцы редакции H1.9 на месте. Файл 01 идёт следом и
    --    отказывается работать без них, поэтому проверка стоит здесь.
    SELECT count(*) INTO v_cnt
      FROM (VALUES ('actor', 'db_role'),
                   ('evidence', 'session_role'),
                   ('evidence', 'identity_mode'),
                   ('outbox', 'next_attempt_at'),
                   ('handoff_packet', 'accepted_by')) AS t(tbl, col)
      JOIN information_schema.columns c
        ON c.table_schema = 'bem_core'
       AND c.table_name   = t.tbl
       AND c.column_name  = t.col;
    IF v_cnt <> 5 THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: новых столбцов % вместо 5', v_cnt;
    END IF;

    -- 9. Время следующей попытки обязательно и заполнено у всех строк
    SELECT count(*) INTO v_cnt
      FROM information_schema.columns
     WHERE table_schema = 'bem_core' AND table_name = 'outbox'
       AND column_name = 'next_attempt_at' AND is_nullable = 'NO';
    IF v_cnt <> 1 THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: время следующей попытки не обязательно';
    END IF;

    -- 10. Версия отпечатка: у старых строк 1, умолчание для новых 2
    IF to_regclass('bem_core.command_log') IS NOT NULL THEN
        SELECT count(*) INTO v_cnt
          FROM information_schema.columns
         WHERE table_schema = 'bem_core' AND table_name = 'command_log'
           AND column_name = 'fingerprint_version'
           AND is_nullable = 'NO'
           AND column_default LIKE '2%';
        IF v_cnt <> 1 THEN
            RAISE EXCEPTION 'UPGRADE_FAILED: версия отпечатка не в форме';
        END IF;
    END IF;

    -- 11. Ядро не получило права записи обратно ни на одну таблицу
    IF has_table_privilege('bem_kernel_rw', 'bem_core.evidence', 'INSERT') THEN
        RAISE EXCEPTION
          'UPGRADE_FAILED: ядру осталось право прямой записи доказательств';
    END IF;

    -- 12. Столбцы редакции H1.10 на месте, договор личности обязателен
    --     и у новых строк равен 2. Файл 01 идёт следом и отказывается
    --     работать без этих столбцов, поэтому проверка стоит здесь.
    SELECT count(*) INTO v_cnt
      FROM information_schema.columns
     WHERE table_schema = 'bem_core' AND table_name = 'evidence'
       AND column_name IN ('delegation_id', 'identity_contract');
    IF v_cnt <> 2 THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: столбцов доверенности % вместо 2', v_cnt;
    END IF;

    SELECT count(*) INTO v_cnt
      FROM information_schema.columns
     WHERE table_schema = 'bem_core' AND table_name = 'evidence'
       AND column_name = 'identity_contract'
       AND is_nullable = 'NO'
       AND column_default LIKE '2%';
    IF v_cnt <> 1 THEN
        RAISE EXCEPTION 'UPGRADE_FAILED: договор личности не в форме';
    END IF;

    -- 13. Связь договора с основанием проверяется базой, а не кодом
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname  = 'evidence_delegation_basis'
                      AND conrelid = 'bem_core.evidence'::regclass
                      AND convalidated) THEN
        RAISE EXCEPTION
          'UPGRADE_FAILED: ограничения evidence_delegation_basis нет или оно непроверенное';
    END IF;
END
$$;

-- BEM954-FINAL-SECURITY-CHECKPOINT: 02_upgrade_to_h110.sql
-- Ниже этой строки не должно быть ни одной команды, меняющей роль,
-- членство, владельца или право. Это проверяет статический сверщик
-- раздела 15.11: команда после маркера — расхождение, а не мелочь.

