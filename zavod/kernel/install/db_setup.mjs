// ДОКУМЕНТ: install/db_setup.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 14:11 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 14:11 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.4 §4.C — база ядра: initdb (суперпользователь zavod_dba, входы
//   host/local закрыты), TLS 1.3 со своим CA, только 127.0.0.1, pg_hba — только hostssl … cert clientcert=verify-full
//   для bem_kernel_rw, bem_rules_gate (база bem) и zavod_dba; схема H1.31 + Z-EXT-01..03 и итоговая проверка той же
//   цепочкой, что ci/kernel_ci.sh (без проб подмены). MODE не трогается.
// ЗАПУСК: node install/db_setup.mjs <init|config|schema> <файл настроек JSON>
//   init — initdb в пустой data; config — сертификаты, postgresql.conf, pg_hba.conf; schema — установка схемы
//   на запущенном кластере (запускает установщик: служба Windows или pg_ctl в репетиции).
// ОГРАНИЧЕНИЯ: паролей нет — вход только сертификатом. Ключи в журнал не пишутся.

import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, appendFileSync, copyFileSync, existsSync, readdirSync } from 'node:fs';
import { join, isAbsolute } from 'node:path';
import { pathToFileURL } from 'node:url';

export const HBA_ROLES = Object.freeze([['bem', 'bem_kernel_rw'], ['bem', 'bem_rules_gate'], ['all', 'zavod_dba']]);

// migration=true — временная строка окна миграции H1.31: run_migration.mjs входит ролью schema_migrator,
// а окружение libpq одно на процесс, поэтому сертификат zavod_dba на время окна сопоставлен роли schema_migrator
// картой pg_ident (zavod_migr). После окна строка и карта убираются, это сверяется по pg_hba_file_rules.
export function hbaText({ migration = false } = {}) {
  return ['# Завод: только TLS, только 127.0.0.1, только клиентский сертификат своего CA (CN = имя роли).',
    '# TYPE  DATABASE  USER  ADDRESS  METHOD',
    ...HBA_ROLES.map(([db, u]) => `hostssl ${db} ${u} 127.0.0.1/32 cert clientcert=verify-full`),
    ...(migration ? ['hostssl bem schema_migrator 127.0.0.1/32 cert clientcert=verify-full map=zavod_migr'] : []), ''].join('\n');
}

export function identText({ migration = false } = {}) {
  return ['# Завод: карта имён сертификатов. Пуста вне окна миграции.', '# MAPNAME  SYSTEM-USERNAME  PG-USERNAME',
    ...(migration ? ['zavod_migr  zavod_dba  schema_migrator'] : []), ''].join('\n');
}

export function confText(port) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('DB_PORT_INVALID');
  return ['', '# --- Завод (install/db_setup.mjs) ---', "listen_addresses = '127.0.0.1'", `port = ${port}`, 'ssl = on',
    "ssl_cert_file = 'server.crt.pem'", "ssl_key_file = 'server.key.pem'", "ssl_ca_file = 'ca.crt.pem'",
    "ssl_min_protocol_version = 'TLSv1.3'", "password_encryption = 'scram-sha-256'", 'logging_collector = on',
    "log_directory = 'log'", 'log_connections = on', 'log_disconnections = on', ''].join('\n');
}

function readCfg(path) {
  const c = JSON.parse(readFileSync(path, 'utf8'));
  for (const k of ['pgBin', 'data', 'certs', 'pkg', 'kernelDir']) if (typeof c[k] !== 'string' || !isAbsolute(c[k])) throw new Error(`DB_CFG_${k}`);
  if (!Number.isInteger(c.port)) throw new Error('DB_CFG_port');
  return c;
}

const bin = (c, t) => join(c.pgBin, `${t}.exe`);

export function init(c) {
  if (existsSync(c.data) && readdirSync(c.data).length) throw new Error('DB_DATA_NOT_EMPTY');
  execFileSync(bin(c, 'initdb'), ['-D', c.data, '-U', 'zavod_dba', '--auth-host=reject', '--auth-local=reject',
    '-E', 'UTF8', '--locale=C'], { stdio: ['ignore', 'ignore', 'inherit'], windowsHide: true });
}

export function config(c) {
  for (const f of ['server.crt.pem', 'server.key.pem', 'ca.crt.pem']) copyFileSync(join(c.certs, f), join(c.data, f));
  appendFileSync(join(c.data, 'postgresql.conf'), confText(c.port));
  writeFileSync(join(c.data, 'pg_hba.conf'), hbaText());
  writeFileSync(join(c.data, 'pg_ident.conf'), identText());
}

