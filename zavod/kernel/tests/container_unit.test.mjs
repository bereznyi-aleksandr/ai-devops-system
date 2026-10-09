// ДОКУМЕНТ: tests/container_unit.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 09:05 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 09:05 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: E4-8, единица «контейнер» (CONTAINER_TERMINATED) — тот же сценарий, что fencer.test.mjs для
//   cgroup v2: отметка → исполнитель порождает потомка с доступом к адаптеру (setsid) → пауза до вызова →
//   аренда истекла → UNKNOWN_OUTCOME → сверка без ограждения — отказ → живая единица — отказ без записи →
//   надзиратель останавливает контейнер целиком, видит его остановленным и пишет ограждение → «продолжай»
//   эффекта не даёт → новая попытка — ровно один эффект. Мутация «только ведущий»: отказ FENCE_RUNTIME_ALIVE,
//   выживший потомок даёт эффект. Номера процессов — внутри контейнера, живость — через docker exec.
//   Нужны Linux, docker и ZAVOD_CONTAINER_IMAGE; при CI=true и заданном образе пропуск запрещён.
// ОГРАНИЧЕНИЯ: стенд PG16 с Z-EXT-01; контейнеры остаются остановленными (ничего не удаляется, P4.702).

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Kernel } from '../src/kernel.mjs';
import { SendSupervisor, ContainerUnit } from '../src/fencer.mjs';
import { CONN, bootFixture, withRole, uuid, operatorLogin, runStopFile } from './helpers.mjs';

const OK = ContainerUnit.supported();
const REQUIRED = process.env.CI === 'true' && Boolean(process.env.ZAVOD_CONTAINER_IMAGE);
const skip = OK || REQUIRED ? false : 'нет docker или ZAVOD_CONTAINER_IMAGE — только локально';
const CHILD = fileURLToPath(new URL('./paused_sender.mjs', import.meta.url));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let ids;
let kernel;
let sup;
let dir;
let op;
before(async () => {
  if (skip) return;
  ids = await bootFixture();
  dir = mkdtempSync(join(tmpdir(), 'zavod-container-'));
  kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-container-stop-') });
  await kernel.assertIdentity();
  op = await operatorLogin();
  sup = new SendSupervisor({ connection: { ...CONN, user: op.role }, unit: 'container' });
});
after(async () => {
  for (const r of sup?.runtimes.values() ?? []) {
    try { if (r.unit.populated()) await r.unit.kill(5000); } catch { /* уже остановлен */ }
  }
  await sup?.close();
  await kernel?.close();
});

