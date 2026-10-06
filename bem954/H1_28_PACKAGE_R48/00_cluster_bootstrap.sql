-- 00_cluster_bootstrap.sql
-- Назначение: роли кластера, их атрибуты, членства и база данных.
-- Запуск:     psql -v ON_ERROR_STOP=1 -U <администратор кластера> -d postgres \
--                  -f 00_cluster_bootstrap.sql
-- Паролей в файле нет. Вход настраивается сертификатом через pg_hba.conf.

\set ON_ERROR_STOP on

BEGIN;

-- ---------------------------------------------------------------
-- Шаг 1. Роли и их атрибуты.
--        Роль существует — атрибуты выравниваются по эталону.
--        Роли нет — создаётся. Пароли не задаются никогда.
-- ---------------------------------------------------------------
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('bem_core_owner',
             'NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'),
            ('bem_engine_owner',
             'NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'),
            ('bem_control_owner',
             'NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS'),
            ('bem_kernel_rw',
             'LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'),
            ('bem_engine_rw',
             'LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'),
            -- PASSWORD NULL обнуляет пароль и у новой роли, и у уже
            -- существующей: вход только по сертификату, пароля нет вовсе.
            ('backup_reader',
             'NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS CONNECTION LIMIT 0 PASSWORD NULL'),
            -- Сторож копирования: ни CREATEROLE, ни наследования прав.
            -- NOINHERIT — второй слой: даже если членство появится по ошибке,
            -- права по нему сами собой не включатся.
            ('bem_backup_admin',
             'LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT PASSWORD NULL'),
            -- Владелец двух узких функций окна копирования. Входить не умеет.
            ('bem_backup_ctl_owner',
             'NOLOGIN NOSUPERUSER NOCREATEDB CREATEROLE NOBYPASSRLS INHERIT'),
            ('schema_migrator',
             'NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'),
            -- Управляющая группа. Чувствительные функции — назначение
            -- проверяющих, операторский разбор, заведение заказчика —
            -- выданы ей, а не общей рабочей роли ядра (C-H18-R8-04).
            -- Это группа без входа: войти ею нельзя, можно только
            -- состоять в ней.
            ('bem_governance',
             'NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'),
            -- Вход первой установки. Связан с участником human:bootstrap
            -- колонкой actor.db_role (раздел 26). Предел подключений — 0:
            -- роль есть, но войти ею нельзя, пока администратор
            -- сознательно не поднимет предел и не настроит pg_hba.conf.
            -- Так первая личность существует, но не ждёт, когда ею
            -- кто-нибудь воспользуется (замечание M-H18-R8-07).
            ('bem_bootstrap_admin',
             'LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT'
             ' CONNECTION LIMIT 0 PASSWORD NULL')
        ) AS t(role_name, attrs)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.role_name) THEN
            EXECUTE format('CREATE ROLE %I %s', r.role_name, r.attrs);
        ELSE
            EXECUTE format('ALTER ROLE %I %s', r.role_name, r.attrs);
        END IF;
    END LOOP;
END
$$;

-- ---------------------------------------------------------------
-- Шаг 2. Членства.
--        Мигратор получает владельцев схем, чтобы переключаться
--        на них командой SET ROLE внутри файла 01.
--        Сторож копирования получает право администрировать
--        ровно одну роль — backup_reader — и ничего больше.
-- ---------------------------------------------------------------
-- Мигратору членства выдаёт и отзывает внешняя обёртка раздела 25.7,
-- а не этот файл: постоянное членство у роли с закрытым входом —
-- это право, которое ждёт своего часа.

-- Сторож копирования не получает НИ ОДНОГО членства и ни одного
-- системного права. В H1.7 он имел membership в backup_reader и
-- pg_signal_backend, то есть мог стать читателем всех данных и
-- завершить чужую сессию (замечание C-H17-R7-03).

-- Всё это переходит владельцу двух узких функций окна копирования.
GRANT pg_signal_backend TO bem_backup_ctl_owner;

-- Право администрировать роль чтения — но БЕЗ наследования её прав
-- и БЕЗ возможности стать ею командой SET ROLE.
-- Три отдельные команды, а не одна с тремя словами: синопсис GRANT
-- в PostgreSQL 16 допускает в предложении WITH ровно один параметр,
-- а при изменении существующего членства неуказанные параметры
-- сохраняют прежнее значение — так сказано в описании команды.
GRANT backup_reader TO bem_backup_ctl_owner WITH ADMIN OPTION;
GRANT backup_reader TO bem_backup_ctl_owner WITH INHERIT FALSE;
GRANT backup_reader TO bem_backup_ctl_owner WITH SET FALSE;

-- Вход первой установки состоит в управляющей группе и наследует её
-- права: иначе он не смог бы вызвать ни create_tenant, ни назначение
-- проверяющих. Больше в группе нет никого — своих людей оператор
-- добавляет сам после установки.
GRANT bem_governance TO bem_bootstrap_admin;

