// ДОКУМЕНТ: tests/egress_matrix.test.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 08:30 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 10:52 +03:00 (аудит E4-6 M-E46-02: явная роль вызывающего; прежнее 2026-10-09 08:30 +03:00)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: критерий E4-8 протокола Z1 v1.9 — строки Egress матрицы 6.2 на адаптере-заглушке со
//   счётчиком внешних вызовов и счётчиком эффектов (внешняя система; идемпотентный вид сводит повтор
//   с тем же ключом к одному эффекту). Строки: R1 Egress упал до отметки; R2 отметка не удалась (аренда
//   истекла); R3 отметка стоит, вызов прошёл, аренда истекла до исхода, вид неидемпотентный; R4 то же,
//   закреплена «идемпотентно»; R5 отметка стоит, исполнитель упал до вызова; R6 неидемпотентная v1
//   закреплена, затем идемпотентная v2; R7 внешняя система приняла, ответ не дошёл, аренда жива
//   (неидемпотентный и идемпотентный вид). UNKNOWN_OUTCOME сам не повторяется: после каждой строки —
//   ещё проходы доставщика Kernel, счётчик не растёт. У неидемпотентного вида вызовов = 1.
//   Сценарий «пауза исполнителя» на настоящей единице (cgroup v2) и мутация «только родитель» —
//   tests/fencer.test.mjs; Job Object — tests/jobhost.test.mjs (ветка zavod/stage4-jobobject).
// ОГРАНИЧЕНИЯ: ограждение в R5 пишется с доказательством единицы, как в ext01.test.mjs (здесь проверяется
//   порядок сверки и счётчик, а не гашение единицы — оно в fencer.test.mjs). Стенд PG16 с Z-EXT-01.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { Kernel } from '../src/kernel.mjs';
import { CONN, bootFixture, withRole, runStopFile, uuid } from './helpers.mjs';

let ids;
let kernel;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const RT = 'runtime:e48-w1';

// Внешняя система-заглушка: calls — все внешние вызовы; effects — эффекты по ключу.
class StubExternal {
  constructor() { this.calls = new Map(); this.effects = new Map(); }
  send(id, key, idempotent) {
    this.calls.set(id, (this.calls.get(id) || 0) + 1);
    if (!(idempotent && this.effects.has(key))) this.effects.set(key, (this.effects.get(key) || 0) + 1);
  }
  n(id) { return this.calls.get(id) || 0; }
  e(key) { return this.effects.get(key) || 0; }
}
const ext = new StubExternal();

before(async () => {
  ids = await bootFixture();
  kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-e48-') });
  await kernel.assertIdentity();
});
after(async () => { await kernel?.close(); });

