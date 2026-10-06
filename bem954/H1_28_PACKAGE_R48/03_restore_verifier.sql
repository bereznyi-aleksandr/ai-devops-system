-- ===============================================================
-- 03_restore_verifier.sql
-- Запускает: администратор кластера, ТОЛЬКО в базе восстановления.
-- Назначение: лицо, которое доказывает совпадение копии с оригиналом.
-- В рабочей базе этот файл не запускается никогда — шаг 0 не даст.
-- Транзакции: файл идёт одной транзакцией обёрткой psql
--             (--single-transaction), своих BEGIN и COMMIT в нём нет.
-- ===============================================================

-- Шаг 0. Отказ вне базы восстановления — до любого изменения.
-- Курсор без WITH HOLD вне транзакции возбуждает ошибку 25P01:
-- так файл отказывается идти по одной команде за раз.
DECLARE bem_restore_guard CURSOR FOR SELECT 1;
CLOSE bem_restore_guard;

DO $$
BEGIN
    IF current_database() NOT LIKE 'bem_restore%' THEN
        RAISE EXCEPTION
          'RESTORE_ONLY_FILE: файл запущен в базе %. Он предназначен только'
          ' для базы восстановления, имя которой начинается с bem_restore.'
          ' Ни одного изменения не сделано', current_database();
    END IF;
END
$$;

-- Шаг 1. Роль. Пароля нет; вход настраивается сертификатом отдельно.
-- NOINHERIT: даже случайное членство не даст ей чужих прав.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'restore_verifier') THEN
        EXECUTE 'CREATE ROLE restore_verifier LOGIN NOSUPERUSER NOCREATEDB'
             || ' NOCREATEROLE NOBYPASSRLS NOINHERIT CONNECTION LIMIT 2 PASSWORD NULL';
    ELSE
        EXECUTE 'ALTER ROLE restore_verifier LOGIN NOSUPERUSER NOCREATEDB'
             || ' NOCREATEROLE NOBYPASSRLS NOINHERIT CONNECTION LIMIT 2 PASSWORD NULL';
    END IF;
END
$$;

-- Шаг 1б. Членства. Это и есть главная дыра H1.9 (замечание
-- `M-H19-R9-04`). В PostgreSQL 16 признаки INHERIT и SET принадлежат
-- не роли, а КАЖДОЙ СТРОКЕ членства: `pg_auth_members.inherit_option`
-- и `pg_auth_members.set_option`. Поэтому `ALTER ROLE ... NOINHERIT`
-- из шага 1 не снимает уже выданного членства и не отнимает
-- возможности `SET ROLE`. Роль, однажды включённая в сильную группу
-- с `SET TRUE`, переключится в неё и получит все её права —
-- а `has_table_privilege` шага 4 этого не покажет, потому что сама
-- по себе роль прав не имеет.
--
-- Поэтому список приводится к точному нулю: сначала снимаем всё, что
-- нашли, потом требуем, чтобы не осталось ничего.
DO $$
-- ПОКРЫТИЕ: K-R8-16, K-R9-11
DECLARE
    r     record;
    v_cnt integer;
BEGIN
    FOR r IN
        SELECT g.rolname AS grp
          FROM pg_auth_members m
          JOIN pg_roles g ON g.oid = m.roleid
          JOIN pg_roles v ON v.oid = m.member
         WHERE v.rolname = 'restore_verifier'
    LOOP
        EXECUTE format('REVOKE %I FROM restore_verifier', r.grp);
        RAISE NOTICE 'RESTORE_VERIFIER_MEMBERSHIP_REVOKED: снято членство в %', r.grp;
    END LOOP;

    SELECT count(*) INTO v_cnt
      FROM pg_auth_members m
      JOIN pg_roles v ON v.oid = m.member
     WHERE v.rolname = 'restore_verifier';

    IF v_cnt <> 0 THEN
        RAISE EXCEPTION
          'RESTORE_VERIFIER_TOO_WIDE: осталось % членств, снять их не удалось.'
          ' Признаки INHERIT и SET живут в строке членства, поэтому'
          ' ALTER ROLE NOINHERIT здесь не помогает', v_cnt;
    END IF;

    -- Обратная сторона: роль сама не должна быть группой для других.
    SELECT count(*) INTO v_cnt
      FROM pg_auth_members m
      JOIN pg_roles g ON g.oid = m.roleid
     WHERE g.rolname = 'restore_verifier';

    IF v_cnt <> 0 THEN
        RAISE EXCEPTION
          'RESTORE_VERIFIER_TOO_WIDE: в роль включено % других ролей', v_cnt;
    END IF;
END
$$;

-- Шаг 1в. Настройки роли. rolconfig может нести search_path или
-- role, и тогда «узкая» роль ведёт себя не так, как читается.
ALTER ROLE restore_verifier RESET ALL;

DO $$
-- ПОКРЫТИЕ: K-R8-16, K-R9-11
DECLARE
    v_cfg text[];
BEGIN
    SELECT rolconfig INTO v_cfg FROM pg_roles WHERE rolname = 'restore_verifier';
    IF v_cfg IS NOT NULL AND array_length(v_cfg, 1) > 0 THEN
        RAISE EXCEPTION
          'RESTORE_VERIFIER_TOO_WIDE: у роли остались настройки %', v_cfg;
    END IF;
END
$$;

-- Шаг 2. Права — ровно две строки: вход в базу восстановления
--        и вход в схему управления.
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO restore_verifier',
                   current_database());
END
$$;

