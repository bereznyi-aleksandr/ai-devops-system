// ДОКУМЕНТ: tests/dead_letter.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 11:10 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 11:10 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: дефект, найденный при проверке E4-6 (не из замечаний аудита): доставщик Kernel падал на строке,
//   исчерпавшей попытки. finish_outbox_row переводит её в DEAD_LETTER и пишет доказательство OUTBOX_DEAD_LETTER,
//   а запись доказательства требует контекст заказчика и участника; у доставщика их не было (NO_TENANT_CONTEXT),
//   итог откатывался, строка оставалась LEASED и снова захватывалась — очередь стояла. Проверки: (1) тупик
//   пишется, доказательство от имени автора команды, проход не падает; (2) сбой итога одной строки (у автора
//   отозвана доверенность) не останавливает проход: другая строка того же прохода завершена.
// ОГРАНИЧЕНИЯ: стенд PG16 с H1.31 + Z-EXT-01. Число попыток строки поднимается ролью postgres — так тест не ждёт
//   выдержек 30 с … 8 мин между попытками; остальное состояние меняют только функции bem_control.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { Kernel } from '../src/kernel.mjs';
import { CONN, bootFixture, withRole, runStopFile, uuid } from './helpers.mjs';

let ids;
let kernel;
const logs = [];
before(async () => {
  ids = await bootFixture();
  kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-dlq-'), log: (o) => logs.push(o) });
  await kernel.assertIdentity();
});
after(async () => { await kernel?.close(); });

const ok = (r) => { assert.equal(r.ok, true, JSON.stringify(r.error)); return r.result; };

async function outboxRow(actor, kind) {
  const wi = uuid();
  const as = { actor_id: actor, role: 'kernel' };
  ok(await kernel.execute(as, { type: 'CreateWorkItem', actor_id: actor, tenant_id: ids.tenantA,
    payload: { work_item_id: wi, evidence: { t: 'dlq' } } }));
  const r = ok(await kernel.execute(as, { type: 'Transition', actor_id: actor, tenant_id: ids.tenantA, command_id: uuid(),
    payload: { work_item_id: wi, expected_revision: 1, new_status: 'PLANNED', evidence: { t: 'dlq' },
      outbox_kind: kind, outbox_payload: { t: kind } } }));
  return r.outbox_id;
}
// Строка на последней попытке: следующий захват — пятая попытка, неудача — тупик.
const lastAttempt = (id) => withRole('postgres', (c) => c.query(
  "UPDATE bem_core.outbox SET attempt_count = bem_control.outbox_retry_limit() - 1, next_attempt_at = now() - interval '1 second' WHERE id = $1",
  [id]));
const rowOf = (id) => withRole('postgres', async (c) => (await c.query(
  'SELECT status, attempt_count, dead_letter_reason FROM bem_core.outbox WHERE id = $1', [id])).rows[0]);
const dlqEvidence = (id) => withRole('postgres', async (c) => (await c.query(
  "SELECT actor_id, payload FROM bem_core.evidence WHERE kind = 'OUTBOX_DEAD_LETTER' AND payload->>'outbox_id' = $1",
  [id])).rows);
// Чужие строки в этом проходе тоже получают FAILED — тест не зависит от остатков очереди.
const failAll = () => kernel.dispatchOnce(async () => ({ outcome: 'FAILED', detail: { t: 'dlq' } }),
  { limit: 500, lease: '30 seconds', worker: 'dlq-worker' });

test('доставщик: строка исчерпала попытки — DEAD_LETTER и доказательство от автора команды, проход не падает', async () => {
  const id = await outboxRow(ids.author, `zavod.dlq.${ids.run}`);
  await lastAttempt(id);
  const d = await failAll();
  const mine = d.results.find((x) => x.outbox_id === id);
  assert.deepEqual(mine, { outbox_id: id, outcome: 'FAILED', finished: true });
  const row = await rowOf(id);
  assert.equal(row.status, 'DEAD_LETTER');
  assert.equal(row.dead_letter_reason, 'RETRY_LIMIT_REACHED');
  const ev = await dlqEvidence(id);
  assert.equal(ev.length, 1, 'exactly one dead-letter evidence');
  assert.equal(ev[0].actor_id, ids.author);
  assert.equal(ev[0].payload.automatic, true);
});

test('доставщик: сбой итога одной строки (доверенность автора отозвана) не останавливает проход', async () => {
  const lost = `claude:dlq-lost-${ids.run}`;
  const delegation = await withRole('bem_bootstrap_admin', async (c) => {
    await c.query('SELECT bem_control.create_actor($1, $2, NULL, NULL)', [lost, 'anthropic']);
    return (await c.query("SELECT bem_control.grant_delegation('bem_kernel_rw', $1, 'dlq test') AS d", [lost])).rows[0].d;
  });
  const bad = await outboxRow(lost, `zavod.dlq.bad.${ids.run}`);
  const good = await outboxRow(ids.author, `zavod.dlq.good.${ids.run}`);
  await lastAttempt(bad);
  await withRole('bem_bootstrap_admin', (c) => c.query('SELECT bem_control.revoke_delegation($1)', [delegation]));
  const before = logs.length;
  const d = await failAll();
  const b = d.results.find((x) => x.outbox_id === bad);
  assert.equal(b.finished, false);
  assert.equal(b.error, 'DISPATCH_FINISH_FAILED');
  assert.equal(b.cause, 'DELEGATION_NOT_GRANTED');
  assert.equal((await rowOf(bad)).status, 'LEASED', 'failed finish rolled back, row keeps its lease');
  assert.deepEqual(await dlqEvidence(bad), []);
  const g = d.results.find((x) => x.outbox_id === good);
  assert.deepEqual(g, { outbox_id: good, outcome: 'FAILED', finished: true }, 'next row of the same pass finished');
  assert.equal((await rowOf(good)).status, 'FAILED');
  assert.ok(logs.slice(before).some((o) => o.ev === 'dispatch_finish_failed' && o.outbox_id === bad));
});
