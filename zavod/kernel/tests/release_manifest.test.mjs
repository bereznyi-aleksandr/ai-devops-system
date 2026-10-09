// ДОКУМЕНТ: tests/release_manifest.test.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:36 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 07:55 +03:00 (v0.2: строка outbox по command_id)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: критерий E5-7 протокола Z1 v1.9 (SR-13, T14) на уровне сверки: подмена одного байта
//   артефакта после ACCEPT блокирует выпуск; верный артефакт с манифестом другого репозитория, tenant_id
//   или заказа блокирует выпуск; точный манифест проходит. Внешний вызов считается заглушкой: при любом
//   отказе вызовов 0 (отказ до внешнего действия). Плюс раздел 5.2: предмет WORKING и BEM954_PROTOCOL,
//   невыпущенный предмет и строка без решения оператора-человека отклоняются.
// ОГРАНИЧЕНИЯ: без базы; строки предмета, outbox и Evidence собраны в тесте. Сверка со строками Kernel —
//   при подключении к Egress выпуска (этап 5, следующий шаг).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { sealManifest, verifyRelease, releaseViaEgress, canonical } from '../src/release_manifest.mjs';

const sha = (b) => createHash('sha256').update(b).digest('hex');
const ARTIFACT = Buffer.from('zavod-p1-bot build output\n'.repeat(64));
const T = randomUUID(); const W = randomUUID(); const S = randomUUID();
const O = randomUUID(); const D = randomUUID();
const HEAD = 'a'.repeat(40);

function rows() {
  const manifest = sealManifest({
    repo_id: 812345678, repo_full_name: 'zavod-products/p1-bot', tenant_id: T, work_item_id: W,
    subject_id: S, head_sha: HEAD, lock_sha256: sha('lock'), artifact_sha256: sha(ARTIFACT),
    build_run: 37900000001, test_run: 37900000002, verdict_ids: [randomUUID(), randomUUID()],
    outbox_command_id: O, decision_evidence_id: D,
  });
  return {
    manifest,
    artifact: Buffer.from(ARTIFACT),
    subject: { id: S, scope: 'ZAVOD_PRODUCT_RELEASE', released_at: '2026-10-09T04:30:00Z', head_sha: HEAD,
      tenant_id: T, work_item_id: W },
    outbox: { id: randomUUID(), command_id: O, tenant_id: T, work_item_id: W, kind: 'ZAVOD_PRODUCT_RELEASE',
      payload: { repo_id: 812345678, repo_full_name: 'zavod-products/p1-bot',
        manifest_sha256: manifest.manifest_sha256, artifact_sha256: manifest.artifact_sha256 } },
    decision: { id: D, kind: 'OPERATOR_DECISION', tenant_id: T, actor_id: 'human:operator', provider: 'human',
      payload: { decision_code: 'ZAVOD_PRODUCT_RELEASE', decision: { subject_id: S, head_sha: HEAD } } },
  };
}

// Внешняя сторона-заглушка со счётчиком вызовов.
let calls = 0;
const send = async () => { calls += 1; return { sent: true }; };

async function refused(r, code) {
  const before = calls;
  await assert.rejects(releaseViaEgress(r, send), (e) => e.code === code);
  assert.equal(calls, before, `${code}: внешний вызов до отказа`);
}

test('E5-7 точный манифест проходит, ровно один внешний вызов', async () => {
  const before = calls;
  const r = rows();
  assert.deepEqual(await releaseViaEgress(r, send), { sent: true });
  assert.equal(calls, before + 1);
  assert.equal(verifyRelease(r), r.manifest.manifest_sha256);
});

test('E5-7 подмена одного байта артефакта после ACCEPT — отказ', async () => {
  for (const i of [0, ARTIFACT.length >> 1, ARTIFACT.length - 1]) {
    const r = rows(); r.artifact[i] ^= 0x01;
    await refused(r, 'ARTIFACT_MISMATCH');
  }
  const r = rows(); r.artifact = Buffer.concat([r.artifact, Buffer.from([0])]);
  await refused(r, 'ARTIFACT_MISMATCH');
});

