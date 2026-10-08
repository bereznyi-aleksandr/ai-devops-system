// ДОКУМЕНТ: tests/kernel.test.mjs
// ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 23:30 +03:00 (v0.3: аудит E3-5 —
//   M-E35-01: подмена входа после старта ловится в каждой команде и каждом проходе доставщика;
//   M-E35-05: SR-10 закрыт по умолчанию, server.mjs без стоп-файла не стартует;
//   v0.2: отрицательные случаи §6.1 для обеих областей)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: тесты Kernel этапа 3 (протокол Z1, E3-1, E3-4) на живом PG16 с пакетом H1.31.
// ЗАПУСК: PGHOST=127.0.0.1 PGPORT=54337 node --test tests/

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import pg from 'pg';
import { stopState } from '../src/guards.mjs';
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

// ---------- §6.1 протокола Z1 v1.2: отрицательные случаи серверного выпуска ----------
// Каждый случай — для обеих областей с правилом ровно {anthropic, openai}: протокол BEM954_PROTOCOL
// (H1.31 §13.5) и выпуск продукта ZAVOD_PRODUCT_RELEASE (Z-EXT-01, аудит Z2 M-Z2-01).

async function publishProtocolSubject(authors = [ids.author], scope = 'BEM954_PROTOCOL') {
  const wi = await newItem();
  const subj = uuid();
  const head = 'sha-' + uuid().slice(0, 8);
  const pub = await kernel.execute(as(ids.author), { type: 'PublishSubject', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { subject_id: subj, work_item_id: wi, head_sha: head, criticality: 'CRITICAL', scope,
      authors, evidence: { test: 'publish' } } });
  assert.equal(pub.ok, true, JSON.stringify(pub.error));
  return { subj, head };
}
const verdict = (aud, subj, head, v = 'ACCEPT') => kernel.execute(as(aud), { type: 'RecordVerdict', actor_id: aud,
  tenant_id: ids.tenantA, payload: { subject_id: subj, head_sha: head, verdict: v, evidence: { reviewed: head } } });
const release = (subj, head) => kernel.execute(as(ids.author), { type: 'ReleaseSubject', actor_id: ids.author,
  tenant_id: ids.tenantA, payload: { subject_id: subj, head_sha: head } });

for (const scope of ['BEM954_PROTOCOL', 'ZAVOD_PRODUCT_RELEASE']) {
test(`§6.1 ${scope}: один ACCEPT (только openai) — выпуск отклонён`, async () => {
  const { subj, head } = await publishProtocolSubject(undefined, scope);
  await assignAuditor(ids.tenantA, subj, ids.audOpenai);
  assert.equal((await verdict(ids.audOpenai, subj, head)).ok, true);
  const r = await release(subj, head);
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'BEM954_PROVIDER_SET_MISMATCH');
});

test(`§6.1 ${scope}: вердикт по другой версии не принимается, выпуск по чужой версии отклонён`, async () => {
  const { subj, head } = await publishProtocolSubject(undefined, scope);
  await assignAuditor(ids.tenantA, subj, ids.audOpenai);
  const v = await verdict(ids.audOpenai, subj, head + '-other');
  assert.equal(v.ok, false);
  assert.equal(v.error.code, 'HEAD_MISMATCH');
  const r = await release(subj, head + '-other');
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'HEAD_MISMATCH');
});

test(`§6.1 ${scope}: автор не может быть проверяющим своего предмета`, async () => {
  const { subj, head } = await publishProtocolSubject([ids.author, ids.audAnthropic], scope);
  let assignErr = null;
  try { await assignAuditor(ids.tenantA, subj, ids.audAnthropic); } catch (e) { assignErr = e; }
  if (!assignErr) {
    await assignAuditor(ids.tenantA, subj, ids.audOpenai);
    await verdict(ids.audAnthropic, subj, head);
    await verdict(ids.audOpenai, subj, head);
    const r = await release(subj, head);
    assert.equal(r.ok, false, 'author-auditor verdict must not count');
  } else {
    assert.ok(/AUTHOR|SELF/i.test(assignErr.message), assignErr.message);
  }
});

test(`§6.1 ${scope}: один отрицательный вердикт при паре ACCEPT — выпуска нет, открыто разногласие`, async () => {
  const { subj, head } = await publishProtocolSubject(undefined, scope);
  const third = `codex:aud3-${scope === 'BEM954_PROTOCOL' ? 'p' : 'z'}-${ids.run}`;
  await withRole('bem_bootstrap_admin', async (c) => {
    await c.query('SELECT bem_control.create_actor($1, $2, NULL, NULL)', [third, 'openai']);
    await c.query("SELECT bem_control.grant_delegation('bem_kernel_rw', $1, 'zavod 6.1 test')", [third]);
  });
  for (const a of [ids.audOpenai, ids.audAnthropic, third]) await assignAuditor(ids.tenantA, subj, a);
  assert.equal((await verdict(ids.audOpenai, subj, head)).ok, true);
  assert.equal((await verdict(ids.audAnthropic, subj, head)).ok, true);
  assert.equal((await verdict(third, subj, head, 'REVISE')).ok, true);
  const r = await release(subj, head);
  assert.equal(r.ok, true, JSON.stringify(r.error));
  assert.equal(r.result.released, false);
});
test(`§6.1 ${scope}: 0 вердиктов и вердикт без назначения — отказ`, async () => {
  const { subj, head } = await publishProtocolSubject(undefined, scope);
  assert.equal((await release(subj, head)).error.code, 'WAITING_AUDIT');
  const v = await verdict(ids.audOpenai, subj, head);
  assert.equal(v.ok, false);
  assert.equal(v.error.code, 'AUDITOR_NOT_ASSIGNED');
});
}

