// ДОКУМЕНТ: zavod/catalog/P1_telegram_bot/acceptance/selftest/selftest.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:48 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 07:48 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: проверка приёмки P1 и заглушки Bot API. (1) Заглушка: неизвестный токен — 401; JSON,
//   form-urlencoded и multipart разбираются; длинный опрос отдаёт обновление. (2) Плохой бот
//   (selftest/bad_bot.mjs) получает P1_ACCEPTANCE=FAIL: нет меню, токен в ответе, лишний метод.
// ОГРАНИЧЕНИЯ: положительный путь приёмки доказывается первым ботом, написанным рабочими (E5-2):
//   эталонного бота автор брифа не пишет.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { TelegramStub } from '../telegram_stub.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));

test('заглушка Bot API: 401, три вида тела, длинный опрос', async () => {
  const s = new TelegramStub();
  const base = await s.start();
  s.addBot('1:t', 1);
  try {
    assert.equal((await fetch(`${base}/bot9:x/getMe`)).status, 401);
    const j = await (await fetch(`${base}/bot1:t/sendMessage`, { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ chat_id: 5, text: 'привет', reply_markup: { keyboard: [['A']] } }) })).json();
    assert.equal(j.result.text, 'привет');
    await fetch(`${base}/bot1:t/sendMessage`, { method: 'POST', body: new URLSearchParams({ chat_id: '5', text: 'форма',
      reply_markup: JSON.stringify({ inline_keyboard: [[{ text: 'B', callback_data: 'b' }]] }) }) });
    const fd = new FormData();
    fd.append('chat_id', '5');
    fd.append('document', new Blob([Buffer.from('id,name\n1,Иван\n')]), 'applications.csv');
    await fetch(`${base}/bot1:t/sendDocument`, { method: 'POST', body: fd });
    const out = s.outbound('1:t', 5);
    assert.equal(out.length, 3);
    assert.deepEqual(out[1].params.reply_markup.inline_keyboard[0][0], { text: 'B', callback_data: 'b' });
    assert.equal(out[2].params.document.filename, 'applications.csv');
    assert.equal(out[2].params.document.content.toString('utf8'), 'id,name\n1,Иван\n');
    setTimeout(() => s.pushText('1:t', 5, '/start'), 300);
    const t0 = Date.now();
    const u = await (await fetch(`${base}/bot1:t/getUpdates?offset=0&timeout=2`)).json();
    assert.equal(u.result[0].message.text, '/start');
    assert.ok(Date.now() - t0 >= 250, 'long poll waited');
  } finally { await s.close(); }
});

test('плохой бот не проходит приёмку', () => {
  const out = mkdtempSync(join(tmpdir(), 'p1-selftest-'));
  const r = spawnSync(process.execPath, [join(HERE, '..', 'p1_acceptance.mjs'), '--cmd',
    `"${process.execPath}" "${join(HERE, 'bad_bot.mjs')}"`, '--cwd', HERE, '--out', out, '--step-ms', '1500'],
  { encoding: 'utf8', timeout: 180000 });
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stdout, /P1_ACCEPTANCE=FAIL/);
  const res = JSON.parse(readFileSync(join(out, 'p1_acceptance.json'), 'utf8'));
  const failed = new Set(res.checks.filter((c) => !c.ok).map((c) => c.id));
  for (const id of ['A1_menu', 'A3_application_saved', 'A5_export_admin', 'A6_token_not_sent', 'A6_methods_allowlist']) {
    assert.ok(failed.has(id), `${id} must fail`);
  }
  assert.ok(res.checks.find((c) => c.id === 'A0_bot_polls').ok, 'bad bot still polls');
  assert.ok(!JSON.stringify(res).includes(':P1TEST'), 'evidence file holds no token');
  assert.ok(!r.stdout.includes(':P1TEST'), 'output holds no token');
});
