// run_migration.mjs — внешняя обёртка окна мигратора.
// PASSPORT: ACTIVE vR51.1, раунд R51, H1.31.
// AUTHOR: ChatGPT, DEVELOPER R38; Claude, DEVELOPER R42–R51 (РАУНД-R51-ПЕРЕНОС-ИМЁН: H1.31; логика программ в R47–R51 не менялась, последняя правка логики — D1 и D2 проб R46; базовая пара — в build_package, verify_package, chk_round_facts); UPDATED: 2026-10-05.
// SUPERSEDES: версия из H1.30/R50; LIVE_POSTGRESQL_16: PG16_D05=EXECUTED_PASS, пробы R46 — раздел 22.1, пробы движка R47, R49, R50 и R51 — раздел 22.2, остальное — раздел 15.44.
// Запуск: node run_migration.mjs --files 01_database_migration.sql
//         node run_migration.mjs --files 02_upgrade_to_h110.sql,01_database_migration.sql
// Подключение: администратор кластера. Паролей в файле нет — они берутся
// из стандартных средств psql (сертификат, .pgpass, переменные окружения).
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, openSync, writeSync, fsyncSync,
         closeSync, renameSync } from 'node:fs';
import { createHash } from 'node:crypto';

const ADMIN_DB   = process.env.BEM_ADMIN_DB   || 'postgres';
const TARGET_DB  = process.env.BEM_TARGET_DB  || 'bem';
const ADMIN_USER = process.env.BEM_ADMIN_USER || 'postgres';

const MANIFEST_FILE      = 'migration_manifest.json';
const BACKUP_WINDOW_FILE = '04_backup_window.sql';
const FINAL_CHECK_FILE   = '05_final_state_check.sql';

// Сумма описи — единственное число, написанное в обёртке от руки. Опись
// перечисляет суммы всех файлов пакета; сумма самой описи лежит здесь.
// Подменить опись, не тронув обёртку, нельзя. В документе на этом месте
// стоят нули: настоящее значение проставляет шаг нарезки пакета, а пока
// стоят нули, обёртка запускаться отказывается.
const MANIFEST_SHA256 = '41f2f59d4d944f5020ec0e70503de4fc19b20dfb75de74b64ecb86ab446811eb';

const ZEROS = /^0{64}$/;
const HEX64 = /^[0-9a-f]{64}$/;
const sumOf = (buf) => createHash('sha256').update(buf).digest('hex');

// Разбор ключей — ДО открытия окна. H1.8 брал значение по индексу
// «следующий после --files»; без ключа indexOf возвращал -1, и файлом
// становился argv[0] — путь к самому node. Окно при этом уже было
// открыто (лёгкое замечание 2).
const files = (() => {
  const i = process.argv.indexOf('--files');
  if (i < 0 || !process.argv[i + 1]) {
    console.error('USAGE_ERROR: нужен ключ --files со списком файлов через запятую.'
      + ' Пример: node run_migration.mjs --files 02_upgrade_to_h110.sql,01_database_migration.sql');
    process.exit(2);
  }
  const list = process.argv[i + 1].split(',').map((f) => f.trim()).filter(Boolean);
  if (list.length === 0) {
    console.error('USAGE_ERROR: список файлов пуст');
    process.exit(2);
  }
  return list;
})();

// Опись читается и сверяется ДО открытия окна.
const manifest = (() => {
  if (ZEROS.test(MANIFEST_SHA256)) {
    console.error('MANIFEST_ERROR: в обёртке не проставлена сумма описи.'
      + ' Пакет не нарезан — запускать нечего.');
    process.exit(2);
  }
  let raw;
  try { raw = readFileSync(MANIFEST_FILE); }
  catch (e) { console.error('MANIFEST_ERROR: описи нет на диске: ' + MANIFEST_FILE); process.exit(2); }
  const got = sumOf(raw);
  if (got !== MANIFEST_SHA256) {
    console.error('MANIFEST_ERROR: сумма описи не совпала с зашитой в обёртке.'
      + ' обёртка=' + MANIFEST_SHA256 + ' диск=' + got);
    process.exit(2);
  }
  let parsed;
  try { parsed = JSON.parse(raw.toString('utf8')); }
  catch (e) { console.error('MANIFEST_ERROR: опись не читается как JSON'); process.exit(2); }
  const map = parsed && parsed.files;
  if (!map || typeof map !== 'object') {
    console.error('MANIFEST_ERROR: в описи нет раздела files');
    process.exit(2);
  }
  for (const name of Object.keys(map)) {
    if (!HEX64.test(map[name]) || ZEROS.test(map[name])) {
      console.error('MANIFEST_ERROR: сумма файла не проставлена при нарезке пакета: ' + name);
      process.exit(2);
    }
  }
  return parsed;
})();

