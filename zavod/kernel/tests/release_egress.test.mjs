// ДОКУМЕНТ: tests/release_egress.test.mjs
// ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:37 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 13:17 +03:00 (v0.3: E5-2 выгрузка авторства живого предмета; E5-7 манифест другого репозитория;
//   E5-3 предмет BEM954_PROTOCOL с парой ACCEPT; v0.2: слияние с аудитом E4-6
//   M-E46-02 — явная роль вызывающего в каждой команде)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: E5-7 и §5.2 протокола Z1 v1.9 на Kernel (PG16 + Z-EXT-01): выпуск продукта по цепочке
//   «предмет ZAVOD_PRODUCT_RELEASE → ACCEPT {anthropic, openai} → выпуск → решение оператора-человека →
//   Evidence манифеста → переход со строкой outbox». Egress берёт строку claim_outbox_batch, читает строки
//   из Kernel (loadReleaseRows) и сверяет их до внешнего вызова. Отказы: подмена байта артефакта, манифест
//   другого заказчика, другого заказа, предмет WORKING с одним ACCEPT, без решения оператора, ссылка без
//   манифеста. Внешний вызов — заглушка со счётчиком: при отказе вызовов 0. Evidence манифеста не правится.
// ОГРАНИЧЕНИЯ: стенд PG16 с Z-EXT-01 (как ext01.test.mjs). Чужие строки outbox, попавшие в выборку, тест
//   закрывает FAILED, как tests/egress_matrix.test.mjs.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { Kernel } from '../src/kernel.mjs';
import { CONN, bootFixture, withRole, assignAuditor, runStopFile, uuid } from './helpers.mjs';
import { sealManifest, loadReleaseRows, releaseViaEgress, MANIFEST_KIND, RELEASE_SCOPE } from '../src/release_manifest.mjs';
import { checkAuthorship, loadAuthorship } from '../src/authorship_check.mjs';

let ids;
let kernel;
const sha = (b) => createHash('sha256').update(b).digest('hex');
const ARTIFACT = Buffer.from('zavod p1 bot release artifact\n'.repeat(32));
const KIND = 'zavod.product.release';
const WORKER = 'egress:e57';

before(async () => {
  ids = await bootFixture();
  kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-e57-') });
  await kernel.assertIdentity();
});
after(async () => { await kernel?.close(); });

// M-E46-02: роль вызывающего обязательна — по таблице 3.1: вердикт — auditor, решение — operator, остальное — kernel.
const ROLE_OF = { RecordVerdict: 'auditor', OperatorDecision: 'operator' };
async function ex(actor, type, payload, { tenant = ids.tenantA, command_id } = {}) {
  const r = await kernel.execute({ actor_id: actor, role: ROLE_OF[type] || 'kernel' }, { type, actor_id: actor, tenant_id: tenant, payload,
    ...(command_id ? { command_id } : {}) });
  assert.equal(r.ok, true, `${type}: ${JSON.stringify(r.error)}`);
  return r.result;
}

// Выпущенный предмет: scope и число ACCEPT задаются; вердикты — проверяющие, не автор.
async function releasedSubject(tenant, scope = RELEASE_SCOPE, auditors = ['audOpenai', 'audAnthropic'], criticality = 'NORMAL') {
  const wi = uuid();
  await ex(ids.author, 'CreateWorkItem', { work_item_id: wi, evidence: { test: 'E5-7' } }, { tenant });
  const subj = uuid();
  const head = sha(subj).slice(0, 40);
  await ex(ids.author, 'PublishSubject', { subject_id: subj, work_item_id: wi, head_sha: head, criticality,
    scope, authors: [ids.author], evidence: { test: 'E5-7' } }, { tenant });
  for (const a of auditors) {
    await assignAuditor(tenant, subj, ids[a]);
    await ex(ids[a], 'RecordVerdict', { subject_id: subj, head_sha: head, verdict: 'ACCEPT', evidence: { reviewed: head } },
      { tenant });
  }
  const rel = await ex(ids.author, 'ReleaseSubject', { subject_id: subj, head_sha: head }, { tenant });
  assert.equal(rel.released, true);
  return { wi, subj, head };
}

