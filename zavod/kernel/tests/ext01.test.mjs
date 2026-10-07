// ДОКУМЕНТ: tests/ext01.test.mjs
// ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 16:15 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 17:55 +03:00 (v0.3: аудит Z4 M-Z4-01 —
//   отметка и ограждение с экземпляром среды исполнения; сценарий на настоящем процессе — fencer.test.mjs;
//   v0.2: аудит Z3 —
//   M-Z3-02 версии политики и закрепление за строкой; M-Z3-03 ограждение перед сверкой)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: расширение Z-EXT-01 (ответ на аудит Z2):
//   M-Z2-01 — область ZAVOD_PRODUCT_RELEASE выпускается только при ровно {anthropic, openai};
//   M-Z2-02 — после начала отправки истёкшая аренда неидемпотентного вида даёт UNKNOWN_OUTCOME,
//   второго внешнего вызова нет; идемпотентный вид (только по записи управления) повторяется.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Kernel } from '../src/kernel.mjs';
import { CONN, bootFixture, withRole, assignAuditor, uuid } from './helpers.mjs';

let ids;
let kernel;
const as = (actor) => ({ actor_id: actor });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const RT1 = 'runtime:ext01-w1';   // экземпляр среды исполнения исполнителя w1 (M-Z4-01)

before(async () => {
  ids = await bootFixture();
  const stopFile = join(mkdtempSync(join(tmpdir(), 'zavod-ext01-')), 'KERNEL_STOP');
  writeFileSync(stopFile, 'RUN\n');
  kernel = new Kernel({ connection: CONN, stopFile });
  await kernel.assertIdentity();
});
after(async () => { await kernel?.close(); });

