// ДОКУМЕНТ: tests/scan.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 13:25 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: SR-02 и SR-08 — сканер ловит поддельный ключ и платный маршрут, не печатая значение;
//   зависимости закреплены точной версией. База не нужна.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { scan } from '../ci/leak_scan.mjs';
import { findSecret } from '../src/guards.mjs';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SCANNER = fileURLToPath(new URL('../ci/leak_scan.mjs', import.meta.url));

test('SR-02 сканер находит поддельные ключ и платный маршрут, значение не печатает', () => {
  const dir = mkdtempSync(join(tmpdir(), 'zavod-scan-'));
  const fake = 'ghp_' + 'Z'.repeat(36);
  writeFileSync(join(dir, 'a.js'), `const t = "${fake}";\n`);
  writeFileSync(join(dir, 'b.yml'), 'env:\n  K: ${{ secrets.OPENAI_API_KEY }}\n');
  writeFileSync(join(dir, 'c.md'), 'clean text\n');
  const hits = scan(dir);
  assert.deepEqual(hits.map((h) => `${h.file}|${h.pattern}`).sort(), ['a.js|github_token', 'b.yml|openai_key_env']);
  const r = spawnSync(process.execPath, [SCANNER, dir], { encoding: 'utf8' });
  assert.equal(r.status, 1);
  assert.ok(!r.stdout.includes(fake), 'value must not be printed');
  assert.match(r.stdout, /LEAK_SCAN=FAIL/);
});

test('SR-02 сам репозиторий Kernel чист', () => {
  const r = spawnSync(process.execPath, [SCANNER, ROOT, '--allow', join(ROOT, 'ci', 'leak_scan_allow.txt')],
    { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stdout);
});

test('findSecret ловит образцы и пропускает обычный текст', () => {
  assert.equal(findSecret({ a: 'hello world', n: 12345 }), null);
  assert.equal(findSecret('-----BEGIN OPENSSH PRIVATE KEY-----'), 'private_key');
  assert.equal(findSecret({ x: '123456789:' + 'a'.repeat(35) }), 'telegram_token');
});

test('SR-08 зависимости закреплены точной версией и есть файл блокировки', () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  for (const [name, ver] of Object.entries({ ...pkg.dependencies, ...pkg.devDependencies })) {
    assert.match(ver, /^\d+\.\d+\.\d+$/, `${name} must be pinned exactly, got ${ver}`);
  }
  const lock = JSON.parse(readFileSync(join(ROOT, 'package-lock.json'), 'utf8'));
  assert.equal(lock.lockfileVersion >= 2, true);
  for (const [p, meta] of Object.entries(lock.packages)) {
    if (p) assert.ok(meta.integrity, `${p} must have integrity hash`);
  }
});