-- H1.24, M-R43-01 (аудит R43): копия несёт чужие права. До выдачи
-- единственного права снимаются прежние права роли на три схемы.
-- Права, выданные не владельцем схемы, такой REVOKE не снимает: их
-- ловит точная сверка списка прав в шаге 4. Без CASCADE: если роль
-- успела передать право дальше, REVOKE отказывает, и файл останавливается.
REVOKE CREATE, USAGE ON SCHEMA bem_core FROM restore_verifier;
REVOKE CREATE, USAGE ON SCHEMA bem_engine FROM restore_verifier;
REVOKE CREATE, USAGE ON SCHEMA bem_control FROM restore_verifier;
GRANT USAGE ON SCHEMA bem_control TO restore_verifier;

-- Шаг 3. Одна функция. Остальные две свёртки она вызывает сама,
--        правами своего владельца, поэтому выдавать их не нужно.
GRANT EXECUTE ON FUNCTION bem_control.database_digest() TO restore_verifier;

-- Шаг 4. Доказательство узости. Файл падает, если роль получила лишнее.
DO $$
-- ПОКРЫТИЕ: K-R8-16, K-R9-11
DECLARE
    v_cnt integer;
    v_dbs text[] := ARRAY[]::text[];
    r     record;
BEGIN
    SELECT count(*) INTO v_cnt
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname IN ('bem_core', 'bem_engine', 'bem_control')
       -- H1.23, дефект D7 живого прогона R42: функции bem_core открыты
       -- PUBLIC по умолчанию (current_tenant нужна политикам строк всех
       -- рабочих ролей), но без входа в схему их не вызвать. Вход в
       -- bem_core и bem_engine запрещён отдельной проверкой ниже.
       AND has_schema_privilege('restore_verifier', n.oid, 'USAGE')
       AND has_function_privilege('restore_verifier', p.oid, 'EXECUTE')
       AND p.proname <> 'database_digest';
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'RESTORE_VERIFIER_TOO_WIDE: доступно % лишних функций', v_cnt;
    END IF;

    SELECT count(*) INTO v_cnt
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname IN ('bem_core', 'bem_engine', 'bem_control')
       AND c.relkind IN ('r', 'p')
       AND has_table_privilege('restore_verifier', c.oid, 'SELECT');
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'RESTORE_VERIFIER_TOO_WIDE: видит % таблиц', v_cnt;
    END IF;

    IF has_schema_privilege('restore_verifier', 'bem_core',   'USAGE')
       OR has_schema_privilege('restore_verifier', 'bem_engine', 'USAGE') THEN
        RAISE EXCEPTION 'RESTORE_VERIFIER_TOO_WIDE: есть вход в схемы данных';
    END IF;

    -- H1.24, M-R43-01 (аудит R43): CREATE роли не нужен ни на одной
    -- схеме. Проверяется фактическое право — с PUBLIC и членствами.
    IF has_schema_privilege('restore_verifier', 'bem_control', 'CREATE')
       OR has_schema_privilege('restore_verifier', 'bem_core', 'CREATE')
       OR has_schema_privilege('restore_verifier', 'bem_engine', 'CREATE') THEN
        RAISE EXCEPTION 'RESTORE_VERIFIER_TOO_WIDE: есть право CREATE на схему';
    END IF;

    -- И точный список прав роли на три схемы: допустима ровно одна
    -- запись — USAGE на bem_control без права передачи. USAGE с правом
    -- передачи или любое право на bem_core и bem_engine — лишнее.
    -- H1.25, L-R44-01 (аудит R44): допустимая запись обязана быть
    -- выдана владельцем схемы. То же USAGE от другой роли REVOKE шага 2
    -- не снимает, и оно тоже лишнее.
    SELECT count(*) INTO v_cnt
      FROM pg_namespace n, aclexplode(n.nspacl) e
     WHERE n.nspname IN ('bem_core', 'bem_engine', 'bem_control')
       AND e.grantee = 'restore_verifier'::regrole
       AND NOT (n.nspname = 'bem_control'
                AND e.privilege_type = 'USAGE'
                AND NOT e.is_grantable
                AND e.grantor = n.nspowner);
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'RESTORE_VERIFIER_TOO_WIDE: лишних прав роли на схемы: %', v_cnt;
    END IF;

    -- Вход в чужие базы. Проверяются все базы кластера, кроме шаблонов
    -- и баз восстановления. Смотрится фактическое право, а не только
    -- явная запись в списке доступа: право может прийти и от PUBLIC,
    -- и тогда «узкая» роль всё равно войдёт.
    --
    -- На свежем кластере эта проверка отказывает: база postgres по
    -- умолчанию открыта для PUBLIC. Это не ложная тревога, а настоящее
    -- состояние — и файл прямо говорит, чем его лечить.
    FOR r IN
        SELECT d.datname
          FROM pg_database d
         WHERE NOT d.datistemplate
           AND d.datname NOT LIKE 'bem_restore%'
           AND has_database_privilege('restore_verifier', d.oid, 'CONNECT')
         ORDER BY d.datname
    LOOP
        v_dbs := v_dbs || r.datname;
    END LOOP;

    IF array_length(v_dbs, 1) > 0 THEN
        RAISE EXCEPTION
          'RESTORE_VERIFIER_TOO_WIDE: есть вход в базы %.'
          ' Лечение: REVOKE CONNECT ON DATABASE <имя> FROM PUBLIC,'
          ' и отдельно REVOKE CONNECT ... FROM restore_verifier,'
          ' если право выдано роли поимённо', v_dbs;
    END IF;
END
$$;

-- BEM954-FINAL-SECURITY-CHECKPOINT: 03_restore_verifier.sql
-- Ниже этой строки не должно быть ни одной команды, меняющей роль,
-- членство, владельца или право. Это проверяет статический сверщик
-- раздела 15.11: команда после маркера — расхождение, а не мелочь.