-- ---------------------------------------------------------------
-- Шаг 3. Проверка результата. Файл обязан упасть здесь, а не
--        оставить кластер в половинчатом состоянии.
-- ---------------------------------------------------------------
DO $$
DECLARE
    v_roles text[] := ARRAY['bem_core_owner', 'bem_engine_owner', 'bem_control_owner',
                            'bem_kernel_rw', 'bem_engine_rw', 'backup_reader',
                            'bem_backup_admin', 'bem_backup_ctl_owner',
                            'schema_migrator', 'bem_governance',
                            'bem_bootstrap_admin'];
    v_cnt   integer;
BEGIN
    SELECT count(*) INTO v_cnt
      FROM pg_roles WHERE rolname = ANY(v_roles);
    IF v_cnt <> 11 THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: создано % ролей из 11', v_cnt;
    END IF;

    -- Роль проверки восстановления файлом 00 НЕ создаётся: её создаёт
    -- файл 03 и только в базе восстановления (раздел 25.8). Проверка
    -- разбита на два вложенных условия намеренно: SQL не обещает, что
    -- второе условие в AND не будет вычислено, а has_database_privilege
    -- у несуществующей роли или базы возбуждает ошибку.
    IF EXISTS (SELECT 1 FROM pg_roles   WHERE rolname = 'restore_verifier')
       AND EXISTS (SELECT 1 FROM pg_database WHERE datname = 'bem') THEN
        IF has_database_privilege('restore_verifier', 'bem', 'CONNECT') THEN
            RAISE EXCEPTION
              'BOOTSTRAP_FAILED: у роли restore_verifier есть вход в рабочую базу';
        END IF;
    END IF;

    -- Вход первой установки заперт пределом подключений: роль есть,
    -- войти ею нельзя, пока администратор не решит иначе.
    SELECT rolconnlimit INTO v_cnt
      FROM pg_roles WHERE rolname = 'bem_bootstrap_admin';
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION
          'BOOTSTRAP_FAILED: предел подключений входа установки % вместо 0', v_cnt;
    END IF;

    SELECT count(*) INTO v_cnt
      FROM pg_roles WHERE rolname = ANY(v_roles) AND rolsuper;
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: % проектных ролей с правами суперпользователя', v_cnt;
    END IF;

    SELECT count(*) INTO v_cnt
      FROM pg_roles WHERE rolname = ANY(v_roles) AND rolbypassrls;
    IF v_cnt <> 2 THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: BYPASSRLS у % ролей вместо двух', v_cnt;
    END IF;

    -- У сторожа копирования НЕТ НИ ОДНОГО членства: ни в backup_reader,
    -- ни в pg_signal_backend, ни в чём-либо ещё.
    SELECT count(*) INTO v_cnt
      FROM pg_auth_members m JOIN pg_roles s ON s.oid = m.member
     WHERE s.rolname = 'bem_backup_admin';
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: у сторожа % членств вместо нуля', v_cnt;
    END IF;

    -- Владелец функций окна: администрирует роль чтения, но не наследует
    -- её прав и не может ею стать.
    IF NOT EXISTS (
        SELECT 1
          FROM pg_auth_members m
          JOIN pg_roles g ON g.oid = m.roleid
          JOIN pg_roles s ON s.oid = m.member
         WHERE g.rolname = 'backup_reader'
           AND s.rolname = 'bem_backup_ctl_owner'
           AND m.admin_option
           AND NOT m.inherit_option
           AND NOT m.set_option) THEN
        RAISE EXCEPTION
          'BOOTSTRAP_FAILED: членство владельца окна копирования не в нужном виде';
    END IF;

    IF NOT pg_has_role('bem_backup_ctl_owner', 'pg_signal_backend', 'MEMBER') THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: владелец окна не входит в pg_signal_backend';
    END IF;

    -- Владелец функций окна не умеет входить: выполнить от его имени
    -- произвольную команду снаружи нельзя.
    IF EXISTS (SELECT 1 FROM pg_roles
                WHERE rolname = 'bem_backup_ctl_owner' AND rolcanlogin) THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: владелец окна копирования умеет входить';
    END IF;

    -- У мигратора после файла 00 членств нет: их выдаёт обёртка окна.
    SELECT count(*) INTO v_cnt
      FROM pg_auth_members m JOIN pg_roles s ON s.oid = m.member
     WHERE s.rolname = 'schema_migrator';
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: у мигратора % членств вместо нуля', v_cnt;
    END IF;

    -- Пароля у ролей без парольного входа нет вовсе.
    SELECT count(*) INTO v_cnt
      FROM pg_authid
     WHERE rolname IN ('backup_reader', 'bem_backup_admin')
       AND rolpassword IS NOT NULL;
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: у % ролей копирования остался пароль', v_cnt;
    END IF;
