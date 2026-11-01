-- ДОКУМЕНТ: db/test_ext04_session_start.sql
-- ВЕРСИЯ: v0.4  СТАТУС: DRAFT
-- ДАТА СОЗДАНИЯ: 2026-11-01 13:47 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 16:24 +02:00 (v0.4: срок аренды T47–T49; v0.3: аудит M33-06 — тревоги клетки T30–T46; v0.2: аудит C33-01 — живая сессия место не освобождает; M33-02 — lease_stop_check)
-- ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
-- НАЗНАЧЕНИЕ: проверка Z-EXT-04 (карта 3.3.8.5): ответы lease_reserve_start, lease_mark_running,
--   lease_start_reconcile; одна живая сессия на ячейку; предел 6 запусков в минуту; кто что может вызвать.
-- ОГРАНИЧЕНИЯ: всё в одной транзакции и откатывается; база после проверки та же. Запуск от postgres.
\set ON_ERROR_STOP on
BEGIN;
DO $t$
DECLARE
    a uuid := 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    b uuid := 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
    c uuid := 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
    d uuid := 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    e uuid := 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee';
    f uuid := 'ffffffff-ffff-4fff-8fff-ffffffffffff';
    g uuid := '99999999-9999-4999-8999-999999999999';
    v text;
    n integer;
    tenant uuid := gen_random_uuid();
    k integer := 0;
    x uuid;
