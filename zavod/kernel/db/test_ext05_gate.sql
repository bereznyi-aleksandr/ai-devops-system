-- ДОКУМЕНТ: db/test_ext05_gate.sql
-- ВЕРСИЯ: v0.2  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 23:12 +02:00 (v0.2: T14 — FORCE проверяется по каталогу и ролью без BYPASSRLS; bem_control_owner по H1.31 4.4 обходит правила строк)
-- ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
-- НАЗНАЧЕНИЕ: проверка Z-EXT-05 (карта 3.3.10.1, 3.3.10.3): ответы gate_accept и gate_command_status; повтор
--   одноразового номера — отказ (ПБ-5); чужая аренда, неверная сумма, закрытая аренда, неработающая сессия,
--   нестрогий JSON — отказ; текст SQL в теле — только данные; правила строк: чужой заказчик и пустой номер
--   заказчика видят пусто; FORCE включён; кто что может вызвать.
-- ОГРАНИЧЕНИЯ: всё в одной транзакции и откатывается; база после проверки та же. Запуск от postgres.
\set ON_ERROR_STOP on
BEGIN;
DO $t$
DECLARE
    a  uuid := 'a1a1a1a1-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    b  uuid := 'b1b1b1b1-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
    d  uuid := 'd1d1d1d1-dddd-4ddd-8ddd-dddddddddddd';
    t1 uuid := gen_random_uuid();
    t2 uuid := gen_random_uuid();
    n1 text := repeat('1', 64);
    n2 text := repeat('2', 64);
    hb bytea := convert_to('{"kind":"HEARTBEAT","args":{}}', 'UTF8');
    inj bytea := convert_to('{"kind":"PROGRESS","args":{"text":"x''); DROP TABLE bem_control.gate_command; --"}}', 'UTF8');
    bad bytea;
    v  text;
    n  integer;
    i  integer := 0;
