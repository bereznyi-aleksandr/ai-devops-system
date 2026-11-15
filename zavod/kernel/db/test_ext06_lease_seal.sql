-- ДОКУМЕНТ: db/test_ext06_lease_seal.sql
-- ВЕРСИЯ: v0.1  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-11-14 22:04 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 22:04 +02:00
-- ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 09» (3037f186-2fea-4583-9aca-8c36857f6aff)
-- НАЗНАЧЕНИЕ: проверка Z-EXT-06 (08_zavod_ext_06.sql, проект B10 v0.17 раздел 4.2; CI 6, 7, 32, 40, 41 и права):
--   ответы lease_seal_unstarted (SEALED_NOW, ALREADY_SEALED, REFUSED_*), три строки печати с одним временем,
--   бронь после печати — ALREADY_STARTED, сверка и «просроченные» печать не трогают, отказ ничего не пишет,
--   владелец видит команды привратника сквозь защиту строк (RLS), кто может вызвать функцию и писать таблицы.
--   Одновременная печать и бронь (CI 10) — отдельно в kernel_ci.sh: нужны два сеанса.
-- ОГРАНИЧЕНИЯ: всё в одной транзакции и откатывается; база после проверки та же. Запуск от postgres.
--   Проверки «подложенной строки» идут во вложенном блоке, который откатывается своим исключением ZT_UNDO.
\set ON_ERROR_STOP on
BEGIN;
DO $t$
DECLARE
    a  uuid := 'a6a6a6a6-aaaa-4aaa-8aaa-aaaaaaaaaaa6';   -- своя аренда серии pb1ci1, будет запечатана
    b  uuid := 'b6b6b6b6-bbbb-4bbb-8bbb-bbbbbbbbbbb6';   -- своя, но есть строка session_start (настоящий отказ запуска)
    c  uuid := 'c6c6c6c6-cccc-4ccc-8ccc-ccccccccccc6';   -- своя, есть строка session_start_log
    d  uuid := 'd6d6d6d6-dddd-4ddd-8ddd-ddddddddddd6';   -- своя, есть команда привратника (другой заказчик, RLS)
    e  uuid := 'e6e6e6e6-eeee-4eee-8eee-eeeeeeeeeee6';   -- чужая: держатель другой серии
    f  uuid := 'f6f6f6f6-ffff-4fff-8fff-fffffffffff6';   -- чужая: открыта не бегунком пробы
    g  uuid := '96969696-9999-4999-8999-999999999996';   -- чужая: другая роль
    h  uuid := '86868686-8888-4888-8888-888888888886';   -- чужая: аренда закрыта
    q  uuid := '76767676-7777-4777-8777-777777777776';   -- обычная аренда для брони после печати
    P  text := repeat('1', 64);
    P2 text := repeat('2', 64);
    v  text;
    n  integer;
    k  integer := 0;
    x  uuid;
    t0 timestamptz;
    r_seal  bem_control.lease_seal;
    r_start bem_control.session_start;