BEGIN
    FOREACH x IN ARRAY ARRAY[a, b, c, e, f, g] LOOP
        k := k + 1;
        INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
                                            holder_session, rules_commit, code_commit, status, opened_by)
        VALUES (x, tenant, '0' || k || '_ci_start', 'Z0000' || k, 1, gen_random_uuid(), 'ci-session-' || k,
                repeat('a', 40), repeat('b', 40), 'OPEN', 'ci');
    END LOOP;

    v := bem_control.lease_reserve_start(a);   IF v <> 'RESERVED'        THEN RAISE EXCEPTION 'T01 %', v; END IF;
    v := bem_control.lease_reserve_start(b);   IF v <> 'BUSY'            THEN RAISE EXCEPTION 'T02 %', v; END IF;
    v := bem_control.lease_reserve_start(a);   IF v <> 'ALREADY_STARTED' THEN RAISE EXCEPTION 'T03 %', v; END IF;
    v := bem_control.lease_reserve_start(d);   IF v <> 'LEASE_NOT_OPEN'  THEN RAISE EXCEPTION 'T04 %', v; END IF;
    v := bem_control.lease_mark_running(b);    IF v <> 'NOT_STARTING'    THEN RAISE EXCEPTION 'T05 %', v; END IF;
    v := bem_control.lease_mark_running(a);    IF v <> 'RUNNING'         THEN RAISE EXCEPTION 'T06 %', v; END IF;
    n := bem_control.lease_start_reconcile(ARRAY[a], false); IF n <> 0  THEN RAISE EXCEPTION 'T07 %', n; END IF;
    n := bem_control.lease_start_reconcile('{}', false);     IF n <> 1  THEN RAISE EXCEPTION 'T08 %', n; END IF;
    SELECT status INTO v FROM bem_control.session_start WHERE lease_id = a;
    IF v <> 'INTERRUPTED' THEN RAISE EXCEPTION 'T09 %', v; END IF;

    -- Отметка «работает» позже 2 минут — TOO_LATE, бронь остаётся (аудит C33-01): место держит, пока служба жива.
    v := bem_control.lease_reserve_start(b);   IF v <> 'RESERVED'        THEN RAISE EXCEPTION 'T10 %', v; END IF;
    UPDATE bem_control.session_start SET reserved_at = clock_timestamp() - interval '3 minutes' WHERE lease_id = b;
    v := bem_control.lease_mark_running(b);    IF v <> 'TOO_LATE'        THEN RAISE EXCEPTION 'T11 %', v; END IF;
    SELECT status INTO v FROM bem_control.session_start WHERE lease_id = b;
    IF v <> 'STARTING' THEN RAISE EXCEPTION 'T12 %', v; END IF;
    IF bem_control.lease_start_overdue() <> ARRAY[b] THEN RAISE EXCEPTION 'T12a %', bem_control.lease_start_overdue(); END IF;
    n := bem_control.lease_start_reconcile(ARRAY[b], false); IF n <> 0  THEN RAISE EXCEPTION 'T12b live overdue released %', n; END IF;
    v := bem_control.lease_reserve_start(c);   IF v <> 'BUSY'            THEN RAISE EXCEPTION 'T12c %', v; END IF;
    n := bem_control.lease_start_reconcile('{}', false);     IF n <> 1  THEN RAISE EXCEPTION 'T12d %', n; END IF;
    SELECT status INTO v FROM bem_control.session_start WHERE lease_id = b;
    IF v <> 'START_FAILED' THEN RAISE EXCEPTION 'T12e %', v; END IF;
    IF bem_control.lease_start_overdue() <> '{}'::uuid[] THEN RAISE EXCEPTION 'T12f'; END IF;

    -- Первый проход после загрузки: живую сессию не трогает (аудит C33-01), неживую STARTING — START_FAILED.
    v := bem_control.lease_reserve_start(c);   IF v <> 'RESERVED'        THEN RAISE EXCEPTION 'T13 %', v; END IF;
    n := bem_control.lease_start_reconcile(ARRAY[c], true);  IF n <> 0  THEN RAISE EXCEPTION 'T14a %', n; END IF;
    n := bem_control.lease_start_reconcile('{}', true);      IF n <> 1  THEN RAISE EXCEPTION 'T14 %', n; END IF;

    -- Предел: 6 броней за 60 секунд (3 настоящие + 3 добавленные) — RATE_LIMITED, без записи.
    INSERT INTO bem_control.session_start_log (lease_id, outcome)
    SELECT gen_random_uuid(), 'RESERVED' FROM generate_series(1, 3);
    v := bem_control.lease_reserve_start(e);   IF v <> 'RATE_LIMITED'    THEN RAISE EXCEPTION 'T15 %', v; END IF;
    IF EXISTS (SELECT 1 FROM bem_control.session_start WHERE lease_id = e) THEN RAISE EXCEPTION 'T16'; END IF;
    UPDATE bem_control.session_start_log SET at = at - interval '2 minutes';

    -- Аренда закрыта, служба не жива — ENDED.
    v := bem_control.lease_reserve_start(e);   IF v <> 'RESERVED'        THEN RAISE EXCEPTION 'T17 %', v; END IF;
    v := bem_control.lease_mark_running(e);    IF v <> 'RUNNING'         THEN RAISE EXCEPTION 'T18 %', v; END IF;
    UPDATE bem_control.chat_lease SET status = 'COMPLETED', closed_at = clock_timestamp(),
           completion_evidence_id = gen_random_uuid(), result_evidence_id = gen_random_uuid(),
           memory_evidence_id = gen_random_uuid(), next_evidence_id = gen_random_uuid(), report_id = gen_random_uuid()
     WHERE lease_id = e;
    n := bem_control.lease_start_reconcile('{}', false);     IF n <> 1  THEN RAISE EXCEPTION 'T19 %', n; END IF;
    SELECT status INTO v FROM bem_control.session_start WHERE lease_id = e;
    IF v <> 'ENDED' THEN RAISE EXCEPTION 'T20 %', v; END IF;
    v := bem_control.lease_reserve_start(e);   IF v <> 'ALREADY_STARTED' THEN RAISE EXCEPTION 'T21 %', v; END IF;

    -- Срок аренды (вопрос аудитора «а»): запуск позже 30 минут после открытия — LEASE_EXPIRED, без брони.
    x := gen_random_uuid();
    INSERT INTO bem_control.chat_lease (lease_id, tenant_id, role_key, chat_number, generation, work_item_id,
                                        holder_session, rules_commit, code_commit, status, opened_by, opened_at)
    VALUES (x, tenant, '07_ci_start', 'Z00007', 1, gen_random_uuid(), 'ci-session-7',
            repeat('a', 40), repeat('b', 40), 'OPEN', 'ci', clock_timestamp() - interval '31 minutes');
    v := bem_control.lease_reserve_start(x);   IF v <> 'LEASE_EXPIRED'   THEN RAISE EXCEPTION 'T47 %', v; END IF;
    IF EXISTS (SELECT 1 FROM bem_control.session_start WHERE lease_id = x) THEN RAISE EXCEPTION 'T48'; END IF;

    -- Права: zstarter бронирует и сверяет, но не отмечает «работает» и не читает таблицы.
    SET LOCAL ROLE zstarter;
    v := bem_control.lease_reserve_start(f);   IF v <> 'RESERVED'        THEN RAISE EXCEPTION 'T22 %', v; END IF;
    IF bem_control.lease_start_overdue() <> '{}'::uuid[] THEN RAISE EXCEPTION 'T22a'; END IF;
    v := bem_control.lease_stop_check(f);      IF v <> 'OPEN'            THEN RAISE EXCEPTION 'T22b %', v; END IF;
    v := bem_control.lease_stop_check(d);      IF v <> 'LEASE_NOT_OPEN'  THEN RAISE EXCEPTION 'T22c %', v; END IF;
    v := bem_control.lease_stop_check(e);      IF v <> 'LEASE_NOT_OPEN'  THEN RAISE EXCEPTION 'T22d closed %', v; END IF;
    BEGIN
        PERFORM bem_control.lease_mark_running(f);
        RAISE EXCEPTION 'T23 zstarter marked running';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM 1 FROM bem_control.session_start;
        RAISE EXCEPTION 'T24 zstarter read session_start';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM 1 FROM bem_control.chat_lease;
        RAISE EXCEPTION 'T25 zstarter read chat_lease';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    RESET ROLE;
    SET LOCAL ROLE bem_kernel_rw;
    BEGIN
        PERFORM bem_control.lease_reserve_start(f);
        RAISE EXCEPTION 'T26 kernel reserved a start';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM bem_control.lease_start_reconcile('{}', false);
        RAISE EXCEPTION 'T27 kernel reconciled';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM bem_control.lease_start_overdue();
        RAISE EXCEPTION 'T27a kernel read overdue';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM bem_control.lease_stop_check(f);
        RAISE EXCEPTION 'T27b kernel checked a stop';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    v := bem_control.lease_mark_running(f);    IF v <> 'RUNNING'         THEN RAISE EXCEPTION 'T28 %', v; END IF;
    RESET ROLE;

    -- Вторая живая строка напрямую — отказ уникального индекса.
    BEGIN
        INSERT INTO bem_control.session_start (lease_id, status) VALUES (g, 'STARTING');
        RAISE EXCEPTION 'T29 second live row accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    -- Сеанс дольше срока (4 часа 5 минут) попадает в список на остановку.
    UPDATE bem_control.session_start SET running_at = clock_timestamp() - interval '4 hours 10 minutes' WHERE lease_id = f;
    IF bem_control.lease_start_overdue() <> ARRAY[f] THEN RAISE EXCEPTION 'T49 %', bem_control.lease_start_overdue(); END IF;

    -- Тревоги клетки (аудит M33-06): запись, повтор ключа, плохая запись, доставка, ошибка канала, права.
    DECLARE
        k1 text := repeat('a', 32);
        k2 text := repeat('b', 32);
        x  uuid;
        n  integer;
        w  text;
    BEGIN
        SET LOCAL ROLE zstarter;
        w := bem_control.cell_alert_store(k1, 'zagent-start', 'overflow', clock_timestamp()); IF w <> 'STORED'    THEN RAISE EXCEPTION 'T30 %', w; END IF;
        w := bem_control.cell_alert_store(k1, 'zagent-start', 'overflow', clock_timestamp()); IF w <> 'DUPLICATE' THEN RAISE EXCEPTION 'T31 %', w; END IF;
        w := bem_control.cell_alert_store('BAD', 'zagent-start', 'x', clock_timestamp());    IF w <> 'INVALID'   THEN RAISE EXCEPTION 'T32 %', w; END IF;
        w := bem_control.cell_alert_store(k2, 'zagent-start', '', clock_timestamp());        IF w <> 'INVALID'   THEN RAISE EXCEPTION 'T32a %', w; END IF;
        SELECT d.alert_id INTO x FROM bem_control.cell_alert_due(10) d;
        IF x IS NULL THEN RAISE EXCEPTION 'T33 nothing due'; END IF;
        w := bem_control.cell_alert_result(x, NULL, 'channel down');  IF w <> 'RETRY' THEN RAISE EXCEPTION 'T34 %', w; END IF;
        SELECT count(*) INTO n FROM bem_control.cell_alert_due(10);   IF n <> 0 THEN RAISE EXCEPTION 'T35 retried alert due at once (%)', n; END IF;
        BEGIN
            PERFORM bem_control.cell_alert_result(x, 'r', 'e');
            RAISE EXCEPTION 'T36 both receipt and error accepted';
        EXCEPTION WHEN raise_exception THEN
            IF SQLERRM <> 'CELL_ALERT_RESULT_SHAPE' THEN RAISE; END IF;
        END;
        w := bem_control.cell_alert_result(x, 'telegram:42', NULL);   IF w <> 'DELIVERED' THEN RAISE EXCEPTION 'T37 %', w; END IF;
        w := bem_control.cell_alert_result(x, 'telegram:43', NULL);   IF w <> 'ALREADY_DELIVERED' THEN RAISE EXCEPTION 'T38 %', w; END IF;
        w := bem_control.cell_alert_result(gen_random_uuid(), 'r', NULL); IF w <> 'UNKNOWN' THEN RAISE EXCEPTION 'T39 %', w; END IF;
        n := bem_control.cell_alert_stale(interval '0 seconds');     IF n <> 0 THEN RAISE EXCEPTION 'T40 delivered counted stale (%)', n; END IF;
        w := bem_control.cell_alert_store(k2, 'zagent-start', 'second', clock_timestamp()); IF w <> 'STORED' THEN RAISE EXCEPTION 'T41 %', w; END IF;
        n := bem_control.cell_alert_stale(interval '0 seconds');     IF n <> 1 THEN RAISE EXCEPTION 'T42 stale %', n; END IF;
        BEGIN
            UPDATE bem_control.cell_alert SET receipt = 'forged';
            RAISE EXCEPTION 'T43 zstarter wrote cell_alert';
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;
        RESET ROLE;
        SELECT receipt INTO w FROM bem_control.cell_alert WHERE alert_id = x;
        IF w IS DISTINCT FROM 'telegram:42' THEN RAISE EXCEPTION 'T44 receipt %', w; END IF;
        SET LOCAL ROLE bem_kernel_rw;
        BEGIN
            PERFORM bem_control.cell_alert_store(repeat('c', 32), 'zagent-start', 'x', clock_timestamp());
            RAISE EXCEPTION 'T45 kernel stored an alert';
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;
        BEGIN
            PERFORM bem_control.cell_alert_result(x, NULL, 'e');
            RAISE EXCEPTION 'T46 kernel marked an alert';
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;
        RESET ROLE;
    END;
END
$t$;
\echo ZAVOD_EXT04_SESSION_START_TEST=PASS
ROLLBACK;
