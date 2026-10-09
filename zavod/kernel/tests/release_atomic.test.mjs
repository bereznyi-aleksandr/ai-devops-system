// ДОКУМЕНТ: tests/release_atomic.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 10:52 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 10:52 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: аудит E4-6, M-E46-01 (§12.2 узел 17): команда Kernel ReleaseAndTransition выпускает предмет,
//   переводит работу в RELEASED и создаёт строку outbox в одной транзакции. Проверки: (1) сбой после выпуска
//   и до COMMIT — нет ни выпуска, ни перехода, ни outbox, ни записи команды; (2) повтор того же command_id —
//   та же строка outbox, второй нет; (3) обычный Transition в RELEASED запрещён; (4) чужой предмет и
//   предмет, выпущенный раньше отдельной командой, — отказ без изменений.
// ОГРАНИЧЕНИЯ: стенд PG16 с H1.31 + Z-EXT-01, как остальные тесты Kernel.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { Kernel } from '../src/kernel.mjs';
import { CONN, bootFixture, withRole, assignAuditor, runStopFile, uuid } from './helpers.mjs';

const KIND = 'zavod.e43.deliver';
let ids;
let kernel;
before(async () => {
  ids = await bootFixture();
  kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-m46-01-') });
  await kernel.assertIdentity();
});
after(async () => { await kernel?.close(); });

const run = (k, role, actor, type, payload, command_id) => k.execute({ actor_id: actor, role },
  { type, actor_id: actor, tenant_id: ids.tenantA, ...(command_id ? { command_id } : {}), payload });
const ok = (r) => { assert.equal(r.ok, true, JSON.stringify(r.error)); return r.result; };

// Работа в ACCEPTED и предмет ZAVOD_PRODUCT_RELEASE с ACCEPT от {anthropic, openai}: готово к узлу 17.
async function readyToRelease() {
  const wi = uuid();
  ok(await run(kernel, 'kernel', ids.author, 'CreateWorkItem', { work_item_id: wi, evidence: { t: 'm46-01' } }));
  let rev = 1;
  for (const st of ['PLANNED', 'IN_PROGRESS', 'IN_REVIEW', 'ACCEPTED']) {
    rev = ok(await run(kernel, 'kernel', ids.author, 'Transition', { work_item_id: wi, expected_revision: rev,
      new_status: st, evidence: { t: st } }, uuid())).new_revision;
  }
  const subj = uuid();
  const head = 'sha-' + uuid().slice(0, 8);
  ok(await run(kernel, 'kernel', ids.author, 'PublishSubject', { subject_id: subj, work_item_id: wi, head_sha: head,
    criticality: 'CRITICAL', scope: 'ZAVOD_PRODUCT_RELEASE', authors: [ids.author], evidence: { t: 'publish' } }));
  for (const aud of [ids.audOpenai, ids.audAnthropic]) {
    await assignAuditor(ids.tenantA, subj, aud);
    ok(await run(kernel, 'auditor', aud, 'RecordVerdict', { subject_id: subj, head_sha: head, verdict: 'ACCEPT',
      evidence: { reviewed: head } }));
  }
  return { wi, subj, head, rev };
}

const releaseReq = (x, extra = {}) => ({ work_item_id: x.wi, subject_id: x.subj, head_sha: x.head,
  expected_revision: x.rev, outbox_kind: KIND, outbox_payload: { subject_id: x.subj, head_sha: x.head },
  evidence: { t: 'n17' }, ...extra });

// Состояние из базы ролью postgres (мимо RLS): выпуск, статус, строки outbox и запись команды.
const facts = (x, commandId) => withRole('postgres', async (c) => {
  const s = (await c.query('SELECT released_at FROM bem_core.subject WHERE id = $1', [x.subj])).rows[0];
  const w = (await c.query('SELECT status, revision FROM bem_core.work_item WHERE id = $1', [x.wi])).rows[0];
  const o = (await c.query('SELECT count(*)::int AS n FROM bem_core.outbox WHERE work_item_id = $1', [x.wi])).rows[0].n;
  const l = (await c.query('SELECT count(*)::int AS n FROM bem_core.command_log WHERE command_id = $1', [commandId])).rows[0].n;
  return { released: s.released_at !== null, status: w.status, revision: w.revision, outbox: o, log: l };
});

