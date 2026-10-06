\set ON_ERROR_STOP on

-- 04_backup_window.sql — четыре функции окна копирования.
-- Запускает АДМИНИСТРАТОР КЛАСТЕРА, после закрытия окна мигратора.
-- Мигратор этот файл не видит и роль bem_backup_ctl_owner не получает
-- ни на одну команду (замечание C-H113-R13-01).
--
-- Файл идёт одной транзакцией ключом --single-transaction обёртки,
-- поэтому BEGIN и COMMIT внутри него нет. Курсор без WITH HOLD вне
-- транзакции даёт ошибку 25P01 — запустить файл по команде за раз
-- нельзя.
DECLARE bem_backup_guard CURSOR FOR SELECT 1;
CLOSE bem_backup_guard;

SET ROLE bem_control_owner;
-- Владелец меняется до создания, потому что SECURITY DEFINER работает
-- правами владельца, а не вызывающего. Право создавать объекты в схеме
-- выдаётся ровно на эти функции и отзывается сразу после них.
GRANT CREATE ON SCHEMA bem_control TO bem_backup_ctl_owner;
SET ROLE bem_backup_ctl_owner;

-- Функция 21 — открыть окно копирования.
CREATE OR REPLACE FUNCTION bem_control.backup_window_open(p_limit integer DEFAULT 2)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF session_user <> 'bem_backup_admin' THEN
        RAISE EXCEPTION 'BACKUP_WINDOW_WRONG_CALLER: %', session_user;
    END IF;
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 4 THEN
        RAISE EXCEPTION 'BACKUP_WINDOW_BAD_LIMIT: %', p_limit;
    END IF;

    -- имя роли записано в тексте функции и аргументом не передаётся:
    -- подставить сюда другую роль вызывающий не может
    EXECUTE format('ALTER ROLE backup_reader LOGIN CONNECTION LIMIT %s', p_limit);

    -- H1.24, L-BW-01: новое окно начинается без признаков прошлого закрытия.
    UPDATE bem_control.backup_window
       SET locked_xid  = NULL,
           zero_streak = 0,
           closed_at   = NULL
     WHERE id = 1;
    RETURN true;
END;
$$;

-- Функция 22 — запереть вход. Первая фаза закрытия.
-- Эта транзакция обязана завершиться фиксацией до того, как кто-то
-- начнёт выгонять сеансы: пока фиксации нет, чужое подключение видит
-- старую строку роли и входит законно (замечание M-H18-R8-02).
CREATE OR REPLACE FUNCTION bem_control.backup_window_lock()
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF session_user <> 'bem_backup_admin' THEN
        RAISE EXCEPTION 'BACKUP_WINDOW_WRONG_CALLER: %', session_user;
    END IF;

    -- Номер своей транзакции записывается рядом с замком. Он нужен
    -- второй фазе, чтобы отличить «замок зафиксирован» от «замок
    -- поставлен в этой же незавершённой транзакции».
    UPDATE bem_control.backup_window
       SET locked_xid  = pg_current_xact_id(),
           locked_at   = clock_timestamp(),
           locked_by   = session_user,
           zero_streak = 0,
           closed_at   = NULL
     WHERE id = 1;

    -- имя роли записано в тексте функции и аргументом не передаётся
    ALTER ROLE backup_reader NOLOGIN CONNECTION LIMIT 0;
    RETURN true;
END;
$$;

-- Функция 23 — выгнать оставшиеся сеансы и пересчитать. Вторая фаза.
-- Вызывается столько раз, сколько нужно, каждый раз своей транзакцией.
CREATE OR REPLACE FUNCTION bem_control.backup_window_drain(
    OUT out_left        integer,
    OUT out_zero_streak smallint)
RETURNS record
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_xid      xid8;
    v_canlogin boolean;
    v_limit    integer;
