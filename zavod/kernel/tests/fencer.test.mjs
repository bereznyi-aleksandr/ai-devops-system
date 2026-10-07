// ДОКУМЕНТ: tests/fencer.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 17:55 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 17:55 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: аудит Z4 M-Z4-01, сценарий E4-8 на настоящем процессе. Исполнитель ставит отметку
//   начала отправки и замирает перед адаптером; аренда истекает → UNKNOWN_OUTCOME; сверка без
//   ограждения — отказ; «доказательство есть, среда жива» — отказ без записи в базу; надзиратель
//   завершает экземпляр, видит выход и только тогда пишет ограждение; команда GO мёртвому
//   исполнителю эффекта не даёт; новая попытка отправляет — итог ровно один внешний эффект.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Kernel } from '../src/kernel.mjs';
import { SendSupervisor, pidAlive } from '../src/fencer.mjs';
import { CONN, bootFixture, withRole, uuid } from './helpers.mjs';

let ids;
let kernel;
let sup;
let dir;
const as = (actor) => ({ actor_id: actor });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CHILD = fileURLToPath(new URL('./paused_sender.mjs', import.meta.url));

before(async () => {
  ids = await bootFixture();
  dir = mkdtempSync(join(tmpdir(), 'zavod-fencer-'));
  const stopFile = join(dir, 'KERNEL_STOP');
  writeFileSync(stopFile, 'RUN\n');
  kernel = new Kernel({ connection: CONN, stopFile });
  await kernel.assertIdentity();
  sup = new SendSupervisor({ connection: { ...CONN, user: 'bem_bootstrap_admin' } });
});
after(async () => {
  for (const r of sup?.runtimes.values() ?? []) if (!r.exit) r.child.kill('SIGKILL');
  await sup?.close();
  await kernel?.close();
});

async function outboxRow(kind) {
  const wi = uuid();
  let r = await kernel.execute(as(ids.author), { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: wi, evidence: { test: 'fencer' } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  r = await kernel.execute(as(ids.author), { type: 'Transition', actor_id: ids.author, tenant_id: ids.tenantA,
    command_id: uuid(), payload: { work_item_id: wi, expected_revision: 1, new_status: 'PLANNED',
      evidence: { test: 'fencer outbox' }, outbox_kind: kind, outbox_payload: { t: kind } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  return withRole('postgres', async (c) =>
    (await c.query('SELECT id FROM bem_core.outbox WHERE work_item_id = $1', [wi])).rows[0].id);
}
const rowOf = (id) => withRole('postgres', async (c) => (await c.query(
  'SELECT status, lease_epoch, send_started_epoch, send_runtime_instance, result FROM bem_core.outbox WHERE id = $1',
  [id])).rows[0]);
const fenceRows = (id) => withRole('postgres', async (c) =>
  (await c.query('SELECT runtime_instance FROM bem_control.outbox_send_fence WHERE outbox_id = $1', [id])).rows);
const kq = (sql, args) => withRole('bem_kernel_rw', async (c) => (await c.query(sql, args)).rows[0]);
const gov = (sql, args) => withRole('bem_bootstrap_admin', async (c) => {
  await c.query("SELECT set_config('app.tenant_id', $1, false)", [ids.tenantA]);
  return (await c.query(sql, args)).rows[0];
});
const reconcile = (id, outcome) => gov('SELECT bem_control.reconcile_unknown_outcome($1, $2, $3, $4) AS s',
  [ids.tenantA, id, outcome, { test: 'fencer reconcile' }]);
const dbFence = (id, epoch, worker, rt, ev) => gov(
  'SELECT bem_control.record_outbox_fence($1, $2, $3, $4, $5, $6, $7) AS e',
  [ids.tenantA, id, epoch, worker, rt, 'PROCESS_TERMINATED', ev]);
// Захват другим исполнителем: чужие строки сразу возвращаются как FAILED.
async function claim(worker, lease, mine) {
  return withRole('bem_kernel_rw', async (c) => {
    const { rows } = await c.query('SELECT * FROM bem_control.claim_outbox_batch(500, $1::interval, $2)', [lease, worker]);
    for (const x of rows.filter((x) => x.outbox_id !== mine)) {
      await c.query('SELECT bem_control.finish_outbox_row($1, $2, $3, \'FAILED\', $4)',
        [x.outbox_id, x.lease_epoch, worker, { released_by_test: 'fencer' }]);
    }
    return rows.find((x) => x.outbox_id === mine);
  });
}
function waitMessage(child, ev, ms = 20000) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`no ${ev} from child`)), ms);
    child.on('message', (m) => { if (m?.ev === ev) { clearTimeout(t); resolve(m); } });
    child.once('exit', (code) => { clearTimeout(t); reject(new Error(`child exited ${code} before ${ev}`)); });
  });
}
const effects = (file) => (existsSync(file) ? readFileSync(file, 'utf8').split('\n').filter(Boolean) : []);

