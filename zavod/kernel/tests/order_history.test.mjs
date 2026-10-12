// ДОКУМЕНТ: tests/order_history.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:50 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 07:50 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: E5-1 (W1) — проверка истории заказа: заявка от человека допустима, любой следующий переход
//   от человека — ручной перенос (MANUAL_RELAY); чужая строка и пустая история — отказ; сумма выгрузки
//   не зависит от порядка строк на входе и меняется при подмене автора.
// ОГРАНИЧЕНИЯ: без базы; на живом заказе проверка идёт в engine/ci/e43_training_order.mjs.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { checkOrderHistory } from '../src/order_history.mjs';

const W = randomUUID();
const row = (i, actor) => ({ command_id: randomUUID(), work_item_id: W, actor_id: actor, result_revision: i + 2,
  kind: null, created_at: new Date(Date.UTC(2026, 9, 9, 5, 0, i)).toISOString() });
const history = () => [row(0, 'human:operator'), row(1, 'claude:director'), row(2, 'claude:director'),
  row(3, 'codex:worker'), row(4, 'claude:director')];

test('E5-1 заявка от человека, дальше только роли Завода — PASS', () => {
  const r = checkOrderHistory(history(), W);
  assert.deepEqual(r.problems, []);
  assert.equal(r.ok, true);
  assert.match(r.sha256, /^[0-9a-f]{64}$/);
});

test('E5-1 переход от человека после заявки — MANUAL_RELAY', () => {
  for (const i of [1, 2, 4]) {
    const h = history(); h[i].actor_id = 'human:operator';
    const r = checkOrderHistory(h, W);
    assert.equal(r.ok, false);
    assert.equal(r.problems.length, 1);
    assert.match(r.problems[0], /^MANUAL_RELAY /);
  }
});

test('E5-1 чужая строка и пустая история — отказ', () => {
  const h = history(); h[3].work_item_id = randomUUID();
  assert.match(checkOrderHistory(h, W).problems[0], /^FOREIGN_ROW /);
  assert.deepEqual(checkOrderHistory([], W).problems, ['EMPTY_HISTORY']);
});

test('E5-1 сумма выгрузки: порядок входа не важен, подмена автора меняет сумму', () => {
  const h = history();
  const a = checkOrderHistory(h, W).sha256;
  assert.equal(checkOrderHistory([...h].reverse(), W).sha256, a);
  h[2].actor_id = 'codex:worker';
  assert.notEqual(checkOrderHistory(h, W).sha256, a);
});
