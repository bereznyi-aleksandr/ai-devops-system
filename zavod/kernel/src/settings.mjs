// ДОКУМЕНТ: src/settings.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-31 17:16 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-31 17:16 +02:00 (v0.1: этап 3.3.2.1 и 3.3.2.4
//   дорожной карты v3.1 — один файл настроек вместо путей в коде, база по сокету Linux по умолчанию)
// ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
// НАЗНАЧЕНИЕ: настройки Завода приходят только из окружения процесса. Окружение заполняет один файл
//   настроек вида KEY=value: на сервере /etc/zavod/zavod.env (systemd EnvironmentFile=, протокол И.7 п. 4),
//   при ручном запуске — node --env-file=<файл>. Здесь: список допустимых ключей, проверка файла настроек
//   (лишний ключ, повтор, ключ-секрет, путь Windows на Linux — отказ) и подключение к базе.
// ОГРАНИЧЕНИЯ: секретов в файле настроек нет и быть не может: ключи служб лежат в /etc/zavod/secrets/<служба>/
//   (И.7 п. 4); ключ с PASSWORD, TOKEN, SECRET или KEY в имени — отказ.

import { readFileSync } from 'node:fs';
import { isAbsolute } from 'node:path';

export class SettingsError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

// Ключ -> вид значения: 'path' — абсолютный путь, 'port' — число 1..65535, 'int' — целое > 0, 'text' — строка.
export const SETTINGS_KEYS = Object.freeze({
  PGHOST: 'pghost', PGPORT: 'port', PGDATABASE: 'text', PGUSER: 'text',
  KERNEL_STOP_FILE: 'path', KERNEL_HEALTH_PORT: 'port', KERNEL_DISPATCH_MS: 'int',
  ZAVOD_RUNTIME_DIR: 'path', ZAVOD_RUNTIME_INSTANCE: 'text',
  ZAVOD_CGROUP_ROOT: 'path', ZAVOD_JOBHOST: 'path', ZAVOD_CONTAINER_IMAGE: 'text',
  P1_RUN_DIR: 'path', P1_FOREIGN_RUN_DIR: 'path', P1_PRODUCT_CLONE: 'path', P1_PYTHON: 'text', P1_JAVA: 'text',
  P1_FLOWABLE_WAR: 'path', P1_TAG: 'text', P1_ENGINE_PORT: 'port', P1_WORKER_TIMEOUT_MIN: 'int',
});

// Папка сокета PostgreSQL в Ubuntu 24.04 (пакет postgresql-16). Сетевой вход базы на сервере выключен (И.7 п. 3).
export const LINUX_PG_SOCKET_DIR = '/var/run/postgresql';

const SECRET_NAME = /PASSWORD|TOKEN|SECRET|KEY/;
const WINDOWS_PATH = /^[A-Za-z]:[\\/]|\\/;

function checkValue(key, kind, value, platform) {
  if (value === '') throw new SettingsError('SETTING_EMPTY', key);
  if (/[\r\n\0]/.test(value)) throw new SettingsError('SETTING_BAD_VALUE', key);
  const isPath = kind === 'path' || (kind === 'pghost' && (value.startsWith('/') || WINDOWS_PATH.test(value)));
  if (isPath) {
    if (platform !== 'win32' && WINDOWS_PATH.test(value)) throw new SettingsError('SETTING_WINDOWS_PATH', key);
    if (!isAbsolute(value)) throw new SettingsError('SETTING_PATH_NOT_ABSOLUTE', key);
  }
  if (kind === 'port' && !(/^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 65535)) {
    throw new SettingsError('SETTING_BAD_PORT', key);
  }
  if (kind === 'int' && !(/^\d+$/.test(value) && Number(value) > 0)) throw new SettingsError('SETTING_BAD_INT', key);
}

// Разбор файла настроек. Строгий вид: пустые строки и строки с # в начале пропускаются, остальные — KEY=value
// без кавычек и пробелов вокруг «=» (так файл одинаково читают systemd и node --env-file).
export function parseSettings(text, { platform = process.platform } = {}) {
  const out = {};
  text.split('\n').forEach((raw, i) => {
    const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw;
    if (line.trim() === '' || line.trimStart().startsWith('#')) return;
    const m = /^([A-Z][A-Z0-9_]*)=(.*)$/.exec(line);
    if (!m) throw new SettingsError('SETTINGS_BAD_LINE', `line ${i + 1}`);
    const [, key, value] = m;
    if (SECRET_NAME.test(key)) throw new SettingsError('SETTINGS_SECRET_KEY', key);
    if (!Object.hasOwn(SETTINGS_KEYS, key)) throw new SettingsError('SETTINGS_UNKNOWN_KEY', key);
    if (Object.hasOwn(out, key)) throw new SettingsError('SETTINGS_DUPLICATE_KEY', key);
    if (/^["']|["']$|^\s|\s$/.test(value)) throw new SettingsError('SETTING_BAD_VALUE', key);
    checkValue(key, SETTINGS_KEYS[key], value, platform);
    out[key] = value;
  });
  return Object.freeze(out);
}

export function readSettingsFile(path, opts) {
  return parseSettings(readFileSync(path, 'utf8'), opts);
}

// Обязательная настройка: нет — отказ с кодом, без подстановки пути компьютера оператора.
export function requireSetting(key, env = process.env) {
  const v = env[key];
  if (v === undefined || v === '') throw new SettingsError('SETTING_REQUIRED', key);
  return v;
}

// Подключение к базе. Без PGHOST на Linux — сокет (вход peer, И.7 п. 3), на Windows — 127.0.0.1 как раньше,
// пока Завод работает на компьютере оператора (до подписи 3.8).
export function pgConnection(env = process.env, { platform = process.platform, defaultPort = 5432, max } = {}) {
  const host = env.PGHOST || (platform === 'win32' ? '127.0.0.1' : LINUX_PG_SOCKET_DIR);
  const c = { host, port: Number(env.PGPORT || defaultPort), database: env.PGDATABASE || 'bem' };
  if (env.PGUSER) c.user = env.PGUSER;
  if (max !== undefined) c.max = max;
  return c;
}
