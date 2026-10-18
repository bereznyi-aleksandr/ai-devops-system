// ДОКУМЕНТ: install/pg_files_check.mjs
// ВЕРСИЯ: v0.2  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 14:27 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 15:08 +03:00
// ИСПОЛНИТЕЛЬ: Claude (v0.1 сессия fd43469f; v0.2 сессия 9951b86f)
// v0.2: режим --make (список сумм из дерева, по пути) — эталон списка снимается в CI с подписанного установщика EDB:
//   CI 18.10 показал, что установщик 16.15-1 и архив binaries 16.15-5 — разные сборки (183 файла различаются).
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.4 §3.2c — сверка файлов PostgreSQL 16.15 (bin, lib, share) со списком сумм
//   (install/pg16_15_1_installer_files.sha256 — из установщика 16.15-1): каждый файл списка есть и его SHA-256 совпадает, лишних файлов в bin/lib/share нет.
//   Любое расхождение — отказ (установщик останавливается). Другие каталоги (pgAdmin, StackBuilder, doc, include)
//   не сверяются и не копируются.
// ЗАПУСК: node install/pg_files_check.mjs <корень с bin,lib,share> <список сумм>  → JSON; код 3 при расхождении.
//   node install/pg_files_check.mjs --make <корень> [файл]  → список сумм bin/lib/share (строки «сумма␠␠путь», по пути,
//   конец строки LF) в новый файл (существующий не перезаписывается) или в stdout.

import { readFileSync, readdirSync, statSync, existsSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join, relative, sep } from 'node:path';
import { pathToFileURL } from 'node:url';

export const PG_DIRS = Object.freeze(['bin', 'lib', 'share']);

export function parseList(text) {
  const m = new Map();
  for (const line of text.split(/\r?\n/)) {
    if (!line) continue;
    const r = /^([0-9a-f]{64}) {2}((?:bin|lib|share)\/[^\\]+)$/.exec(line);
    if (!r || r[2].split('/').includes('..') || m.has(r[2])) throw new Error('PG_LIST_BAD_LINE');
    m.set(r[2], r[1]);
  }
  if (!m.size) throw new Error('PG_LIST_EMPTY');
  return m;
}

function walk(dir, out) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

export function verifyTree(root, listText) {
  const want = parseList(listText);
  const res = { checked: 0, missing: [], mismatch: [], extra: [] };
  for (const [rel, sum] of want) {
    const p = join(root, ...rel.split('/'));
    if (!existsSync(p) || !statSync(p).isFile()) { res.missing.push(rel); continue; }
    res.checked += 1;
    if (createHash('sha256').update(readFileSync(p)).digest('hex') !== sum) res.mismatch.push(rel);
  }
  for (const d of PG_DIRS) {
    if (!existsSync(join(root, d))) continue;
    for (const p of walk(join(root, d), [])) {
      const rel = relative(root, p).split(sep).join('/');
      if (!want.has(rel)) res.extra.push(rel);
    }
  }
  res.ok = res.missing.length === 0 && res.mismatch.length === 0 && res.extra.length === 0 && res.checked === want.size;
  return res;
}

// makeList — список в формате parseList: каждый файл bin/lib/share, сортировка по пути.
export function makeList(root) {
  const rows = [];
  for (const d of PG_DIRS) {
    if (!existsSync(join(root, d))) throw new Error(`PG_DIR_MISSING ${d}`);
    for (const p of walk(join(root, d), [])) rows.push([relative(root, p).split(sep).join('/'), createHash('sha256').update(readFileSync(p)).digest('hex')]);
  }
  rows.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  const text = rows.map(([rel, sum]) => `${sum}  ${rel}`).join('\n') + '\n';
  parseList(text);
  return text;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url && process.argv[2] === '--make') {
  const text = makeList(process.argv[3] || '');
  if (process.argv[4]) writeFileSync(process.argv[4], text, { flag: 'wx' }); else process.stdout.write(text);
} else if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  try {
    const r = verifyTree(process.argv[2] || '', readFileSync(process.argv[3] || '', 'utf8'));
    const cut = (a) => a.slice(0, 20);
    process.stdout.write(`${JSON.stringify({ ok: r.ok, checked: r.checked, missing: cut(r.missing), mismatch: cut(r.mismatch), extra: cut(r.extra),
      counts: { missing: r.missing.length, mismatch: r.mismatch.length, extra: r.extra.length } })}\n`);
    if (!r.ok) process.exit(3);
  } catch (e) {
    process.stdout.write(`${JSON.stringify({ ok: false, code: String(e.message).slice(0, 80) })}\n`);
    process.exit(3);
  }
}
