-- ДОКУМЕНТ: sql08_wrap.sql (обёртка установки db/08_zavod_ext_06.sql на сервере, выпуск B10, шаг 3.5.5)
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-15 21:40 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-15 21:40 +02:00
-- ИСПОЛНИТЕЛЬ: Claude, терминальный чат f23e7e60. ОСНОВАНИЕ: DESIGN_B10 v0.24 разделы 4.2 и 7 (SQL 08 — одна
--   транзакция, только новые объекты, точная проверка состава изменений).
-- КАК РАБОТАЕТ: команда оператора подаёт в psql (суперпользователь postgres, база bem) эту обёртку, в которую на место
--   строки-метки вставлены байты файла 08 из проверенного пакета. Всё — одна транзакция:
--   1) отказ, если сервер не PostgreSQL 16 или объекты Z-EXT-06 уже есть (SQL08_ALREADY_PRESENT);
--   2) снимок каталога всех несистемных схем ДО (схемы, таблицы, столбцы, ограничения, индексы, функции, триггеры,
--      права по умолчанию, политики, роли, членство, права базы);
--   3) файл 08; 4) снимок ПОСЛЕ;
--   5) убрано или изменено хоть что-то из прежнего → откат; добавленные строки каталога сверяются с SHA-256,
--      полученной в CI на той же цепочке базы (переменная psql expect) → иначе откат; в lease_seal строк нет;
--   6) COMMIT и строка ZPROBE_B10_SQL08=OK. Ошибка в любом месте → psql выходит с кодом 3, транзакция откатывается.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL search_path = pg_catalog, pg_temp;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '120s';
SELECT set_config('zs.expect', :'expect', true) IS NULL AS skip \gset zs_
DO $z$ BEGIN
  IF current_setting('server_version_num')::int / 10000 <> 16 THEN
    RAISE EXCEPTION 'SQL08_REFUSED: server is not PostgreSQL 16; nothing changed';
  END IF;
  IF to_regclass('bem_control.lease_seal') IS NOT NULL
     OR to_regprocedure('bem_control.lease_seal_unstarted(text,uuid,text)') IS NOT NULL THEN
    RAISE EXCEPTION 'SQL08_ALREADY_PRESENT: lease_seal or lease_seal_unstarted exists; nothing changed';
  END IF;
END $z$;
CREATE FUNCTION pg_temp.zs_snap() RETURNS SETOF text LANGUAGE sql STABLE AS $f$
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
SELECT 'T|'||t.tgrelid::regclass::text||'|'||t.tgname||'|'||pg_get_triggerdef(t.oid)
  FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE NOT t.tgisinternal AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
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
$f$;
CREATE TEMP TABLE zs_before ON COMMIT DROP AS SELECT x FROM pg_temp.zs_snap() x;
--@@SQL08@@
CREATE TEMP TABLE zs_after ON COMMIT DROP AS SELECT x FROM pg_temp.zs_snap() x;
DO $z$ DECLARE r int; rs text; a int; d text; e text := current_setting('zs.expect'); n bigint; BEGIN
  SELECT count(*), string_agg(x, ' ; ' ORDER BY x COLLATE "C") INTO r, rs
    FROM (SELECT x FROM zs_before EXCEPT ALL SELECT x FROM zs_after) q;
  IF r > 0 THEN
    RAISE EXCEPTION 'SQL08_REFUSED: % existing catalog rows removed or changed (%); nothing changed', r, left(rs, 200);
  END IF;
  SELECT count(*), encode(sha256(convert_to(coalesce(string_agg(x, E'\n' ORDER BY x COLLATE "C"), ''), 'UTF8')), 'hex')
    INTO a, d FROM (SELECT x FROM zs_after EXCEPT ALL SELECT x FROM zs_before) q;
  IF d IS DISTINCT FROM e THEN
    RAISE EXCEPTION 'SQL08_REFUSED: added % rows, digest % (expected %); nothing changed', a, d, e;
  END IF;
  SELECT count(*) INTO n FROM bem_control.lease_seal;
  IF n <> 0 THEN RAISE EXCEPTION 'SQL08_REFUSED: lease_seal has % rows; nothing changed', n; END IF;
  PERFORM set_config('zs.result', 'added=' || a || ' digest=' || left(d, 16), true);
END $z$;
SELECT 'ZPROBE_B10_SQL08_CHECKED ' || current_setting('zs.result');
COMMIT;
SELECT 'ZPROBE_B10_SQL08=OK table=' || coalesce(to_regclass('bem_control.lease_seal')::text, 'MISSING')
       || ' function=' || coalesce(to_regprocedure('bem_control.lease_seal_unstarted(text,uuid,text)')::text, 'MISSING');