END
$$;

COMMIT;

-- ---------------------------------------------------------------
-- Шаг 4. База данных. Вне транзакции: CREATE DATABASE внутри
--        транзакционного блока PostgreSQL не выполняет.
--        Приём \gexec выполняет команду, только если базы ещё нет.
-- ---------------------------------------------------------------
SELECT 'CREATE DATABASE bem OWNER bem_core_owner '
       'ENCODING ''UTF8'' LC_COLLATE ''C'' LC_CTYPE ''C'' TEMPLATE template0'
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'bem')
\gexec

\connect bem

-- ---------------------------------------------------------------
-- Шаг 5. Права на саму базу и на схему public.
--        Подключаться может только тот, кому это нужно.
--
--        Отзыв именно ALL, а не CONNECT. PostgreSQL выдаёт PUBLIC на
--        новую базу два права: CONNECT и TEMPORARY. Отзыв одного
--        оставлял второе, и любая подключившаяся роль могла создавать
--        временные таблицы: место на диске и имена, перекрывающие
--        настоящие таблицы в пути поиска. Перечислять права поимённо
--        тоже нельзя: их набор задаёт сервер, и перечисление устареет
--        молча. Найдено построением точного множества прав (R30).
-- ---------------------------------------------------------------
REVOKE ALL    ON DATABASE bem FROM PUBLIC;
REVOKE ALL    ON SCHEMA   public FROM PUBLIC;

GRANT CONNECT ON DATABASE bem
   TO bem_kernel_rw, bem_engine_rw, backup_reader, bem_backup_admin,
      schema_migrator, bem_bootstrap_admin;

-- Роль проверки восстановления в этот список не входит и не войдёт:
-- в рабочую базу она не подключается вовсе (раздел 25.8).

-- ---------------------------------------------------------------
-- Шаг 6. Финальная проверка итогового состояния.
--        Шаг 3 стоит в середине файла и потому доказывает только
--        середину: команду можно дописать после него, и прежние
--        проверки её не увидят (замечание C-H112-R12-01). Этот шаг
--        стоит после последней команды файла, способной изменить
--        роль, членство, владельца или право, и сверяет не число
--        ролей с одним признаком, а точные признаки каждой роли и
--        полный набор строк pg_auth_members.
-- ---------------------------------------------------------------
DO $$
DECLARE
    -- Признаки по порядку: вход, суперпользователь, создание баз,
    -- создание ролей, репликация, обход защиты строк, наследование,
    -- предел подключений. Те же значения объявлены машинным блоком
    -- BEM954-H1-18-ROLE-ATTRIBUTES и сверяются статическим сверщиком.
    v_expect  constant text[] := ARRAY[
        'backup_reader|f|f|f|f|f|t|t|0',
        'bem_backup_admin|t|f|f|f|f|f|f|-1',
        'bem_backup_ctl_owner|f|f|f|t|f|f|t|-1',
        'bem_bootstrap_admin|t|f|f|f|f|f|t|0',
        'bem_control_owner|f|f|f|f|f|t|t|-1',
        'bem_core_owner|f|f|f|f|f|f|t|-1',
        'bem_engine_owner|f|f|f|f|f|f|t|-1',
        'bem_engine_rw|t|f|f|f|f|f|t|-1',
        'bem_governance|f|f|f|f|f|f|t|-1',
        'bem_kernel_rw|t|f|f|f|f|f|t|-1',
        'schema_migrator|f|f|f|f|f|f|t|-1'];
    -- Членства: роль-группа, член, право администрирования,
    -- наследование, возможность стать ролью командой SET ROLE.
    v_members constant text[] := ARRAY[
        'backup_reader|bem_backup_ctl_owner|t|f|f',
        'bem_governance|bem_bootstrap_admin|f|t|t',
        'pg_signal_backend|bem_backup_ctl_owner|f|t|t'];
    v_names   constant text[] := ARRAY[
        'backup_reader', 'bem_backup_admin', 'bem_backup_ctl_owner',
        'bem_bootstrap_admin', 'bem_control_owner', 'bem_core_owner',
        'bem_engine_owner', 'bem_engine_rw', 'bem_governance',
        'bem_kernel_rw', 'schema_migrator'];
    v_row     text;
    v_cnt     integer;