async function outboxRow(kind) {
  const wi = uuid();
  let r = await kernel.execute({ actor_id: ids.author }, { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: wi, evidence: { test: 'container' } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  r = await kernel.execute({ actor_id: ids.author }, { type: 'Transition', actor_id: ids.author, tenant_id: ids.tenantA,
    command_id: uuid(), payload: { work_item_id: wi, expected_revision: 1, new_status: 'PLANNED',
      evidence: { test: 'container outbox' }, outbox_kind: kind, outbox_payload: { t: kind } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  return withRole('postgres', async (c) =>
    (await c.query('SELECT id FROM bem_core.outbox WHERE work_item_id = $1', [wi])).rows[0].id);
}
const rowOf = (id) => withRole('postgres', async (c) => (await c.query(
  'SELECT status, send_runtime_instance, result FROM bem_core.outbox WHERE id = $1', [id])).rows[0]);
const fenceRows = (id) => withRole('postgres', async (c) =>
  (await c.query('SELECT runtime_instance, method FROM bem_control.outbox_send_fence WHERE outbox_id = $1', [id])).rows);
const reconcile = (id, outcome) => withRole(op.role, async (c) => {
  await c.query("SELECT set_config('app.tenant_id', $1, false)", [ids.tenantA]);
  return (await c.query('SELECT bem_control.reconcile_unknown_outcome($1, $2, $3, $4) AS s',
    [ids.tenantA, id, outcome, { test: 'container reconcile' }])).rows[0];
});
async function claim(worker, lease, mine) {
  return withRole('bem_kernel_rw', async (c) => {
    const { rows } = await c.query('SELECT * FROM bem_control.claim_outbox_batch(500, $1::interval, $2)', [lease, worker]);
    for (const x of rows.filter((x) => x.outbox_id !== mine)) {
      await c.query('SELECT bem_control.finish_outbox_row($1, $2, $3, \'FAILED\', $4)',
        [x.outbox_id, x.lease_epoch, worker, { released_by_test: 'container' }]);
    }
    return rows.find((x) => x.outbox_id === mine);
  });
}
const effects = (file) => (existsSync(file) ? readFileSync(file, 'utf8').split('\n').filter(Boolean) : []);
const key = (id, epoch, runtimeInstance) => ({ tenantId: ids.tenantA, outboxId: id, leaseEpoch: epoch, worker: 'w1', runtimeInstance });

async function pausedAttempt(tag) {
  const counter = join(dir, `effects-${tag}-${ids.run}.txt`);
  const go = join(dir, `GO-${tag}-${ids.run}`);
  const id = await outboxRow(`zavod.container.${tag}.${ids.run}`);
  const { runtimeInstance } = sup.spawnAttempt(CHILD, [counter, 'w1', '1 second', id, go, '1']);
  const desc = sup.waitMessage(runtimeInstance, 'DESCENDANT', 60000);
  const m = await sup.waitMessage(runtimeInstance, 'MARKED', 60000);
  const { pid: descPid } = await desc;
  assert.equal(m.outbox_id, id);
  assert.equal((await rowOf(id)).send_runtime_instance, runtimeInstance);
  await sleep(1500);
  assert.equal(await claim('w2', '30 seconds', id), undefined);
  assert.equal((await rowOf(id)).status, 'UNKNOWN_OUTCOME');
  return { id, epoch: m.lease_epoch, runtimeInstance, descPid, counter, go, unit: sup.runtimes.get(runtimeInstance).unit };
}

test('E4-8 контейнер: живой потомок; остановка всего контейнера; GO эффекта не даёт; эффект ровно один', { skip }, async () => {
  assert.ok(OK, 'CI must run the container unit test: docker and ZAVOD_CONTAINER_IMAGE are required');
  const a = await pausedAttempt('tree');
  assert.equal(a.unit.nsAlive(a.descPid), true, 'descendant with adapter access is alive inside the container');
  await assert.rejects(reconcile(a.id, 'CONFIRMED_NOT_SENT'), /RECONCILE_NOT_FENCED/);
  await assert.rejects(sup.fence(key(a.id, a.epoch, a.runtimeInstance), { terminate: false }), /FENCE_RUNTIME_ALIVE/);
  assert.deepEqual(await fenceRows(a.id), []);
  const f = await sup.fence(key(a.id, a.epoch, a.runtimeInstance));
  assert.equal(f.evidence.unit_kind, 'CONTAINER');
  assert.equal(f.evidence.unit_empty_observed, true);
  assert.equal(f.evidence.terminated_by, 'fencer');
  assert.ok(f.evidence.pids_before.length >= 3, `holder, leader and descendant were in the unit: ${f.evidence.pids_before}`);
  assert.equal(a.unit.populated(), false, 'container stopped');
  assert.deepEqual(await fenceRows(a.id), [{ runtime_instance: a.runtimeInstance, method: 'CONTAINER_TERMINATED' }]);
  writeFileSync(a.go, 'GO\n');
  await sleep(600);
  assert.equal(effects(a.counter).length, 0, 'stopped container never reached the adapter');
  assert.equal((await reconcile(a.id, 'CONFIRMED_NOT_SENT')).s, 'PENDING');
  const d = await kernel.dispatchOnce(async (row) => {
    if (row.outbox_id !== a.id) return { outcome: 'FAILED', detail: { released_by_test: 'container' } };
    writeFileSync(a.counter, 'retry\n', { flag: 'a' });
    return { outcome: 'SENT', detail: { stub: true } };
  }, { limit: 500, worker: 'w3' });
  assert.ok(d.results.some((x) => x.outbox_id === a.id && x.finished === true));
  assert.deepEqual(effects(a.counter), ['retry'], 'exactly one external effect');
});

test('E4-8 контейнер, мутация «только ведущий»: отказ, потомок жив и даёт эффект', { skip }, async () => {
  assert.ok(OK, 'CI must run the container mutation test');
  const a = await pausedAttempt('mut');
  await assert.rejects(sup.fence(key(a.id, a.epoch, a.runtimeInstance), { strategy: 'leader-only' }), /FENCE_RUNTIME_ALIVE/);
  const rec = sup.runtimes.get(a.runtimeInstance);
  assert.ok(rec.exit, 'leader process has exited');
  assert.equal(a.unit.nsAlive(a.descPid), true, 'descendant survived the leader-only kill');
  assert.deepEqual(await fenceRows(a.id), []);
  await assert.rejects(reconcile(a.id, 'CONFIRMED_NOT_SENT'), /RECONCILE_NOT_FENCED/);
  writeFileSync(a.go, 'GO\n');
  for (let i = 0; i < 60 && effects(a.counter).length === 0; i += 1) await sleep(50);
  assert.deepEqual(effects(a.counter), [`descendant:${a.runtimeInstance}`]);
  await rec.unit.kill(10000);
  assert.equal(rec.unit.populated(), false);
  assert.equal((await rowOf(a.id)).status, 'UNKNOWN_OUTCOME');
});
