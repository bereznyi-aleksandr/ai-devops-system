// tamper_manifest28.mjs — машинный манифест подделок H1.29.
// PASSPORT: ACTIVE vR49.1, раунд R49, H1.29.
// AUTHOR: ChatGPT, DEVELOPER R38; Claude, DEVELOPER R42–R49 (РАУНД-R49-ПЕРЕНОС-ИМЁН: H1.29; логика программ в R47–R49 не менялась, последняя правка логики — D1 и D2 проб R46; базовая пара — в build_package, verify_package, chk_round_facts); UPDATED: 2026-10-05.
// SUPERSEDES: версия из H1.28/R48; LIVE_POSTGRESQL_16: PG16_D05=EXECUTED_PASS, пробы R46 — раздел 22.1, пробы движка R47 и R49 — раздел 22.2, остальное — раздел 15.42.
// ИСТОРИЯ: прежний активный паспорт. Версия 4.0, раунд R33 (случаи A58–A65 и строки K-R17-01…03;
// замечания M-H117-R17-01=B-01, M-H117-R17-02=B-02, L-H117-R17-01=L-C-02;
// решение D-08). Строка K-R17-04 (правка 4, `--expect-edition`) добавляется
// отдельно, после того как паспорт и последний абзац документа сами станут
// верно называть H1.18: совместный откат должен уходить от верного текста,
// а не от ещё не выправленного. Версия 3.0, раунд R32 (РАУНД-R32-ПОДДЕЛКИ:
// случаи A28–A54 и строки K-R16-01…09; РАУНД-R32-РЕДАКЦИЯ: случаи A55–A57 и
// строка K-R16-10; замечание M-H116-R16-02 и добавки автора). Версия 2.0 —
// раунд R31, замечания C-H115-R15-01 и M-H115-R15-01. Версия 1.0 — раунд
// R28, замечание M-H113-R13-02.
// Версия 2.0 добавила вид случая «оба», поле level и подделки K-R15;
// у двух прежних случаев (D1, A15) перенесён якорь — текст канона
// изменился, смысл правки и ожидаемый код прежние.
//
// Это данные, а не программа. Ни одна запись не содержит кода: пять
// коротких помощников ниже только складывают поля в объект, и прочесть
// их целиком — пять строк. Из этого файла берутся сразу четыре вещи:
// прогон набора, отчёт в JSON, таблица в разделе 15.18 и строки
// реестра. До H1.13 их было три разных, и они расходились.
//
// Поля записи:
//   kind   — какому сверщику адресована подделка: син, смысл или оба;
//            «оба» — прогоняется через каждый, ожидание у каждого своё;
//   name   — короткое название, оно же попадает в отчёт;
//   op     — способ правки: plain, last, in_function, after_mark,
//            before_mark, pair;
//   from   — якорь, to — чем заменить, cmd — что дописать;
//   row    — строка реестра, которую этот случай доказывает;
//   expect — ожидаемый код возврата сверщика;
//   level  — ожидаемый уровень отказа: «поле отчёта» или «поле: начало
//            строки»; у вида «оба» — отдельно для реестра и смысла.
//            У новых случаев раундов R31 и R32 обязателен.
//
// Ожидаемый код указан у каждого случая. По умолчанию он равен 1:
// подделка обязана быть поймана. У положительного случая он равен 0 —
// и это не мелочь: набор, в котором ЛЮБАЯ правка даёт единицу,
// доказывал бы только чувствительность сверщика к любому шуму.

const rec = (o) => o;
const plain = (a, b) => rec({ op: 'plain', from: a, to: b });
const lastPlain = (a, b) => rec({ op: 'last', from: a, to: b });
const inFunction = (fn, a, b) => rec({ op: 'in_function', fn, from: a, to: b });
const afterMark = (cmd) => rec({ op: 'after_mark', cmd });
const beforeMark = (cmd) => rec({ op: 'before_mark', cmd });
const pair = (list) => rec({ op: 'pair', list });

// Длинные якоря, встречающиеся в нескольких записях, названы один раз.
const GUARD = '    PERFORM bem_control.assert_tenant(p_tenant_id);   -- граница заказчика, C-H17-R7-04';
const RESOLVE = '    SELECT out_actor_id INTO v_actor\n      FROM bem_control.current_actor_checked(p_tenant_id);';

export const legacy = [
  // --- синтаксический сверщик -----------------------------------------
  ['син', 'имя отказа',
   plain('| `K-R8-06` | участник со связанной личностью',
         '| `K-R8-06` | отказ `NO_SUCH_ERROR_NAME`; участник со связанной личностью')],
  ['син', 'роль',
   plain('| `K-R8-06` | участник со связанной личностью',
         '| `K-R8-06` | роль `bem_no_such_role`; участник со связанной личностью')],
  ['син', 'функция',
   plain('| `K-R8-06` | участник со связанной личностью',
         '| `K-R8-06` | вызов `no_such_function()`; участник со связанной личностью')],
  ['син', 'число', plain('CONTROL_FUNCTIONS=42', 'CONTROL_FUNCTIONS=43')],
  ['син', 'снятый грант',
   plain('GRANT  EXECUTE ON FUNCTION bem_control.create_tenant(uuid, text, text, uuid, jsonb)\n       TO bem_governance;',
         '-- грант намеренно убран')],
  ['син', 'ссылка на несуществующую строку',
   plain('| `K-R8-06` | участник со связанной личностью',
         '| `K-R8-06` | см. также `K-R9-99`; участник со связанной личностью')],
  ['син', 'пробел объявлен, а строка есть',
   plain('MISSING=K-TENANT-01', 'MISSING=K-R8-01,K-TENANT-01')],
  ['син', 'лишняя строка-двойник',
   plain('## 15.10. Машинная сверка',
         '| `K-R8-18` | строка-двойник | пояснение |\n\n## 15.10. Машинная сверка')],

  // --- смысловой сверщик, правила редакции 1.0 -------------------------
  ['смысл', 'снятая граница заказчика',
   inFunction('apply_transition', GUARD, '    -- граница намеренно убрана')],
  ['смысл', 'поздняя граница заказчика',
   inFunction('apply_transition', GUARD + '\n' + RESOLVE, RESOLVE + '\n' + GUARD)],
  ['смысл', 'вторая дверь доказательства',
   inFunction('finish_outbox_row', "    IF v_new = 'DEAD_LETTER' THEN",
              "    INSERT INTO bem_core.evidence (id) VALUES (gen_random_uuid());\n    IF v_new = 'DEAD_LETTER' THEN")],
  ['смысл', 'ожидание с чужой ветки: K-R8-07',
   plain('первый вызов — `UNKNOWN_ACTOR` из `current_actor_checked()`',
         'первый вызов — `UNKNOWN_OR_INACTIVE_ACTOR` из `current_actor_checked()`')],
  ['смысл', 'ожидание с чужой ветки: K-R4-02',
   plain('вторая — триггером `forbid_self_audit()` с отказом `AUTHOR_CANNOT_AUDIT`; имя `SELF_AUDIT_FORBIDDEN` H1.9 назвала здесь ошибочно — его возбуждает `assign_auditor()` при назначении проверяющего, а не запись вердикта;',
         'вторая — исключением `SELF_AUDIT_FORBIDDEN`;')],
  ['смысл', 'ожидание с чужой ветки: K-R8-02',
   plain('останавливается отказом `RLS_EXTRA_POLICY` **до первой команды',
         'останавливается отказом `POLICY_SHAPE_MISMATCH` **до первой команды')],
  ['смысл', 'помощник, которому выдали право',
   plain('TENANT_HELPER=evidence_write,', 'TENANT_HELPER=current_actor_checked,evidence_write,')],
  ['смысл', 'объявлено имя, которого нет',
   plain('NO_REVOKE=current_tenant\n', 'NO_REVOKE=current_tenant,no_such_function\n')],

  // --- смысловой сверщик, новые правила редакции 2.0 -------------------
  // Правило 8: читаются ВСЕ получатели. Именно эту подделку назвал аудит.
  ['смысл', 'вторая роль приписана к двери доказательства',
   plain('GRANT  EXECUTE ON FUNCTION bem_control.evidence_write(uuid, text, jsonb) TO bem_control_owner;',
         'GRANT  EXECUTE ON FUNCTION bem_control.evidence_write(uuid, text, jsonb)\n       TO bem_control_owner, bem_kernel_rw;')],
  // Правило 6: два тела одной подписи обязаны совпадать побайтно.
  ['смысл', 'две копии одной функции разошлись',
   lastPlain("AS $$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$;",
             "AS $$ SELECT current_setting('app.tenant_id', true)::uuid $$;")],
  // Правило 9: канонический диапазон замкнут.
  ['смысл', 'право живёт только в пояснении',
   plain('GRANT USAGE ON SCHEMA bem_core, bem_engine, bem_control TO backup_reader;',
         'GRANT USAGE ON SCHEMA bem_core, bem_engine, bem_control TO backup_reader;\nGRANT INSERT ON bem_core.evidence TO bem_kernel_rw;')],
  ['смысл', 'определение функции вне канона',
   plain('GRANT USAGE  ON SCHEMA bem_engine TO bem_control_owner;',
         'CREATE OR REPLACE FUNCTION bem_control.shadow_writer()\nRETURNS void LANGUAGE sql AS $$ SELECT 1 $$;\nGRANT USAGE  ON SCHEMA bem_engine TO bem_control_owner;')],
  // Правило 7: договор записи, обе стороны.
  ['смысл', 'снятое право записи',
   plain('GRANT INSERT ON bem_core.actor            TO bem_control_owner;\n',
         '-- право намеренно убрано\n')],
  ['смысл', 'лишнее право записи',
   plain('GRANT INSERT ON bem_core.actor            TO bem_control_owner;',
         'GRANT INSERT ON bem_core.actor            TO bem_control_owner;\nGRANT DELETE ON bem_core.evidence        TO bem_control_owner;')],
  ['смысл', 'широкое право вместо точного',
   plain('GRANT INSERT ON bem_core.tenant        TO bem_control_owner;',
         'GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA bem_core TO bem_control_owner;')],
  ['смысл', 'право по умолчанию в обход договора',
   plain('    GRANT SELECT ON TABLES TO backup_reader, bem_kernel_rw, bem_control_owner;',
         '    GRANT SELECT, INSERT ON TABLES TO backup_reader, bem_kernel_rw, bem_control_owner;')],
  ['смысл', 'новая запись в теле без права',
   inFunction('create_actor',
              '    INSERT INTO bem_core.actor (actor_id, provider, user_id, is_active, db_role)',
              '    UPDATE bem_core.actor SET is_active = false WHERE false;\n    INSERT INTO bem_core.actor (actor_id, provider, user_id, is_active, db_role)')],
  ['смысл', 'список в самопроверке разошёлся с телами',
   plain("        'bem_control_owner|bem_core.actor|INSERT|',\n", '')],
  // Правило 4: граница там, где аргумента заказчика нет вовсе.
  ['смысл', 'через заказчиков без объявления',
   plain('CROSS_TENANT=claim_outbox_batch,finish_outbox_row',
         'CROSS_TENANT=finish_outbox_row')],
  ['смысл', 'объявление, которое нечем подтвердить',
   plain('CROSS_TENANT=claim_outbox_batch,finish_outbox_row',
         'CROSS_TENANT=claim_outbox_batch,finish_outbox_row,create_tenant')],
  // --- R26: закрытый набор прав (замечание M-H111-R11-02) -------------
  // Ровно та подделка, которой аудит обошёл обе редакции 2.0.
  ['смысл', 'право очистки таблицы доказательств',
   plain('GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;',
         'GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;\nGRANT TRUNCATE ON bem_core.evidence TO bem_control_owner;')],
  ['смысл', 'право внешнего ключа',
   plain('GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;',
         'GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;\nGRANT REFERENCES ON bem_core.actor TO bem_kernel_rw;')],
  ['смысл', 'право триггера',
   plain('GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;',
         'GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;\nGRANT TRIGGER ON bem_core.evidence TO bem_kernel_rw;')],
  ['смысл', 'широкая выдача всех прав',
   plain('GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;',
         'GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;\nGRANT ALL ON bem_core.evidence TO bem_kernel_rw;')],
  ['смысл', 'право, которого нет в словаре PostgreSQL 16',
   plain('GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;',
         'GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;\nGRANT MAINTAIN ON bem_core.evidence TO bem_kernel_rw;')],
  ['смысл', 'лишнее право последовательности',
   plain('GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;',
         'GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;\nGRANT UPDATE ON ALL SEQUENCES IN SCHEMA bem_core TO bem_kernel_rw;')],
  ['смысл', 'право по умолчанию с очисткой таблицы',
   plain('    GRANT SELECT ON SEQUENCES TO backup_reader, bem_kernel_rw, bem_control_owner;',
         '    GRANT SELECT, TRUNCATE ON SEQUENCES TO backup_reader, bem_kernel_rw, bem_control_owner;')],
  // --- R26: договор чтения --------------------------------------------
  ['смысл', 'второй получатель у строки чтения',
   plain('GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw;',
         'GRANT SELECT ON ALL TABLES    IN SCHEMA bem_core TO bem_kernel_rw, bem_engine_rw;')],
  ['смысл', 'объявленное чтение, которого в каноне нет',
   plain('bem_kernel_rw|ALLTABLES:bem_core|SELECT',
         'bem_kernel_rw|ALLTABLES:bem_core|SELECT\nbem_engine_rw|ALLTABLES:bem_core|SELECT')],
  // --- R26: поверхность исполнения (замечание M-H111-R11-03) ----------
  ['смысл', 'стёртый получатель в поверхности исполнения',
   plain('bem_control.create_tenant(uuid, text, text, uuid, jsonb) -> bem_governance',
         'bem_control.create_tenant(uuid, text, text, uuid, jsonb) ->')],
  ['смысл', 'подменённый тип аргумента в поверхности исполнения',
   plain('bem_control.create_tenant(uuid, text, text, uuid, jsonb) -> bem_governance',
         'bem_control.create_tenant(uuid, text, text, uuid, text) -> bem_governance')],
  ['смысл', 'снятый грант исполнения при целом объявлении',
   plain('GRANT  EXECUTE ON FUNCTION bem_control.grant_authority(text, text, uuid) TO bem_governance;',
         '-- грант исполнения намеренно убран')],
  // === R27 ===========================================================
  // Повышение роли и поздний отзыв — замечания C-H112-R12-01 и
  // M-H112-R12-01. Каждая подделка ставится дважды: после финального
  // маркера файла 00 и до первой выдачи прав. H1.12 не ловила ни одну
  // из них ни в одном месте.
  ['смысл', 'членство рабочей роли во владельце ядра, после маркера',
   afterMark('GRANT bem_core_owner TO bem_kernel_rw;')],
  ['смысл', 'членство рабочей роли во владельце ядра, до маркера',
   beforeMark('GRANT bem_core_owner TO bem_kernel_rw;')],
  ['смысл', 'суперпользователь у рабочей роли, после маркера',
   afterMark('ALTER ROLE bem_kernel_rw SUPERUSER;')],
  ['смысл', 'суперпользователь у рабочей роли, до маркера',
   beforeMark('ALTER ROLE bem_kernel_rw SUPERUSER;')],
  ['смысл', 'обход защиты строк у рабочей роли, после маркера',
   afterMark('ALTER ROLE bem_kernel_rw BYPASSRLS;')],
  ['смысл', 'обход защиты строк у рабочей роли, до маркера',
   beforeMark('ALTER ROLE bem_kernel_rw BYPASSRLS;')],
  ['смысл', 'поздний отзыв обязательного чтения, после маркера',
   afterMark('REVOKE SELECT ON ALL TABLES IN SCHEMA bem_core FROM bem_kernel_rw;')],
  ['смысл', 'поздний отзыв обязательного чтения, до маркера',
   beforeMark('REVOKE SELECT ON ALL TABLES IN SCHEMA bem_core FROM bem_kernel_rw;')],
  ['смысл', 'поздний отзыв обязательного вызова, после маркера',
   afterMark('REVOKE EXECUTE ON FUNCTION bem_control.record_evidence(uuid, text, jsonb)'
             + ' FROM bem_kernel_rw;')],
  ['смысл', 'поздний отзыв обязательного вызова, до маркера',
   beforeMark('REVOKE EXECUTE ON FUNCTION bem_control.record_evidence(uuid, text, jsonb)'
              + ' FROM bem_kernel_rw;')],
  ['смысл', 'поздний REVOKE ALL при целом договоре, после маркера',
   afterMark('REVOKE ALL ON ALL TABLES IN SCHEMA bem_core FROM bem_kernel_rw;')],
  ['смысл', 'поздний REVOKE ALL при целом договоре, до маркера',
   beforeMark('REVOKE ALL ON ALL TABLES IN SCHEMA bem_core FROM bem_kernel_rw;')],

  // Поздние команды других видов. Все они стоят после последней
  // проверки файла, и до этого раунда там разрешалось всё.
  ['смысл', 'поздняя смена владельца таблицы доказательств',
   afterMark('ALTER TABLE bem_core.evidence OWNER TO bem_kernel_rw;')],
  ['смысл', 'позднее переключение роли',
   afterMark('SET ROLE bem_core_owner;')],
  ['смысл', 'поздние права по умолчанию на запись',
   afterMark('ALTER DEFAULT PRIVILEGES IN SCHEMA bem_core'
             + ' GRANT INSERT ON TABLES TO bem_kernel_rw;')],
  ['смысл', 'позднее переназначение владения',
   afterMark('REASSIGN OWNED BY bem_core_owner TO bem_kernel_rw;')],

  // Отзыв, после которого право снова выдано: итоговое состояние цело,
  // и складыванием прав такую подделку не найти. Ловит её договор
  // отзывов: этого отзыва в нём нет.
  ['смысл', 'выдача, отзыв и снова выдача',
   beforeMark('REVOKE SELECT ON ALL TABLES IN SCHEMA bem_core FROM bem_kernel_rw;'
              + '\nGRANT SELECT ON ALL TABLES IN SCHEMA bem_core TO bem_kernel_rw;')],

  // Обратный случай: объявленный отзыв, которого в коде нет. Такой
  // договор описывает не документ, а пожелание.
  ['смысл', 'объявленный отзыв, которого нет в каноне',
   plain('BEM954-PACKAGE-REVOKE-CONTRACT\n',
         'BEM954-PACKAGE-REVOKE-CONTRACT\n'
         + 'REVOKE SELECT ON ALL TABLES IN SCHEMA bem_core FROM bem_engine_rw\n')],

  // Снятый получатель из строки, где их двое. Число строк прав при
  // этом не меняется вовсе.
  ['смысл', 'снятый второй получатель вызова',
   plain('GRANT  EXECUTE ON FUNCTION bem_control.data_digest(regclass)\n'
         + '       TO bem_kernel_rw, bem_backup_admin;',
         'GRANT  EXECUTE ON FUNCTION bem_control.data_digest(regclass)\n'
         + '       TO bem_kernel_rw;')],

  // Убранный финальный маркер: без него после последней проверки
  // снова можно дописать что угодно.
  ['смысл', 'убранный финальный маркер файла 02',
   plain('-- BEM954-FINAL-SECURITY-CHECKPOINT: 02_upgrade_to_h110.sql',
         '-- финальный маркер намеренно убран')],

  // Списки живой самопроверки файла 01. Они обязаны совпадать с тем,
  // что выводится из канона, иначе это второй договор, расходящийся с
  // первым молча.
  ['смысл', 'убранная строка из списка обязательного чтения',
   plain("        'bem_kernel_rw|ALLTABLES:bem_core|SELECT',\n", '')],
  ['смысл', 'лишняя строка в списке обязательного чтения',
   plain("        'bem_kernel_rw|ALLTABLES:bem_core|SELECT',",
         "        'bem_kernel_rw|ALLTABLES:bem_core|SELECT',\n"
         + "        'bem_engine_rw|ALLTABLES:bem_core|SELECT',")],
  ['смысл', 'подменённый получатель в списке обязательных вызовов',
   plain("        'bem_control.accept_handoff(uuid, uuid, integer, text)|bem_kernel_rw',",
         "        'bem_control.accept_handoff(uuid, uuid, integer, text)|bem_engine_rw',")],
  ['смысл', 'убранная строка из списка обязательных вызовов',
   plain("        'bem_control.accept_handoff(uuid, uuid, integer, text)|bem_kernel_rw',\n", '')],
];

