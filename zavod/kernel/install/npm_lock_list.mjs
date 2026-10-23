// ДОКУМЕНТ: install/npm_lock_list.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 15:50 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 15:50 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 §3 — список пакетов из package-lock.json для шага npm установщика.
//   PowerShell 5.1 не читает этот файл (ConvertFrom-Json отказывает на пустом имени ключа корневого пакета — CI 18.10),
//   поэтому разбор делает node. Каждый пакет: путь только node_modules/…, адрес только https://registry.npmjs.org/….tgz,
//   integrity только sha512. Любое отклонение — отказ всего списка.
// ЗАПУСК: node install/npm_lock_list.mjs <package-lock.json>  → строки «путь<TAB>адрес<TAB>sha512 base64»; код 3 при отказе.

import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const NAME = /^node_modules\/(?:@[a-z0-9][a-z0-9._-]*\/)?[a-z0-9][a-z0-9._-]*(?:\/node_modules\/(?:@[a-z0-9][a-z0-9._-]*\/)?[a-z0-9][a-z0-9._-]*)*$/;
const URL_RE = /^https:\/\/registry\.npmjs\.org\/[A-Za-z0-9@%._\/-]+\.tgz$/;
const SRI = /^sha512-([A-Za-z0-9+/]{86}==)$/;

export function lockList(text) {
  const lock = JSON.parse(text);
  if (lock.lockfileVersion !== 3 || !lock.packages || typeof lock.packages !== 'object') throw new Error('NPM_LOCK_FORMAT');
  const rows = [];
  for (const [name, pkg] of Object.entries(lock.packages)) {
    if (name === '') continue;
    if (!NAME.test(name) || name.split('/').includes('..')) throw new Error(`NPM_NAME ${name.slice(0, 80)}`);
    if (pkg.link || typeof pkg.resolved !== 'string' || !URL_RE.test(pkg.resolved) || pkg.resolved.includes('..')) throw new Error(`NPM_RESOLVED ${name}`);
    const m = SRI.exec(pkg.integrity || '');
    if (!m) throw new Error(`NPM_INTEGRITY ${name}`);
    rows.push([name, pkg.resolved, m[1]]);
  }
  if (!rows.length) throw new Error('NPM_LOCK_EMPTY');
  return rows;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  try {
    process.stdout.write(lockList(readFileSync(process.argv[2] || '', 'utf8')).map((r) => r.join('\t')).join('\n') + '\n');
  } catch (e) {
    process.stdout.write(`NPM_LOCK_FAILED ${String(e.message).slice(0, 120)}\n`);
    process.exit(3);
  }
}
