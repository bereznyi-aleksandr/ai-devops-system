// ДОКУМЕНТ: zavod/engine/tests/product_egress.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 08:16 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: модульная проверка src/product_egress.mjs v0.1 без сети и базы: точный выпуск — один вызов;
//   подмена байта, чужой репозиторий (в том числе согласованный в манифесте и outbox), чужой заказчик,
//   чужой заказ — отказ до внешнего вызова (счётчик вызовов не растёт). Строки собраны в памяти по форме
//   release_manifest.loadReleaseRows; та же сверка на строках Kernel — ci/e5_egress_refusals.mjs.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { sealManifest, verifyRelease, RELEASE_SCOPE } from '../../kernel/src/release_manifest.mjs';
import { productEgress } from '../src/product_egress.mjs';

const sha = (b) => createHash('sha256').update(b).digest('hex');
const ARTIFACT = Buffer.from('product tar bytes '.repeat(64));
const TARGET = { repo_id: 1412203481, repo_full_name: 'bereznyi-aleksandr/zavod-p1-bot' };
const FOREIGN = { repo_id: 900000001, repo_full_name: 'other-org/other-bot' };

function rows(over = {}) {
  const tenant = randomUUID(), wi = randomUUID(), subj = randomUUID(), head = 'a'.repeat(40);
  const cmd = randomUUID(), dec = randomUUID();
  const repo = over.repo || TARGET;
  const manifest = sealManifest({ ...repo, tenant_id: over.manifestTenant || tenant, work_item_id: over.manifestWi || wi,
    subject_id: subj, head_sha: head, lock_sha256: sha('lock'), artifact_sha256: sha(ARTIFACT), build_run: 1, test_run: 2,
    verdict_ids: [randomUUID(), randomUUID()], outbox_command_id: cmd, decision_evidence_id: dec });
  const payloadRepo = over.payloadRepo || repo;
  return {
    manifest,
    artifact: Buffer.from(ARTIFACT),
    subject: { id: subj, tenant_id: tenant, work_item_id: wi, head_sha: head, scope: RELEASE_SCOPE, released_at: new Date() },
    outbox: { id: randomUUID(), tenant_id: tenant, work_item_id: wi, command_id: cmd, kind: 'zavod.product.release',
      payload: { ...payloadRepo, manifest_sha256: manifest.manifest_sha256, artifact_sha256: manifest.artifact_sha256 } },
    decision: { id: dec, tenant_id: tenant, kind: 'OPERATOR_DECISION', actor_id: 'human:op', provider: 'human',
      payload: { decision_code: RELEASE_SCOPE, decision: { subject_id: subj, head_sha: head } } },
  };
}

let calls = 0;
const send = async ({ manifest_sha256 }) => { calls += 1; return { ok: true, manifest_sha256 }; };
const eg = productEgress(TARGET);
async function refused(r, code) {
  const before = calls;
  await assert.rejects(eg.release(r, send), (e) => e.code === code, code);
  assert.equal(calls, before, `${code}: external call before refusal`);
}

test('точный выпуск: сверка пройдена, внешний вызов ровно один', async () => {
  const r = rows();
  const before = calls;
  assert.deepEqual(await eg.release(r, send), { ok: true, manifest_sha256: r.manifest.manifest_sha256 });
  assert.equal(calls, before + 1);
});

test('подмена одного байта артефакта — ARTIFACT_MISMATCH до вызова', async () => {
  const r = rows();
  r.artifact[r.artifact.length >> 1] ^= 0x01;
  await refused(r, 'ARTIFACT_MISMATCH');
});

test('манифест и outbox согласованно называют чужой репозиторий — TARGET_MISMATCH до вызова', async () => {
  const r = rows({ repo: FOREIGN });
  assert.equal(verifyRelease(r), r.manifest.manifest_sha256, 'строки Kernel между собой согласованы — без цели адаптера сверка прошла бы');
  await refused(r, 'TARGET_MISMATCH');
});

test('манифест называет цель, строка outbox — чужой репозиторий — REPO_MISMATCH до вызова', async () => {
  await refused(rows({ payloadRepo: FOREIGN }), 'REPO_MISMATCH');
});

test('манифест другого заказчика — TENANT_MISMATCH до вызова', async () => {
  await refused(rows({ manifestTenant: randomUUID() }), 'TENANT_MISMATCH');
});

test('манифест другого заказа — ORDER_MISMATCH до вызова', async () => {
  await refused(rows({ manifestWi: randomUUID() }), 'ORDER_MISMATCH');
});

test('цель адаптера проверяется при создании и не меняется', () => {
  assert.throws(() => productEgress({ repo_id: 0, repo_full_name: 'a/b' }), TypeError);
  assert.throws(() => productEgress({ repo_id: 1, repo_full_name: 'no-slash' }), TypeError);
  assert.ok(Object.isFrozen(eg.target));
});