test('M-Z4-01 / E4-8: исполнитель замер после отметки; ограждение — настоящее завершение; эффект ровно один', async () => {
  const counter = join(dir, `effects-${ids.run}.txt`);
  const id = await outboxRow(`zavod.fencer.${ids.run}`);
  const { runtimeInstance, child, pid } = sup.spawnAttempt(CHILD, [counter, 'w1', '1 second', id]);
  const m = await waitMessage(child, 'MARKED');
  assert.equal(m.outbox_id, id);
  assert.equal(m.runtime_instance, runtimeInstance);
  let st = await rowOf(id);
  assert.equal(st.send_runtime_instance, runtimeInstance, 'mark pinned to this runtime instance');
  const epoch = m.lease_epoch;

  // Аренда истекла: второй исполнитель строку не получает, она в UNKNOWN_OUTCOME с экземпляром.
  await sleep(1500);
  assert.equal(await claim('w2', '30 seconds', id), undefined);
  st = await rowOf(id);
  assert.equal(st.status, 'UNKNOWN_OUTCOME');
  assert.equal(st.result.runtime_instance, runtimeInstance);
  await assert.rejects(reconcile(id, 'CONFIRMED_NOT_SENT'), /RECONCILE_NOT_FENCED/);

  // Негативная проба: доказательство есть, а среда жива — надзиратель отказывает, база не тронута.
  await assert.rejects(sup.fence({ tenantId: ids.tenantA, outboxId: id, leaseEpoch: epoch, worker: 'w1',
    runtimeInstance }, { terminate: false }), /FENCE_RUNTIME_ALIVE/);
  assert.equal(pidAlive(pid), true);
  assert.deepEqual(await fenceRows(id), []);
  await assert.rejects(reconcile(id, 'CONFIRMED_NOT_SENT'), /RECONCILE_NOT_FENCED/);
  // Неизвестный надзирателю экземпляр оградить нельзя.
  await assert.rejects(sup.fence({ tenantId: ids.tenantA, outboxId: id, leaseEpoch: epoch, worker: 'w1',
    runtimeInstance: 'runtime:unknown' }), /FENCE_RUNTIME_UNKNOWN/);

  // Настоящее ограждение: завершить, дождаться выхода, проверить отсутствие процесса, затем запись.
  const f = await sup.fence({ tenantId: ids.tenantA, outboxId: id, leaseEpoch: epoch, worker: 'w1', runtimeInstance });
  assert.ok(f.evidenceId);
  assert.equal(f.evidence.exit_observed, true);
  assert.equal(f.evidence.terminated_by, 'fencer');
  assert.equal(pidAlive(pid), false, 'old executor process is gone');
  assert.deepEqual(await fenceRows(id), [{ runtime_instance: runtimeInstance }]);

  // Поздняя команда «продолжай» старому исполнителю эффекта не даёт: процесса нет.
  const sendErr = await new Promise((r) => {
    try { child.send('GO', (e) => r(e || null)); } catch (e) { r(e); }
  });
  assert.equal(sendErr?.code, 'ERR_IPC_CHANNEL_CLOSED', 'no live executor to receive GO');
  await sleep(300);
  assert.equal(effects(counter).length, 0, 'fenced executor never reached the adapter');

  assert.equal((await reconcile(id, 'CONFIRMED_NOT_SENT')).s, 'PENDING');
  const d = await kernel.dispatchOnce(async (row) => {
    if (row.outbox_id !== id) return { outcome: 'FAILED', detail: { released_by_test: 'fencer' } };
    writeFileSync(counter, 'retry\n', { flag: 'a' });
    return { outcome: 'SENT', detail: { stub: true } };
  }, { limit: 500, worker: 'w3' });
  assert.ok(d.results.some((x) => x.outbox_id === id && x.finished === true));
  assert.deepEqual(effects(counter), ['retry'], 'exactly one external effect');
  assert.equal((await rowOf(id)).status, 'SENT');
});