test('M-E46-01: сбой после выпуска и до COMMIT — всё или ничего; затем штатный выпуск и честный повтор', async () => {
  const x = await readyToRelease();
  const cmd = uuid();
  let injected = 0;
  const faulty = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-m46-01f-'),
    testBeforeCommit: (out) => { if (out && out.outbox_id) { injected += 1; throw new Error('FAULT_INJECTED: before COMMIT'); } } });
  try {
    const r = await run(faulty, 'kernel', ids.author, 'ReleaseAndTransition', releaseReq(x), cmd);
    assert.equal(r.ok, false);
    assert.equal(r.error.code, 'FAULT_INJECTED');
  } finally { await faulty.close(); }
  assert.equal(injected, 1, 'fault fired after release and outbox were written');
  assert.deepEqual(await facts(x, cmd), { released: false, status: 'ACCEPTED', revision: x.rev, outbox: 0, log: 0 });

  const first = ok(await run(kernel, 'kernel', ids.author, 'ReleaseAndTransition', releaseReq(x), cmd));
  assert.equal(first.released, true);
  assert.equal(first.replay, false);
  assert.ok(first.outbox_id);
  assert.deepEqual(await facts(x, cmd), { released: true, status: 'RELEASED', revision: x.rev + 1, outbox: 1, log: 1 });

  const again = ok(await run(kernel, 'kernel', ids.author, 'ReleaseAndTransition', releaseReq(x), cmd));
  assert.equal(again.replay, true);
  assert.equal(again.released, false);
  assert.equal(again.outbox_id, first.outbox_id);
  assert.deepEqual(await facts(x, cmd), { released: true, status: 'RELEASED', revision: x.rev + 1, outbox: 1, log: 1 });

  // Новый command_id по уже выпущенному предмету — отказ, второй строки outbox нет.
  const cmd2 = uuid();
  const dup = await run(kernel, 'kernel', ids.author, 'ReleaseAndTransition', releaseReq(x), cmd2);
  assert.equal(dup.ok, false);
  assert.equal(dup.error.code, 'ALREADY_RELEASED');
  assert.equal((await facts(x, cmd2)).outbox, 1);
});

test('M-E46-01: обход узла 17 закрыт — Transition в RELEASED, чужой предмет, раздельный выпуск', async () => {
  const x = await readyToRelease();
  const tr = await run(kernel, 'kernel', ids.author, 'Transition', { work_item_id: x.wi, expected_revision: x.rev,
    new_status: 'RELEASED', evidence: { t: 'bypass' }, outbox_kind: KIND, outbox_payload: {} }, uuid());
  assert.equal(tr.error.code, 'RELEASE_VIA_RELEASE_COMMAND');

  const other = await readyToRelease();
  const cmd = uuid();
  const wrong = await run(kernel, 'kernel', ids.author, 'ReleaseAndTransition', releaseReq(x, { subject_id: other.subj,
    head_sha: other.head }), cmd);
  assert.equal(wrong.error.code, 'SUBJECT_WORK_MISMATCH');
  assert.deepEqual(await facts(x, cmd), { released: false, status: 'ACCEPTED', revision: x.rev, outbox: 0, log: 0 });
  assert.equal((await facts(other, cmd)).released, false);

  // Предмет выпущен отдельной командой (старый путь) — узел 17 его не «довыпускает».
  ok(await run(kernel, 'kernel', ids.author, 'ReleaseSubject', { subject_id: x.subj, head_sha: x.head }));
  const late = await run(kernel, 'kernel', ids.author, 'ReleaseAndTransition', releaseReq(x), cmd);
  assert.equal(late.error.code, 'ALREADY_RELEASED');
  assert.deepEqual(await facts(x, cmd), { released: true, status: 'ACCEPTED', revision: x.rev, outbox: 0, log: 0 });

  // Команда выпуска — только у роли kernel.
  for (const role of ['director_production', 'auditor', 'operator', 'analyst_executor']) {
    const r = await run(kernel, role, ids.author, 'ReleaseAndTransition', releaseReq(other), uuid());
    assert.equal(r.error.code, 'ROLE_FORBIDDEN', role);
  }
});