// --- Строки реестра, которые доказывает набор ----------------------------
// Ключ — идентификатор строки в разделе 15.9. Значение — короткое имя
// того, что строка обещает. Таблица раздела 15.18 собирается отсюда и из
// поля row каждого случая: подпись и случай больше не могут разойтись,
// потому что они одна запись.
export const rows = {
  'K-R12-01': 'лишняя строка членства в двух местах пакета',
  'K-R12-02': 'признак SUPERUSER у рабочей роли',
  'K-R12-03': 'признаки BYPASSRLS, CREATEROLE и REPLICATION у рабочей роли',
  'K-R12-04': 'смена одного параметра у строки членства: ADMIN, INHERIT, SET',
  'K-R12-05': 'поздний отзыв обязательного чтения',
  'K-R12-06': 'поздний отзыв обязательного вызова',
  'K-R12-07': 'команда безопасности после финального маркера и убранный маркер',
  'K-R12-08': 'прогон набора целиком одной командой',
  'K-R12-13': 'выдача, отзыв и снова выдача: итог равен договору',
  'K-R12-14': 'снятый получатель, смена владельца функции, снятый SECURITY DEFINER',
  'K-R13-01': 'ALTER USER до маркера',
  'K-R13-02': 'имя роли в двойных кавычках',
  'K-R13-03': 'составной ALTER ROLE, собранный на ходу',
  'K-R13-04': 'членство с именем в двойных кавычках',
  'K-R13-05': 'выдача членства, собранная на ходу',
  'K-R13-06': 'переименование роли',
  'K-R13-07': 'снятие SECURITY DEFINER до маркера',
  'K-R13-08': 'незакреплённый путь поиска у функции',
  'K-R13-09': 'ALTER USER после живой самопроверки файла 01',
  'K-R13-10': 'составной ALTER ROLE после живой самопроверки',
  'K-R13-11': 'пояснение внутри опасной команды',
  'K-R13-12': 'позднее WITH ADMIN FALSE',
  'K-R13-13': 'пароль, добавленный роли',
  'K-R13-14': 'позднее отключение построчной защиты',
  'K-R13-15': 'жёсткий режим защиты снят и не возвращён',
  'K-R13-16': 'позднее удаление политики',
  'K-R13-17': 'позднее удаление триггера личности',
  'K-R13-18': 'снятие SECURITY DEFINER после живой самопроверки',
  'K-R13-19': 'мигратор делает роль копирования входной и с паролем',
  'K-R13-20': 'мигратору выдают владельца окна копирования',
  'K-R13-21': 'объявленный список окна разошёлся с обёрткой',
  'K-R13-22': 'смена роли на роль вне окна мигратора',
  'K-R13-23': 'форма команды вне закрытого словаря',
  'K-R13-24': 'право, выданное с правом передачи',
  'K-R13-25': 'настройка сеанса, назначенная роли',
  'K-R13-26': 'срок годности роли',
  'K-R13-27': 'выборочный сброс настроек роли',
  'K-R13-28': 'удаление всего принадлежащего роли',
  'K-R13-29': 'изменение настроек сервера',
  'K-R13-30': 'новый шаблон команды, собираемой на ходу',
  'K-R13-31': 'изменённый шаблон команды, собираемой на ходу',
  'K-R13-32': 'объявленный шаблон, которого нет в коде',
  'K-R13-33': 'выдавший членство сверяется не с начальным суперпользователем',
  'K-R13-34': 'блочное пояснение в каноне',
  'K-R13-35': 'удвоенная кавычка в значении прячет следующую команду',
  'K-R13-36': 'команда безопасности после маркера файла 05',
  'K-R13-37': 'убранный маркер файла 04',
  'K-R13-38': 'список чтения терминальной проверки разошёлся с каноном',
  'K-R13-39': 'роль со входом сверх договора',
  'K-R13-40': 'пароль в объявленном договоре секретов роли',
  'K-R13-41': 'ослабленная политика в списке терминальной проверки',
  'K-R13-42': 'триггер, убранный из списка терминальной проверки',
  'K-R13-43': 'незакреплённый путь поиска в списке терминальной проверки',
  'K-R13-44': 'обёртка передаёт psql имя файла, а не прочитанные байты',
  'K-R13-45': 'обёртка не сверяет сумму описи',
  'K-R13-46': 'триггер снят и не создан заново',
  'K-R13-47': 'пояснение командой не является',
  'K-R13-48': 'сброс всех настроек роли после маркера',
  'K-R13-49': 'встроенные листинги совпадают с файлами байт в байт',
  'K-R13-50': 'манифест, отчёт, таблица и реестр собраны из одного списка',
  'K-R14-01': 'определение триггера сверяется целиком, а не по имени',
  'K-R14-02': 'политика построчной защиты сверяется по всем полям',
  'K-R14-03': 'закреплённый путь поиска у функции сверяется с договором',
  'K-R14-04': 'ветка отказа не может стоять под постоянным условием',
  'K-R14-05': 'успех невозможен без исполненной терминальной проверки',
  'K-R14-06': 'отказ записи финальной квитанции останавливает пакет',
  'K-R14-07': 'множество прав доступа сверяется точно и в обе стороны',
  'K-R15-01': 'условие WHEN триггера сверяется точно на всех трёх уровнях',
  'K-R15-02': 'функция, события, столбцы, аргументы и режим триггера сверяются точно',
  'K-R15-03': 'полное определение триггера сверяется с pg_get_triggerdef',
  'K-R15-04': 'триггер нельзя отключить или перевести в другой режим',
  'K-R15-05': 'у каждого права сверяется роль, которая его выдала',
  'K-R15-06': 'права сравниваются с учётом числа повторов',
  'K-R15-07': 'лишнее право передачи и лишнее право PUBLIC в договоре',
  'K-R16-01': 'в списке прав файла 01 у каждой строки сверяется выдавший',
  'K-R16-02': 'права в файле 01 сравниваются с учётом числа повторов',
  'K-R16-03': 'в списке файла 01 нет права передачи и права PUBLIC',
  'K-R16-04': 'список прав файла 01 полон и не зависит от порядка строк',
  'K-R16-05': 'права функций окна в файле 01 принимаются «все или ни одной»',
  'K-R16-06': 'запрос каталога прав в файле 01 совпадает с шагом 10 файла 05',
  'K-R16-07': 'повтор имени в секции DECLARE отклоняется',
  'K-R16-08': 'разделы 5.2 и 5.3 не противоречат разделу 4.3 о записи доказательства',
  'K-R16-09': 'сравнение прав в файле 01 и в файле 05 совпадает целиком',
  'K-R16-10': 'последний абзац документа называет только текущую редакцию',
  'K-R17-01': 'форма соединения в файле 01 и в файле 05 проверяется у каждого отдельно',
  'K-R17-02': 'повтор имени в DECLARE ловится и в кавычках, и в смеси кавычек',
  'K-R17-03': 'tgqual::text файла 01 сравнивается с эталонным триггером',
  'K-R17-04': 'ожидаемая редакция - из независимого источника, совместный откат отклоняется',
  'K-R43-01': 'права restore_verifier на схемы: свёртка убирает одно право, файл 03 снимает и сверяет',
  'K-R44-01': 'права restore_verifier на схемы: исключение только для права, выданного владельцем схемы',
  'K-R46-01': 'ограничения: файл 01 знает каждое, файл 05 сверяет точное множество',
  'K-R46-02': 'назначение проверяющих BEM-954: без запрета компании автора, с прежними проверками',
};