BEGIN
    -- 1. Каждая роль договора существует.
    SELECT e.name INTO v_row
      FROM unnest(v_names) AS e(name)
     WHERE NOT EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = e.name)
     LIMIT 1;
    IF v_row IS NOT NULL THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: роли договора нет: %', v_row;
    END IF;

    -- 2. Признаки совпадают точно. Любое повышение роли после шага 3
    --    останавливает файл здесь и называет роль.
    SELECT r.rolname || ': ' ||
           r.rolcanlogin || r.rolsuper || r.rolcreatedb || r.rolcreaterole ||
           r.rolreplication || r.rolbypassrls || r.rolinherit || ' ' || r.rolconnlimit
      INTO v_row
      FROM pg_roles r
     WHERE r.rolname = ANY(v_names)
       AND (r.rolname || '|' || left(r.rolcanlogin::text, 1) || '|' || left(r.rolsuper::text, 1)
            || '|' || left(r.rolcreatedb::text, 1) || '|' || left(r.rolcreaterole::text, 1)
            || '|' || left(r.rolreplication::text, 1) || '|' || left(r.rolbypassrls::text, 1)
            || '|' || left(r.rolinherit::text, 1) || '|' || r.rolconnlimit) <> ALL (v_expect)
     LIMIT 1;
    IF v_row IS NOT NULL THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: признаки роли вне договора: %', v_row;
    END IF;

    -- 3. Ни одного членства сверх объявленных — ни у проектной роли
    --    как у члена, ни в проектную роль как в группу.
    SELECT g.rolname || ' -> ' || s.rolname
           || ' (admin ' || m.admin_option || ', inherit ' || m.inherit_option
           || ', set ' || m.set_option || ')'
      INTO v_row
      FROM pg_auth_members m
      JOIN pg_roles g ON g.oid = m.roleid
      JOIN pg_roles s ON s.oid = m.member
     WHERE (s.rolname = ANY(v_names) OR g.rolname = ANY(v_names))
       AND (g.rolname || '|' || s.rolname || '|' || left(m.admin_option::text, 1)
            || '|' || left(m.inherit_option::text, 1)
            || '|' || left(m.set_option::text, 1)) <> ALL (v_members)
     LIMIT 1;
    IF v_row IS NOT NULL THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: членство вне договора: %', v_row;
    END IF;

    -- 4. И наоборот: каждое объявленное членство существует и в том
    --    же виде. Снятая строка — такая же порча, как лишняя.
    SELECT e.row INTO v_row
      FROM unnest(v_members) AS e(row)
     WHERE NOT EXISTS (
        SELECT 1 FROM pg_auth_members m
          JOIN pg_roles g ON g.oid = m.roleid
          JOIN pg_roles s ON s.oid = m.member
         WHERE (g.rolname || '|' || s.rolname || '|' || left(m.admin_option::text, 1)
                || '|' || left(m.inherit_option::text, 1)
                || '|' || left(m.set_option::text, 1)) = e.row)
     LIMIT 1;
    IF v_row IS NOT NULL THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: объявленного членства нет: %', v_row;
    END IF;

    -- 5. Выдавшим членство записан начальный суперпользователь кластера.
    --    PostgreSQL 16 не пишет сюда имя того, кто выполнил команду:
    --    выдачу от любого суперпользователя он приписывает НАЧАЛЬНОМУ
    --    суперпользователю — роли с постоянным номером 10. Прежняя
    --    проверка сравнивала выдавшего с current_user и поэтому
    --    отказывала на каждом кластере, где администратор входит не
    --    начальной ролью, а любой другой с правами суперпользователя
    --    (замечание M-H113-R13-03). Номер 10 — не догадка: он задан в
    --    самом PostgreSQL и переименование роли его не меняет.
    SELECT g.rolname || ' -> ' || s.rolname || ' (выдал ' || o.rolname || ')' INTO v_row
      FROM pg_auth_members m
      JOIN pg_roles g ON g.oid = m.roleid
      JOIN pg_roles s ON s.oid = m.member
      JOIN pg_roles o ON o.oid = m.grantor
     WHERE s.rolname = ANY(v_names)
       AND m.grantor <> 10
     LIMIT 1;
    IF v_row IS NOT NULL THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: членство выдал не начальный суперпользователь: %', v_row;
    END IF;

    -- 6. Мигратор выходит из файла 00 без членств: их выдаёт и
    --    отзывает обёртка окна, и только внутри окна.
    SELECT count(*) INTO v_cnt
      FROM pg_auth_members m JOIN pg_roles s ON s.oid = m.member
     WHERE s.rolname = 'schema_migrator';
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'BOOTSTRAP_FAILED: у мигратора % членств вместо нуля', v_cnt;
    END IF;
END
$$;

-- BEM954-FINAL-SECURITY-CHECKPOINT: 00_cluster_bootstrap.sql
-- Ниже этой строки не должно быть ни одной команды, меняющей роль,
-- членство, владельца или право. Это проверяет статический сверщик
-- раздела 15.11: команда после маркера — расхождение, а не мелочь.

-- Готово. Дальше запускается обёртка, и уже она открывает окно:
--   node run_migration.mjs --files 01_database_migration.sql
-- Окно мигратора открывает и закрывает обёртка (раздел 25.7),
-- а не файлы 01 и 02.