test('E5-7 верный артефакт, манифест другого репозитория — отказ', async () => {
  const r = rows(); r.outbox.payload.repo_full_name = 'zavod-products/other-bot';
  await refused(r, 'REPO_MISMATCH');
  const r2 = rows(); r2.outbox.payload.repo_id = 812345679;
  await refused(r2, 'REPO_MISMATCH');
  // Манифест честно собран на другой репозиторий: печать верна, строка outbox — на этот.
  const r3 = rows();
  r3.manifest = sealManifest({ ...r3.manifest, repo_full_name: 'zavod-products/other-bot', manifest_sha256: undefined });
  r3.outbox.payload.manifest_sha256 = r3.manifest.manifest_sha256;
  await refused(r3, 'REPO_MISMATCH');
});

test('E5-7 верный артефакт, манифест другого tenant_id или заказа — отказ', async () => {
  const other = randomUUID();
  for (const [field, code] of [['tenant_id', 'TENANT_MISMATCH'], ['work_item_id', 'ORDER_MISMATCH']]) {
    const r = rows();
    const { manifest_sha256, ...b } = r.manifest;
    r.manifest = sealManifest({ ...b, [field]: other });
    r.outbox.payload.manifest_sha256 = r.manifest.manifest_sha256;
    await refused(r, code);
    const r2 = rows(); r2.outbox[field] = other;
    await refused(r2, code);
  }
});

test('SR-13 правка поля манифеста без новой печати — отказ', async () => {
  for (const [k, v] of [['repo_full_name', 'x/y'], ['build_run', 1], ['lock_sha256', sha('other lock')],
    ['verdict_ids', [randomUUID()]]]) {
    const r = rows(); r.manifest = { ...r.manifest, [k]: v };
    await refused(r, 'MANIFEST_TAMPERED');
  }
  const r = rows(); r.manifest = { ...r.manifest, extra: 1 };
  await refused(r, 'BAD_MANIFEST');
  const r2 = rows(); r2.outbox.payload.manifest_sha256 = sha('x');
  await refused(r2, 'MANIFEST_MISMATCH');
  const r3 = rows(); r3.outbox.payload.artifact_sha256 = sha('x');
  await refused(r3, 'ARTIFACT_MISMATCH');
});

test('§5.2 предмет WORKING и BEM954_PROTOCOL, невыпущенный и чужой предмет — отказ', async () => {
  for (const scope of ['WORKING', 'BEM954_PROTOCOL']) {
    const r = rows(); r.subject.scope = scope;
    await refused(r, 'BAD_SCOPE');
  }
  const r = rows(); r.subject.released_at = null;
  await refused(r, 'NOT_RELEASED');
  const r2 = rows(); r2.subject.head_sha = 'b'.repeat(40);
  await refused(r2, 'HEAD_MISMATCH');
  const r3 = rows(); r3.subject.id = randomUUID();
  await refused(r3, 'SUBJECT_MISMATCH');
  const r4 = rows(); r4.outbox.command_id = randomUUID();
  await refused(r4, 'OUTBOX_MISMATCH');
});

test('§5.2 строка без решения оператора-человека — отказ', async () => {
  const cases = [
    (r) => { r.decision = null; },
    (r) => { r.decision.kind = 'NOTE'; },
    (r) => { r.decision.id = randomUUID(); },
    (r) => { r.decision.provider = 'anthropic'; r.decision.actor_id = 'claude:worker'; },
    (r) => { r.decision.actor_id = 'claude:worker'; },
    (r) => { r.decision.tenant_id = randomUUID(); },
    (r) => { r.decision.payload.decision.subject_id = randomUUID(); },
    (r) => { r.decision.payload.decision.head_sha = 'c'.repeat(40); },
    (r) => { r.decision.payload.decision_code = 'OD-8'; },
  ];
  for (const mutate of cases) {
    const r = rows(); mutate(r);
    await refused(r, 'NO_OPERATOR_DECISION');
  }
});

test('канонический текст не зависит от порядка ключей', () => {
  assert.equal(canonical({ b: 1, a: [{ d: 2, c: 3 }] }), canonical({ a: [{ c: 3, d: 2 }], b: 1 }));
});