function setWindow(c, psqlC, migration) {
  writeFileSync(join(c.data, 'pg_hba.conf'), hbaText({ migration }));
  writeFileSync(join(c.data, 'pg_ident.conf'), identText({ migration }));
  psqlC('postgres', 'SELECT pg_reload_conf()');
  const n = Number(psqlC('postgres', "SELECT count(*) FROM pg_hba_file_rules WHERE 'schema_migrator' = ANY(user_name) OR error IS NOT NULL"));
  if (n !== (migration ? 1 : 0)) throw new Error(`DB_HBA_WINDOW_${migration ? 'OPEN' : 'CLOSE'}_FAILED`);
}

// Окружение libpq для psql и run_migration.mjs: вход zavod_dba сертификатом, сервер — verify-full.
export function dbaEnv(c) {
  const keep = ['SystemRoot', 'TEMP', 'TMP', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'];
  const env = Object.fromEntries(keep.filter((k) => process.env[k]).map((k) => [k, process.env[k]]));
  return { ...env, PATH: `${c.pgBin};${process.env.SystemRoot || 'C:\\Windows'}\\System32`, PGHOST: '127.0.0.1',
    PGPORT: String(c.port), PGUSER: 'zavod_dba', PGSSLMODE: 'verify-full', PGSSLROOTCERT: join(c.certs, 'ca.crt.pem'),
    PGSSLCERT: join(c.certs, 'zavod_dba.crt.pem'), PGSSLKEY: join(c.certs, 'zavod_dba.key.pem'), BEM_ADMIN_USER: 'zavod_dba', PGCLIENTENCODING: 'UTF8',
    PGCONNECT_TIMEOUT: '10' };
}

export function schema(c, log = (s) => process.stdout.write(`${s}\n`)) {
  const env = dbaEnv(c);
  const psql = (db, file, single = true) => execFileSync(bin(c, 'psql'), ['-v', 'ON_ERROR_STOP=1', ...(single ? ['--single-transaction'] : []),
    '-U', 'zavod_dba', '-d', db, '-f', file], { env, cwd: c.pkg, stdio: ['ignore', 'ignore', 'inherit'], windowsHide: true });
  const psqlC = (db, sqlText) => execFileSync(bin(c, 'psql'), ['-v', 'ON_ERROR_STOP=1', '-At', '-U', 'zavod_dba', '-d', db, '-c', sqlText],
    { env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'], windowsHide: true }).trim();
  const K = c.kernelDir;
  psql('postgres', join(c.pkg, '00_cluster_bootstrap.sql'), false);
  log('00 ok');
  setWindow(c, psqlC, true);
  try {
    execFileSync(process.execPath, ['run_migration.mjs', '--files', '01_database_migration.sql'],
      { env, cwd: c.pkg, stdio: ['ignore', 'ignore', 'inherit'], windowsHide: true });
  } finally {
    setWindow(c, psqlC, false);
  }
  log('01 ok');
  execFileSync(process.execPath, [join(K, 'db', 'build_ext.mjs'), '01_database_migration.sql', '--check'], { env, cwd: c.pkg, stdio: ['ignore', 'ignore', 'inherit'], windowsHide: true });
  psql('bem', join(K, 'db', '02_zavod_ext_01.sql'), false);
  psql('bem', join(K, 'db', '03_zavod_ext_02.sql'));
  psql('bem', join(K, 'db', '04_zavod_ext_03.sql'));
  execFileSync(process.execPath, [join(K, 'db', 'build_final_ext.mjs'), '05_final_state_check.sql', '--check'], { env, cwd: c.pkg, stdio: ['ignore', 'ignore', 'inherit'], windowsHide: true });
  psql('bem', join(K, 'db', '05_final_state_check_ext01.sql'));
  log('ext 01..03 + final check ok');
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const [step, cfgPath] = process.argv.slice(2);
  try {
    const c = readCfg(cfgPath || '');
    if (step === 'init') init(c);
    else if (step === 'config') config(c);
    else if (step === 'schema') schema(c);
    else throw new Error('DB_STEP_UNKNOWN');
    process.stdout.write(`${JSON.stringify({ ok: true, step })}\n`);
  } catch (e) {
    process.stdout.write(`${JSON.stringify({ ok: false, step, code: String(e.message).split('\n')[0].slice(0, 120) })}\n`);
    process.exit(3);
  }
}