async function newItem() {
  const wi = uuid();
  const r = await kernel.execute(as(ids.author), { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: wi, evidence: { test: 'ext01' } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  return wi;
}

// ---------- M-Z2-01: область выпуска продукта ----------

async function publish(scope, criticality = 'CRITICAL') {
  const wi = await newItem();
  const subj = uuid();
  const head = 'sha-' + uuid().slice(0, 8);
  const r = await kernel.execute(as(ids.author), { type: 'PublishSubject', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { subject_id: subj, work_item_id: wi, head_sha: head, criticality, scope,
      authors: [ids.author], evidence: { test: 'ext01 publish' } } });
  return { r, subj, head };
}
const verdict = (aud, subj, head) => kernel.execute(as(aud), { type: 'RecordVerdict', actor_id: aud,
  tenant_id: ids.tenantA, payload: { subject_id: subj, head_sha: head, verdict: 'ACCEPT', evidence: { reviewed: head } } });
const release = (subj, head) => kernel.execute(as(ids.author), { type: 'ReleaseSubject', actor_id: ids.author,
  tenant_id: ids.tenantA, payload: { subject_id: subj, head_sha: head } });

test('M-Z2-01 неизвестная область отклоняется', async () => {
  const { r } = await publish('PRODUCT_ANY');
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'BAD_SCOPE');
});

test('M-Z2-01 ZAVOD_PRODUCT_RELEASE: 0 и 1 вердикт — отказ; ровно {anthropic, openai} — выпуск', async () => {
  const { r, subj, head } = await publish('ZAVOD_PRODUCT_RELEASE');
  assert.equal(r.ok, true, JSON.stringify(r.error));
  assert.equal((await release(subj, head)).error.code, 'WAITING_AUDIT');
  await assignAuditor(ids.tenantA, subj, ids.audOpenai);
  assert.equal((await verdict(ids.audOpenai, subj, head)).ok, true);
  assert.equal((await release(subj, head)).error.code, 'BEM954_PROVIDER_SET_MISMATCH');
  await assignAuditor(ids.tenantA, subj, ids.audAnthropic);
  assert.equal((await verdict(ids.audAnthropic, subj, head)).ok, true);
  const ok = await release(subj, head);
  assert.equal(ok.ok, true, JSON.stringify(ok.error));
  assert.equal(ok.result.released, true);
});

test('M-Z2-01 для сравнения: WORKING по матрице §9.4 выпускается одним чужим ACCEPT, продуктовая область — нет', async () => {
  const w = await publish('WORKING', 'NORMAL');
  await assignAuditor(ids.tenantA, w.subj, ids.audOpenai);
  assert.equal((await verdict(ids.audOpenai, w.subj, w.head)).ok, true);
  assert.equal((await release(w.subj, w.head)).result?.released, true);
  const p = await publish('ZAVOD_PRODUCT_RELEASE', 'NORMAL');
  await assignAuditor(ids.tenantA, p.subj, ids.audOpenai);
  assert.equal((await verdict(ids.audOpenai, p.subj, p.head)).ok, true);
  assert.equal((await release(p.subj, p.head)).error.code, 'BEM954_PROVIDER_SET_MISMATCH');
});

// ---------- M-Z2-02: гонка истечения аренды после начала отправки ----------

async function outboxRow(kind) {
  const wi = await newItem();
  const r = await kernel.execute(as(ids.author), { type: 'Transition', actor_id: ids.author, tenant_id: ids.tenantA,
    command_id: uuid(), payload: { work_item_id: wi, expected_revision: 1, new_status: 'PLANNED',
      evidence: { test: 'ext01 outbox' }, outbox_kind: kind, outbox_payload: { t: kind } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  return withRole('postgres', async (c) =>
    (await c.query('SELECT id FROM bem_core.outbox WHERE work_item_id = $1', [wi])).rows[0].id);
}
// Захват ролью Kernel; чужие строки сразу возвращаются как FAILED, чтобы не держать их.
async function claim(worker, lease, mine) {
  return withRole('bem_kernel_rw', async (c) => {
    const { rows } = await c.query('SELECT * FROM bem_control.claim_outbox_batch(500, $1::interval, $2)', [lease, worker]);
    for (const x of rows.filter((x) => x.outbox_id !== mine)) {
      await c.query('SELECT bem_control.finish_outbox_row($1, $2, $3, \'FAILED\', $4)',
        [x.outbox_id, x.lease_epoch, worker, { released_by_test: 'ext01' }]);
    }
    return rows.find((x) => x.outbox_id === mine);
  });
}
const kq = (sql, args) => withRole('bem_kernel_rw', async (c) => (await c.query(sql, args)).rows[0]);
const rowOf = (id) => withRole('postgres', async (c) =>
  (await c.query('SELECT status, lease_epoch, send_started_epoch, result FROM bem_core.outbox WHERE id = $1', [id])).rows[0]);

test('M-Z2-02 неидемпотентный вид: аренда истекла после начала отправки — второй отправки нет, UNKNOWN_OUTCOME', async () => {
  const id = await outboxRow(`zavod.nonidem.${ids.run}`);
  const a = await claim('w1', '1 second', id);
  assert.ok(a, 'first worker claims the row');
  assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id, a.lease_epoch, 'w1', RT1])).ok, true);
  await sleep(1500);
  const b = await claim('w2', '30 seconds', id);
  assert.equal(b, undefined, 'second worker must not get the row');
  const st = await rowOf(id);
  assert.equal(st.status, 'UNKNOWN_OUTCOME');
  assert.equal(st.result.reason, 'LEASE_EXPIRED_AFTER_SEND_START');
  const late = await kq('SELECT bem_control.finish_outbox_row($1, $2, $3, \'SENT\', $4) AS ok', [id, a.lease_epoch, 'w1', {}]);
  assert.equal(late.ok, false, 'stale worker cannot write the outcome');
});

test('M-Z2-02 отметка после истечения аренды отклоняется; неотмеченная строка безопасно берётся снова', async () => {
  const id = await outboxRow(`zavod.nonidem2.${ids.run}`);
  const a = await claim('w1', '1 second', id);
  await sleep(1500);
  assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id, a.lease_epoch, 'w1', RT1])).ok, false);
  const b = await claim('w2', '30 seconds', id);
  assert.ok(b, 'not started -> reclaim is safe');
  assert.equal(Number(b.lease_epoch), Number(a.lease_epoch) + 1);
});

// Регистрация версии политики — путь управления (bem_governance; в тесте — bem_bootstrap_admin).
const setPolicy = (kind, idem, note) => withRole('bem_bootstrap_admin', async (c) =>
  (await c.query('SELECT bem_control.set_outbox_kind_policy($1, $2, $3, $4, $5) AS v',
    [kind, idem, 'stub-adapter 1.0', 'outbox_id', `ext01 test: ${note}`])).rows[0].v);