BEGIN
    -- Аренды. У каждой свой заказчик: «одна открытая аренда на роль» действует в пределах заказчика.
    FOREACH x IN ARRAY ARRAY[a, b, c, d] LOOP
        k := k + 1;
        INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
                                            holder_session, rules_commit, code_commit, status, opened_by)
        VALUES (x, gen_random_uuid(), '01_install_probe', 'Z0000' || k, 1, gen_random_uuid(),
                'zprobe-pb1ci' || k, repeat('a', 40), repeat('b', 40), 'OPEN', 'zprobe-run');
    END LOOP;
    INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
                                        holder_session, rules_commit, code_commit, status, opened_by)
    VALUES (e, gen_random_uuid(), '01_install_probe', 'Z00005', 1, gen_random_uuid(), 'zprobe-other',
            repeat('a', 40), repeat('b', 40), 'OPEN', 'zprobe-run'),
           (f, gen_random_uuid(), '01_install_probe', 'Z00006', 1, gen_random_uuid(), 'zprobe-pb1ci6',
            repeat('a', 40), repeat('b', 40), 'OPEN', 'ci'),
           (g, gen_random_uuid(), '02_install_probe', 'Z00007', 1, gen_random_uuid(), 'zprobe-pb1ci7',
            repeat('a', 40), repeat('b', 40), 'OPEN', 'zprobe-run'),
           (q, gen_random_uuid(), '03_ci_start', 'Z00009', 1, gen_random_uuid(), 'ci-session-9',
            repeat('a', 40), repeat('b', 40), 'OPEN', 'ci');
    INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
                                        holder_session, rules_commit, code_commit, status, opened_by, closed_at,
                                        completion_evidence_id, result_evidence_id, memory_evidence_id,
                                        next_evidence_id, report_id)
    VALUES (h, gen_random_uuid(), '01_install_probe', 'Z00008', 1, gen_random_uuid(), 'zprobe-pb1ci8',
            repeat('a', 40), repeat('b', 40), 'COMPLETED', 'zprobe-run', clock_timestamp(),
            gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), gen_random_uuid());

    -- S01–S05: аргументы.
    v := bem_control.lease_seal_unstarted('pb1/ci1', a, P);        IF v <> 'REFUSED_ARGS' THEN RAISE EXCEPTION 'S01 %', v; END IF;
    v := bem_control.lease_seal_unstarted(repeat('x', 41), a, P);  IF v <> 'REFUSED_ARGS' THEN RAISE EXCEPTION 'S02 %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci1', a, repeat('1', 63)); IF v <> 'REFUSED_ARGS' THEN RAISE EXCEPTION 'S03 short %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci1', a, 'ABCDEF' || repeat('0', 58)); IF v <> 'REFUSED_ARGS' THEN RAISE EXCEPTION 'S04 upper %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci1', NULL, P);      IF v <> 'REFUSED_ARGS' THEN RAISE EXCEPTION 'S05 %', v; END IF;
    v := bem_control.lease_seal_unstarted(NULL, a, P);             IF v <> 'REFUSED_ARGS' THEN RAISE EXCEPTION 'S05a %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci1', a, NULL);      IF v <> 'REFUSED_ARGS' THEN RAISE EXCEPTION 'S05b %', v; END IF;

    -- S06–S10: не своя аренда (держатель вычисляется из серии).
    v := bem_control.lease_seal_unstarted('pb1ci1', gen_random_uuid(), P); IF v <> 'REFUSED_NOT_OWN' THEN RAISE EXCEPTION 'S06 missing %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci5', e, P);         IF v <> 'REFUSED_NOT_OWN' THEN RAISE EXCEPTION 'S07 holder %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci6', f, P);         IF v <> 'REFUSED_NOT_OWN' THEN RAISE EXCEPTION 'S08 opened_by %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci7', g, P);         IF v <> 'REFUSED_NOT_OWN' THEN RAISE EXCEPTION 'S09 role %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci8', h, P);         IF v <> 'REFUSED_NOT_OWN' THEN RAISE EXCEPTION 'S10 closed %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci2', a, P);         IF v <> 'REFUSED_NOT_OWN' THEN RAISE EXCEPTION 'S10a other series %', v; END IF;

    -- S11 (CI 7): строка session_start без печати (настоящий неудачный запуск) → REFUSED_HAS_SESSION.
    INSERT INTO bem_control.session_start (lease_id, status, reserved_at, ended_at)
         VALUES (b, 'START_FAILED', clock_timestamp(), clock_timestamp());
    v := bem_control.lease_seal_unstarted('pb1ci2', b, P);         IF v <> 'REFUSED_HAS_SESSION' THEN RAISE EXCEPTION 'S11 %', v; END IF;

    -- S12: строка журнала запуска без строки запуска → REFUSED_HAS_LOG.
    INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (c, 'LEASE_EXPIRED');
    v := bem_control.lease_seal_unstarted('pb1ci3', c, P);         IF v <> 'REFUSED_HAS_LOG' THEN RAISE EXCEPTION 'S12 %', v; END IF;

    -- S13: команда привратника по аренде другого заказчика: владелец функции видит её сквозь RLS → REFUSED_HAS_GATE.
    INSERT INTO bem_control.gate_command (tenant_id, lease_id, nonce, body_sha256, kind, args)
         SELECT l.tenant_id, d, repeat('d', 64), repeat('e', 64), 'HEARTBEAT', '{}'::jsonb
           FROM bem_control.chat_lease l WHERE l.lease_id = d;
    v := bem_control.lease_seal_unstarted('pb1ci4', d, P);         IF v <> 'REFUSED_HAS_GATE' THEN RAISE EXCEPTION 'S13 %', v; END IF;

    -- S14: отказы ничего не записали.
    IF EXISTS (SELECT 1 FROM bem_control.lease_seal) THEN RAISE EXCEPTION 'S14 seal row after refusals'; END IF;
    SELECT count(*) INTO n FROM bem_control.session_start;         IF n <> 1 THEN RAISE EXCEPTION 'S14a session_start rows %', n; END IF;
    SELECT count(*) INTO n FROM bem_control.session_start_log;     IF n <> 1 THEN RAISE EXCEPTION 'S14b log rows %', n; END IF;

    -- S14c (CI 9, REL65 L-04): сбой второй вставки (подложенный отказ на session_start) → откат всей печати:
    --   ни строки lease_seal, ни session_start, ни session_start_log. Ловушка снимается сразу после.
    EXECUTE 'CREATE FUNCTION pg_temp.zt_fail_insert() RETURNS trigger LANGUAGE plpgsql AS '
            '$f$BEGIN RAISE EXCEPTION ''ZT_SECOND_INSERT''; END$f$';
    EXECUTE 'CREATE TRIGGER zt_fail_second BEFORE INSERT ON bem_control.session_start '
            'FOR EACH ROW EXECUTE FUNCTION pg_temp.zt_fail_insert()';
    BEGIN
        v := bem_control.lease_seal_unstarted('pb1ci1', a, P);
        RAISE EXCEPTION 'S14c no error, got %', v;
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM <> 'ZT_SECOND_INSERT' THEN RAISE; END IF;
    END;
    EXECUTE 'DROP TRIGGER zt_fail_second ON bem_control.session_start';
    IF EXISTS (SELECT 1 FROM bem_control.lease_seal WHERE lease_id = a) THEN RAISE EXCEPTION 'S14c seal row kept'; END IF;
    SELECT count(*) INTO n FROM bem_control.session_start;         IF n <> 1 THEN RAISE EXCEPTION 'S14c session_start %', n; END IF;
    SELECT count(*) INTO n FROM bem_control.session_start_log;     IF n <> 1 THEN RAISE EXCEPTION 'S14c log %', n; END IF;

    -- S15–S17 (CI 6): печать — три строки с одним временем, sealed_by = кто вошёл.
    t0 := clock_timestamp();
    v := bem_control.lease_seal_unstarted('pb1ci1', a, P);         IF v <> 'SEALED_NOW' THEN RAISE EXCEPTION 'S15 %', v; END IF;
    SELECT s.* INTO r_seal FROM bem_control.lease_seal s WHERE s.lease_id = a;
    IF r_seal.series <> 'pb1ci1' OR r_seal.reason <> 'NO_SESSION_PRE_START' OR r_seal.proof_sha256 <> P
       OR r_seal.sealed_by <> 'postgres' OR r_seal.sealed_at < t0 THEN
        RAISE EXCEPTION 'S16 seal row %', r_seal;
    END IF;
    SELECT st.* INTO r_start FROM bem_control.session_start st WHERE st.lease_id = a;
    IF r_start.status <> 'START_FAILED' OR r_start.running_at IS NOT NULL
       OR r_start.reserved_at <> r_seal.sealed_at OR r_start.ended_at <> r_seal.sealed_at THEN
        RAISE EXCEPTION 'S17 start row %', r_start;
    END IF;
    SELECT count(*) INTO n FROM bem_control.session_start_log g
     WHERE g.lease_id = a AND g.outcome = 'START_FAILED' AND g.at = r_seal.sealed_at;
    IF n <> 1 THEN RAISE EXCEPTION 'S17a log %', n; END IF;
    SELECT status INTO v FROM bem_control.chat_lease WHERE lease_id = a;
    IF v <> 'OPEN' THEN RAISE EXCEPTION 'S17b lease %', v; END IF;

    -- S18: повтор с тем же доказательством → ALREADY_SEALED, новых строк нет.
    v := bem_control.lease_seal_unstarted('pb1ci1', a, P);         IF v <> 'ALREADY_SEALED' THEN RAISE EXCEPTION 'S18 %', v; END IF;
    SELECT count(*) INTO n FROM bem_control.session_start_log WHERE lease_id = a; IF n <> 1 THEN RAISE EXCEPTION 'S18a %', n; END IF;

    -- S19–S20 (CI 6, 40): бронь после печати → ALREADY_STARTED (и строка журнала); повтор печати → ALREADY_SEALED.
    v := bem_control.lease_reserve_start(a);   IF v <> 'ALREADY_STARTED' THEN RAISE EXCEPTION 'S19 %', v; END IF;
    v := bem_control.lease_reserve_start(a);   IF v <> 'ALREADY_STARTED' THEN RAISE EXCEPTION 'S19a %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci1', a, P);         IF v <> 'ALREADY_SEALED' THEN RAISE EXCEPTION 'S20 %', v; END IF;

    -- S21–S22 (CI 32): другое доказательство, другая серия → REFUSED_INCONSISTENT.
    v := bem_control.lease_seal_unstarted('pb1ci1', a, P2);        IF v <> 'REFUSED_INCONSISTENT' THEN RAISE EXCEPTION 'S21 %', v; END IF;
    v := bem_control.lease_seal_unstarted('pb1ci9', a, P);         IF v <> 'REFUSED_INCONSISTENT' THEN RAISE EXCEPTION 'S22 %', v; END IF;

    -- S23–S27 (CI 32, 41): подложенные строки и правка строки запуска → REFUSED_INCONSISTENT (каждая — отдельно, откат).
    FOR k IN 1..6 LOOP
        BEGIN
            CASE k
            WHEN 1 THEN INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (a, 'RESERVED');
            WHEN 2 THEN INSERT INTO bem_control.session_start_log (lease_id, outcome, at)
                             VALUES (a, 'ALREADY_STARTED', r_seal.sealed_at - interval '1 second');
            WHEN 3 THEN INSERT INTO bem_control.session_start_log (lease_id, outcome) VALUES (a, 'START_FAILED');
            WHEN 4 THEN UPDATE bem_control.session_start_log SET at = at - interval '1 second'
                         WHERE lease_id = a AND outcome = 'START_FAILED';
            WHEN 5 THEN UPDATE bem_control.session_start SET reserved_at = reserved_at - interval '1 second' WHERE lease_id = a;
            WHEN 6 THEN UPDATE bem_control.session_start SET status = 'INTERRUPTED', running_at = ended_at WHERE lease_id = a;
            END CASE;
            v := bem_control.lease_seal_unstarted('pb1ci1', a, P);
            IF v <> 'REFUSED_INCONSISTENT' THEN RAISE EXCEPTION 'S23 case % %', k, v; END IF;
            RAISE EXCEPTION 'ZT_UNDO';
        EXCEPTION WHEN raise_exception THEN
            IF SQLERRM <> 'ZT_UNDO' THEN RAISE; END IF;
        END;
    END LOOP;
    v := bem_control.lease_seal_unstarted('pb1ci1', a, P);         IF v <> 'ALREADY_SEALED' THEN RAISE EXCEPTION 'S27 after undo %', v; END IF;

    -- S28: сверка и «просроченные» печать не трогают; уникальная «одна живая сессия» свободна — другая аренда бронируется.
    IF bem_control.lease_start_overdue() <> '{}'::uuid[] THEN RAISE EXCEPTION 'S28 overdue'; END IF;
    n := bem_control.lease_start_reconcile('{}', true);  IF n <> 0 THEN RAISE EXCEPTION 'S28a reconcile %', n; END IF;
    SELECT status INTO v FROM bem_control.session_start WHERE lease_id = a; IF v <> 'START_FAILED' THEN RAISE EXCEPTION 'S28b %', v; END IF;
    v := bem_control.lease_reserve_start(q);   IF v <> 'RESERVED' THEN RAISE EXCEPTION 'S28c %', v; END IF;

    -- S29–S31: кто может вызвать. Роли — нет права EXECUTE; владелец функции (не суперпользователь) → REFUSED_CALLER.
    FOREACH v IN ARRAY ARRAY['zstarter', 'bem_kernel_rw', 'backup_reader', 'zgate'] LOOP
        EXECUTE format('SET LOCAL ROLE %I', v);
        BEGIN
            PERFORM bem_control.lease_seal_unstarted('pb1ci1', a, P);
            RAISE EXCEPTION 'S29 % called seal', v;
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;
        RESET ROLE;
    END LOOP;
    SET LOCAL SESSION AUTHORIZATION bem_control_owner;
    v := bem_control.lease_seal_unstarted('pb1ci1', a, P);
    RESET SESSION AUTHORIZATION;
    IF v <> 'REFUSED_CALLER' THEN RAISE EXCEPTION 'S30 owner %', v; END IF;
    IF session_user <> 'postgres' THEN RAISE EXCEPTION 'S31 session_user %', session_user; END IF;

    -- S32 (CI 41): ни одна роль, кроме владельца, не может менять три таблицы и не может вызвать функцию;
    --      backup_reader читает признак печати.
    SELECT count(*) INTO n
      FROM pg_catalog.pg_roles r
      CROSS JOIN (VALUES ('bem_control.lease_seal'), ('bem_control.session_start'), ('bem_control.session_start_log')) t(name)
      CROSS JOIN (VALUES ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE')) p(priv)
     WHERE NOT r.rolsuper AND r.rolname <> 'bem_control_owner' AND r.rolname !~ '^pg_'
       AND pg_catalog.has_table_privilege(r.oid, t.name, p.priv);
    IF n <> 0 THEN RAISE EXCEPTION 'S32 write privileges %', n; END IF;
    SELECT count(*) INTO n FROM pg_catalog.pg_roles r
     WHERE NOT r.rolsuper AND r.rolname <> 'bem_control_owner' AND r.rolname !~ '^pg_'
       AND pg_catalog.has_function_privilege(r.oid, 'bem_control.lease_seal_unstarted(text, uuid, text)', 'EXECUTE');
    IF n <> 0 THEN RAISE EXCEPTION 'S32a execute %', n; END IF;
    IF NOT pg_catalog.has_table_privilege('backup_reader', 'bem_control.lease_seal', 'SELECT') THEN RAISE EXCEPTION 'S32b'; END IF;

    -- S33: вид функции — SECURITY DEFINER, владелец, путь поиска.
    SELECT count(*) INTO n FROM pg_catalog.pg_proc p
     WHERE p.oid = 'bem_control.lease_seal_unstarted(text, uuid, text)'::regprocedure
       AND p.prosecdef AND pg_catalog.pg_get_userbyid(p.proowner) = 'bem_control_owner'
       AND p.proconfig = ARRAY['search_path=pg_catalog, pg_temp'];
    IF n <> 1 THEN RAISE EXCEPTION 'S33 function shape'; END IF;
END
$t$;
\echo ZAVOD_EXT06_LEASE_SEAL_TEST=PASS
ROLLBACK;
