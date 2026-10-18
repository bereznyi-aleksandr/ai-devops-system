// ДОКУМЕНТ: install/pg_files_check.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 14:27 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 14:27 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.4 §3.2c — сверка файлов PostgreSQL 16.15 (bin, lib, share) со списком сумм
//   install/pg16_15_files.sha256: каждый файл списка есть и его SHA-256 совпадает, лишних файлов в bin/lib/share нет.
//   Любое расхождение — отказ (установщик останавливается). Другие каталоги (pgAdmin, StackBuilder, doc, include)
//   не сверяются и не копируются.
// ЗАПУСК: node install/pg_files_check.mjs <корень с bin,lib,share> <список сумм>  → JSON; код 3 при расхождении.

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
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

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
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
