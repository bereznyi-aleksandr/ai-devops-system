-- ДОКУМЕНТ: chk08.sql (проверка базы ТОЛЬКО ЧТЕНИЕМ после установки SQL 08, выпуск B10, шаг 3.5.5)
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-16 20:12 +02:00
-- ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель), сменщик после HANDOFF_20261116_1916.
-- ОСНОВАНИЕ: аудит ChatGPT REL83 («при успешной SQL08 — независимая read-only проверка таблицы/функции, прав,
--   FK-триггеров и неизменности B8/B9, новый R0 перед рассмотрением R2»); DESIGN_B10 v0.24 разделы 4.2 и 7.
-- КАК РАБОТАЕТ: одна транзакция READ ONLY (плюс default_transaction_read_only=on от команды), в конце ROLLBACK.
--   Ничего не создаёт: ни временных таблиц, ни функций. Проверки (любая не прошла → ошибка CHK08_FAILED, psql код 3):
--   1) цель — PostgreSQL 16, локальный сокет, порт 5432, база bem, пользователь postgres, не реплика; транзакция read only;
--   2) таблица bem_control.lease_seal и функция bem_control.lease_seal_unstarted(text,uuid,text) есть; строк печати 0;
--   3) строки снимка каталога (тот же снимок, что у обёртки SQL 08), в тексте которых есть «lease_seal», — их число и
--      SHA-256 равны добавленному SQL 08 (переменные psql cnt и expect: 20 и c460cbc2… из CI и с сервера). Снимок
--      включает права таблицы и столбцов (relacl, attacl), права, владельца и SECURITY DEFINER функции, ограничения,
--      индексы, обычные и внутренние триггеры внешнего ключа;
--   4) функция: SECURITY DEFINER, владелец bem_control_owner, EXECUTE только у владельца (как CI S08);
--   5) внутренние триггеры внешнего ключа lease_seal → chat_lease: на chat_lease 2, оба включены (как CI S12);
--   6) справочно (не проверка): число и SHA-256 остальных строк снимка — опора для следующих проверок.
--   Неизменность прежних объектов B8/B9 в базе доказала сама SQL 08 (снимок до/после в одной транзакции, 0 изменённых);
--   неизменность файлов B8/B9 на сервере проверяет новый R0.
\set ON_ERROR_STOP on
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL search_path = pg_catalog, pg_temp;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';
SELECT set_config('zc.expect', :'expect', true) IS NULL AS a, set_config('zc.cnt', :'cnt', true) IS NULL AS b \gset zc_
DO $z$ DECLARE
  v_e text := current_setting('zc.expect'); v_ec int := current_setting('zc.cnt')::int;
  v_a int; v_d text; v_ra int; v_rd text; v_n bigint; v_f text; v_t text;