// --- Точки вставки -------------------------------------------------------
const MARK00 = '-- BEM954-FINAL-SECURITY-CHECKPOINT: 00_cluster_bootstrap.sql';
const MARK01 = '-- BEM954-FINAL-SECURITY-CHECKPOINT: 01_database_migration.sql';
const MARK04 = '-- BEM954-FINAL-SECURITY-CHECKPOINT: 04_backup_window.sql';
const MARK05 = '-- BEM954-FINAL-SECURITY-CHECKPOINT: 05_final_state_check.sql';
const EARLY  = 'GRANT CONNECT ON DATABASE bem';
const after  = (mark, cmd) => rec({ op: 'plain', from: mark, to: mark + '\n' + cmd });
const before = (mark, cmd) => rec({ op: 'plain', from: mark, to: cmd + '\n' + mark });
const N = (name, row, r, expect = 1) => rec({ kind: 'смысл', name, row, expect, ...r });
// R31: случай с уровнем отказа — один смысловой сверщик или оба сразу.
const L = (name, row, level, r, expect = 1) => rec({ kind: 'смысл', name, row, expect, level, ...r });
const B = (name, row, level, r, expect = 1) => rec({ kind: 'оба', name, row, expect, level, ...r });

const FAKE = 'подделка-не-настоящий-пароль';