const human = (tenant) => (tenant === ids.tenantB ? ids.humanB : ids.humanA);
async function decision(tenant, s, code = RELEASE_SCOPE) {
  return (await ex(human(tenant), 'OperatorDecision', { decision_code: code,
    decision: { subject_id: s.subj, head_sha: s.head }, note: 'E5-7 test' }, { tenant })).evidence_id;
}

// Полная цепочка; over — подмены для отрицательных случаев.
async function chain(over = {}) {
  const tenant = ids.tenantA;
  const s = over.subject || await releasedSubject(tenant);
  const decisionId = over.decisionId || await decision(tenant, s);
  const cmd = uuid();
  const manifest = sealManifest({
    repo_id: 812345678, repo_full_name: 'zavod-products/p1-bot', tenant_id: tenant, work_item_id: s.wi,
    subject_id: s.subj, head_sha: s.head, lock_sha256: sha('package-lock'), artifact_sha256: sha(ARTIFACT),
    build_run: 37900000001, test_run: 37900000002, verdict_ids: [uuid(), uuid()],
    outbox_command_id: cmd, decision_evidence_id: decisionId, ...(over.manifest || {}),
  });
  const manifestTenant = over.manifestTenant || tenant;
  const manifestId = (await ex(ids.author, 'RecordEvidence', { kind: MANIFEST_KIND, payload: manifest },
    { tenant: manifestTenant })).evidence_id;
  const t = await ex(ids.author, 'Transition', { work_item_id: s.wi, expected_revision: 1, new_status: 'PLANNED',
    evidence: { test: 'E5-7' }, outbox_kind: KIND, outbox_payload: {
      manifest_evidence_id: over.noManifestRef ? null : manifestId, manifest_sha256: manifest.manifest_sha256,
      repo_id: 812345678, repo_full_name: 'zavod-products/p1-bot', artifact_sha256: manifest.artifact_sha256 } },
  { tenant, command_id: cmd });
  return { outboxId: t.outbox_id, manifestId };
}

async function claim(mine) {
  return withRole('bem_kernel_rw', async (c) => {
    const { rows } = await c.query("SELECT * FROM bem_control.claim_outbox_batch(500, '5 minutes'::interval, $1)", [WORKER]);
    for (const x of rows.filter((x) => x.outbox_id !== mine)) {
      await c.query("SELECT bem_control.finish_outbox_row($1, $2, $3, 'FAILED', $4)",
        [x.outbox_id, x.lease_epoch, WORKER, { released_by_test: 'E5-7' }]);
    }
    const row = rows.find((x) => x.outbox_id === mine);
    assert.ok(row, 'own outbox row claimed');
    return row;
  });
}

let calls = 0;
const send = async () => { calls += 1; return { sent: true }; };

async function egress(outboxId, artifact = Buffer.from(ARTIFACT)) {
  const claimed = await claim(outboxId);
  const rows = await withRole('bem_kernel_rw', (c) => loadReleaseRows(c, claimed));
  return releaseViaEgress({ ...rows, artifact }, send);
}
async function refused(outboxId, code, artifact) {
  const before = calls;
  await assert.rejects(egress(outboxId, artifact), (e) => e.code === code, code);
  assert.equal(calls, before, `${code}: external call before refusal`);
}

test('E5-7 точный манифест: Egress сверил строки Kernel и сделал один внешний вызов', async () => {
  const { outboxId } = await chain();
  const before = calls;
  assert.deepEqual(await egress(outboxId), { sent: true });
  assert.equal(calls, before + 1);
});

test('E5-7 подмена одного байта артефакта после ACCEPT — отказ до вызова', async () => {
  const { outboxId } = await chain();
  const bad = Buffer.from(ARTIFACT); bad[bad.length >> 1] ^= 0x01;
  await refused(outboxId, 'ARTIFACT_MISMATCH', bad);
});