BEGIN
  IF current_setting('server_version_num')::int / 10000 <> 16 THEN
    RAISE EXCEPTION 'CHK08_FAILED: server is not PostgreSQL 16';
  END IF;
  IF inet_server_addr() IS NOT NULL OR current_setting('port') <> '5432' OR current_database() <> 'bem'
     OR session_user <> 'postgres' OR pg_is_in_recovery() THEN
    RAISE EXCEPTION 'CHK08_FAILED: wrong target (addr=% port=% db=% user=% recovery=%)',
      coalesce(inet_server_addr()::text, 'socket'), current_setting('port'), current_database(), session_user,
      pg_is_in_recovery();
  END IF;
  IF current_setting('transaction_read_only') <> 'on' THEN
    RAISE EXCEPTION 'CHK08_FAILED: transaction is not read only';
  END IF;
  IF to_regclass('bem_control.lease_seal') IS NULL
     OR to_regprocedure('bem_control.lease_seal_unstarted(text,uuid,text)') IS NULL THEN
    RAISE EXCEPTION 'CHK08_FAILED: lease_seal or lease_seal_unstarted is missing';
  END IF;
  EXECUTE 'SELECT count(*) FROM bem_control.lease_seal' INTO v_n;
  IF v_n <> 0 THEN RAISE EXCEPTION 'CHK08_FAILED: lease_seal has % rows', v_n; END IF;
  WITH s(x) AS (
SELECT 'S|'||n.nspname||'|'||pg_get_userbyid(n.nspowner)||'|'||coalesce(n.nspacl::text,'-')
  FROM pg_namespace n WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
UNION ALL
SELECT 'R|'||n.nspname||'.'||c.relname||'|'||c.relkind::text||'|'||pg_get_userbyid(c.relowner)||'|'||coalesce(c.relacl::text,'-')
       ||'|'||c.relrowsecurity||'|'||c.relforcerowsecurity
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
UNION ALL
SELECT 'C|'||n.nspname||'.'||c.relname||'|'||a.attname||'|'||format_type(a.atttypid, a.atttypmod)||'|'||a.attnotnull
       ||'|'||coalesce(pg_get_expr(d.adbin, d.adrelid),'-')||'|'||coalesce(a.attacl::text,'-')
  FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
  LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
 WHERE a.attnum > 0 AND NOT a.attisdropped AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
UNION ALL
SELECT 'K|'||n.nspname||'|'||coalesce(c.relname,'-')||'|'||k.conname||'|'||pg_get_constraintdef(k.oid)
  FROM pg_constraint k JOIN pg_namespace n ON n.oid = k.connamespace LEFT JOIN pg_class c ON c.oid = k.conrelid
 WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
UNION ALL
SELECT 'I|'||n.nspname||'.'||c.relname||'|'||pg_get_indexdef(i.indexrelid)
  FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
UNION ALL
SELECT 'F|'||p.oid::regprocedure::text||'|'||pg_get_userbyid(p.proowner)||'|'||coalesce(p.proacl::text,'-')||'|'||p.prosecdef
       ||'|'||p.provolatile::text||'|'||coalesce(array_to_string(p.proconfig, ','),'-')||'|'||md5(p.prosrc)
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
UNION ALL
SELECT 'T|'||t.tgrelid::regclass::text||'|'||t.tgname||'|'||pg_get_triggerdef(t.oid)||'|'||t.tgenabled::text
  FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE NOT t.tgisinternal AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
UNION ALL
SELECT 'TI|'||t.tgrelid::regclass::text||'|'||coalesce(k.conname,'-')||'|'||coalesce(kc.relname,'-')||'|'
       ||t.tgconstrrelid::regclass::text||'|'||t.tgfoid::regproc::text||'|'||t.tgtype||'|'||t.tgenabled::text
       ||'|'||t.tgdeferrable||'|'||t.tginitdeferred||'|'||t.tgnargs
  FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
  LEFT JOIN pg_constraint k ON k.oid = t.tgconstraint LEFT JOIN pg_class kc ON kc.oid = k.conrelid
 WHERE t.tgisinternal AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
UNION ALL
SELECT 'D|'||pg_get_userbyid(d.defaclrole)||'|'||coalesce(n.nspname,'-')||'|'||d.defaclobjtype::text||'|'||d.defaclacl::text
  FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
UNION ALL
SELECT 'P|'||n.nspname||'.'||c.relname||'|'||po.polname||'|'||po.polcmd::text||'|'||coalesce(pg_get_expr(po.polqual, po.polrelid),'-')
  FROM pg_policy po JOIN pg_class c ON c.oid = po.polrelid JOIN pg_namespace n ON n.oid = c.relnamespace
UNION ALL
SELECT 'G|'||r.rolname||'|'||r.rolsuper||'|'||r.rolcanlogin||'|'||r.rolinherit||'|'||r.rolbypassrls||'|'||r.rolcreaterole
  FROM pg_roles r WHERE r.rolname !~ '^pg_'
UNION ALL
SELECT 'M|'||m.roleid::regrole::text||'|'||m.member::regrole::text||'|'||m.admin_option FROM pg_auth_members m
UNION ALL
SELECT 'B|'||d.datname||'|'||pg_get_userbyid(d.datdba)||'|'||coalesce(d.datacl::text,'-')
  FROM pg_database d WHERE d.datname = current_database()
  )
  SELECT count(*) FILTER (WHERE strpos(x, 'lease_seal') > 0),
         encode(sha256(convert_to(coalesce(string_agg(x, E'\n' ORDER BY x COLLATE "C")
                FILTER (WHERE strpos(x, 'lease_seal') > 0), ''), 'UTF8')), 'hex'),
         count(*) FILTER (WHERE strpos(x, 'lease_seal') = 0),
         encode(sha256(convert_to(coalesce(string_agg(x, E'\n' ORDER BY x COLLATE "C")
                FILTER (WHERE strpos(x, 'lease_seal') = 0), ''), 'UTF8')), 'hex')
    INTO v_a, v_d, v_ra, v_rd FROM s;
  IF v_a <> v_ec OR v_d IS DISTINCT FROM v_e THEN
    RAISE EXCEPTION 'CHK08_FAILED: lease_seal rows % digest % (expected % rows, %)', v_a, v_d, v_ec, v_e;
  END IF;
  SELECT p.prosecdef::text||'|'||pg_get_userbyid(p.proowner)||'|'||coalesce(p.proacl::text,'-') INTO v_f
    FROM pg_proc p WHERE p.oid = 'bem_control.lease_seal_unstarted(text,uuid,text)'::regprocedure;
  IF v_f IS DISTINCT FROM 'true|bem_control_owner|{bem_control_owner=X/bem_control_owner}' THEN
    RAISE EXCEPTION 'CHK08_FAILED: function rights %', v_f;
  END IF;
  SELECT count(*) FILTER (WHERE tgenabled = 'O') || '/' || count(*) INTO v_t FROM pg_trigger
   WHERE tgrelid = 'bem_control.chat_lease'::regclass AND tgisinternal AND tgconstrrelid = 'bem_control.lease_seal'::regclass;
  IF v_t <> '2/2' THEN RAISE EXCEPTION 'CHK08_FAILED: FK triggers on chat_lease %', v_t; END IF;
  PERFORM set_config('zc.r1', 'target=socket:' || current_setting('port') || '/' || current_database() || ' ro=on rows=0', true);
  PERFORM set_config('zc.r2', 'seal_rows=' || v_a || ' digest=' || left(v_d, 16) || ' fn=secdef,owner,execute_owner_only fk=' || v_t, true);
  PERFORM set_config('zc.r3', 'rest_rows=' || v_ra || ' rest_digest=' || left(v_rd, 16), true);
END $z$;
SELECT 'CHK08 ' || current_setting('zc.r1');
SELECT 'CHK08 ' || current_setting('zc.r2');
SELECT 'CHK08 ' || current_setting('zc.r3');
ROLLBACK;
\echo ZPROBE_B10_CHK08=OK