BEGIN
    IF session_user <> 'bem_backup_admin' THEN
        RAISE EXCEPTION 'BACKUP_WINDOW_WRONG_CALLER: %', session_user;
    END IF;

    SELECT w.locked_xid INTO v_xid
      FROM bem_control.backup_window w WHERE w.id = 1;

    IF v_xid IS NULL THEN
        RAISE EXCEPTION 'BACKUP_WINDOW_NOT_LOCKED: замок не ставили';
    END IF;

    -- Одна и та же транзакция видит собственную незафиксированную
    -- правку. Значит, совпадение номеров означает ровно одно: обе
    -- фазы идут в одной транзакции, и это запрещено.
    IF v_xid = pg_current_xact_id() THEN
        RAISE EXCEPTION
          'BACKUP_WINDOW_SAME_TRANSACTION: замок и выселение обязаны'
          ' идти разными транзакциями';
    END IF;

    -- Строка замка видна этой транзакции — значит, та, что её писала,
    -- зафиксирована: неудавшаяся транзакция не оставляет видимых строк.
    -- Состояние роли проверяется отдельно на случай ручной правки.
    SELECT r.rolcanlogin, r.rolconnlimit INTO v_canlogin, v_limit
      FROM pg_roles r WHERE r.rolname = 'backup_reader';

    IF v_canlogin OR v_limit <> 0 THEN
        RAISE EXCEPTION
          'BACKUP_WINDOW_NOT_LOCKED: вход роли backup_reader открыт'
          ' (вход=%, предел=%)', v_canlogin, v_limit;
    END IF;

    -- Фильтр по имени роли стоит в тексте функции, поэтому чужой
    -- процесс сюда не попадёт. Второй аргумент — ожидание пять секунд:
    -- вызов возвращается, когда процесс завершён, а не когда послан
    -- сигнал.
    PERFORM pg_terminate_backend(a.pid, 5000)
       FROM pg_stat_activity a
       JOIN pg_roles r ON r.oid = a.usesysid
      WHERE r.rolname = 'backup_reader'
        AND a.pid <> pg_backend_pid();

    -- H1.24, дефект D11: сведения pg_stat_activity кешируются при первом
    -- обращении в транзакции, и без сброса счёт ниже видел бы сеансы,
    -- уже завершённые вызовом выше. Сброс кеша — перед счётом.
    PERFORM pg_stat_clear_snapshot();

    SELECT count(*) INTO out_left
      FROM pg_stat_activity a
      JOIN pg_roles r ON r.oid = a.usesysid
     WHERE r.rolname = 'backup_reader';

    -- Устойчивый ноль считает база, а не сценарий вокруг неё.
    UPDATE bem_control.backup_window w
       SET zero_streak = CASE WHEN out_left = 0
                              THEN least(w.zero_streak + 1, 32767)
                              ELSE 0 END,
           closed_at   = CASE WHEN out_left = 0 AND w.zero_streak + 1 >= 2
                              THEN clock_timestamp() END
     WHERE w.id = 1
    RETURNING w.zero_streak INTO out_zero_streak;
END;
$$;

-- Функция 24 — доказать, что окно закрыто.
CREATE OR REPLACE FUNCTION bem_control.backup_window_assert_closed()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_canlogin boolean;
    v_limit    integer;
    v_streak   smallint;
    v_left     integer;
BEGIN
    IF session_user <> 'bem_backup_admin' THEN
        RAISE EXCEPTION 'BACKUP_WINDOW_WRONG_CALLER: %', session_user;
    END IF;

    SELECT r.rolcanlogin, r.rolconnlimit INTO v_canlogin, v_limit
      FROM pg_roles r WHERE r.rolname = 'backup_reader';

    IF v_canlogin OR v_limit <> 0 THEN
        RAISE EXCEPTION
          'BACKUP_WINDOW_NOT_LOCKED: вход роли backup_reader открыт';
    END IF;

    SELECT w.zero_streak INTO v_streak
      FROM bem_control.backup_window w WHERE w.id = 1;

    IF v_streak < 2 THEN
        RAISE EXCEPTION
          'BACKUP_WINDOW_NOT_STABLE: нулевых пересчётов подряд %, нужно 2',
          v_streak;
    END IF;

    SELECT count(*) INTO v_left
      FROM pg_stat_activity a
      JOIN pg_roles r ON r.oid = a.usesysid
     WHERE r.rolname = 'backup_reader';

    IF v_left <> 0 THEN
        RAISE EXCEPTION 'BACKUP_WINDOW_NOT_CLOSED: осталось % сессий', v_left;
    END IF;
    RETURN 0;
END;
$$;

REVOKE EXECUTE ON FUNCTION bem_control.backup_window_open(integer)   FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION bem_control.backup_window_lock()          FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION bem_control.backup_window_drain()         FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION bem_control.backup_window_assert_closed() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION bem_control.backup_window_open(integer)   TO bem_backup_admin;
GRANT  EXECUTE ON FUNCTION bem_control.backup_window_lock()          TO bem_backup_admin;
GRANT  EXECUTE ON FUNCTION bem_control.backup_window_drain()         TO bem_backup_admin;
GRANT  EXECUTE ON FUNCTION bem_control.backup_window_assert_closed() TO bem_backup_admin;

RESET ROLE;
SET ROLE bem_control_owner;
REVOKE CREATE ON SCHEMA bem_control FROM bem_backup_ctl_owner;
RESET ROLE;

-- Ни одной команды безопасности после этой строки быть не должно.
-- BEM954-FINAL-SECURITY-CHECKPOINT: 04_backup_window.sql