export const fresh = [
  // --- Все 19 подделок аудита 75, раздел 3 ------------------------------
  N('I01: ALTER USER до маркера', 'K-R13-01',
    before(EARLY, 'ALTER USER bem_kernel_rw SUPERUSER;')),
  N('I02: ALTER ROLE с именем в кавычках', 'K-R13-02',
    after(MARK00, 'ALTER ROLE "bem_kernel_rw" SUPERUSER;')),
  N('I03: составной ALTER ROLE, собранный на ходу', 'K-R13-03',
    after(MARK00, "DO $tamper$ BEGIN EXECUTE format('ALTER ROLE %I SUPERUSER', 'bem_kernel_rw'); END $tamper$;")),
  N('I04: членство с именем в кавычках', 'K-R13-04',
    after(MARK00, 'GRANT "bem_core_owner" TO bem_kernel_rw;')),
  N('I05: выдача членства, собранная на ходу', 'K-R13-05',
    after(MARK00, "DO $tamper$ BEGIN EXECUTE format('GRANT %I TO %I', 'bem_core_owner', 'bem_kernel_rw'); END $tamper$;")),
  N('I06: переименование роли', 'K-R13-06',
    after(MARK00, 'ALTER ROLE bem_kernel_rw RENAME TO bem_kernel_admin;')),
  N('I07: SECURITY INVOKER до маркера', 'K-R13-07',
    before(EARLY, 'ALTER FUNCTION bem_control.assert_tenant(uuid) SECURITY INVOKER;')),
  N('I08: незакреплённый путь поиска до маркера', 'K-R13-08',
    before(EARLY, 'ALTER FUNCTION bem_control.assert_tenant(uuid) SET search_path = public;')),
  N('I09: ALTER USER после живой самопроверки', 'K-R13-09',
    before(MARK01, 'ALTER USER bem_kernel_rw SUPERUSER;')),
  N('I10: составной ALTER ROLE после живой самопроверки', 'K-R13-10',
    before(MARK01, "DO $tamper$ BEGIN EXECUTE format('ALTER ROLE %I CREATEROLE', 'bem_kernel_rw'); END $tamper$;")),
  N('I11: пояснение внутри опасной команды', 'K-R13-11',
    after(MARK00, 'ALTER ROLE bem_kernel_rw -- обычная правка\n  SUPERUSER;')),
  N('I12: позднее WITH ADMIN FALSE', 'K-R13-12',
    after(MARK00, 'GRANT bem_governance TO bem_bootstrap_admin WITH ADMIN FALSE;')),
  N('I13: пароль добавлен роли', 'K-R13-13',
    after(MARK00, "ALTER ROLE bem_kernel_rw PASSWORD '" + FAKE + "';")),
  N('I14: позднее отключение построчной защиты', 'K-R13-14',
    before(MARK01, 'ALTER TABLE bem_core.evidence DISABLE ROW LEVEL SECURITY;')),
  N('I15: позднее снятие жёсткого режима защиты', 'K-R13-15',
    before(MARK01, 'ALTER TABLE bem_core.evidence NO FORCE ROW LEVEL SECURITY;')),
  N('I16: позднее удаление политики', 'K-R13-16',
    before(MARK01, 'DROP POLICY tenant_isolation ON bem_core.evidence;')),
  N('I17: позднее удаление триггера личности', 'K-R13-17',
    before(MARK01, 'DROP TRIGGER audit_record_append_only ON bem_core.audit_record;')),
  N('I18: SECURITY INVOKER после живой самопроверки', 'K-R13-18',
    before(MARK01, 'ALTER FUNCTION bem_control.record_evidence(uuid, text, jsonb) SECURITY INVOKER;')),
  N('I19: мигратор делает роль копирования входной и с паролем', 'K-R13-19',
    before(MARK01, "SET ROLE bem_backup_ctl_owner;\nALTER ROLE backup_reader LOGIN PASSWORD '" + FAKE + "';\nRESET ROLE;")),

  // --- Класс критического замечания C-H113-R13-01 -----------------------
  N('мигратору выдают владельца окна копирования', 'K-R13-20',
    rec({ op: 'plain',
          from: 'GRANT bem_core_owner, bem_engine_owner, bem_control_owner\n          TO schema_migrator;',
          to:   'GRANT bem_core_owner, bem_engine_owner, bem_control_owner,\n          bem_backup_ctl_owner TO schema_migrator;' })),
  N('объявленный список окна разошёлся с обёрткой', 'K-R13-21',
    rec({ op: 'plain',
          from: 'BEM954-PACKAGE-MIGRATOR-GRANTS\nbem_control_owner',
          to:   'BEM954-PACKAGE-MIGRATOR-GRANTS\nbem_backup_ctl_owner\nbem_control_owner' })),
  N('смена роли на роль вне окна мигратора', 'K-R13-22',
    before(MARK01, 'SET ROLE bem_backup_ctl_owner;')),

  // --- Закрытый словарь форм --------------------------------------------
  N('форма команды вне закрытого словаря', 'K-R13-23',
    after(MARK00, 'CREATE PUBLICATION bem_all FOR ALL TABLES;')),
  N('право с правом передачи', 'K-R13-24',
    after(MARK00, 'GRANT SELECT ON bem_core.evidence TO bem_kernel_rw WITH GRANT OPTION;')),
  N('настройка сеанса у роли', 'K-R13-25',
    after(MARK00, 'ALTER ROLE bem_kernel_rw SET search_path = public;')),
  N('срок годности роли', 'K-R13-26',
    after(MARK00, "ALTER ROLE bem_kernel_rw VALID UNTIL '2030-01-01';")),
  N('выборочный сброс настроек роли', 'K-R13-27',
    after(MARK00, 'ALTER ROLE bem_kernel_rw RESET search_path;')),
  N('удаление всего принадлежащего роли', 'K-R13-28',
    after(MARK00, 'DROP OWNED BY bem_kernel_rw;')),
  N('изменение настроек сервера', 'K-R13-29',
    after(MARK00, "ALTER SYSTEM SET log_statement = 'none';")),

  // --- Команды, собираемые на ходу ---------------------------------------
  N('новый шаблон команды, собираемой на ходу', 'K-R13-30',
    rec({ op: 'plain',
          from: "EXECUTE format('ALTER TABLE bem_core.%I FORCE  ROW LEVEL SECURITY', t);",
          to:   "EXECUTE format('ALTER TABLE bem_core.%I FORCE  ROW LEVEL SECURITY', t);\n        EXECUTE format('GRANT SELECT ON bem_core.%I TO backup_reader', t);" })),
  N('изменённый шаблон команды, собираемой на ходу', 'K-R13-31',
    rec({ op: 'plain',
          from: "EXECUTE format('ALTER ROLE backup_reader LOGIN CONNECTION LIMIT %s', p_limit);",
          to:   "EXECUTE format('ALTER ROLE backup_reader LOGIN CREATEROLE CONNECTION LIMIT %s', p_limit);" })),
  N('объявленный шаблон, которого нет в коде', 'K-R13-32',
    rec({ op: 'plain',
          from: 'BEM954-PACKAGE-DYNAMIC-STATEMENTS\nALTER POLICY',
          to:   'BEM954-PACKAGE-DYNAMIC-STATEMENTS\nALTER ROLE %I SUPERUSER\nALTER POLICY' })),

  // --- Новые договоры редакции H1.14 -------------------------------------
  N('выдавший членство сверяется с current_user', 'K-R13-33',
    rec({ op: 'plain', from: 'AND m.grantor <> 10', to: 'AND o.rolname <> current_user' })),
  N('блочное пояснение в каноне', 'K-R13-34',
    after(MARK00, '/* тихо */ GRANT bem_core_owner TO bem_kernel_rw;')),
  N('удвоенная кавычка в значении прячет следующую команду', 'K-R13-35',
    before(EARLY, "INSERT INTO bem_core.tenant (id, name) VALUES ('00000000-0000-0000-0000-000000000000', 'don''t');\nGRANT bem_core_owner TO bem_kernel_rw;")),
  N('команда безопасности после маркера файла 05', 'K-R13-36',
    after(MARK05, 'GRANT SELECT ON bem_core.evidence TO bem_kernel_rw;')),
  N('убранный маркер файла 04', 'K-R13-37',
    rec({ op: 'plain', from: MARK04, to: '-- маркер убран подделкой' })),

  // --- Терминальная проверка, файл 05 ------------------------------------
  N('строка убрана из списка чтения терминальной проверки', 'K-R13-38',
    rec({ op: 'plain', from: "        'backup_reader|ALLSEQUENCES:bem_control|SELECT',\n", to: '' })),
  N('роль со входом сверх договора', 'K-R13-39',
    rec({ op: 'plain',
          from: "    v_login   constant text[] := ARRAY[\n        'bem_backup_admin',",
          to:   "    v_login   constant text[] := ARRAY[\n        'backup_reader',\n        'bem_backup_admin'," })),
  N('пароль в объявленном договоре секретов роли', 'K-R13-40',
    rec({ op: 'plain', from: 'bem_kernel_rw|password:none|valid_until:none|config:none',
          to: 'bem_kernel_rw|password:set|valid_until:none|config:none' })),
  N('ослабленная политика в списке терминальной проверки', 'K-R13-41',
    rec({ op: 'plain', from: "'bem_core.evidence|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())'",
          to: "'bem_core.evidence|tenant_isolation|SELECT|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())'" })),
  N('триггер убран из списка терминальной проверки', 'K-R13-42',
    rec({ op: 'plain', from: "        'bem_core.audit_record|audit_record_append_only|27||bem_core.forbid_update_delete()|O|f|f|f|f|0',\n", to: '' })),
  N('незакреплённый путь поиска в списке терминальной проверки', 'K-R13-43',
    rec({ op: 'plain',
          from: "'bem_control.assert_authority(text, uuid)|bem_control_owner|invoker|search_path=bem_core, pg_catalog, pg_temp'",
          to:   "'bem_control.assert_authority(text, uuid)|bem_control_owner|invoker|search_path=public'" })),

  // --- Форма обёртки ------------------------------------------------------
  N('обёртка передаёт psql имя файла, а не прочитанные байты', 'K-R13-44',
    rec({ op: 'plain', from: "'-U', user, '-d', TARGET_DB, '-f', '-'],",
          to: "'-U', user, '-d', TARGET_DB, '-f', name]," })),
  N('обёртка не сверяет сумму описи', 'K-R13-45',
    rec({ op: 'plain', from: 'sumOf(raw);\n  if (got !== MANIFEST_SHA256) {',
          to: 'sumOf(raw);\n  if (false) {' })),
  N('триггер снят и не создан заново', 'K-R13-46',
    before(MARK01, 'DROP TRIGGER IF EXISTS audit_record_guard ON bem_core.audit_record;')),

  // --- Случаи, которых аудит не нашёл в наборе H1.13 ---------------------
  N('признак CREATEROLE у рабочей роли', 'K-R12-03',
    after(MARK00, 'ALTER ROLE bem_kernel_rw CREATEROLE;')),
  N('признак REPLICATION у рабочей роли', 'K-R12-03',
    after(MARK00, 'ALTER ROLE bem_kernel_rw REPLICATION;')),
  N('у строки членства сменился ADMIN', 'K-R12-04',
    rec({ op: 'plain', from: 'GRANT backup_reader TO bem_backup_ctl_owner WITH ADMIN OPTION;',
          to: 'GRANT backup_reader TO bem_backup_ctl_owner WITH ADMIN FALSE;' })),
  N('у строки членства сменился INHERIT', 'K-R12-04',
    rec({ op: 'plain', from: 'GRANT backup_reader TO bem_backup_ctl_owner WITH INHERIT FALSE;',
          to: 'GRANT backup_reader TO bem_backup_ctl_owner WITH INHERIT TRUE;' })),
  N('у строки членства сменился SET', 'K-R12-04',
    rec({ op: 'plain', from: 'GRANT backup_reader TO bem_backup_ctl_owner WITH SET FALSE;',
          to: 'GRANT backup_reader TO bem_backup_ctl_owner WITH SET TRUE;' })),
  N('поздняя смена владельца функции', 'K-R12-14',
    after(MARK00, 'ALTER FUNCTION bem_control.assert_tenant(uuid) OWNER TO bem_kernel_rw;')),
  N('позднее снятие SECURITY DEFINER', 'K-R12-14',
    after(MARK00, 'ALTER FUNCTION bem_control.record_evidence(uuid, text, jsonb) SECURITY INVOKER;')),

  // --- Положительные случаи ----------------------------------------------
  // Набор, в котором любая правка даёт единицу, доказывал бы только
  // чувствительность сверщика к шуму. Эти два случая обязаны дать ноль.
  N('выдача, отзыв и снова выдача с объявленным отзывом', 'K-R12-13',
    pair([
      rec({ op: 'plain',
            from: 'GRANT SELECT ON ALL TABLES IN SCHEMA bem_core TO bem_control_owner;',
            to:   'GRANT SELECT ON ALL TABLES IN SCHEMA bem_core TO bem_control_owner;\nREVOKE SELECT ON ALL TABLES IN SCHEMA bem_core FROM bem_control_owner;\nGRANT SELECT ON ALL TABLES IN SCHEMA bem_core TO bem_control_owner;' }),
      rec({ op: 'plain',
            from: 'REVOKE CREATE ON SCHEMA bem_control FROM bem_backup_ctl_owner\n',
            to:   'REVOKE CREATE ON SCHEMA bem_control FROM bem_backup_ctl_owner\nREVOKE SELECT ON ALL TABLES IN SCHEMA bem_core FROM bem_control_owner\n' }),
    ]), 0),
  N('пояснение командой не является', 'K-R13-47',
    after(MARK00, '-- GRANT bem_core_owner TO bem_kernel_rw;'), 0),

  // Дописано после первой сборки манифеста и потому стоит в конце:
  // номер случая — это его место в списке, и переставлять список ради
  // красоты нельзя, иначе разъедутся уже выданные номера.
  // Полный сброс настроек роли — форма разрешённая: им пакет приводит
  // роль проверяющего в чистое состояние. Опасно не написание, а место:
  // после маркера разрешённых команд безопасности нет ни одной.
  N('сброс всех настроек роли после маркера', 'K-R13-48',
    after(MARK00, 'ALTER ROLE bem_kernel_rw RESET ALL;')),

  // --- R30. Застава терминальной проверки (M-H114-R14-04) --------------
  // Пять подделок обёртки. Каждая оставляет на месте все пять кусков
  // текста, которых требовал прежний сверщик формы, — и каждая делает
  // успех возможным без фактически пройденной терминальной проверки.
  N("W1 (I-H114-03): вызов терминальной проверки под постоянным условием", 'K-R14-05',
    plain("try {\n  runAs(ADMIN_USER, finalText);\n  finalReceipt.terminal_check_passed = true;\n} catch (e) {", "try {\n  if (false) runAs(ADMIN_USER, finalText);\n  finalReceipt.terminal_check_passed = true;\n} catch (e) {")),
  N("W2: ранний выход с успехом до терминальной проверки", 'K-R14-05',
    plain("// Терминальная административная проверка. Она читает итоговое состояние", "if (finalReceipt.backup_window_applied) {\n  console.log('MIGRATION_OK: окно копирования применено');\n  process.exit(0);\n}\n// Терминальная административная проверка. Она читает итоговое состояние")),
  N("W3: окно копирования переставлено за терминальную проверку", 'K-R14-05',
    pair([
      plain("try {\n  runAs(ADMIN_USER, backupText);\n  finalReceipt.backup_window_applied = true;\n} catch (e) {\n  finalReceipt.error = 'backup_window: ' + (e.message || String(e));\n  writeFinalQuiet();\n  console.error('BACKUP_WINDOW_FILE_FAILED: ' + finalReceipt.error);\n  process.exit(5);\n}", "// окно копирования переставлено ниже"),
      plain("  console.error('TERMINAL_CHECK_FAILED: ' + finalReceipt.error);\n  process.exit(6);\n}", "  console.error('TERMINAL_CHECK_FAILED: ' + finalReceipt.error);\n  process.exit(6);\n}\n\ntry {\n  runAs(ADMIN_USER, backupText);\n  finalReceipt.backup_window_applied = true;\n} catch (e) {\n  finalReceipt.error = 'backup_window: ' + (e.message || String(e));\n  writeFinalQuiet();\n  console.error('BACKUP_WINDOW_FILE_FAILED: ' + finalReceipt.error);\n  process.exit(5);\n}"),
    ])),
  N("W4: признак поднят не итогом вызова", 'K-R14-05',
    plain("try {\n  runAs(ADMIN_USER, finalText);\n  finalReceipt.terminal_check_passed = true;\n} catch (e) {", "try {\n  const ok = true;\n  runAs(ADMIN_USER, finalText);\n  finalReceipt.terminal_check_passed = ok;\n} catch (e) {")),
  N("W5: признак поднят напрямую в другом месте", 'K-R14-05',
    plain("  runAs(ADMIN_USER, backupText);\n  finalReceipt.backup_window_applied = true;", "  runAs(ADMIN_USER, backupText);\n  finalReceipt.backup_window_applied = true;\n  finalReceipt.terminal_check_passed = true;")),
  // Положительный случай: правка пояснения внутри той же обёртки. Набор,
  // где любая правка даёт единицу, доказывал бы чувствительность к шуму.
  N("W6: правка пояснения внутри обёртки", 'K-R14-05',
    plain("// На путях отказа код возврата уже ненулевой, и осечка записи его не", "// На путях отказа код возврата уже ненулевой, и осечка записи его не меняет,"), 0),

  // --- R30. Обязательность финальной квитанции (M-H114-R14-05) ---------
  N("W7: неудачная запись квитанции не останавливает успех", 'K-R14-06',
    plain("  console.error('FINAL_RECEIPT_NOT_WRITTEN: ' + (e.message || String(e)));\n  process.exit(7);", "  console.error('FINAL_RECEIPT_NOT_WRITTEN: ' + (e.message || String(e)));\n  finalSha = null;")),
  N("W8: записанная квитанция не перечитывается с диска", 'K-R14-06',
    plain("  const back = readFileSync(RECEIPT_FILE, 'utf8');\n  if (back !== text) {", "  const back = text;\n  if (back !== text) {")),

  // --- R30. Точное множество прав доступа (M-H114-R14-02) --------------
  // Каждый класс лишнего права — отдельная подделка. Ни одна из них не
  // трогает ни одной объявленной строки: она только ДОБАВЛЯЕТ право.
  // Односторонняя проверка H1.14 не видела ни одной из них.
  N("A01: лишнее право чтения таблицы", 'K-R14-07',
    before(MARK01, "GRANT SELECT ON bem_core.evidence TO bem_engine_rw;")),
  N("A02: лишнее право записи строк", 'K-R14-07',
    before(MARK01, "GRANT INSERT ON bem_core.audit_record TO bem_kernel_rw;")),
  N("A03: лишнее право изменения строк", 'K-R14-07',
    before(MARK01, "GRANT UPDATE ON bem_core.evidence TO bem_kernel_rw;")),
  N("A04: лишнее право удаления строк", 'K-R14-07',
    before(MARK01, "GRANT DELETE ON bem_core.command_log TO bem_kernel_rw;")),
  N("A05: лишнее право очистки таблицы", 'K-R14-07',
    before(MARK01, "GRANT TRUNCATE ON bem_core.evidence TO bem_kernel_rw;")),
  N("A06: лишнее право ссылаться ключом", 'K-R14-07',
    before(MARK01, "GRANT REFERENCES ON bem_core.evidence TO bem_kernel_rw;")),
  N("A07: лишнее право создавать триггер", 'K-R14-07',
    before(MARK01, "GRANT TRIGGER ON bem_core.evidence TO bem_kernel_rw;")),
  N("A08: лишний вход в схему", 'K-R14-07',
    before(MARK01, "GRANT USAGE ON SCHEMA bem_core TO bem_engine_rw;")),
  N("A09: лишнее право создавать в схеме", 'K-R14-07',
    before(MARK01, "GRANT CREATE ON SCHEMA bem_core TO bem_kernel_rw;")),
  N("A10: лишнее право вызова функции", 'K-R14-07',
    before(MARK01, "GRANT EXECUTE ON FUNCTION bem_control.assert_tenant(uuid) TO bem_engine_rw;")),
  N("A11: право выдано всем подряд", 'K-R14-07',
    before(MARK01, "GRANT SELECT ON bem_core.evidence TO PUBLIC;")),
  N("A12: лишнее право по столбцу", 'K-R14-07',
    before(MARK01, "GRANT UPDATE (tenant_id) ON bem_core.work_item TO bem_kernel_rw;")),
  N("A13: право выдано с правом передачи", 'K-R14-07',
    before(MARK01, "GRANT SELECT ON bem_core.evidence TO backup_reader WITH GRANT OPTION;")),
  N("A14: право по умолчанию от чужого владельца", 'K-R14-07',
    before(MARK01, "ALTER DEFAULT PRIVILEGES FOR ROLE bem_control_owner IN SCHEMA bem_core GRANT SELECT ON TABLES TO backup_reader;")),
  // Подделка не канона, а самого договора: строку из списка файла 05
  // убрали. Вывод из канона её по-прежнему даёт — расхождение видно.
  N('A15: строка договора прав убрана', 'K-R14-07',
    rec({ op: "plain", from: "        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", to: "" })),
  // Положительный случай: повторная выдача того, что в договоре есть.
  // Новой строки не появляется, и сверщик обязан промолчать.
  N('A16: команда канона повторена слово в слово', 'K-R14-07',
    before(MARK01, "GRANT SELECT ON ALL TABLES IN SCHEMA bem_core TO bem_control_owner;"), 0),

  // --- R30. Определение триггера целиком (C-H114-R14-01) ---------------
  // G1 — это подделка I-H114-01 из самого аудита: существующий триггер с
  // правильным именем получает другое определение и переживает миграцию.
  // H1.14 сверяла у триггера только имя и таблицу и не видела ни одной
  // из первых четырёх правок.
  N("G1 (I-H114-01): момент срабатывания триггера аудита сужен до одного столбца", 'K-R14-01',
    plain("'BEFORE UPDATE OR DELETE ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',", "'BEFORE UPDATE OF head_sha ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',")),
  N("G2: триггер личности доказательства переставлен на после вставки", 'K-R14-01',
    plain("'BEFORE INSERT ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.evidence_identity()',", "'AFTER INSERT ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.evidence_identity()',")),
  N("G3: триггер личности доказательства переведён на уровень команды", 'K-R14-01',
    plain("'BEFORE INSERT ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.evidence_identity()',", "'BEFORE INSERT ON bem_core.evidence FOR EACH STATEMENT EXECUTE FUNCTION bem_core.evidence_identity()',")),
  N("G4: триггеру журнала команд подменена вызываемая функция", 'K-R14-01',
    plain("'BEFORE DELETE ON bem_core.command_log FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',", "'BEFORE DELETE ON bem_core.command_log FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_self_audit()',")),
  N("G5: строка договора триггеров убрана", 'K-R14-01',
    plain("        'bem_core.evidence|evidence_identity|7||bem_core.evidence_identity()|O|f|f|f|f|0',\n", "")),
  N("G6: две строки договора триггеров переставлены местами", 'K-R14-01',
    plain("        'bem_core.audit_record|audit_record_head_match|7||bem_core.audit_head_matches_subject()|O|f|f|f|f|0',\n        'bem_core.audit_record|audit_record_no_self_audit|7||bem_core.forbid_self_audit()|O|f|f|f|f|0',\n", "        'bem_core.audit_record|audit_record_no_self_audit|7||bem_core.forbid_self_audit()|O|f|f|f|f|0',\n        'bem_core.audit_record|audit_record_head_match|7||bem_core.audit_head_matches_subject()|O|f|f|f|f|0',\n"), 0),

  // --- R30. Поля политики построчной защиты (M-H114-R14-01) -----------
  // P2 сильнее P1: она правит ОБА шаблона согласованно, поэтому проверка
  // «шаблоны описывают одну политику» молчит. Ловит только сверка с
  // объявленным договором, которой в H1.14 не было.
  N("P1: условие политики ослаблено только в шаблоне создания", 'K-R14-02',
    plain("        IF NOT FOUND THEN\n            EXECUTE format(\n                'CREATE POLICY tenant_isolation ON bem_core.%I'\n                ' USING (tenant_id = bem_core.current_tenant())'", "        IF NOT FOUND THEN\n            EXECUTE format(\n                'CREATE POLICY tenant_isolation ON bem_core.%I'\n                ' USING (true)'")),
  N('P2 (I-H114-04): обе канонические политики ослаблены до (true)', 'K-R14-02',
    pair([
      plain("        IF NOT FOUND THEN\n            EXECUTE format(\n                'CREATE POLICY tenant_isolation ON bem_core.%I'\n                ' USING (tenant_id = bem_core.current_tenant())'\n                ' WITH CHECK (tenant_id = bem_core.current_tenant())', t);", "        IF NOT FOUND THEN\n            EXECUTE format(\n                'CREATE POLICY tenant_isolation ON bem_core.%I'\n                ' USING (true)'\n                ' WITH CHECK (true)', t);"),
      plain("                EXECUTE format(\n                    'ALTER POLICY tenant_isolation ON bem_core.%I TO public'\n                    ' USING (tenant_id = bem_core.current_tenant())'\n                    ' WITH CHECK (tenant_id = bem_core.current_tenant())', t);", "                EXECUTE format(\n                    'ALTER POLICY tenant_isolation ON bem_core.%I TO public'\n                    ' USING (true)'\n                    ' WITH CHECK (true)', t);"),
      plain("            EXECUTE format(\n                'ALTER POLICY tenant_isolation ON bem_core.%I TO public'\n                ' USING (tenant_id = bem_core.current_tenant())'\n                ' WITH CHECK (tenant_id = bem_core.current_tenant())', t);", "            EXECUTE format(\n                'ALTER POLICY tenant_isolation ON bem_core.%I TO public'\n                ' USING (true)'\n                ' WITH CHECK (true)', t);"),
      plain("        ELSE\n            EXECUTE format(\n                'CREATE POLICY tenant_isolation ON bem_core.%I'\n                ' USING (tenant_id = bem_core.current_tenant())'\n                ' WITH CHECK (tenant_id = bem_core.current_tenant())', t);", "        ELSE\n            EXECUTE format(\n                'CREATE POLICY tenant_isolation ON bem_core.%I'\n                ' USING (true)'\n                ' WITH CHECK (true)', t);")
    ])),
  N("P3: строка договора политик убрана", 'K-R14-02',
    plain("        'bem_core.evidence|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',\n", "")),
  N("P4: команда политики сужена с ALL до SELECT", 'K-R14-02',
    plain("        'bem_core.evidence|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',\n", "        'bem_core.evidence|tenant_isolation|SELECT|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',\n")),

  // --- R30. Закреплённый путь поиска у функций (M-H114-R14-01) --------
  // Незакреплённый путь поиска у функции с правами владельца — это чужая
  // схема впереди своей и подменённое имя таблицы внутри тела.
  N("S1: путь поиска у функции снят совсем", 'K-R14-03',
    plain("CREATE OR REPLACE FUNCTION bem_core.evidence_identity()\nRETURNS trigger\nLANGUAGE plpgsql\nSET search_path = bem_core, pg_catalog, pg_temp", "CREATE OR REPLACE FUNCTION bem_core.evidence_identity()\nRETURNS trigger\nLANGUAGE plpgsql")),
  N("S2: в путь поиска добавлена общая схема", 'K-R14-03',
    plain("CREATE OR REPLACE FUNCTION bem_core.evidence_identity()\nRETURNS trigger\nLANGUAGE plpgsql\nSET search_path = bem_core, pg_catalog, pg_temp", "CREATE OR REPLACE FUNCTION bem_core.evidence_identity()\nRETURNS trigger\nLANGUAGE plpgsql\nSET search_path = public, bem_core, pg_catalog, pg_temp")),
  N("S3: путь поиска ослаблен в самом договоре", 'K-R14-03',
    plain("'bem_control.assert_authority(text, uuid)|bem_control_owner|invoker|search_path=bem_core, pg_catalog, pg_temp',", "'bem_control.assert_authority(text, uuid)|bem_control_owner|invoker|search_path=public, bem_core, pg_catalog, pg_temp',")),

  // --- R30. Постоянное условие ветвления (I-H114-02) ------------------
  // Ветка, условие которой не зависит ни от одного имени, всегда идёт
  // одинаково. Так отключают проверку, не убирая её текст.
  N('D1 (I-H114-02): отказ сверки политик погашен постоянным условием', 'K-R14-04',
    plain("        IF v_got IS DISTINCT FROM v_row THEN\n            RAISE EXCEPTION 'FINAL_POLICY_MISMATCH: объявлено % , найдено %',", "        IF false THEN\n            RAISE EXCEPTION 'FINAL_POLICY_MISMATCH: объявлено % , найдено %',")),
  N("D2: слагаемые условия формы политики переставлены местами", 'K-R14-04',
    plain("IF v_cmd <> 'ALL' OR v_perm <> 'PERMISSIVE' THEN", "IF v_perm <> 'PERMISSIVE' OR v_cmd <> 'ALL' THEN"), 0),

  // --- R30. Остальные свойства записи квитанции (M-H114-R14-05) -------
  // Задание требует отрицательных тестов на запрет записи, отказ вроде
  // полного диска и повреждение готовой квитанции. W7 и W8 закрывают
  // фатальность отказа и перечитывание; эти четыре — остальное.
  N("W9: обязательные поля готовой квитанции не проверяются", 'K-R14-06',
    plain("  const parsed = JSON.parse(back);\n  for (const f of RECEIPT_FIELDS) {\n    if (!(f in parsed)) throw new Error('в квитанции нет обязательного поля ' + f);\n  }\n", "  const parsed = JSON.parse(back);\n")),
  N("W10: сумма готовой квитанции с диском не сверяется", 'K-R14-06',
    plain("  if (sha !== sumOf(readFileSync(RECEIPT_FILE))) {\n    throw new Error('сумма квитанции на диске не совпала с записанной');\n  }\n", "")),
  N("W11: квитанция пишется прямо в целевой файл, без временного и переименования", 'K-R14-06',
    plain("  renameSync(tmp, RECEIPT_FILE);", "  writeFileSync(RECEIPT_FILE, text);")),
  N("W12: содержимое не сбрасывается на диск до переименования", 'K-R14-06',
    plain("  try { writeSync(fd, text); fsyncSync(fd); } finally { closeSync(fd); }", "  try { writeSync(fd, text); } finally { closeSync(fd); }")),
  // --- R31. Условие и определение триггера (C-H115-R15-01) -------------
  // T01 — это подделка I-H115-01 из аудита 85, та же правка той же
  // строки. H1.15 её пропускала: оба сверщика проверяли только, что
  // условие есть, но не какое.
  B('T01 (I-H115-01): условие constraint-триггера заменено на WHEN (true)', 'K-R15-01',
    { реестр: 'trigger_when_mismatch: условие WHEN bem_core.subject|subject_requires_author', смысл: 'trigger_definition_problems: файл 01, пункт 15, определения: не хватает bem_core.subject|subject_requires_author' },
    plain("        WHEN (NEW.published_at IS NOT NULL)\n", "        WHEN (true)\n")),
  B('T02: другое непустое условие — IS NULL вместо IS NOT NULL', 'K-R15-01',
    { реестр: 'trigger_when_mismatch: условие WHEN bem_core.subject|subject_requires_author', смысл: 'trigger_definition_problems: файл 01, пункт 15, определения: не хватает bem_core.subject|subject_requires_author' },
    plain("        WHEN (NEW.published_at IS NOT NULL)\n", "        WHEN (NEW.published_at IS NULL)\n")),
  B('T03: обычному триггеру дописано условие WHEN (true)', 'K-R15-01',
    { реестр: 'trigger_when_mismatch: условие WHEN bem_core.evidence|evidence_identity', смысл: 'trigger_parse_problems: файл 01: evidence_identity: по телу условие WHEN' },
    plain("'BEFORE INSERT ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.evidence_identity()',", "'BEFORE INSERT ON bem_core.evidence FOR EACH ROW WHEN (true) EXECUTE FUNCTION bem_core.evidence_identity()',")),
  B('T04: условие в договоре файла 05 заменено на true', 'K-R15-01',
    { реестр: 'trigger_when_mismatch: условие WHEN bem_core.subject|subject_requires_author', смысл: 'terminal_problems: v_trigger_def: не хватает bem_core.subject|subject_requires_author' },
    plain("|subject_requires_author|new.published_at IS NOT NULL||CREATE CONSTRAINT", "|subject_requires_author|true||CREATE CONSTRAINT")),
  L('T05: немедленная сверка условия убрана из цикла файла 01', 'K-R15-01', 'trigger_definition_problems: файл 01: немедленная сверка не сравнивает условие WHEN',
    plain("                 WHEN v_when <> r.want_when\n                   THEN 'условие WHEN (' || v_when || ') вместо (' || r.want_when || ')'\n", "")),
  B('T06: лишние скобки вокруг условия', 'K-R15-01', null,
    plain("        WHEN (NEW.published_at IS NOT NULL)\n", "        WHEN ((NEW.published_at IS NOT NULL))\n"), 0),
  B('T07: условие записано строчными буквами', 'K-R15-01', null,
    plain("        WHEN (NEW.published_at IS NOT NULL)\n", "        WHEN (new.published_at is not null)\n"), 0),
  L('T08: другая функция при том же имени триггера', 'K-R15-02', 'trigger_definition_problems: файл 01, пункт 15, отпечатки: не хватает bem_core.subject|subject_requires_author',
    plain("        EXECUTE FUNCTION bem_core.require_at_least_one_author();", "        EXECUTE FUNCTION bem_core.forbid_self_audit();")),
  L('T09: лишнее событие DELETE', 'K-R15-02', 'trigger_definition_problems: файл 01, пункт 15, отпечатки: не хватает bem_core.subject|subject_requires_author',
    plain("        AFTER INSERT OR UPDATE OF published_at ON bem_core.subject\n", "        AFTER INSERT OR DELETE OR UPDATE OF published_at ON bem_core.subject\n")),
  L('T10: другой список столбцов', 'K-R15-02', 'trigger_definition_problems: файл 01, пункт 15, отпечатки: не хватает bem_core.subject|subject_requires_author',
    plain("        AFTER INSERT OR UPDATE OF published_at ON bem_core.subject\n", "        AFTER INSERT OR UPDATE OF published_at, tenant_id ON bem_core.subject\n")),
  L('T11: у триггера появился аргумент', 'K-R15-02', 'trigger_definition_problems: файл 01, пункт 15, отпечатки: не хватает bem_core.subject|subject_requires_author',
    plain("        EXECUTE FUNCTION bem_core.require_at_least_one_author();", "        EXECUTE FUNCTION bem_core.require_at_least_one_author('x');")),
  L('T12: срабатывание сразу, а не в конце транзакции', 'K-R15-02', 'trigger_definition_problems: файл 01, пункт 15, отпечатки: не хватает bem_core.subject|subject_requires_author',
    plain("        DEFERRABLE INITIALLY DEFERRED\n        FOR EACH ROW\n        WHEN (NEW", "        DEFERRABLE INITIALLY IMMEDIATE\n        FOR EACH ROW\n        WHEN (NEW")),
  L('T13: триггер не откладываемый', 'K-R15-02', 'trigger_definition_problems: файл 01, пункт 15, отпечатки: не хватает bem_core.subject|subject_requires_author',
    plain("        DEFERRABLE INITIALLY DEFERRED\n        FOR EACH ROW\n        WHEN (NEW", "        NOT DEFERRABLE INITIALLY IMMEDIATE\n        FOR EACH ROW\n        WHEN (NEW")),
  L('T14: обычный триггер вместо constraint-триггера', 'K-R15-02', 'trigger_definition_problems: файл 01, пункт 15, отпечатки: не хватает bem_core.subject|subject_requires_author',
    plain("    CREATE CONSTRAINT TRIGGER subject_requires_author\n        AFTER INSERT OR UPDATE OF published_at ON bem_core.subject\n        DEFERRABLE INITIALLY DEFERRED\n", "    CREATE TRIGGER subject_requires_author\n        AFTER INSERT OR UPDATE OF published_at ON bem_core.subject\n")),
  L('T15: ожидаемое определение в файле 01 разошлось с командой', 'K-R15-03', 'trigger_definition_problems: файл 01: по команде определение',
    plain("    v_want_def  := 'CREATE CONSTRAINT TRIGGER subject_requires_author AFTER INSERT OR UPDATE OF", "    v_want_def  := 'CREATE CONSTRAINT TRIGGER subject_requires_author AFTER UPDATE OF")),
  L('T16: определение в договоре файла 05 разошлось с командой', 'K-R15-03', 'terminal_problems: v_trigger_def: не хватает bem_core.evidence|evidence_identity',
    plain("'bem_core.evidence|evidence_identity|||CREATE TRIGGER evidence_identity BEFORE INSERT ON bem_core.evidence FOR EACH ROW", "'bem_core.evidence|evidence_identity|||CREATE TRIGGER evidence_identity BEFORE INSERT ON bem_core.evidence FOR EACH STATEMENT")),
  L('T17: определение в списке пункта 15а файла 01 разошлось с командой', 'K-R15-03', 'trigger_definition_problems: файл 01, пункт 15, определения: не хватает bem_core.evidence|evidence_identity',
    lastPlain("'bem_core.evidence|evidence_identity|||CREATE TRIGGER evidence_identity BEFORE INSERT ON bem_core.evidence FOR EACH ROW", "'bem_core.evidence|evidence_identity|||CREATE TRIGGER evidence_identity BEFORE INSERT ON bem_core.evidence FOR EACH STATEMENT")),
  L('T18: сверка определений в файле 05 без закреплённого пути поиска', 'K-R15-03', 'trigger_definition_problems: файл 05 читает определение без закреплённого пути поиска',
    plain("    --     же условии, что и в шаге 7.\n    v_path := current_setting('search_path');\n    PERFORM set_config('search_path', 'pg_catalog, pg_temp', true);\n", "    --     же условии, что и в шаге 7.\n    v_path := current_setting('search_path');\n")),
  L('T19: определение в файле 05 читается без нормализации', 'K-R15-03', 'trigger_definition_problems: файл 05 не читает определение триггера у сервера',
    plain("CROSS JOIN LATERAL (SELECT regexp_replace(pg_get_triggerdef(tg.oid, true)", "CROSS JOIN LATERAL (SELECT regexp_replace(pg_get_triggerdef(tg.oid, false)")),
  B('T20: пояснение у constraint-триггера переписано', 'K-R15-03', null,
    plain("    -- Constraint-триггер пересоздаётся так же безусловно. У него\n", "    -- Constraint-триггер тоже пересоздаётся безусловно. У него\n"), 0),
  L('T21: триггер отключён после живой самопроверки', 'K-R15-04', 'vocabulary_problems: запрещённая форма — отключение триггера',
    before(MARK01, 'ALTER TABLE bem_core.subject DISABLE TRIGGER subject_requires_author;')),
  L('T22: триггер переведён в режим REPLICA', 'K-R15-04', 'vocabulary_problems: запрещённая форма — смена режима триггера',
    before(MARK01, 'ALTER TABLE bem_core.subject ENABLE REPLICA TRIGGER subject_requires_author;')),
  L('T23: триггер отключён внутри блока пересоздания', 'K-R15-04', 'trigger_definition_problems: файл 01_database_migration.sql: меняется режим срабатывания триггеров: DISABLE TRIGGER',
    plain("        WHEN (NEW.published_at IS NOT NULL)\n        EXECUTE FUNCTION bem_core.require_at_least_one_author();\n", "        WHEN (NEW.published_at IS NOT NULL)\n        EXECUTE FUNCTION bem_core.require_at_least_one_author();\n    ALTER TABLE bem_core.subject DISABLE TRIGGER subject_requires_author;\n")),

  // --- R31. Кто выдал право и сколько раз (M-H115-R15-01) -------------
  L('A17: право верному получателю от неверного выдавшего', 'K-R15-05', 'terminal_problems: v_acl: лишнее TABLE|bem_core.evidence|backup_reader|SELECT|bem_control_owner',
    plain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_control_owner',\n")),
  L('A18: неверный выдавший у права по умолчанию', 'K-R15-05', 'terminal_problems: v_acl: лишнее DEFAULT|bem_core_owner|bem_core|r|backup_reader|SELECT|bem_control_owner',
    plain("        'DEFAULT|bem_core_owner|bem_core|r|backup_reader|SELECT|bem_core_owner',\n", "        'DEFAULT|bem_core_owner|bem_core|r|backup_reader|SELECT|bem_control_owner',\n")),
  L('A19: выдача от имени другой роли (GRANTED BY)', 'K-R15-05', 'vocabulary_problems: команда безопасности вне закрытого списка: GRANT SELECT ON bem_core.evidence TO backup_reader GRANTED BY',
    before(MARK01, 'GRANT SELECT ON bem_core.evidence TO backup_reader GRANTED BY bem_core_owner;')),
  L('A20: сверка каталога потеряла выдавшего в ветке таблиц', 'K-R15-05', 'acl_grantor_problems: файл 05: выдавший читается не во всех списках прав',
    plain("               || '|' || coalesce(gr.rolname, a.grantor::text)\n          FROM pg_class c\n", "          FROM pg_class c\n")),
  L('A21: проверка выдавшего в файле 01 ослаблена', 'K-R15-05', 'acl_grantor_problems: в самопроверке файла 01 нет правила',
    plain("      LEFT JOIN pg_roles o ON o.oid = i.owner\n     WHERE i.grantor <> i.owner OR i.is_grantable", "      LEFT JOIN pg_roles o ON o.oid = i.owner\n     WHERE i.is_grantable")),
  L('A22: два одинаковых права от разных выдавших', 'K-R15-06', 'terminal_problems: v_acl: лишнее TABLE|bem_core.evidence|backup_reader|SELECT|bem_control_owner',
    plain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_control_owner',\n        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n")),
  L('A23: одна и та же строка договора дважды', 'K-R15-06', 'terminal_problems: v_acl: повтор строки',
    plain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n")),
  L('A24: сравнение прав возвращено к EXCEPT', 'K-R15-06', 'acl_grantor_problems: файл 05: права сравниваются через EXCEPT',
    plain("    SELECT count(*), left(coalesce(string_agg(x.r || ' x' || (x.n_got - x.n_want), ', '\n                                              ORDER BY x.r COLLATE \"C\"), ''), 600)\n      INTO v_cnt, v_got\n      FROM (SELECT coalesce(g.r, w.r) AS r, coalesce(g.n, 0) AS n_got, coalesce(w.n, 0) AS n_want\n              FROM (SELECT r, count(*) AS n FROM unnest(v_acl_got) AS r GROUP BY r) g\n              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n", "    SELECT count(*), left(coalesce(string_agg(x.r, ', ' ORDER BY x.r COLLATE \"C\"), ''), 600)\n      INTO v_cnt, v_got\n      FROM (SELECT unnest(v_acl_got) AS r EXCEPT SELECT unnest(v_acl)) x;\n")),
  L('A25: пояснение к сверке прав переписано', 'K-R15-06', null,
    plain("    --     R31 (замечание M-H115-R15-01). Последнее поле строки — кто\n", "    --     R31 (замечание M-H115-R15-01). Последнее поле строки — роль, что\n"), 0),
  L('A26: лишнее право передачи в договоре', 'K-R15-07', 'terminal_problems: v_acl: лишнее TABLE|bem_core.evidence|backup_reader|SELECT*|bem_core_owner',
    plain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|backup_reader|SELECT*|bem_core_owner',\n")),
  L('A27: лишнее право PUBLIC в договоре', 'K-R15-07', 'terminal_problems: v_acl: лишнее TABLE|bem_core.evidence|PUBLIC|SELECT|bem_core_owner',
    plain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|PUBLIC|SELECT|bem_core_owner',\n        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n")),
  // --- РАУНД-R32-ПОДДЕЛКИ. Точные права в файле 01, повторы объявлений, текст раздела 5 ---
  // Замечание M-H116-R16-02 и добавки автора. Якоря файла 01, которые стоят и в
  // договоре файла 05, берутся последним вхождением: файл 05 в документе идёт
  // раньше файла 01. Длинные якоря взяты из частей документа при записи набора.
  L("A28: право верному получателю от неверного выдавшего, список файла 01", "K-R16-01", "selfcheck_problems: v_acl: лишнее TABLE|bem_core.evidence|backup_reader|SELECT|bem_control_owner",
    lastPlain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_control_owner',\n")),
  L("A29: неверный выдавший у права по умолчанию, список файла 01", "K-R16-01", "selfcheck_problems: v_acl: лишнее DEFAULT|bem_core_owner|bem_core|r|backup_reader|SELECT|bem_control_owner",
    lastPlain("        'DEFAULT|bem_core_owner|bem_core|r|backup_reader|SELECT|bem_core_owner',\n", "        'DEFAULT|bem_core_owner|bem_core|r|backup_reader|SELECT|bem_control_owner',\n")),
  L("A30: неверный выдавший у права функции окна, список файла 01", "K-R16-01", "selfcheck_problems: v_acl_04: лишнее FUNCTION|bem_control.backup_window_drain()|bem_backup_admin|EXECUTE|bem_control_owner",
    lastPlain("        'FUNCTION|bem_control.backup_window_drain()|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',\n", "        'FUNCTION|bem_control.backup_window_drain()|bem_backup_admin|EXECUTE|bem_control_owner',\n")),
  L("A31: выдавший потерян в ветке таблиц запроса файла 01", "K-R16-01", "acl_grantor_problems: файл 01: выдавший читается не во всех списках прав",
    lastPlain("               || '|' || coalesce(gr.rolname, a.grantor::text)\n          FROM pg_class c\n", "          FROM pg_class c\n")),
  L("A32: два одинаковых права от разных выдавших, список файла 01", "K-R16-02", "selfcheck_problems: v_acl: лишнее TABLE|bem_core.evidence|backup_reader|SELECT|bem_control_owner",
    lastPlain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_control_owner',\n        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n")),
  L("A33: одна и та же строка договора дважды, список файла 01", "K-R16-02", "selfcheck_problems: v_acl: повтор строки",
    lastPlain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n")),
  L("A34: сравнение прав в файле 01 возвращено к EXCEPT", "K-R16-02", "acl_grantor_problems: файл 01: права сравниваются через EXCEPT",
    plain("    SELECT count(*), left(coalesce(string_agg(x.r || ' x' || (x.n_got - x.n_want), ', '\n                                              ORDER BY x.r COLLATE \"C\"), ''), 600)\n      INTO v_cnt, v_got\n      FROM (SELECT coalesce(g.r, w.r) AS r, coalesce(g.n, 0) AS n_got, coalesce(w.n, 0) AS n_want\n              FROM (SELECT r, count(*) AS n FROM unnest(v_acl_got) AS r GROUP BY r) g\n              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl_want) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n", "    SELECT count(*), left(coalesce(string_agg(x.r, ', ' ORDER BY x.r COLLATE \"C\"), ''), 600)\n      INTO v_cnt, v_got\n      FROM (SELECT unnest(v_acl_got) AS r EXCEPT SELECT unnest(v_acl_want)) x;\n")),
  L("A35: в файле 01 снята сверка «объявленных прав нет»", "K-R16-02", "acl_grantor_problems: файл 01: права сравниваются не с учётом повторов: нет WHERE x.n_want > x.n_got",
    plain("    SELECT count(*), left(coalesce(string_agg(x.r || ' x' || (x.n_want - x.n_got), ', '\n                                              ORDER BY x.r COLLATE \"C\"), ''), 600)\n      INTO v_cnt, v_got\n      FROM (SELECT coalesce(g.r, w.r) AS r, coalesce(g.n, 0) AS n_got, coalesce(w.n, 0) AS n_want\n              FROM (SELECT r, count(*) AS n FROM unnest(v_acl_got) AS r GROUP BY r) g\n              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl_want) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_want > x.n_got;\n    IF v_cnt <> 0 THEN\n        RAISE EXCEPTION 'MIGRATION_FAILED: объявленных прав нет %: %', v_cnt, v_got;\n    END IF;\n", "")),
  L("A36: лишнее право передачи в списке файла 01", "K-R16-03", "selfcheck_problems: v_acl: лишнее TABLE|bem_core.evidence|backup_reader|SELECT*|bem_core_owner",
    lastPlain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|backup_reader|SELECT*|bem_core_owner',\n")),
  L("A37: лишнее право PUBLIC в списке файла 01", "K-R16-03", "selfcheck_problems: v_acl: лишнее TABLE|bem_core.evidence|PUBLIC|SELECT|bem_core_owner",
    lastPlain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "        'TABLE|bem_core.evidence|PUBLIC|SELECT|bem_core_owner',\n        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n")),
  L("A38: потеряна строка списка прав файла 01", "K-R16-04", "selfcheck_problems: v_acl: не хватает TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner",
    lastPlain("        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',\n", "")),
  L("A39: потеряна строка прав функции окна в файле 01", "K-R16-04", "selfcheck_problems: v_acl_04: не хватает FUNCTION|bem_control.backup_window_assert_closed()|bem_backup_admin|EXECUTE|bem_backup_ctl_owner",
    lastPlain("        'FUNCTION|bem_control.backup_window_assert_closed()|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',\n", "")),
  L("A40: список прав в файле 01 убран", "K-R16-04", "selfcheck_problems: v_acl: массива в файле 01 нет",
    plain("    v_acl    constant text[] := ARRAY[\n", "    v_acl_old constant text[] := ARRAY[\n")),
  L("A41: порядок строк списка прав переставлен", "K-R16-04", null,
    lastPlain("        'COLUMN|bem_control.backup_window.closed_at|bem_backup_ctl_owner|UPDATE|bem_control_owner',\n        'COLUMN|bem_control.backup_window.locked_at|bem_backup_ctl_owner|UPDATE|bem_control_owner',\n", "        'COLUMN|bem_control.backup_window.locked_at|bem_backup_ctl_owner|UPDATE|bem_control_owner',\n        'COLUMN|bem_control.backup_window.closed_at|bem_backup_ctl_owner|UPDATE|bem_control_owner',\n"), 0),
  L("A42: пояснение внутри списка прав файла 01", "K-R16-04", null,
    plain("    v_acl    constant text[] := ARRAY[\n", "    v_acl    constant text[] := ARRAY[\n        -- пояснение внутри списка\n"), 0),
  L("A43: охрана «все или ни одной» снята", "K-R16-05", "acl_grantor_problems: файл 01: нет охраны «все или ни одной» для прав функций окна: нет IF v_cnt NOT IN (0, cardinality(v_acl_04)) THEN",
    plain("    IF v_cnt NOT IN (0, cardinality(v_acl_04)) THEN\n", "    IF v_cnt < 0 THEN\n")),
  L("A44: ветви выбора договора переставлены", "K-R16-05", "acl_grantor_problems: файл 01: нет охраны «все или ни одной» для прав функций окна: нет IF v_cnt = 0 THEN",
    plain("    IF v_cnt = 0 THEN\n        v_acl_want := v_acl;\n    ELSE\n        v_acl_want := v_acl || v_acl_04;\n    END IF;\n", "    IF v_cnt = 0 THEN\n        v_acl_want := v_acl || v_acl_04;\n    ELSE\n        v_acl_want := v_acl;\n    END IF;\n")),
  L("A45: из запроса каталога файла 01 убран фильтр системных схем", "K-R16-06", "acl_grantor_problems: файл 01: запрос прав каталога не совпадает с запросом шага 10 файла 05",
    lastPlain("           AND nspname NOT LIKE 'pg\\_toast%'\n           AND nspname NOT LIKE 'pg\\_temp%'\n    ), got AS (\n", "    ), got AS (\n")),
  L("A46: пояснение к проверке 20 файла 01 переписано", "K-R16-06", null,
    plain("    --     разницу, а не выпасть из рассмотрения вместе со схемой. Запрос\n", "    --     разницу, а не выпасть из рассмотрения вместе со схемой. Тот же запрос\n"), 0),
  L("A47: второе объявление v_read в файле 01", "K-R16-07", "declaration_duplicate_problems: файл 01_database_migration.sql: имя v_read объявлено 2 раза",
    lastPlain("    v_acl_want text[];\n    v_got      text;\n", "    v_acl_want text[];\n    v_got      text;\n    v_read  constant text[] := ARRAY['x'];\n")),
  L("A48: раздел 5.2 снова называет право на запись доказательства выданным", "K-R16-08", "prose_problems: раздел 5.2: право на запись доказательства названо выданным",
    plain("| Записать доказательство | нет: право `INSERT` на `bem_core.evidence` отозвано (замечание `C-H18-R8-05`) | `bem_control.record_evidence` |\n", "| Записать доказательство | да, `INSERT` на `bem_core.evidence` | — |\n")),
  L("A49: заголовок 5.3 снова называет запись доказательства прямой", "K-R16-08", "prose_problems: раздел 5: запись доказательства «оставлена прямой»",
    plain("## 5.3. Почему запись доказательства идёт только через функцию\n", "## 5.3. Почему запись доказательства оставлена прямой\n")),
  L("A50: последняя фраза раздела 5.3 переписана", "K-R16-08", null,
    plain("Отрицательный тест — `K-R8-08`.\n", "Это проверяет отрицательный тест `K-R8-08`.\n"), 0),
  L("A51: первая сверка файла 01 сравнивает каталог сам с собой", "K-R16-09", "acl_grantor_problems: сравнение прав в файле 01 (пункт 22) и в файле 05 (шаг 10) разошлось",
    plain("              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl_want) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n", "              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl_got) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n")),
  L("A52: первая сверка файла 05 сравнивает каталог сам с собой", "K-R16-09", "acl_grantor_problems: сравнение прав в файле 01 (пункт 22) и в файле 05 (шаг 10) разошлось",
    plain("              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n", "              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl_got) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n")),
  L("A53: условие отказа первой сверки файла 01 ослаблено", "K-R16-09", "acl_grantor_problems: сравнение прав в файле 01 (пункт 22) и в файле 05 (шаг 10) разошлось",
    plain("    IF v_cnt <> 0 THEN\n        RAISE EXCEPTION 'MIGRATION_FAILED: прав сверх договора %: %', v_cnt, v_got;\n", "    IF v_cnt < 0 THEN\n        RAISE EXCEPTION 'MIGRATION_FAILED: прав сверх договора %: %', v_cnt, v_got;\n")),
  L("A54: отказ второй сверки файла 05 заменён уведомлением", "K-R16-09", "acl_grantor_problems: сравнение прав в файле 01 (пункт 22) и в файле 05 (шаг 10) разошлось",
    plain("        RAISE EXCEPTION 'FINAL_ACL_MISSING: объявленных прав нет %: %', v_cnt, v_got;\n", "        RAISE NOTICE 'FINAL_ACL_MISSING: объявленных прав нет %: %', v_cnt, v_got;\n")),
  // --- РАУНД-R32-РЕДАКЦИЯ. Последний абзац документа называет только текущую редакцию ---
  // Замечание L-H116-R16-02. Якоря лежат в последнем абзаце документа.
  L("A55: последний абзац называет прежнюю редакцию H1.16 в первой фразе", "K-R16-10", "edition_problems: последний абзац называет чужую редакцию H1.16",
    plain("Оно не означает, что H1.29 верна", "Оно не означает, что H1.16 верна")),
  L("A56: последний абзац называет редакцию H1.14 в последней фразе", "K-R16-10", "edition_problems: последний абзац называет чужую редакцию H1.14",
    plain("Принять или отклонить H1.29 может", "Принять или отклонить H1.14 может")),
  L("A57: последняя фраза последнего абзаца переписана", "K-R16-10", null,
    plain("Старые номера редакций выше остаются только как явно исторические входы.", "Старые номера редакций выше остаются только как исторические входы."), 0),

  // --- R33. Правка 1 (M-H117-R17-01 = B-01): независимый инвариант
  // «ровно два FULL JOIN» на файл 01 и файл 05 по отдельности ------------
  L("A58: совместная подделка FULL JOIN -> LEFT JOIN в файле 01 и в файле 05 разом", "K-R17-01",
    "acl_grantor_problems: файл 01 (пункт 22): сравнение прав использует не два FULL JOIN",
    pair([
      rec({ op: 'plain', from: "              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n    IF v_cnt <> 0 THEN\n        RAISE EXCEPTION 'FINAL_ACL_SURPLUS: прав сверх договора %: %', v_cnt, v_got;\n    END IF;\n", to: "              LEFT JOIN (SELECT r, count(*) AS n FROM unnest(v_acl) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n    IF v_cnt <> 0 THEN\n        RAISE EXCEPTION 'FINAL_ACL_SURPLUS: прав сверх договора %: %', v_cnt, v_got;\n    END IF;\n" }),
      rec({ op: 'plain', from: "              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl_want) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n    IF v_cnt <> 0 THEN\n        RAISE EXCEPTION 'MIGRATION_FAILED: прав сверх договора %: %', v_cnt, v_got;\n    END IF;\n", to: "              LEFT JOIN (SELECT r, count(*) AS n FROM unnest(v_acl_want) AS r GROUP BY r) w\n                ON w.r = g.r) x\n     WHERE x.n_got > x.n_want;\n    IF v_cnt <> 0 THEN\n        RAISE EXCEPTION 'MIGRATION_FAILED: прав сверх договора %: %', v_cnt, v_got;\n    END IF;\n" }),
    ])),

  // --- R33. Правка 2 (M-H117-R17-02 = B-02): разбор кавычек PostgreSQL
  // в declNames — два вида подделки из ответа аудитора B-NI-2 -------------
  L("A59: повтор имени в кавычках дважды в файле 01", "K-R17-02",
    "declaration_duplicate_problems: файл 01_database_migration.sql: имя v_dupq1 объявлено 2 раза",
    lastPlain("    v_acl_want text[];\n    v_got      text;\n", "    v_acl_want text[];\n    v_got      text;\n    \"v_dupq1\" text;\n    \"v_dupq1\" text;\n")),
  L("A60: повтор имени в кавычках и без кавычек в файле 01", "K-R17-02",
    "declaration_duplicate_problems: файл 01_database_migration.sql: имя v_dupq2 объявлено 2 раза",
    lastPlain("    v_acl_want text[];\n    v_got      text;\n", "    v_acl_want text[];\n    v_got      text;\n    v_dupq2 text;\n    \"v_dupq2\" text;\n")),

  // --- R33. Правка 3 (L-H117-R17-01 = L-C-02, решение D-05): эталонный
  // триггер и сравнение tgqual::text — удаление и три вида ослабления ----
  L("A61: эталонный триггер и сравнение tgqual::text убраны целиком", "K-R17-03",
    "trigger_definition_problems: файл 01: нет эталонного триггера subject_requires_author_ref",
    plain("    DROP TABLE IF EXISTS pg_temp.subject_reference_shape;\n    CREATE TEMP TABLE subject_reference_shape (LIKE bem_core.subject);\n\n    DROP TRIGGER IF EXISTS subject_requires_author_ref ON pg_temp.subject_reference_shape;\n    CREATE CONSTRAINT TRIGGER subject_requires_author_ref\n        AFTER INSERT OR UPDATE OF published_at ON pg_temp.subject_reference_shape\n        DEFERRABLE INITIALLY DEFERRED\n        FOR EACH ROW\n        WHEN (NEW.published_at IS NOT NULL)\n        EXECUTE FUNCTION bem_core.require_at_least_one_author();\n\n    SELECT regexp_replace(tg.tgqual::text, ':location -?[0-9]+', ':location X', 'g')\n      INTO v_tgqual_real\n      FROM pg_trigger tg\n     WHERE tg.tgname = 'subject_requires_author'\n       AND tg.tgrelid = 'bem_core.subject'::regclass\n       AND NOT tg.tgisinternal;\n\n    SELECT regexp_replace(tg.tgqual::text, ':location -?[0-9]+', ':location X', 'g')\n      INTO v_tgqual_ref\n      FROM pg_trigger tg\n     WHERE tg.tgname = 'subject_requires_author_ref'\n       AND tg.tgrelid = 'pg_temp.subject_reference_shape'::regclass\n       AND NOT tg.tgisinternal;\n\n    IF v_tgqual_real IS DISTINCT FROM v_tgqual_ref THEN\n        RAISE EXCEPTION 'TRIGGER_TGQUAL_MISMATCH: subject_requires_author: % вместо %',\n            v_tgqual_real, v_tgqual_ref;\n    END IF;\n\n    DROP TRIGGER IF EXISTS subject_requires_author_ref ON pg_temp.subject_reference_shape;\n    DROP TABLE IF EXISTS pg_temp.subject_reference_shape;\n", '')),
  L("A62: сравнение tgqual::text заменено условием, которое никогда не срабатывает", "K-R17-03",
    "trigger_definition_problems: файл 01: сравнение tgqual::text ослаблено",
    plain('IF v_tgqual_real IS DISTINCT FROM v_tgqual_ref THEN', 'IF false THEN')),
  L("A63: отказ при расхождении tgqual::text заменён уведомлением", "K-R17-03",
    "trigger_definition_problems: файл 01: расхождение tgqual::text не приводит к отказу",
    plain("        RAISE EXCEPTION 'TRIGGER_TGQUAL_MISMATCH: subject_requires_author: % вместо %',\n            v_tgqual_real, v_tgqual_ref;\n", "        RAISE NOTICE 'TRIGGER_TGQUAL_MISMATCH: subject_requires_author: % вместо %',\n            v_tgqual_real, v_tgqual_ref;\n")),
  L("A64: второе чтение каталога подменено на то же самое, что первое", "K-R17-03",
    "trigger_definition_problems: файл 01: сравнение tgqual::text не читает настоящий и эталонный триггер",
    plain("     WHERE tg.tgname = 'subject_requires_author_ref'\n       AND tg.tgrelid = 'pg_temp.subject_reference_shape'::regclass",
          "     WHERE tg.tgname = 'subject_requires_author'\n       AND tg.tgrelid = 'bem_core.subject'::regclass")),

  // --- R33. Правка 4 (L-H117-R17-02 = B-04, решение D-08): ожидаемая
  // редакция независима от документа - совместный откат паспорта и
  // последнего абзаца разом всё равно ловится -------------------------
  L("A65: совместная подделка - паспорт и последний абзац разом откатываются на H1.28", "K-R17-04",
    "edition_problems: паспорт называет редакцию H1.28, а ожидается H1.29",
    pair([
      plain("ВЕРСИЯ:\nv1.29", "ВЕРСИЯ:\nv1.28"),
      plain("Оно не означает, что H1.29 верна или принята.",
            "Оно не означает, что H1.28 верна или принята."),
    ])),

  // --- R44. M-R43-01 (аудит R43): права роли проверки восстановления на
  // схемы - свёртка убирает ровно одно право, файл 03 снимает и сверяет --
  L("A66: условие свёртки схем заменено на WHERE true", "K-R43-01",
    "restore_acl_problems: файл 01: свёртка схем убирает не ровно одно право",
    plain("                                                WHERE NOT (n.nspname = 'bem_control'\n                                                           AND e.grantee <> 0",
          "                                                WHERE true OR (n.nspname = 'bem_control'\n                                                           AND e.grantee <> 0")),
  L("A67: в файле 03 убран отзыв прежних прав роли на схемы", "K-R43-01",
    "restore_acl_problems: файл 03: прежние права роли на три схемы не сняты",
    plain("REVOKE CREATE, USAGE ON SCHEMA bem_control FROM restore_verifier;\nGRANT USAGE ON SCHEMA bem_control TO restore_verifier;",
          "GRANT USAGE ON SCHEMA bem_control TO restore_verifier;")),
  L("A68: в файле 03 проверка CREATE на bem_control ослаблена", "K-R43-01",
    "restore_acl_problems: файл 03: нет отказа при праве CREATE",
    plain("    IF has_schema_privilege('restore_verifier', 'bem_control', 'CREATE')\n       OR has_schema_privilege('restore_verifier', 'bem_core', 'CREATE')",
          "    IF has_schema_privilege('restore_verifier', 'bem_control', 'USAGE') AND false\n       OR has_schema_privilege('restore_verifier', 'bem_core', 'CREATE')")),
  L("A69: в файле 03 отказ при лишних правах на схемы заменён уведомлением", "K-R43-01",
    "restore_acl_problems: файл 03: нет сверки точного списка прав",
    plain("        RAISE EXCEPTION 'RESTORE_VERIFIER_TOO_WIDE: лишних прав роли на схемы: %', v_cnt;",
          "        RAISE NOTICE 'RESTORE_VERIFIER_TOO_WIDE: лишних прав роли на схемы: %', v_cnt;")),
  // --- R45. L-R44-01 (аудит R44): исключение только для права, выданного
  // владельцем схемы, - в свёртке 01 и в точной сверке 03 ----------------
  L("A70: в свёртке схем убрано условие на выдающего права", "K-R44-01",
    "restore_acl_problems: файл 01: свёртка схем убирает не ровно одно право",
    plain("                                                           AND NOT e.is_grantable\n                                                           AND e.grantor = n.nspowner)) z), '-')) AS line",
          "                                                           AND NOT e.is_grantable)) z), '-')) AS line")),
  L("A71: в файле 03 из точной сверки убрано условие на выдающего права", "K-R44-01",
    "restore_acl_problems: файл 03: нет сверки точного списка прав",
    plain("                AND NOT e.is_grantable\n                AND e.grantor = n.nspowner);",
          "                AND NOT e.is_grantable);")),
  // --- R46. D1 проб R46: полный список ограничений в 01 и точная сверка
  // в 05; D2 проб R46: запрет проверяющего из компании автора снят ------
  L("A72: из шага 4 файла 01 убран кортеж outbox_idem_uniq", "K-R46-01",
    "constraint_problems: файл 01: нет ограничения ровно одним кортежем",
    plain("            ('bem_core.outbox', 'outbox_idem_uniq', 'UNIQUE (tenant_id, kind, idempotency_key)'),\n", "")),
  L("A73: в файле 05 отказ при лишнем ограничении заменён уведомлением", "K-R46-01",
    "constraint_problems: файл 05: нет отказа",
    plain("        RAISE EXCEPTION 'FINAL_CONSTRAINT_MISMATCH: ограничений сверх договора: %', v_extra;",
          "        RAISE NOTICE 'FINAL_CONSTRAINT_MISMATCH: ограничений сверх договора: %', v_extra;")),
  L("A74: в шаге 4 файла 01 отказ при другой форме ограничения снят", "K-R46-01",
    "constraint_problems: файл 01: ветвей",
    plain("        ELSIF v_def IS DISTINCT FROM r.def THEN\n", "        ELSIF false THEN\n")),
  L("A75: из шага 2 файла 01 убрана починка проверки домена", "K-R46-01",
    "constraint_problems: файл 01: нет ограничения домена",
    plain("        ALTER DOMAIN bem_core.actor_id ADD CONSTRAINT actor_id_check\n",
          "        ALTER DOMAIN bem_core.actor_id VALIDATE CONSTRAINT actor_id_check\n")),
  L("A76: в assign_auditor возвращён запрет проверяющего из компании автора", "K-R46-02",
    "bem954_assign_problems: assign_auditor: снова запрет",
    inFunction("assign_auditor", "    INSERT INTO bem_core.audit_assignment\n",
               "    IF v_subject.scope = 'BEM954_PROTOCOL' AND EXISTS (SELECT 1 FROM bem_core.subject_author sa\n"
               + "        JOIN bem_core.actor a ON a.actor_id = sa.actor_id\n"
               + "        WHERE sa.subject_id = p_subject_id AND a.provider = v_provider) THEN\n"
               + "        RAISE EXCEPTION 'BEM954_SAME_PROVIDER_AUDITOR: %', p_auditor;\n"
               + "    END IF;\n\n    INSERT INTO bem_core.audit_assignment\n")),
  L("A77: в assign_auditor снят отказ автору", "K-R46-02",
    "bem954_assign_problems: assign_auditor: нет проверки",
    inFunction("assign_auditor", "        RAISE EXCEPTION 'SELF_AUDIT_FORBIDDEN: %', p_auditor;\n", "        NULL;\n")),
];

// --- Строки реестра для случаев, перенесённых из прошлых раундов ---------
// Десять строк раздела 15.9 называют подделку поимённо, и эти случаи
// привязаны к ним. Остальные перенесённые случаи привязаны к строке
// K-R12-08 — «прогон набора целиком»: она и говорит про набор как целое,
// а не про отдельную подделку. Это привязка, а не догадка о прошлом.
const LEGACY_ROW = 'K-R12-08';
const legacyRows = {
  'членство рабочей роли во владельце ядра, после маркера': 'K-R12-01',
  'членство рабочей роли во владельце ядра, до маркера': 'K-R12-01',
  'суперпользователь у рабочей роли, после маркера': 'K-R12-02',
  'суперпользователь у рабочей роли, до маркера': 'K-R12-02',
  'обход защиты строк у рабочей роли, после маркера': 'K-R12-03',
  'обход защиты строк у рабочей роли, до маркера': 'K-R12-03',
  'поздний отзыв обязательного чтения, после маркера': 'K-R12-05',
  'поздний отзыв обязательного чтения, до маркера': 'K-R12-05',
  'поздний REVOKE ALL при целом договоре, после маркера': 'K-R12-05',
  'поздний REVOKE ALL при целом договоре, до маркера': 'K-R12-05',
  'поздний отзыв обязательного вызова, после маркера': 'K-R12-06',
  'поздний отзыв обязательного вызова, до маркера': 'K-R12-06',
  'поздняя смена владельца таблицы доказательств': 'K-R12-07',
  'позднее переключение роли': 'K-R12-07',
  'поздние права по умолчанию на запись': 'K-R12-07',
  'позднее переназначение владения': 'K-R12-07',
  'убранный финальный маркер файла 02': 'K-R12-07',
  'выдача, отзыв и снова выдача': 'K-R12-13',
  'объявленный отзыв, которого нет в каноне': 'K-R12-13',
  'снятый второй получатель вызова': 'K-R12-14',
};

const pad = (n) => String(n).padStart(2, '0');
export const cases = [
  ...legacy.map((c, i) => ({ id: 'T28-L' + pad(i + 1), kind: c[0], name: c[1],
                             row: legacyRows[c[1]] || LEGACY_ROW, expect: 1, ...c[2] })),
  ...fresh.map((c, i) => ({ id: 'T28-N' + pad(i + 1), ...c })),
];