async function outboxRow(kind) {
  const wi = uuid();
  let r = await kernel.execute({ actor_id: ids.author, role: 'kernel' }, { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: wi, evidence: { test: 'E4-8' } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  r = await kernel.execute({ actor_id: ids.author, role: 'kernel' }, { type: 'Transition', actor_id: ids.author, tenant_id: ids.tenantA,
    command_id: uuid(), payload: { work_item_id: wi, expected_revision: 1, new_status: 'PLANNED',
      evidence: { test: 'E4-8' }, outbox_kind: kind, outbox_payload: { t: kind } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  return withRole('postgres', async (c) =>
    (await c.query('SELECT id, idempotency_key FROM bem_core.outbox WHERE work_item_id = $1', [wi])).rows[0]);
}
async function claim(worker, lease, mine) {
  return withRole('bem_kernel_rw', async (c) => {
    const { rows } = await c.query('SELECT * FROM bem_control.claim_outbox_batch(500, $1::interval, $2)', [lease, worker]);
    for (const x of rows.filter((x) => x.outbox_id !== mine)) {
      await c.query('SELECT bem_control.finish_outbox_row($1, $2, $3, \'FAILED\', $4)',
        [x.outbox_id, x.lease_epoch, worker, { released_by_test: 'E4-8' }]);
    }
    return rows.find((x) => x.outbox_id === mine);
  });
}
const kq = async (sql, args) => withRole('bem_kernel_rw', async (c) => (await c.query(sql, args)).rows[0]);
const mark = async (id, epoch, w) => (await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id, epoch, w, RT])).ok;
const finish = async (id, epoch, w, s) => (await kq('SELECT bem_control.finish_outbox_row($1, $2, $3, $4, $5) AS ok', [id, epoch, w, s, { test: 'E4-8' }])).ok;
const rowOf = (id) => withRole('postgres', async (c) =>
  (await c.query('SELECT status, lease_epoch, send_policy_idempotent, result FROM bem_core.outbox WHERE id = $1', [id])).rows[0]);
const setPolicy = (kind, idem, note) => withRole('bem_bootstrap_admin', async (c) =>
  (await c.query('SELECT bem_control.set_outbox_kind_policy($1, $2, $3, $4, $5) AS v',
    [kind, idem, 'stub-adapter 1.0', 'outbox_id', `E4-8: ${note}`])).rows[0].v);

// Исполнитель Egress по протоколу: отметка → внешний вызов → исход. stage задаёт точку отказа.
async function egressAttempt(row, claimRow, worker, { stage = 'ok', idempotent = false } = {}) {
  if (stage === 'crash_before_mark') return 'CRASHED';
  if (!(await mark(row.id, claimRow.lease_epoch, worker))) return 'MARK_REFUSED';     // внешнего вызова нет
  if (stage === 'crash_before_call') return 'CRASHED';
  ext.send(row.id, row.idempotency_key, idempotent);
  if (stage === 'crash_after_call') return 'CRASHED';                                 // исход не записан
  return (await finish(row.id, claimRow.lease_epoch, worker, 'SENT')) ? 'SENT' : 'FINISH_REFUSED';
}

// Проходы доставщика Kernel: свои строки не должны вызываться снова; чужие строки стенда — SENT-заглушка.
async function kernelRounds(mine, n = 3) {
  for (let i = 0; i < n; i++) {
    await kernel.dispatchOnce(async (r) => {
      if (mine.includes(r.outbox_id)) ext.send(r.outbox_id, 'kernel-round', false);
      return { outcome: 'SENT', detail: { stub: 'E4-8' } };
    }, { limit: 500 });
  }
}

test('E4-8 R1: Egress упал до отметки — строка вернулась поколением +1, внешний вызов ровно один', async () => {
  const row = await outboxRow(`zavod.e48.r1.${ids.run}`);
  const a = await claim('w1', '1 second', row.id);
  assert.equal(await egressAttempt(row, a, 'w1', { stage: 'crash_before_mark' }), 'CRASHED');
  await sleep(1500);
  const b = await claim('w2', '30 seconds', row.id);
  assert.equal(Number(b.lease_epoch), Number(a.lease_epoch) + 1);
  assert.equal(await egressAttempt(row, b, 'w2'), 'SENT');
  await kernelRounds([row.id]);
  assert.equal(ext.n(row.id), 1);
  assert.equal((await rowOf(row.id)).status, 'SENT');
});

test('E4-8 R2: отметка после истечения аренды — false, внешнего вызова нет; следующий исполнитель шлёт один раз', async () => {
  const row = await outboxRow(`zavod.e48.r2.${ids.run}`);
  const a = await claim('w1', '1 second', row.id);
  await sleep(1500);
  assert.equal(await egressAttempt(row, a, 'w1'), 'MARK_REFUSED');
  assert.equal(ext.n(row.id), 0);
  const b = await claim('w2', '30 seconds', row.id);
  assert.equal(await egressAttempt(row, b, 'w2'), 'SENT');
  await kernelRounds([row.id]);
  assert.equal(ext.n(row.id), 1);
});

test('E4-8 R3: неидемпотентный вид, вызов прошёл, аренда истекла до исхода — UNKNOWN_OUTCOME, вызовов = 1', async () => {
  const row = await outboxRow(`zavod.e48.r3.${ids.run}`);
  const a = await claim('w1', '1 second', row.id);
  assert.equal(await egressAttempt(row, a, 'w1', { stage: 'crash_after_call' }), 'CRASHED');
  await sleep(1500);
  assert.equal(await claim('w2', '30 seconds', row.id), undefined, 'второй исполнитель строку не получает');
  const st = await rowOf(row.id);
  assert.equal(st.status, 'UNKNOWN_OUTCOME');
  assert.equal(st.result.reason, 'LEASE_EXPIRED_AFTER_SEND_START');
  assert.equal(await finish(row.id, a.lease_epoch, 'w1', 'SENT'), false, 'старый исполнитель исход не пишет');
  await kernelRounds([row.id]);
  assert.equal(ext.n(row.id), 1);
  assert.equal(ext.e(row.idempotency_key), 1);
  assert.equal((await rowOf(row.id)).status, 'UNKNOWN_OUTCOME', 'UNKNOWN_OUTCOME сам не повторяется');
});

test('E4-8 R4: закреплено «идемпотентно» — повтор тем же ключом, второго эффекта нет', async () => {
  const kind = `zavod.e48.r4.${ids.run}`;
  assert.equal(await setPolicy(kind, true, 'R4 adapter dedups by key'), 1);
  const row = await outboxRow(kind);
  const a = await claim('w1', '1 second', row.id);
  assert.equal(await egressAttempt(row, a, 'w1', { stage: 'crash_after_call', idempotent: true }), 'CRASHED');
  assert.equal((await rowOf(row.id)).send_policy_idempotent, true);
  await sleep(1500);
  const b = await claim('w2', '30 seconds', row.id);
  assert.ok(b, 'идемпотентная строка возвращается в очередь');
  assert.equal(await egressAttempt(row, b, 'w2', { idempotent: true }), 'SENT');
  await kernelRounds([row.id]);
  assert.equal(ext.n(row.id), 2, 'два вызова с одним ключом');
  assert.equal(ext.e(row.idempotency_key), 1, 'эффект один');
});

const gov = (sql, args) => withRole('bem_bootstrap_admin', async (c) => {
  await c.query("SELECT set_config('app.tenant_id', $1, false)", [ids.tenantA]);
  return (await c.query(sql, args)).rows[0];
});
const reconcile = (id, outcome) => gov('SELECT bem_control.reconcile_unknown_outcome($1, $2, $3, $4) AS s',
  [ids.tenantA, id, outcome, { test: 'E4-8 reconcile' }]);

test('E4-8 R5: отметка стоит, исполнитель упал до вызова — UNKNOWN_OUTCOME; «не отправлено» только после ограждения; итог один вызов', async () => {
  const row = await outboxRow(`zavod.e48.r5.${ids.run}`);
  const a = await claim('w1', '1 second', row.id);
  assert.equal(await egressAttempt(row, a, 'w1', { stage: 'crash_before_call' }), 'CRASHED');
  await sleep(1500);
  assert.equal(await claim('w2', '30 seconds', row.id), undefined);
  assert.equal((await rowOf(row.id)).status, 'UNKNOWN_OUTCOME', 'осторожно: отправки не было, но исход неизвестен');
  await assert.rejects(reconcile(row.id, 'CONFIRMED_NOT_SENT'), /RECONCILE_NOT_FENCED/);
  await kernelRounds([row.id]);
  assert.equal(ext.n(row.id), 0);
  const ev = { observer: 'fencer:e48', exit_observed: true, exit_observed_at: new Date().toISOString(), runtime_instance: RT,
    unit_kind: 'CGROUP_V2', unit_id: '/sys/fs/cgroup/zavod/e48', unit_empty_observed: true };
  assert.ok((await gov('SELECT bem_control.record_outbox_fence($1, $2, $3, $4, $5, $6, $7) AS e',
    [ids.tenantA, row.id, a.lease_epoch, 'w1', RT, 'CGROUP_KILLED', ev])).e);
  assert.equal((await reconcile(row.id, 'CONFIRMED_NOT_SENT')).s, 'PENDING');
  const b = await claim('w2', '30 seconds', row.id);
  assert.equal(await egressAttempt(row, b, 'w2'), 'SENT');
  await kernelRounds([row.id]);
  assert.equal(ext.n(row.id), 1);
});

test('E4-8 R6: неидемпотентная v1 закреплена, затем идемпотентная v2 — старая строка UNKNOWN_OUTCOME, новая повторяется ключом', async () => {
  const kind = `zavod.e48.r6.${ids.run}`;
  assert.equal(await setPolicy(kind, false, 'R6 v1'), 1);
  const row = await outboxRow(kind);
  const a = await claim('w1', '1 second', row.id);
  assert.equal(await egressAttempt(row, a, 'w1', { stage: 'crash_after_call' }), 'CRASHED');
  assert.equal(await setPolicy(kind, true, 'R6 v2'), 2);
  await sleep(1500);
  assert.equal(await claim('w2', '30 seconds', row.id), undefined);
  assert.equal((await rowOf(row.id)).status, 'UNKNOWN_OUTCOME');
  const row2 = await outboxRow(kind);
  const c1 = await claim('w1', '1 second', row2.id);
  assert.equal(await egressAttempt(row2, c1, 'w1', { stage: 'crash_after_call', idempotent: true }), 'CRASHED');
  await sleep(1500);
  const c2 = await claim('w2', '30 seconds', row2.id);
  assert.ok(c2);
  assert.equal(await egressAttempt(row2, c2, 'w2', { idempotent: true }), 'SENT');
  await kernelRounds([row.id, row2.id]);
  assert.equal(ext.n(row.id), 1, 'v1: вызов один');
  assert.equal(ext.n(row2.id), 2);
  assert.equal(ext.e(row2.idempotency_key), 1, 'v2: эффект один');
});

for (const idem of [false, true]) {
  test(`E4-8 R7 (${idem ? 'идемпотентный' : 'неидемпотентный'}): внешняя система приняла, ответ не дошёл — доставщик пишет UNKNOWN_OUTCOME, повтора нет`, async () => {
    const kind = `zavod.e48.r7${idem ? 'i' : 'n'}.${ids.run}`;
    if (idem) assert.equal(await setPolicy(kind, true, 'R7 idempotent'), 1);
    const row = await outboxRow(kind);
    const d = await kernel.dispatchOnce(async (r) => {
      if (r.outbox_id !== row.id) return { outcome: 'SENT', detail: { stub: 'E4-8' } };
      ext.send(row.id, row.idempotency_key, idem);
      throw new Error('reply lost after external accept');
    }, { limit: 500 });
    assert.ok(d.results.some((x) => x.outbox_id === row.id && x.outcome === 'UNKNOWN_OUTCOME' && x.finished === true));
    await kernelRounds([row.id]);
    assert.equal((await rowOf(row.id)).status, 'UNKNOWN_OUTCOME');
    assert.equal(ext.n(row.id), 1);
    assert.equal(ext.e(row.idempotency_key), 1);
  });
}