// Текст файла читается ОДИН раз. Сверяется и исполняется один и тот же
// массив байтов: psql получает его на стандартный вход, а не читает
// файл заново. Между проверкой и запуском окна подмены нет — это прямой
// ответ на раздел 4.1 аудита 75.
function loadChecked(name) {
  const want = manifest.files[name];
  if (!want) {
    console.error('MANIFEST_ERROR: файла нет в описи: ' + name);
    process.exit(2);
  }
  let buf;
  try { buf = readFileSync(name); }
  catch (e) {
    console.error('USAGE_ERROR: файла нет на диске: ' + name);
    process.exit(2);
  }
  const got = sumOf(buf);
  if (got !== want) {
    console.error('MANIFEST_ERROR: сумма файла не совпала с описью: ' + name
      + ' опись=' + want + ' диск=' + got);
    process.exit(2);
  }
  return buf.toString('utf8');
}

const texts        = files.map(loadChecked);
const backupText   = loadChecked(BACKUP_WINDOW_FILE);
const finalText    = loadChecked(FINAL_CHECK_FILE);

function sql(db, user, text) {
  return execFileSync('psql', ['-v', 'ON_ERROR_STOP=1', '-At',
                               '-U', user, '-d', db, '-c', text],
                      { encoding: 'utf8' }).trim();
}

function openWindow() {
  // Членства выдаются ровно на время миграции и ровно три. Роли
  // bem_backup_ctl_owner здесь нет и быть не может: у неё CREATEROLE и
  // право администрировать backup_reader, а значит миграция, получив
  // её, могла бы выдать роли копирования вход и пароль (замечание
  // C-H113-R13-01). Функции окна копирования создаёт файл 04 —
  // администратором и уже после закрытия окна.
  sql(ADMIN_DB, ADMIN_USER, `
    ALTER ROLE schema_migrator LOGIN;
    GRANT bem_core_owner, bem_engine_owner, bem_control_owner
          TO schema_migrator;`);
}

