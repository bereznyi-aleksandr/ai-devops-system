// ДОКУМЕНТ: tests/kernel.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 13:25 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: тесты Kernel этапа 3 (протокол Z1, E3-1, E3-4) на живом PG16 с пакетом H1.31.
// ЗАПУСК: PGHOST=127.0.0.1 PGPORT=54337 node --test tests/

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import pg from 'pg';
import { Kernel, KERNEL_ROLE } from '../src/kernel.mjs';
import { allowedFrom } from '../src/transitions.mjs';
import { CONN, bootFixture, withRole, assignAuditor, uuid } from './helpers.mjs';

let ids;
let kernel;
let stopFile;
const as = (actor) => ({ actor_id: actor });

before(async () => {
  ids = await bootFixture();
  // Стоп-файл живёт в папке прогона и не удаляется (P4.702): снятие — запись RUN.
  stopFile = join(mkdtempSync(join(tmpdir(), 'zavod-kernel-')), 'KERNEL_STOP');
  writeFileSync(stopFile, 'RUN\n');
  kernel = new Kernel({ connection: CONN, stopFile });
  await kernel.assertIdentity();
});
after(async () => { await kernel?.close(); });

async function newItem(tenant = ids.tenantA, actor = ids.author) {
  const wi = uuid();
  const r = await kernel.execute(as(actor), { type: 'CreateWorkItem', actor_id: actor, tenant_id: tenant,
    payload: { work_item_id: wi, evidence: { test: 'create' } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  return wi;
}
function move(wi, rev, status, extra = {}, actor = ids.author, tenant = ids.tenantA, commandId = uuid()) {
  return kernel.execute(as(actor), { type: 'Transition', actor_id: actor, tenant_id: tenant, command_id: commandId,
    payload: { work_item_id: wi, expected_revision: rev, new_status: status, evidence: { test: status }, ...extra } });
}

// ---------- E3-1: роль и единственный писатель ----------

test('E3-1a Kernel отказывается работать не ролью bem_kernel_rw', async () => {
  const pool = new pg.Pool({ ...CONN, user: 'postgres', max: 1 });
  const k = new Kernel({ pool });
  await assert.rejects(k.assertIdentity(), (e) => e.code === 'KERNEL_WRONG_ROLE');
  await pool.end();
});

test('E3-1b прямые INSERT/UPDATE ролью Kernel отклоняются базой (42501)', async () => {
  const wi = await newItem();
  const attempts = [
    ['INSERT work_item', `INSERT INTO bem_core.work_item (id, tenant_id, status) VALUES ('${uuid()}', '${ids.tenantA}', 'NEW')`],
    ['UPDATE work_item', `UPDATE bem_core.work_item SET status = 'RELEASED' WHERE id = '${wi}'`],
    ['INSERT outbox', `INSERT INTO bem_core.outbox (id, tenant_id, work_item_id, kind) VALUES ('${uuid()}', '${ids.tenantA}', '${wi}', 'x')`],
    ['INSERT evidence', `INSERT INTO bem_core.evidence (tenant_id, kind, payload) VALUES ('${ids.tenantA}', 'X', '{}')`],
    ['UPDATE subject.released_at', `UPDATE bem_core.subject SET released_at = now()`],
    ['DELETE evidence', `DELETE FROM bem_core.evidence`],
  ];
  await withRole(KERNEL_ROLE, async (c) => {
    await c.query("SELECT set_config('app.actor_id', $1, false), set_config('app.tenant_id', $2, false)", [ids.author, ids.tenantA]);
    for (const [name, sql] of attempts) {
      await assert.rejects(c.query(sql), (e) => e.code === '42501', `${name} must be denied`);
    }
  });
});

// ---------- переходы, повтор, изоляция ----------

test('переход по таблице Kernel: версия растёт, строка outbox рождается в той же транзакции', async () => {
  const wi = await newItem();
  const r1 = await move(wi, 1, 'PLANNED');
  assert.equal(r1.ok, true, JSON.stringify(r1.error));
  assert.equal(r1.result.new_revision, 2);
  assert.equal(r1.result.outbox_id, null);
  const r2 = await move(wi, 2, 'IN_PROGRESS', { outbox_kind: 'notify.send', outbox_payload: { text: 'started' } });
  assert.equal(r2.ok, true, JSON.stringify(r2.error));
  assert.ok(r2.result.outbox_id);
  const g = await kernel.execute(as(ids.author), { type: 'GetWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: wi } });
  assert.equal(g.result.status, 'IN_PROGRESS');
  assert.equal(g.result.revision, 3);
});

test('недопустимый переход отклоняется (NEW → ACCEPTED), состояние не меняется', async () => {
  const wi = await newItem();
  assert.deepEqual(allowedFrom('ACCEPTED'), ['IN_REVIEW']);
  const r = await move(wi, 1, 'ACCEPTED');
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'INVALID_TRANSITION');
  const g = await kernel.execute(as(ids.author), { type: 'GetWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: wi } });
  assert.equal(g.result.status, 'NEW');
  assert.equal(g.result.revision, 1);
});

test('устаревшая версия отклоняется', async () => {
  const wi = await newItem();
  assert.equal((await move(wi, 1, 'PLANNED')).ok, true);
  const r = await move(wi, 1, 'CANCELLED');
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'STALE_REVISION');
});

test('повтор той же команды не задваивает; та же команда с другим содержимым — отказ', async () => {
  const wi = await newItem();
  const cmd = uuid();
  const a = await move(wi, 1, 'PLANNED', { outbox_kind: 'notify.send', outbox_payload: { n: 1 } }, ids.author, ids.tenantA, cmd);
  const b = await move(wi, 1, 'PLANNED', { outbox_kind: 'notify.send', outbox_payload: { n: 1 } }, ids.author, ids.tenantA, cmd);
  assert.equal(a.ok, true, JSON.stringify(a.error));
  assert.equal(b.ok, true, JSON.stringify(b.error));
  assert.deepEqual(b.result, a.result);
  const c = await move(wi, 1, 'PLANNED', { outbox_kind: 'notify.send', outbox_payload: { n: 2 } }, ids.author, ids.tenantA, cmd);
  assert.equal(c.ok, false);
  assert.equal(c.error.code, 'COMMAND_ID_REUSED_WITH_DIFFERENT_PAYLOAD');
});

test('изоляция заказчиков: чужую работу не видно и не сдвинуть', async () => {
  const wiA = await newItem(ids.tenantA, ids.author);
  const g = await kernel.execute(as(ids.author), { type: 'GetWorkItem', actor_id: ids.author, tenant_id: ids.tenantB,
    payload: { work_item_id: wiA } });
  assert.equal(g.ok, false);
  assert.equal(g.error.code, 'NOT_FOUND');
  const m = await move(wiA, 1, 'PLANNED', {}, ids.author, ids.tenantB);
  assert.equal(m.ok, false);
  assert.equal(m.error.code, 'NOT_FOUND');
});

test('вызывающий не может выдать себя за другого участника', async () => {
  const r = await kernel.execute(as(ids.author2), { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: uuid(), evidence: {} } });
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'ACTOR_MISMATCH');
});

// ---------- SR-01 секреты ----------

test('SR-01 команда с ключом отклоняется до базы, значение не попадает в ответ', async () => {
  const fake = 'sk-ant-' + 'A'.repeat(40);
  const r = await kernel.execute(as(ids.author), { type: 'RecordEvidence', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { kind: 'NOTE', payload: { leaked: fake } } });
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'SECRET_IN_REQUEST');
  assert.ok(!JSON.stringify(r).includes(fake));
});

// ---------- SR-10 выключатель ----------

test('SR-10 стоп-файл закрывает приём команд без потери состояния; RUN открывает', async () => {
  const wi = await newItem();
  writeFileSync(stopFile, 'STOP\nоператор, тест\n');
  const r = await move(wi, 1, 'PLANNED');
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'KERNEL_STOPPED');
  assert.equal(kernel.health().stopped, true);
  const d = await kernel.dispatchOnce(async () => ({ outcome: 'SENT' }));
  assert.equal(d.stopped, true);
  writeFileSync(stopFile, 'RUN\n');
  const r2 = await move(wi, 1, 'PLANNED');
  assert.equal(r2.ok, true, JSON.stringify(r2.error));
});

// ---------- SR-11 решение оператора ----------

test('SR-11 решение оператора пишется только от человека', async () => {
  const bad = await kernel.execute(as(ids.author), { type: 'OperatorDecision', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { decision_code: 'OD-TEST' } });
  assert.equal(bad.ok, false);
  assert.equal(bad.error.code, 'OPERATOR_MUST_BE_HUMAN');
  const good = await kernel.execute(as(ids.humanA), { type: 'OperatorDecision', actor_id: ids.humanA, tenant_id: ids.tenantA,
    payload: { decision_code: 'OD-TEST', decision: 'APPROVE' } });
  assert.equal(good.ok, true, JSON.stringify(good.error));
  const spoof = await kernel.execute(as(ids.author), { type: 'RecordEvidence', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { kind: 'OPERATOR_DECISION', payload: {} } });
  assert.equal(spoof.ok, false);
  assert.equal(spoof.error.code, 'RESERVED_KIND');
});

// ---------- аудит H1.31 §9.4 ----------

test('§9.4 предмет протокола выпускается только при ACCEPT от {anthropic, openai}, автор себя не проверяет', async () => {
  const wi = await newItem();
  const subj = uuid();
  const head = 'sha-' + uuid().slice(0, 8);
  const pub = await kernel.execute(as(ids.author), { type: 'PublishSubject', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { subject_id: subj, work_item_id: wi, head_sha: head, criticality: 'CRITICAL', scope: 'BEM954_PROTOCOL',
      authors: [ids.author], evidence: { test: 'publish' } } });
  assert.equal(pub.ok, true, JSON.stringify(pub.error));

  const early = await kernel.execute(as(ids.author), { type: 'ReleaseSubject', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { subject_id: subj, head_sha: head } });
  assert.equal(early.ok, false, 'release without verdicts must fail');
  assert.equal(early.error.code, 'WAITING_AUDIT');

  const unassigned = await kernel.execute(as(ids.audOpenai), { type: 'RecordVerdict', actor_id: ids.audOpenai,
    tenant_id: ids.tenantA, payload: { subject_id: subj, head_sha: head, verdict: 'ACCEPT', evidence: { r: 1 } } });
  assert.equal(unassigned.ok, false, 'verdict from unassigned auditor must fail');
  assert.equal(unassigned.error.code, 'AUDITOR_NOT_ASSIGNED');

  await assignAuditor(ids.tenantA, subj, ids.audOpenai);
  await assignAuditor(ids.tenantA, subj, ids.audAnthropic);
  for (const aud of [ids.audOpenai, ids.audAnthropic]) {
    const v = await kernel.execute(as(aud), { type: 'RecordVerdict', actor_id: aud, tenant_id: ids.tenantA,
      payload: { subject_id: subj, head_sha: head, verdict: 'ACCEPT', evidence: { reviewed: head } } });
    assert.equal(v.ok, true, JSON.stringify(v.error));
  }
  const rel = await kernel.execute(as(ids.author), { type: 'ReleaseSubject', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { subject_id: subj, head_sha: head } });
  assert.equal(rel.ok, true, JSON.stringify(rel.error));
  assert.equal(rel.result.released, true);
});

// ---------- журнал расхода и доставщик ----------

test('журнал расхода пишется функцией record_usage', async () => {
  const wi = await newItem();
  const r = await kernel.execute(as(ids.author), { type: 'RecordUsage', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: wi, provider: 'anthropic', model: 'claude-subscription', input_tokens: 1200,
      output_tokens: 300, context_estimate: 5000, context_limit: 200000 } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
});

test('доставщик забирает строку outbox и фиксирует исход; неоднозначный исход не повторяется сам', async () => {
  const wi = await newItem();
  assert.equal((await move(wi, 1, 'PLANNED', { outbox_kind: 'notify.send', outbox_payload: { t: 'x' } })).ok, true);
  const seen = [];
  const d = await kernel.dispatchOnce(async (row) => {
    seen.push(row.outbox_id);
    if (seen.length === 1) return { outcome: 'SENT', detail: { stub: true } };
    throw new Error('timeout after send');
  }, { limit: 50 });
  assert.equal(d.stopped, false);
  assert.ok(d.claimed >= 1);
  assert.ok(d.results.every((x) => x.finished === true));
  const again = await kernel.dispatchOnce(async () => ({ outcome: 'SENT' }), { limit: 50 });
  const repeated = again.results.filter((x) => seen.includes(x.outbox_id));
  assert.equal(repeated.length, 0, 'finished rows are not claimed again');
});