const pinOf = (id) => withRole('postgres', async (c) =>
  (await c.query('SELECT send_policy_version, send_policy_idempotent FROM bem_core.outbox WHERE id = $1', [id])).rows[0]);

test('M-Z2-02 идемпотентный вид (запись управления) после начала отправки повторяется тем же ключом', async () => {
  const kind = `zavod.idem.${ids.run}`;
  assert.equal(await setPolicy(kind, true, 'adapter dedups by idempotency_key'), 1);
  const id = await outboxRow(kind);
  const a = await claim('w1', '1 second', id);
  assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id, a.lease_epoch, 'w1', RT1])).ok, true);
  assert.deepEqual(await pinOf(id), { send_policy_version: 1, send_policy_idempotent: true });
  await sleep(1500);
  const b = await claim('w2', '30 seconds', id);
  assert.ok(b, 'idempotent kind is retried');
  assert.equal((await rowOf(id)).status, 'LEASED');
});

test('M-Z2-02 Kernel не может объявить вид идемпотентным и не пишет таблицу политики', async () => {
  await assert.rejects(kq('SELECT bem_control.set_outbox_kind_policy($1, true, $2, $3, $4)', ['x.y', 'a', 'k', 'self']),
    (e) => e.code === '42501');
  await assert.rejects(kq('INSERT INTO bem_control.outbox_kind_policy (kind, version, idempotent_adapter, adapter_version, key_scheme, evidence) VALUES ($1, 1, true, $2, $2, $2)', ['x.z', 'self']),
    (e) => e.code === '42501');
  await assert.rejects(kq('UPDATE bem_control.outbox_kind_policy SET idempotent_adapter = true', []), (e) => e.code === '42501');
});

// ---------- M-Z3-02: политика закреплена за строкой, новая версия не действует назад ----------

test('M-Z3-02 версии политики только добавляются; номер растёт без пропусков', async () => {
  const kind = `zavod.ver.${ids.run}`;
  assert.equal(await setPolicy(kind, false, 'v1'), 1);
  assert.equal(await setPolicy(kind, true, 'v2'), 2);
  const rows = await withRole('postgres', async (c) => (await c.query(
    'SELECT version, idempotent_adapter FROM bem_control.outbox_kind_policy WHERE kind = $1 ORDER BY version', [kind])).rows);
  assert.deepEqual(rows, [{ version: 1, idempotent_adapter: false }, { version: 2, idempotent_adapter: true }]);
});

test('M-Z3-02 строка начала отправку при неидемпотентной v1; v2 «идемпотентный» после этого — всё равно UNKNOWN_OUTCOME', async () => {
  const kind = `zavod.pin.${ids.run}`;
  assert.equal(await setPolicy(kind, false, 'v1 non-idempotent'), 1);
  const id = await outboxRow(kind);
  const a = await claim('w1', '1 second', id);
  assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id, a.lease_epoch, 'w1', RT1])).ok, true);
  assert.deepEqual(await pinOf(id), { send_policy_version: 1, send_policy_idempotent: false });
  // внешний эффект «принят без ответа»; управление регистрирует идемпотентную v2 того же вида
  assert.equal(await setPolicy(kind, true, 'v2 idempotent'), 2);
  await sleep(1500);
  assert.equal(await claim('w2', '30 seconds', id), undefined, 'old row must not be retried after policy change');
  const st = await rowOf(id);
  assert.equal(st.status, 'UNKNOWN_OUTCOME');
  assert.equal(st.result.policy_version, 1);
  // новая строка того же вида закрепляет v2 и повторяется
  const id2 = await outboxRow(kind);
  const c1 = await claim('w1', '1 second', id2);
  assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id2, c1.lease_epoch, 'w1', RT1])).ok, true);
  assert.deepEqual(await pinOf(id2), { send_policy_version: 2, send_policy_idempotent: true });
  await sleep(1500);
  assert.ok(await claim('w2', '30 seconds', id2), 'v2 row is retried');
});

// ---------- M-Z3-03: сверка требует ограждения исполнителя ----------