// ---------- M-E35-01: роль сверяется на каждом рабочем клиенте ----------

// Пул-подмена: первое подключение — честный bem_kernel_rw (старт проходит), дальше — чужой вход.
class SwitchPool {
  constructor(steps) { this.steps = steps; this.n = 0; this.released = []; }
  async connect() {
    const step = this.steps[Math.min(this.n++, this.steps.length - 1)];
    const c = new pg.Client({ ...CONN, user: step.user });
    await c.connect();
    if (step.setRole) await c.query(`SET ROLE ${step.setRole}`);
    c.release = (broken) => { this.released.push(Boolean(broken)); return c.end(); };
    return c;
  }
  async end() {}
}

test('M-E35-01 подмена входа после старта: команда и доставщик отказывают, данных не появляется', async () => {
  for (const bad of [{ user: 'postgres' }, { user: 'postgres', setRole: KERNEL_ROLE },
    { user: 'postgres', setRole: 'bem_control_owner' }]) {
    const tag = JSON.stringify(bad);
    const pool = new SwitchPool([{ user: KERNEL_ROLE }, bad]);
    const k = new Kernel({ pool, stopFile });
    assert.equal(await k.assertIdentity(), true, tag);
    const wi = uuid();
    const r = await k.execute(as(ids.author), { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
      payload: { work_item_id: wi, evidence: { test: 'M-E35-01' } } });
    assert.equal(r.ok, false, tag);
    assert.equal(r.error.code, 'KERNEL_WRONG_ROLE', tag);
    const n = await withRole('postgres', async (c) =>
      (await c.query('SELECT count(*)::int AS n FROM bem_core.work_item WHERE id = $1', [wi])).rows[0].n);
    assert.equal(n, 0, `${tag}: no work item`);
    let egressCalled = false;
    await assert.rejects(k.dispatchOnce(async () => { egressCalled = true; return { outcome: 'SENT' }; }),
      (e) => e.code === 'KERNEL_WRONG_ROLE', tag);
    assert.equal(egressCalled, false, `${tag}: egress must not run`);
    // Клиент с чужой ролью в пул не возвращается (release(true)); проверенный при старте — возвращается.
    assert.deepEqual(pool.released, [false, true, true], tag);
  }
});

// ---------- M-E35-05: SR-10 закрыт по умолчанию ----------

test('M-E35-05 SR-10: нет пути, нет файла, не читается, пустой, непонятный — отказ с причиной', async () => {
  const d = mkdtempSync(join(tmpdir(), 'zavod-sr10-'));
  const file = (name, text) => { const f = join(d, name); writeFileSync(f, text); return f; };
  const cases = [
    [undefined, 'NO_STOP_FILE'], ['', 'NO_STOP_FILE'], ['   ', 'NO_STOP_FILE'],
    [join(d, 'missing'), 'STOP_FILE_UNREADABLE'], [d, 'STOP_FILE_UNREADABLE'],
    [file('empty', ''), 'STOP_FILE_UNKNOWN'], [file('blank', '\n  \n'), 'STOP_FILE_UNKNOWN'],
    [file('junk', 'maybe\nRUN\n'), 'STOP_FILE_UNKNOWN'], [file('stop', 'STOP\nоператор\n'), 'STOP'],
  ];
  for (const [f, reason] of cases) {
    const s = stopState(f);
    assert.equal(s.stopped, true, `${f}`);
    assert.equal(s.reason, reason, `${f}`);
    const k = new Kernel({ connection: CONN, stopFile: f });
    const r = await k.execute(as(ids.author), { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
      payload: { work_item_id: uuid(), evidence: { test: 'M-E35-05' } } });
    assert.equal(r.ok, false);
    assert.equal(r.error.code, 'KERNEL_STOPPED');
    assert.ok(r.error.message.includes(reason), r.error.message);
    const dd = await k.dispatchOnce(async () => { throw new Error('egress must not run'); });
    assert.deepEqual(dd, { stopped: true, stop_reason: reason, claimed: 0 });
    assert.equal(k.health().stopped, true);
    assert.equal(k.health().stop_reason, reason);
    await k.close();
  }
  // Нет прав на чтение (Linux, не root) — тоже отказ.
  if (process.platform !== 'win32' && process.getuid?.() !== 0) {
    const { chmodSync } = await import('node:fs');
    const f = file('noread', 'RUN\n'); chmodSync(f, 0o000);
    const s = stopState(f);
    assert.deepEqual([s.stopped, s.reason, s.errno], [true, 'STOP_FILE_UNREADABLE', 'EACCES']);
    chmodSync(f, 0o600);
  }
  // Работа открывается только строкой RUN.
  for (const t of ['RUN\n', '  run  \r\nкомментарий\n']) assert.deepEqual(stopState(file('run', t)), { stopped: false, reason: 'RUN' });
});

test('M-E35-05 server.mjs без KERNEL_STOP_FILE не стартует (код 3) и к базе не подключается', () => {
  const SERVER = fileURLToPath(new URL('../src/server.mjs', import.meta.url));
  for (const v of [undefined, '', '   ']) {
    const env = { ...process.env, PGHOST: '127.0.0.1', PGPORT: '1' };
    if (v === undefined) delete env.KERNEL_STOP_FILE; else env.KERNEL_STOP_FILE = v;
    const p = spawnSync(process.execPath, [SERVER], { env, encoding: 'utf8', timeout: 20000 });
    assert.equal(p.status, 3, `${JSON.stringify(v)}: ${p.stdout}${p.stderr}`);
    assert.match(p.stdout, /KERNEL_STOP_FILE_REQUIRED/);
    assert.doesNotMatch(p.stdout + p.stderr, /ECONNREFUSED|connect/i);
  }
});