function closeWindow() {
  // 1. Отозвать временные членства.
  // 2. Закрыть вход.
  // 3. Завершить ВСЕ оставшиеся сессии мигратора — NOLOGIN их не трогает.
  // 4. Отдельными запросами убедиться, что их ноль.
  //
  // Ни один шаг не бросает наружу: квитанция пишется ВСЕГДА, даже если
  // закрытие отказало на первом же шаге. H1.8 бросал исключение прямо
  // из finally, и оно подменяло собой исходную ошибку миграции
  // (лёгкое замечание 3).
  const receipt = {
    document: 'migration_window_receipt',
    closed_at_utc: new Date().toISOString(),
    files,
    sessions_left: null,
    memberships_left: null,
    can_login: null,
    close_errors: [],
    window_closed: false,
  };

  const step = (name, fn) => {
    try { return fn(); }
    catch (e) { receipt.close_errors.push(name + ': ' + (e.message || String(e))); return null; }
  };

  step('revoke_and_nologin', () => sql(ADMIN_DB, ADMIN_USER, `
    REVOKE bem_core_owner, bem_engine_owner, bem_control_owner
           FROM schema_migrator;
    ALTER ROLE schema_migrator NOLOGIN;`));

  step('terminate_sessions', () => sql(ADMIN_DB, ADMIN_USER, `
    SELECT pg_terminate_backend(a.pid, 5000)
      FROM pg_stat_activity a JOIN pg_roles r ON r.oid = a.usesysid
     WHERE r.rolname = 'schema_migrator' AND a.pid <> pg_backend_pid();`));

  const left = step('count_sessions', () => sql(ADMIN_DB, ADMIN_USER, `
    SELECT count(*) FROM pg_stat_activity a JOIN pg_roles r ON r.oid = a.usesysid
     WHERE r.rolname = 'schema_migrator';`));

  const members = step('count_memberships', () => sql(ADMIN_DB, ADMIN_USER, `
    SELECT count(*) FROM pg_auth_members m JOIN pg_roles s ON s.oid = m.member
     WHERE s.rolname = 'schema_migrator';`));

  const canLogin = step('read_can_login', () => sql(ADMIN_DB, ADMIN_USER, `
    SELECT rolcanlogin::text FROM pg_roles WHERE rolname = 'schema_migrator';`));

  receipt.sessions_left    = left     === null ? null : Number(left);
  receipt.memberships_left = members  === null ? null : Number(members);
  receipt.can_login        = canLogin === null ? null : canLogin === 't';
  receipt.window_closed    = receipt.close_errors.length === 0
                          && receipt.sessions_left    === 0
                          && receipt.memberships_left === 0
                          && receipt.can_login        === false;

  // Запись квитанции ловит свою ошибку сама. Эта функция зовётся из
  // finally, а исключение из finally затирает исходную ошибку миграции
  // целиком: читатель увидел бы «не удалось записать квитанцию» и не
  // узнал бы, почему остановилась миграция (лёгкое замечание 4).
  // Поэтому обе причины хранятся раздельно и печатаются раздельно.
  receipt.receipt_written     = true;
  receipt.receipt_write_error = null;
  try {
    writeFileSync('migration_window_receipt.json', JSON.stringify(receipt, null, 2));
  } catch (e) {
    receipt.receipt_written     = false;
    receipt.receipt_write_error = e.message || String(e);
    console.error('RECEIPT_NOT_WRITTEN: ' + receipt.receipt_write_error);
  }
  return receipt;
}

function runAs(user, text) {
  // ОДИН сеанс psql и ОДНА транзакция на весь поданный текст.
  // H1.8 запускал каждый файл своим сеансом, и успешный 02 при
  // неуспешном 01 оставлял базу в промежуточной форме — а runtime
  // после этого возвращался в работу (пункт 4.3 задания).
  // Ключ -f - читает команды со стандартного входа: исполняются ровно
  // те байты, которые обёртка прочитала и сверила с описью.
  execFileSync('psql', ['-v', 'ON_ERROR_STOP=1', '--single-transaction',
                        '-U', user, '-d', TARGET_DB, '-f', '-'],
               { input: text, stdio: ['pipe', 'inherit', 'inherit'] });
}

let failure = null;
let receipt  = null;
try {
  openWindow();
  runAs('schema_migrator', texts.join('\n'));
} catch (e) {
  failure = e;                       // ошибку запоминаем, но окно закрываем всё равно
} finally {
  receipt = closeWindow();           // выполняется и после успеха, и после ошибки
}

// Исходная ошибка миграции — главная. Ошибка закрытия окна её не
// подменяет: она прикладывается отдельно и в квитанции, и в выводе
// (лёгкое замечание 3).
if (failure) {
  console.error('MIGRATION_FAILED: ' + (failure.message || String(failure)));
  if (!receipt.window_closed) {
    console.error('WINDOW_NOT_CLOSED (приложено к ошибке миграции): '
                  + JSON.stringify(receipt.close_errors));
  }
  if (!receipt.receipt_written) {
    console.error('RECEIPT_NOT_WRITTEN (приложено к ошибке миграции): '
                  + receipt.receipt_write_error);
  }
  process.exit(1);
}
if (!receipt.window_closed) {
  console.error('WINDOW_NOT_CLOSED: ' + JSON.stringify(receipt));
  process.exit(3);
}
if (!receipt.receipt_written) {
  console.error('RECEIPT_NOT_WRITTEN: ' + receipt.receipt_write_error);
  process.exit(4);
}