test('E5-7 манифест другого заказчика — отказ до вызова', async () => {
  // Evidence манифеста записан у заказчика B; строка outbox — у A. RLS и сверка tenant_id не дают его взять.
  const { outboxId } = await chain({ manifestTenant: ids.tenantB });
  await refused(outboxId, 'NO_MANIFEST');
});

test('E5-7 манифест другого заказа — отказ до вызова', async () => {
  const other = uuid();
  await ex(ids.author, 'CreateWorkItem', { work_item_id: other, evidence: { test: 'E5-7' } });
  const { outboxId } = await chain({ manifest: { work_item_id: other } });
  await refused(outboxId, 'ORDER_MISMATCH');
});

test('§5.2 предмет WORKING, выпущенный одним ACCEPT, — отказ до вызова', async () => {
  const s = await releasedSubject(ids.tenantA, 'WORKING', ['audOpenai']);
  const { outboxId } = await chain({ subject: s });
  await refused(outboxId, 'BAD_SCOPE');
});

test('§5.2 строка без решения оператора-человека — отказ до вызова', async () => {
  const s = await releasedSubject(ids.tenantA);
  const note = (await ex(ids.author, 'RecordEvidence', { kind: 'NOTE', payload: { subject_id: s.subj } })).evidence_id;
  const { outboxId } = await chain({ subject: s, decisionId: note });
  await refused(outboxId, 'NO_OPERATOR_DECISION');
  const s2 = await releasedSubject(ids.tenantA);
  const other = await decision(ids.tenantA, s2, 'OD-OTHER');
  const r2 = await chain({ subject: s2, decisionId: other });
  await refused(r2.outboxId, 'NO_OPERATOR_DECISION');
});

test('E5-7 верный артефакт, манифест другого репозитория — отказ до вызова', async () => {
  const { outboxId } = await chain({ manifest: { repo_id: 900000001, repo_full_name: 'other-org/other-bot' } });
  await refused(outboxId, 'REPO_MISMATCH');
});

test('E5-3 предмет BEM954_PROTOCOL, выпущенный парой ACCEPT, — отказ до вызова', async () => {
  const s = await releasedSubject(ids.tenantA, 'BEM954_PROTOCOL', ['audOpenai', 'audAnthropic'], 'CRITICAL');
  const { outboxId } = await chain({ subject: s });
  await refused(outboxId, 'BAD_SCOPE');
});

test('E5-2 выгрузка авторства выпущенного предмета из Kernel — PASS, сумма SHA-256', async () => {
  const s = await releasedSubject(ids.tenantA);
  const rows = await withRole('bem_kernel_rw', (c) => loadAuthorship(c, ids.tenantA, s.subj));
  assert.equal(rows.subject.head_sha, s.head);
  assert.deepEqual(rows.authors.map((a) => a.actor_id), [ids.author]);
  const r = checkAuthorship(rows);
  assert.deepEqual(r.problems, []);
  assert.match(r.sha256, /^[0-9a-f]{64}$/);
});

test('SR-13 строка outbox без ссылки на манифест — отказ до вызова', async () => {
  const { outboxId } = await chain({ noManifestRef: true });
  await refused(outboxId, 'NO_MANIFEST');
});

test('SR-13 Evidence манифеста не правится и не удаляется ролью Kernel', async () => {
  const { manifestId } = await chain();
  for (const sql of ["UPDATE bem_core.evidence SET payload = '{}'::jsonb WHERE id = $1",
    'DELETE FROM bem_core.evidence WHERE id = $1']) {
    await assert.rejects(withRole('bem_kernel_rw', async (c) => {
      await c.query("SELECT set_config('app.tenant_id', $1, false)", [ids.tenantA]);
      await c.query(sql, [manifestId]);
    }), /permission denied|EVIDENCE|append/i, sql);
  }
});
