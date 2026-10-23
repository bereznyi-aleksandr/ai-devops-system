// ДОКУМЕНТ: install/pg_files_check.mjs
// ВЕРСИЯ: v0.3  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 14:27 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 15:21 +03:00
// ИСПОЛНИТЕЛЬ: Claude (v0.1 сессия fd43469f; v0.2–v0.3 сессия 9951b86f)
// v0.3: режим --copy-listed — из дерева установщика копируются ровно файлы списка (сумма каждого сверяется до
//   копирования), лишнее (StackBuilder, расширение system_stats: CI 18.10, установщик 16.15-5 — 191 лишний файл в share,
//   1635 файлов совпали) не копируется и только считается; копия затем сверяется строго. v0.2: режим --make.
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.5 §3.2c — сверка файлов PostgreSQL 16.15 (bin, lib, share) со списком сумм
//   install/pg16_15_files.sha256 (архив binaries 16.15-5): каждый файл списка есть и его SHA-256 совпадает, лишних
//   файлов в bin/lib/share нет. Любое расхождение — отказ (установщик останавливается).
// ЗАПУСК: node install/pg_files_check.mjs <корень с bin,lib,share> <список сумм>  → JSON; код 3 при расхождении.
//   node install/pg_files_check.mjs --make <корень> [файл]  → список сумм bin/lib/share (строки «сумма␠␠путь», по пути,
//   конец строки LF) в новый файл (существующий не перезаписывается) или в stdout.
//   node install/pg_files_check.mjs --copy-listed <откуда> <список> <куда (нет или пуст)>  → JSON; код 3 при отказе.

import { readFileSync, readdirSync, statSync, existsSync, writeFileSync, mkdirSync, copyFileSync, constants } from 'node:fs';
import { createHash } from 'node:crypto';
import { join, relative, sep, dirname } from 'node:path';
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

// copyListed — копия ровно файлов списка: у источника каждый файл есть и его сумма совпадает (иначе отказ до копирования
// чего-либо); назначение должно отсутствовать или быть пустым; копия сверяется строго (лишних нет). Лишнее источника — счёт.
export function copyListed(src, listText, dst) {
  const want = parseList(listText);
  const pre = verifyTree(src, listText);
  if (pre.missing.length || pre.mismatch.length || pre.checked !== want.size) {
    return { ok: false, stage: 'source', missing: pre.missing, mismatch: pre.mismatch, extra_ignored: pre.extra.length };
  }
  if (existsSync(dst) && readdirSync(dst).length) return { ok: false, stage: 'destination_not_empty' };
  for (const rel of want.keys()) {
    const to = join(dst, ...rel.split('/'));
    mkdirSync(dirname(to), { recursive: true });
    copyFileSync(join(src, ...rel.split('/')), to, constants.COPYFILE_EXCL);
  }
  const post = verifyTree(dst, listText);
  return { ok: post.ok, stage: 'copy', copied: want.size, extra_ignored: pre.extra.length, post_mismatch: post.mismatch.length, post_extra: post.extra.length };
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url && process.argv[2] === '--copy-listed') {
  try {
    const r = copyListed(process.argv[3] || '', readFileSync(process.argv[4] || '', 'utf8'), process.argv[5] || '');
    const cut = (a) => (Array.isArray(a) ? a.slice(0, 20) : a);
    process.stdout.write(`${JSON.stringify({ ...r, missing: cut(r.missing), mismatch: cut(r.mismatch) })}\n`);
    if (!r.ok) process.exit(3);
  } catch (e) {
    process.stdout.write(`${JSON.stringify({ ok: false, code: String(e.message).slice(0, 80) })}\n`);
    process.exit(3);
  }
} else if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url && process.argv[2] === '--make') {
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