// Окно закрыто. Только теперь администратор создаёт четыре функции окна
// копирования: их владелец — роль с CREATEROLE, и мигратор её не видел
// ни одной командой.
const finalReceipt = {
  document: 'migration_final_receipt',
  finished_at_utc: null,
  manifest_sha256: MANIFEST_SHA256,
  files: Object.fromEntries(
    [...files, BACKUP_WINDOW_FILE, FINAL_CHECK_FILE].map((f) => [f, manifest.files[f]])),
  backup_window_applied: false,
  terminal_check_passed: false,
  error: null,
};
const RECEIPT_FILE = 'migration_final_receipt.json';
const RECEIPT_FIELDS = ['document', 'finished_at_utc', 'manifest_sha256', 'files',
                        'backup_window_applied', 'terminal_check_passed', 'error'];

// Запись квитанции целиком: временный файл, сброс на диск, переименование
// одним действием, перечитывание, сверка текста, обязательных полей и
// суммы. Любая осечка — исключение, а не сообщение: успех без квитанции
// неотличим от незавершённой операции (замечание M-H114-R14-05).
const writeFinal = () => {
  finalReceipt.finished_at_utc = new Date().toISOString();
  const text = JSON.stringify(finalReceipt, null, 2);
  const tmp  = RECEIPT_FILE + '.tmp';
  const fd = openSync(tmp, 'w');
  try { writeSync(fd, text); fsyncSync(fd); } finally { closeSync(fd); }
  renameSync(tmp, RECEIPT_FILE);
  const back = readFileSync(RECEIPT_FILE, 'utf8');
  if (back !== text) {
    throw new Error('перечитанная квитанция не совпала с записанной');
  }
  const parsed = JSON.parse(back);
  for (const f of RECEIPT_FIELDS) {
    if (!(f in parsed)) throw new Error('в квитанции нет обязательного поля ' + f);
  }
  const sha = sumOf(Buffer.from(text, 'utf8'));
  if (sha !== sumOf(readFileSync(RECEIPT_FILE))) {
    throw new Error('сумма квитанции на диске не совпала с записанной');
  }
  return sha;
};

// На путях отказа код возврата уже ненулевой, и осечка записи его не
// меняет. Но видна она обязана быть, поэтому здесь отдельная обёртка.
const writeFinalQuiet = () => {
  try { return writeFinal(); }
  catch (e) {
    console.error('FINAL_RECEIPT_NOT_WRITTEN: ' + (e.message || String(e)));
    return null;
  }
};

try {
  runAs(ADMIN_USER, backupText);
  finalReceipt.backup_window_applied = true;
} catch (e) {
  finalReceipt.error = 'backup_window: ' + (e.message || String(e));
  writeFinalQuiet();
  console.error('BACKUP_WINDOW_FILE_FAILED: ' + finalReceipt.error);
  process.exit(5);
}

// Терминальная административная проверка. Она читает итоговое состояние
// кластера целиком и отказывает, если хоть одна строка разошлась с
// объявленным договором. Успех обёртки объявляется только после неё.
try {
  runAs(ADMIN_USER, finalText);
  finalReceipt.terminal_check_passed = true;
} catch (e) {
  finalReceipt.error = 'terminal_check: ' + (e.message || String(e));
  writeFinalQuiet();
  console.error('TERMINAL_CHECK_FAILED: ' + finalReceipt.error);
  process.exit(6);
}

// Успешный путь. Квитанция обязательна: без неё выхода с кодом 0 нет
// (замечание M-H114-R14-05). Признак терминальной проверки проверяется
// отдельно и последним: он поднимается только строкой сразу за удачным
// вызовом проверки, и никакой другой строки, ставящей его в true, в этом
// файле нет (замечание M-H114-R14-04).
let finalSha = null;
try {
  finalSha = writeFinal();
} catch (e) {
  console.error('FINAL_RECEIPT_NOT_WRITTEN: ' + (e.message || String(e)));
  process.exit(7);
}
if (finalReceipt.terminal_check_passed !== true) {
  console.error('TERMINAL_CHECK_NOT_PASSED: успех без терминальной проверки невозможен');
  process.exit(8);
}
console.log('MIGRATION_OK: ' + RECEIPT_FILE + ' sha256=' + finalSha);
process.exit(0);