const gov = (sql, args) => withRole('bem_bootstrap_admin', async (c) => {
  await c.query("SELECT set_config('app.tenant_id', $1, false)", [ids.tenantA]);
  return (await c.query(sql, args)).rows[0];
});
const reconcile = (id, outcome) => gov('SELECT bem_control.reconcile_unknown_outcome($1, $2, $3, $4) AS s',
  [ids.tenantA, id, outcome, { test: 'ext01 reconcile' }]);
const OBSERVED = { observer: 'fencer:ext01', exit_observed: true, exit_observed_at: '2026-10-07T17:55:00Z',
  runtime_instance: RT1 };
const fence = (id, epoch, worker, method = 'PROCESS_TERMINATED', ev = OBSERVED) =>
  gov('SELECT bem_control.record_outbox_fence($1, $2, $3, $4, $5, $6, $7) AS e',
    [ids.tenantA, id, epoch, worker, RT1, method, ev]);

async function unknownRow(tag) {
  const id = await outboxRow(`zavod.fence.${tag}.${ids.run}`);
  const a = await claim('w1', '1 second', id);
  assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id, a.lease_epoch, 'w1', RT1])).ok, true);
  await sleep(1500);
  assert.equal(await claim('w2', '30 seconds', id), undefined);
  assert.equal((await rowOf(id)).status, 'UNKNOWN_OUTCOME');
  return { id, epoch: a.lease_epoch };
}

test('M-Z3-03 CONFIRMED_NOT_SENT без ограждения — отказ; ограждение сверяет поколение, исполнителя и доказательство', async () => {
  const { id, epoch } = await unknownRow('a');
  await assert.rejects(reconcile(id, 'CONFIRMED_NOT_SENT'), /RECONCILE_NOT_FENCED/);
  assert.equal((await rowOf(id)).status, 'UNKNOWN_OUTCOME');
  await assert.rejects(fence(id, Number(epoch) + 1, 'w1'), /FENCE_EPOCH_MISMATCH/);
  await assert.rejects(fence(id, epoch, 'w9'), /FENCE_WORKER_MISMATCH/);
  await assert.rejects(fence(id, epoch, 'w1', 'PROCESS_TERMINATED', {}), /FENCE_EVIDENCE_REQUIRED/);
  await assert.rejects(fence(id, epoch, 'w1', 'ASKED_NICELY'), /outbox_send_fence_method_check/);
  await assert.rejects(kq('SELECT bem_control.record_outbox_fence($1, $2, $3, $4, $5, $6, $7)',
    [ids.tenantA, id, epoch, 'w1', RT1, 'PROCESS_TERMINATED', OBSERVED]), (e) => e.code === '42501');
  assert.ok((await fence(id, epoch, 'w1')).e);
  assert.equal((await reconcile(id, 'CONFIRMED_NOT_SENT')).s, 'PENDING');
  // строка снова в очереди новым поколением; поздний старый исполнитель ничего не может
  const b = await claim('w2', '30 seconds', id);
  assert.ok(b);
  assert.equal(Number(b.lease_epoch), Number(epoch) + 1);
  assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id, epoch, 'w1', RT1])).ok, false);
  assert.equal((await kq('SELECT bem_control.finish_outbox_row($1, $2, $3, \'SENT\', $4) AS ok', [id, epoch, 'w1', {}])).ok, false);
  assert.deepEqual(await pinOf(id), { send_policy_version: null, send_policy_idempotent: false });
});

test('M-Z3-03 CONFIRMED_SENT и UNRESOLVED ограждения не требуют: строка не возвращается в очередь', async () => {
  const s = await unknownRow('s');
  assert.equal((await reconcile(s.id, 'CONFIRMED_SENT')).s, 'SENT');
  const u = await unknownRow('u');
  assert.equal((await reconcile(u.id, 'UNRESOLVED')).s, 'DEAD_LETTER');
});

test('M-Z2-02 доставщик Kernel ставит отметку до внешнего вызова', async () => {
  const id = await outboxRow(`zavod.dispatch.${ids.run}`);
  let markedAtCall = null;
  const d = await kernel.dispatchOnce(async (row) => {
    if (row.outbox_id === id) markedAtCall = (await rowOf(id)).send_started_epoch;
    return { outcome: 'SENT', detail: { stub: true } };
  }, { limit: 500 });
  assert.ok(d.results.some((x) => x.outbox_id === id && x.finished === true));
  assert.notEqual(markedAtCall, null, 'send_started_epoch set before egress call');
});