test('M-Z4-01 база принимает ограждение только того же экземпляра и только с наблюдённым выходом', async () => {
  const counter = join(dir, `effects-b-${ids.run}.txt`);
  const id = await outboxRow(`zavod.fencer.b.${ids.run}`);
  const { runtimeInstance, child } = sup.spawnAttempt(CHILD, [counter, 'w1', '1 second', id]);
  const m = await waitMessage(child, 'MARKED');
  const epoch = m.lease_epoch;
  // В том же поколении другой экземпляр отметку не ставит; пустой экземпляр — отказ.
  assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok',
    [id, epoch, 'w1', 'runtime:other'])).ok, false);
  await assert.rejects(kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok',
    [id, epoch, 'w1', ' ']), /RUNTIME_INSTANCE_REQUIRED/);
  await sleep(1500);
  assert.equal(await claim('w2', '30 seconds', id), undefined);
  const good = { observer: 'fencer:test', exit_observed: true, exit_observed_at: new Date().toISOString(),
    runtime_instance: runtimeInstance };
  await assert.rejects(dbFence(id, epoch, 'w1', 'runtime:other', { ...good, runtime_instance: 'runtime:other' }),
    /FENCE_RUNTIME_MISMATCH/);
  await assert.rejects(dbFence(id, epoch, 'w1', runtimeInstance, { ...good, exit_observed: false }),
    /FENCE_EVIDENCE_INCOMPLETE/);
  await assert.rejects(dbFence(id, epoch, 'w1', runtimeInstance, { ...good, exit_observed: 'true' }),
    /FENCE_EVIDENCE_INCOMPLETE/);
  await assert.rejects(dbFence(id, epoch, 'w1', runtimeInstance, { ...good, exit_observed_at: '' }),
    /FENCE_EVIDENCE_INCOMPLETE/);
  await assert.rejects(dbFence(id, epoch, 'w1', runtimeInstance, { ...good, runtime_instance: 'runtime:other' }),
    /FENCE_EVIDENCE_INCOMPLETE/);
  await assert.rejects(dbFence(id, epoch, 'w1', runtimeInstance, { ...good, observer: 'w1' }), /FENCE_SELF_REPORT/);
  await assert.rejects(dbFence(id, epoch, 'w1', runtimeInstance, { ...good, observer: runtimeInstance }),
    /FENCE_SELF_REPORT/);
  // Исполнитель (роль Kernel) записать ограждение не может вовсе.
  await assert.rejects(kq('SELECT bem_control.record_outbox_fence($1, $2, $3, $4, $5, $6, $7)',
    [ids.tenantA, id, epoch, 'w1', runtimeInstance, 'PROCESS_TERMINATED', good]), (e) => e.code === '42501');
  assert.deepEqual(await fenceRows(id), []);
  const f = await sup.fence({ tenantId: ids.tenantA, outboxId: id, leaseEpoch: epoch, worker: 'w1', runtimeInstance });
  assert.ok(f.evidenceId);
  assert.equal(effects(counter).length, 0);
});
