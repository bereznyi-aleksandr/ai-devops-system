// ДОКУМЕНТ: zavod/catalog/ci/product_scan.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 13:25 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: проверка сканера E5-6. Чистый продукт — PASS; каждая посадка (ключ бота, ключ модели в коде,
//   адрес платного API, платный SDK в package.json и requirements.txt, файл .env) — FAIL с верным образцом;
//   пустая и несуществующая папка — FAIL; значение ключа не попадает ни в вывод, ни в отчёт.
// ОГРАНИЧЕНИЯ: поддельные ключи собираются во время прогона (в файлах репозитория их нет, SR-02 Kernel
//   их не видит). Папки продуктов — во временной папке ОС; удаление по заметке P4.718, все четыре условия
//   проверены: (1) создаёт сам тест в tmpdir(), вне CANONICAL_ROOT и RUNTIME_ROOT; (2) создаётся и
//   убирается в одном вызове withProduct; (3) итог — в выводе node --test, не в папке; (4) внутри только
//   поддельные файлы теста, данных пользователя и чужих доказательств нет.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { scanProduct } from './product_scan.mjs';

const SCANNER = join(dirname(fileURLToPath(import.meta.url)), 'product_scan.mjs');
const FAKE_BOT = ['1234567890', 'AAF' + 'x'.repeat(32)].join(':');
const FAKE_MODEL = 'sk-' + 'ant-' + 'Q'.repeat(30);
const PAID_HOST = ['api', 'openai', 'com'].join('.');

const CLEAN = {
  'package.json': JSON.stringify({ name: 'p1-bot', dependencies: { grammy: '1.30.0' } }),
  'src/bot.mjs': "const token = process.env.BOT_TOKEN;\nexport const menu = ['/start', '/help'];\n",
  '.env.example': 'BOT_TOKEN=\n',
  'README.md': '# P1 bot\n',
};

function withProduct(files, fn) {
  const dir = mkdtempSync(join(tmpdir(), 'zavod-pscan-'));
  try {
    for (const [p, body] of Object.entries(files)) {
      mkdirSync(dirname(join(dir, p)), { recursive: true });
      writeFileSync(join(dir, p), body);
    }
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const patterns = (dir) => scanProduct(dir).findings.map((f) => f.pattern);

test('чистый продукт — PASS, отчёт с head_sha и числом файлов', () => withProduct(CLEAN, (dir) => {
  const out = join(dir, '..', `pscan-${process.pid}.json`);
  try {
    const r = spawnSync(process.execPath, [SCANNER, dir, '--head-sha', 'a'.repeat(40), '--out', out], { encoding: 'utf8' });
    assert.equal(r.status, 0, r.stdout);
    assert.match(r.stdout, /PRODUCT_SCAN=PASS files=4 findings=0 report_sha256=[0-9a-f]{64}/);
    const rep = JSON.parse(readFileSync(out, 'utf8'));
    assert.equal(rep.result, 'PASS');
    assert.equal(rep.head_sha, 'a'.repeat(40));
    assert.equal(rep.criterion, 'E5-6');
  } finally { rmSync(out, { force: true }); }
}));

const PLANTS = [
  ['ключ бота в коде', { 'src/cfg.mjs': `export const t = '${FAKE_BOT}';\n` }, 'telegram_token'],
  ['ключ модели в коде', { 'src/ai.mjs': `const k = '${FAKE_MODEL}';\n` }, 'anthropic_key'],
  ['адрес платного API', { 'src/ai.mjs': `fetch('https://${PAID_HOST}/v1/chat')\n` }, 'openai_api_host'],
  ['платный SDK в package.json', { 'package.json': JSON.stringify({ dependencies: { grammy: '1', openai: '4' } }) }, 'paid_sdk_npm:openai'],
  ['платный SDK в devDependencies', { 'package.json': JSON.stringify({ devDependencies: { '@anthropic-ai/sdk': '1' } }) }, 'paid_sdk_npm:@anthropic-ai/sdk'],
  ['платный SDK в requirements.txt', { 'requirements.txt': 'aiogram==3.4\nAnthropic>=0.30  # model\n' }, 'paid_sdk_py:anthropic'],
  ['файл .env в репозитории', { '.env': 'BOT_TOKEN=\n' }, 'env_file_committed'],
  ['битый package.json', { 'package.json': '{ not json' }, 'package_json_unreadable'],
];

for (const [name, plant, want] of PLANTS) {
  test(`посадка «${name}» — FAIL (${want})`, () => withProduct({ ...CLEAN, ...plant }, (dir) => {
    assert.ok(patterns(dir).includes(want), JSON.stringify(patterns(dir)));
  }));
}

test('пустая и несуществующая папка — FAIL, а не «чисто»', () => {
  withProduct({}, (dir) => assert.deepEqual(patterns(dir), ['no_files']));
  assert.deepEqual(patterns(join(tmpdir(), `zavod-pscan-none-${process.pid}-x`)), ['root_missing']);
});

test('значение ключа не попадает ни в вывод, ни в отчёт', () => withProduct({ ...CLEAN, 'src/cfg.mjs': `x='${FAKE_BOT}'\n` }, (dir) => {
  const out = join(dir, '..', `pscan-leak-${process.pid}.json`);
  try {
    const r = spawnSync(process.execPath, [SCANNER, dir, '--head-sha', 'b'.repeat(40), '--out', out], { encoding: 'utf8' });
    assert.equal(r.status, 1);
    assert.match(r.stdout, /KEY telegram_token src\/cfg\.mjs:1/);
    assert.ok(!r.stdout.includes(FAKE_BOT.split(':')[1]));
    assert.ok(!readFileSync(out, 'utf8').includes(FAKE_BOT.split(':')[1]));
  } finally { rmSync(out, { force: true }); }
}));

test('неверный вызов — код 2', () => {
  const r = spawnSync(process.execPath, [SCANNER, '.', '--head-sha', 'short', '--out', 'x.json'], { encoding: 'utf8' });
  assert.equal(r.status, 2);
});