BEGIN
    INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
                                        holder_session, rules_commit, code_commit, status, opened_by)
    VALUES (a, t1, '01_ci_gate', 'G00001', 1, gen_random_uuid(), 'ci-gate-1', repeat('a', 40), repeat('b', 40), 'OPEN', 'ci'),
           (b, t2, '02_ci_gate', 'G00002', 1, gen_random_uuid(), 'ci-gate-2', repeat('a', 40), repeat('b', 40), 'OPEN', 'ci');
    INSERT INTO bem_control.session_start (lease_id, status, running_at) VALUES (a, 'RUNNING', clock_timestamp());

    v := bem_control.gate_accept(a, a, n1, encode(sha256(hb), 'hex'), hb);
    IF v !~ '^ACCEPTED [0-9a-f-]{36}$' THEN RAISE EXCEPTION 'T01 %', v; END IF;
    v := bem_control.gate_accept(a, a, n1, encode(sha256(hb), 'hex'), hb);
    IF v <> 'NONCE_REPLAY' THEN RAISE EXCEPTION 'T02 %', v; END IF;
    v := bem_control.gate_accept(a, a, n2, repeat('0', 64), hb);
    IF v <> 'SHA_MISMATCH' THEN RAISE EXCEPTION 'T03 %', v; END IF;
    v := bem_control.gate_accept(a, b, n2, encode(sha256(hb), 'hex'), hb);
    IF v <> 'PEER_MISMATCH' THEN RAISE EXCEPTION 'T04 %', v; END IF;
    v := bem_control.gate_accept(d, d, n2, encode(sha256(hb), 'hex'), hb);
    IF v <> 'LEASE_NOT_OPEN' THEN RAISE EXCEPTION 'T05 %', v; END IF;
    v := bem_control.gate_accept(b, b, n2, encode(sha256(hb), 'hex'), hb);
    IF v <> 'SESSION_NOT_RUNNING' THEN RAISE EXCEPTION 'T06 %', v; END IF;

    -- Нестрогий вид тела — отказ BAD_COMMAND; номер n2 при этом не тратится.
    FOREACH bad IN ARRAY ARRAY[
        convert_to('not json', 'UTF8'),
        convert_to('["HEARTBEAT"]', 'UTF8'),
        convert_to('{"kind":"HEARTBEAT","args":{},"sql":"x"}', 'UTF8'),
        convert_to('{"kind":"HEARTBEAT","kind":"PROGRESS","args":{}}', 'UTF8'),
        convert_to('{"kind":"DROP","args":{}}', 'UTF8'),
        convert_to('{"kind":"HEARTBEAT","args":[]}', 'UTF8'),
        convert_to('{"kind":1,"args":{}}', 'UTF8'),
        convert_to('{"kind":"HEARTBEAT"}', 'UTF8'),
        '\xff'::bytea,
        convert_to('{"kind":"PROGRESS","args":{"text":"' || repeat('x', 16400) || '"}}', 'UTF8')] LOOP
        i := i + 1;
        v := bem_control.gate_accept(a, a, n2, encode(sha256(bad), 'hex'), bad);
        IF v <> 'BAD_COMMAND' THEN RAISE EXCEPTION 'T07.% %', i, v; END IF;
    END LOOP;
    v := bem_control.gate_accept(a, a, repeat('C', 64), encode(sha256(hb), 'hex'), hb);
    IF v <> 'BAD_COMMAND' THEN RAISE EXCEPTION 'T07u %', v; END IF;
    v := bem_control.gate_accept(a, a, n2, encode(sha256(hb), 'hex'), NULL);
    IF v <> 'BAD_COMMAND' THEN RAISE EXCEPTION 'T07n %', v; END IF;

    -- Текст SQL внутри тела — только данные: запись есть, таблица на месте.
    v := bem_control.gate_accept(a, a, n2, encode(sha256(inj), 'hex'), inj);
    IF v !~ '^ACCEPTED ' THEN RAISE EXCEPTION 'T08 %', v; END IF;
    IF to_regclass('bem_control.gate_command') IS NULL THEN RAISE EXCEPTION 'T08 table dropped'; END IF;

    v := bem_control.gate_command_status(a, n1);
    IF v !~ '^ACCEPTED [0-9a-f-]{36}$' THEN RAISE EXCEPTION 'T09 %', v; END IF;
    IF bem_control.gate_command_status(a, repeat('3', 64)) <> 'NONE' THEN RAISE EXCEPTION 'T09a'; END IF;
    IF bem_control.gate_command_status(b, n1) <> 'NONE' THEN RAISE EXCEPTION 'T09b'; END IF;
    IF bem_control.gate_command_status(a, 'x') <> 'NONE' THEN RAISE EXCEPTION 'T09c'; END IF;

    SELECT count(*) INTO n FROM bem_control.gate_command_log WHERE outcome = 'BAD_COMMAND';
    IF n <> 12 THEN RAISE EXCEPTION 'T10 bad %', n; END IF;
    SELECT count(DISTINCT outcome) INTO n FROM bem_control.gate_command_log;
    IF n <> 7 THEN RAISE EXCEPTION 'T10 outcomes %', n; END IF;
    IF current_setting('app.tenant_id', true) IS DISTINCT FROM '' THEN
        RAISE EXCEPTION 'T10 tenant left set: %', current_setting('app.tenant_id', true);
    END IF;

    -- Правила строк (И.7а п.3): ядро видит только строки заказчика, которого поставило; без номера — пусто.
    SET LOCAL ROLE bem_kernel_rw;
    SELECT count(*) INTO n FROM bem_control.gate_command;               IF n <> 0 THEN RAISE EXCEPTION 'T11 none %', n; END IF;
    PERFORM set_config('app.tenant_id', t2::text, true);
    SELECT count(*) INTO n FROM bem_control.gate_command;               IF n <> 0 THEN RAISE EXCEPTION 'T11 other %', n; END IF;
    PERFORM set_config('app.tenant_id', t1::text, true);
    SELECT count(*) INTO n FROM bem_control.gate_command;               IF n <> 2 THEN RAISE EXCEPTION 'T11 own %', n; END IF;
    BEGIN
        INSERT INTO bem_control.gate_command (tenant_id, lease_id, nonce, body_sha256, kind, args)
        VALUES (t1, a, repeat('4', 64), repeat('4', 64), 'HEARTBEAT', '{}');
        RAISE EXCEPTION 'T12 kernel inserted a command';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM bem_control.gate_accept(a, a, repeat('5', 64), encode(sha256(hb), 'hex'), hb);
        RAISE EXCEPTION 'T13 kernel called gate_accept';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM set_config('app.tenant_id', '', true);
    RESET ROLE;

    -- FORCE включён; владелец bem_control_owner имеет BYPASSRLS по H1.31 4.4 (только владелец функций, входа нет),
    -- поэтому FORCE проверяется по каталогу, а пустой ответ — ролью без BYPASSRLS выше (T11).
    IF NOT (SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid = 'bem_control.gate_command'::regclass) THEN
        RAISE EXCEPTION 'T14 rls not forced';
    END IF;
    IF (SELECT rolcanlogin OR NOT rolbypassrls FROM pg_roles WHERE rolname = 'bem_control_owner') THEN
        RAISE EXCEPTION 'T14 owner role attributes changed';
    END IF;

    -- Привратник: только две функции; таблицы ему закрыты.
    SET LOCAL ROLE zgate;
    BEGIN
        SELECT count(*) INTO n FROM bem_control.gate_command;
        RAISE EXCEPTION 'T15 zgate read the table';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO bem_control.gate_command_log (outcome) VALUES ('ACCEPTED');
        RAISE EXCEPTION 'T16 zgate wrote the log';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    v := bem_control.gate_accept(a, a, repeat('6', 64), encode(sha256(hb), 'hex'), hb);
    IF v !~ '^ACCEPTED ' THEN RAISE EXCEPTION 'T17 %', v; END IF;
    BEGIN
        PERFORM bem_control.lease_reserve_start(b);
        RAISE EXCEPTION 'T18 zgate reserved a start';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    RESET ROLE;
END
$t$;
\echo ZAVOD_EXT05_GATE_TEST=PASS
ROLLBACK;
