// ДОКУМЕНТ: tests/rules_handoff.test.mjs
// ВЕРСИЯ: v0.5  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 00:08 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 11:12 +03:00 (v0.5: Л.12 ждёт OPERATOR_TICKET_REQUIRED; подставной посредник отдаёт пустую повторную проверку hold (RG24-01); v0.4: ChatGPT R16 RG16-01 —
//   тест гонок ждёт только соединения, заблокированные держателем; v0.3: 2026-10-18 08:43 +03:00, ChatGPT R15F —
//   RG15-02 снимок всей базы (каждая таблица несистемных схем) до и после каждого отказа; RG15-03 гонки при смене
//   адресата с порядком от удержанной транзакции; v0.2: 2026-10-18 02:25 +03:00, ChatGPT R14B —
//   RG14-01 прямой вызов activate_rules и путь оператора общей ролью ядра — отказ, база не меняется; ядро без пула
//   bem_rules_gate — RULES_GATE_UNSET; RG14-02/03 подтверждение и завершение после смены чата адресата — отказ;
//   v0.1: пакеты Z-RULES-01 и Z-HANDOFF-01, проект v1.2 §6)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: проверки Z-EXT-02 через Kernel на чистом PostgreSQL 16. Проверки GitHub, git и подписи заменены подставным
//   объектом rules (их проверяет tests/rules_gate.test.mjs), поэтому здесь видно, что база сама отклоняет каждый
//   неверный факт. Посредник — тестовый: личность по полю via запроса. Каждый отказ проверяется вместе с
//   неизменностью всей базы (число строк и отпечаток каждой таблицы до и после).
// ОГРАНИЧЕНИЯ: стенд PG16 с H1.31 + Z-EXT-01 + Z-EXT-02, как остальные тесты Kernel; живая база не трогается.

import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { Kernel, RESERVED_EVIDENCE_KINDS, TRANSPORT_COMMANDS } from '../src/kernel.mjs';
import { RulesError } from '../src/rules_gate.mjs';
import { CONN, bootFixture, withRole, assignAuditor, runStopFile, uuid } from './helpers.mjs';

const hex = (n) => randomBytes(n / 2).toString('hex');
const CHECKS = ['static', 'pg16', 'engine-pg', 'engine-pg-probes'];
const APP = 15368;
const FP = `SHA256:${'A'.repeat(43)}`;
const R01 = '01_Куратор_ГД';
const R02 = '02_Куратор_производства';
const R03 = '03_Куратор_качества_и_безопасности';
const PARENTS = { [R01]: 'OPERATOR', [R02]: R01, [R03]: R01 };
const CODE = hex(40);

let ids;
let kernel;
const as = (actor, role = 'kernel') => ({ actor_id: actor, role });
const isoNow = (ms = 0) => new Date(Date.now() + ms).toISOString().replace(/\.\d+Z$/, 'Z');

// Подставные проверки правил: факты задаёт тест.
const gate = {
  next: null,
  wcRules: null,
  collectActivation(args) { return gate.next(args); },
  checkWorkingCopy(r) { return { code_commit: CODE, rules_commit: gate.wcRules ?? r }; },
  verifyReportAck({ tenantId, reportId, reportSha256 }) {
    return { namespace: 'zavod-report-ack@v1', key_fingerprint: FP, signed_ticket_sha256: hex(64),
      ticket: { tenant_id: tenantId, report_id: reportId, report_sha256: reportSha256 } };
  },
};
const SESS = {};
// Подставной посредник: личность из SESS; повторная проверка в транзакции команды (RG24-01) здесь пустая.
const transport = { verify(req) {
  if (req.via === 'throw') throw new Error('boom');
  const v = SESS[req.via];
  return v ? { ...v, hold: async () => {} } : null;
} };

function facts({ tenant, subject, head, commit = hex(40), parents = PARENTS, digest = hex(64) }) {
  const github = { base: 'main', merged: true, merge_commit: commit, head_sha: head, pr_number: 7,
    pr_url: 'https://github.com/zavod-test/rules/pull/7',
    required_checks: CHECKS.map((c) => ({ context: c, app_id: APP })),
    check_runs: CHECKS.map((c, i) => ({ name: c, check_run_id: 5000 + i, app_id: APP, head_sha: head,
      conclusion: 'success', completed_at: '2026-10-17T20:00:00Z' })) };
  const ticket = { tenant_id: tenant, merge_commit: commit, head_sha: head, pr_number: 7, registry_digest: digest,
    subject_id: subject, role_parents: parents, issued_at: isoNow(-60000) };
  return { commit, head_sha: head, pr_number: 7, registry_digest: digest, role_parents: parents, github,
    signature: { namespace: 'zavod-rules-activation@v1', key_fingerprint: FP, signed_ticket_sha256: hex(64), ticket } };
}

// RG15-02: снимок всей базы — число строк и отпечаток каждой таблицы во всех схемах, кроме системных.
async function snap() {
  return withRole('postgres', async (c) => {
    const { rows: tabs } = await c.query(`SELECT format('%I.%I', schemaname, tablename) AS t FROM pg_tables
      WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY 1`);
    const out = {};
    for (const { t } of tabs) {
      out[t] = (await c.query(`SELECT count(*)::int AS n, md5(coalesce(string_agg(x::text, '|' ORDER BY x::text), '')) AS h
        FROM ${t} x`)).rows[0];
    }
    return out;
  });
}
async function refused(fn, code) {
  const before = await snap();
  const r = await fn();
  assert.equal(r.ok, false, `ожидался отказ ${code}, получено ${JSON.stringify(r)}`);
  assert.equal(r.error.code, code, r.error.message);
  assert.deepEqual(await snap(), before, `${code}: база изменилась после отказа`);
  return r;
}
const ok = (r) => { assert.equal(r.ok, true, JSON.stringify(r.error)); return r.result; };
const pg = (sql, args) => withRole('postgres', async (c) => (await c.query(sql, args)).rows);
// RG14-01: вызов функции базы напрямую, мимо ядра, с контекстом участника. Возвращает ошибку базы (или null).
async function direct(role, sql, args, tenant = ids.tenantA) {
  return withRole(role, async (c) => {
    await c.query('BEGIN');
    try {
      await c.query("SELECT set_config('app.actor_id', $1, true), set_config('app.tenant_id', $2, true)", [ids.author, tenant]);
      await c.query(sql, args);
      return null;
    } catch (e) { return e; } finally { await c.query('ROLLBACK'); }
  });
}

const activate = (f, tenant = ids.tenantA, subject = f.signature.ticket.subject_id, k = kernel) => {
  gate.next = () => f;
  return k.execute(as(ids.author), { type: 'ActivateRules', actor_id: ids.author, tenant_id: tenant,
    payload: { pr_number: 7, subject_id: subject, ticket: '{}', signature: 'sig' } });
};
const lease = (via, type, payload, extra = {}) => kernel.execute(null, { type, via, payload, ...extra });

async function newItem(tenant = ids.tenantA) {
  const wi = uuid();
  ok(await kernel.execute(as(ids.author), { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: tenant,
    payload: { work_item_id: wi, evidence: { test: 'create' } } }));
  return wi;
}
async function finish(wi, tenant = ids.tenantA) {
  let rev = 1;
  for (const s of ['PLANNED', 'IN_PROGRESS', 'IN_REVIEW', 'ACCEPTED']) {
    ok(await kernel.execute(as(ids.author), { type: 'Transition', actor_id: ids.author, tenant_id: tenant, command_id: uuid(),
      payload: { work_item_id: wi, expected_revision: rev, new_status: s, evidence: { test: s } } }));
    rev += 1;
  }
}
async function subject({ release = true, tenant = ids.tenantA } = {}) {
  const wi = await newItem(tenant);
  const subj = uuid();
  const head = hex(40);
  ok(await kernel.execute(as(ids.author), { type: 'PublishSubject', actor_id: ids.author, tenant_id: tenant,
    payload: { subject_id: subj, work_item_id: wi, head_sha: head, criticality: 'CRITICAL', scope: 'BEM954_PROTOCOL',
      authors: [ids.author], evidence: { test: 'rules subject' } } }));
  if (release) {
    for (const aud of [ids.audOpenai, ids.audAnthropic]) {
      await assignAuditor(tenant, subj, aud);
      ok(await kernel.execute(as(aud, 'auditor'), { type: 'RecordVerdict', actor_id: aud, tenant_id: tenant,
        payload: { subject_id: subj, head_sha: head, verdict: 'ACCEPT', evidence: { reviewed: head } } }));
    }
    ok(await kernel.execute(as(ids.author), { type: 'ReleaseSubject', actor_id: ids.author, tenant_id: tenant,
      payload: { subject_id: subj, head_sha: head } }));
  }
  return { subj, head };
}

let released;
before(async () => {
  ids = await bootFixture();
  // RG14-01: у входной роли проверки правил своя доверенность говорить за автора, как у bem_kernel_rw (H1.31).
  await withRole('bem_bootstrap_admin', (c) => c.query("SELECT bem_control.grant_delegation('bem_rules_gate', $1, $2)",
    [ids.author, `zavod rules gate test ${ids.run}`]));
  kernel = new Kernel({ connection: CONN, rulesConnection: CONN, stopFile: runStopFile('zavod-rules-'), rules: gate, transport });
  await kernel.assertIdentity();
  const who = (tenant, role, session) => ({ tenant_id: tenant, actor_id: ids.author, role_key: role, session });
  Object.assign(SESS, {
    g1: who(ids.tenantA, R01, 'sess-g1'), g2: who(ids.tenantA, R01, 'sess-g2'),
    p1: who(ids.tenantA, R02, 'sess-p1'), p2: who(ids.tenantA, R02, 'sess-p2'),
    q1: who(ids.tenantA, R03, 'sess-q1'), q2: who(ids.tenantA, R03, 'sess-q2'),
    x1: who(ids.tenantA, '09_Чужая_роль', 'sess-x1'),
    b1: who(ids.tenantB, R02, 'sess-p1'),
    op: who(ids.tenantA, 'OPERATOR', 'phone'),
    bad: { tenant_id: ids.tenantA, actor_id: ids.author, role_key: 'admin', session: 's' },
  });
  released = await subject();
});
after(async () => { await kernel?.close(); });

// ---------- Z-RULES-01 ----------

test('RG12-01: закрытые виды доказательств через RecordEvidence — отказ RESERVED_KIND', async () => {
  for (const kind of RESERVED_EVIDENCE_KINDS) {
    await refused(() => kernel.execute(as(ids.author), { type: 'RecordEvidence', actor_id: ids.author, tenant_id: ids.tenantA,
      payload: { kind, payload: { lease_id: uuid() } } }), 'RESERVED_KIND');
  }
});

test('Z-RULES-01: без проверок правил и при отказе проверок — до базы', async () => {
  const k0 = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-rules0-') });
  try {
    await refused(() => activate(facts({ tenant: ids.tenantA, subject: released.subj, head: released.head }), ids.tenantA,
      released.subj, k0), 'RULES_GATE_UNSET');
  } finally { await k0.close(); }
  gate.next = () => { throw new RulesError('RULES_PR_NOT_MERGED', '7'); };
  await refused(() => kernel.execute(as(ids.author), { type: 'ActivateRules', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { pr_number: 7, subject_id: released.subj, ticket: '{}', signature: 's' } }), 'RULES_PR_NOT_MERGED');
});

test('RG14-01: включить правила может только входная роль bem_rules_gate; общая роль ядра — отказ', async () => {
  const f = facts({ tenant: ids.tenantA, subject: released.subj, head: released.head });
  // Ядро с проверками, но без пула bem_rules_gate — отказ до базы.
  const k1 = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-rules1-'), rules: gate, transport });
  try {
    await refused(() => activate(f, ids.tenantA, released.subj, k1), 'RULES_GATE_UNSET');
  } finally { await k1.close(); }
  // Прямой вызов bem_kernel_rw с полностью верными по виду фактами — нет права вызова, база не меняется.
  const before0 = await snap();
  const e = await direct('bem_kernel_rw', 'SELECT bem_control.activate_rules($1, $2, $3, $4, $5, $6, $7, $8, $9)',
    [ids.tenantA, f.commit, f.head_sha, f.pr_number, f.registry_digest, released.subj, f.role_parents, f.github, f.signature]);
  assert.equal(e?.code, '42501', `ожидался отказ в праве вызова, получено ${e?.code} ${e?.message}`);
  assert.deepEqual(await snap(), before0, 'прямой вызов: база изменилась');
  const [acl] = await pg(`SELECT has_function_privilege('bem_kernel_rw', 'bem_control.activate_rules(uuid, text, text, integer, text, uuid, jsonb, jsonb, jsonb)', 'EXECUTE') AS kr,
    has_function_privilege('bem_rules_gate', 'bem_control.activate_rules(uuid, text, text, integer, text, uuid, jsonb, jsonb, jsonb)', 'EXECUTE') AS rg`);
  assert.deepEqual(acl, { kr: false, rg: true });
});

test('Z-RULES-01: база сама отклоняет каждый неверный факт, база не меняется', async () => {
  const base = () => facts({ tenant: ids.tenantA, subject: released.subj, head: released.head });
  const cases = [
    ['RULES_MERGE_EVIDENCE_MISMATCH', (f) => { f.github.merged = false; }],
    ['RULES_MERGE_EVIDENCE_MISMATCH', (f) => { f.github.base = 'dev'; }],
    ['RULES_MERGE_EVIDENCE_MISMATCH', (f) => { f.github.pr_url = 'https://github.com/zavod-test/rules/pull/8'; }],
    ['RULES_MERGE_EVIDENCE_MISMATCH', (f) => { f.github.merge_commit = hex(40); }],
    ['RULES_CHECK_SOURCE_UNASSIGNED', (f) => { f.github.required_checks[0].app_id = null; }],
    ['RULES_CHECK_SOURCE_UNASSIGNED', (f) => { f.github.required_checks.pop(); }],
    ['RULES_CHECK_WRONG_SOURCE', (f) => { f.github.check_runs[1].app_id = 999; }],
    ['RULES_CHECK_WRONG_HEAD', (f) => { f.github.check_runs[2].head_sha = hex(40); }],
    ['RULES_CHECK_NOT_PASSED', (f) => { f.github.check_runs[3].conclusion = 'failure'; }],
    ['RULES_CHECK_NOT_PASSED', (f) => { f.github.check_runs.push({ ...f.github.check_runs[0], check_run_id: 9 }); }],
    ['RULES_CHECK_NOT_PASSED', (f) => { f.github.check_runs.shift(); }],
    ['RULES_CHECK_BAD_RUN', (f) => { f.github.check_runs[0].completed_at = 'вчера'; }],
    ['RULES_SIGNATURE_MISSING', (f) => { f.signature.namespace = 'zavod-report-ack@v1'; }],
    ['RULES_SIGNATURE_MISSING', (f) => { f.signature.signed_ticket_sha256 = 'x'; }],
    ['RULES_SIGNATURE_MISMATCH', (f) => { f.signature.ticket.registry_digest = hex(64); }],
    ['RULES_SIGNATURE_MISMATCH', (f) => { f.signature.ticket.tenant_id = ids.tenantB; }],
    ['RULES_SIGNATURE_MISMATCH', (f) => { f.signature.ticket.role_parents = { [R01]: 'OPERATOR' }; }],
    ['RULES_SIGNATURE_EXPIRED', (f) => { f.signature.ticket.issued_at = isoNow(-25 * 3600 * 1000); }],
    ['RULES_SIGNATURE_EXPIRED', (f) => { f.signature.ticket.issued_at = isoNow(10 * 60 * 1000); }],
    ['RULES_BAD_ROLE_PARENTS', (f) => { f.role_parents = { [R01]: R02, [R02]: R01 }; f.signature.ticket.role_parents = f.role_parents; }],
    ['RULES_BAD_ROLE_PARENTS', (f) => { f.role_parents = { bad: 'OPERATOR' }; f.signature.ticket.role_parents = f.role_parents; }],
  ];
  for (const [code, mut] of cases) {
    const f = base();
    mut(f);
    await refused(() => activate(f), code);
  }
  const notReleased = await subject({ release: false });
  await refused(() => activate(facts({ tenant: ids.tenantA, subject: notReleased.subj, head: notReleased.head })),
    'RULES_AUDIT_NOT_RELEASED');
  await refused(() => activate(facts({ tenant: ids.tenantA, subject: released.subj, head: hex(40) })),
    'RULES_SUBJECT_HEAD_MISMATCH');
  // Чужой заказчик: предмет заказчика A не виден заказчику B.
  await refused(() => activate(facts({ tenant: ids.tenantB, subject: released.subj, head: released.head }), ids.tenantB),
    'RULES_SUBJECT_MISSING');
});

let first;
test('Z-RULES-01: включение одним действием — факты GitHub и подписи пишет сама база в этой транзакции', async () => {
  first = facts({ tenant: ids.tenantA, subject: released.subj, head: released.head });
  const r = ok(await activate(first));
  assert.equal(r.rules_commit, first.commit);
  assert.equal(r.previous_rules_commit, null);
  const act = ok(await kernel.execute(as(ids.author), { type: 'GetActiveRules', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: {} }));
  assert.equal(act.rules_commit, first.commit);
  assert.deepEqual(act.role_parents, PARENTS);
  assert.equal(act.activation_evidence_id, r.activation_evidence_id);
  const ev = await pg(`SELECT kind, created_at FROM bem_core.evidence WHERE id IN (
      SELECT merge_evidence_id FROM bem_control.rules_activation WHERE rules_commit = $1 UNION ALL
      SELECT signature_evidence_id FROM bem_control.rules_activation WHERE rules_commit = $1 UNION ALL
      SELECT activation_evidence_id FROM bem_control.rules_activation WHERE rules_commit = $1) ORDER BY kind`, [first.commit]);
  assert.deepEqual(ev.map((e) => e.kind), ['RULES_ACTIVATED', 'RULES_OPERATOR_SIGNATURE', 'RULES_PR_MERGED']);
  assert.equal(new Set(ev.map((e) => e.created_at.toISOString())).size, 1, 'все три записи — одна транзакция');
  await refused(() => activate(first), 'RULES_ALREADY_ACTIVE');
  await refused(() => kernel.execute(as(ids.author), { type: 'GetActiveRules', actor_id: ids.author, tenant_id: ids.tenantB,
    payload: {} }), 'RULES_NOT_ACTIVE');
});

test('RG12-03: две одновременные активации одной версии — ровно одна проходит; прежняя версия помечена', async () => {
  const f = facts({ tenant: ids.tenantA, subject: released.subj, head: released.head });
  gate.next = () => f;
  const call = () => kernel.execute(as(ids.author), { type: 'ActivateRules', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { pr_number: 7, subject_id: released.subj, ticket: '{}', signature: 's' } });
  const res = await Promise.all([call(), call()]);
  assert.equal(res.filter((x) => x.ok).length, 1, JSON.stringify(res));
  assert.equal(res.find((x) => !x.ok).error.code, 'RULES_ALREADY_ACTIVE');
  const rows = await pg(`SELECT rules_commit, superseded_by FROM bem_control.rules_activation WHERE tenant_id = $1
                          ORDER BY activated_at`, [ids.tenantA]);
  assert.deepEqual(rows, [{ rules_commit: first.commit, superseded_by: f.commit }, { rules_commit: f.commit, superseded_by: null }]);
});

// ---------- Z-HANDOFF-01 ----------

test('RG12-02: команды аренды без посредника или с непроверенной личностью — отказ до базы', async () => {
  const k0 = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-lease0-'), rules: gate });
  try {
    for (const type of TRANSPORT_COMMANDS) {
      await refused(() => k0.execute(as(ids.author), { type, actor_id: ids.author, tenant_id: ids.tenantA,
        payload: { work_item_id: uuid() } }), 'CALLER_NOT_AUTHENTICATED');
    }
  } finally { await k0.close(); }
  for (const via of [undefined, 'nobody', 'throw', 'bad']) {
    await refused(() => lease(via, 'OpenChatLease', { work_item_id: uuid() }), 'CALLER_NOT_AUTHENTICATED');
  }
  // Заявленная роль команд Kernel не открывает команду аренды обычным путём.
  await refused(() => kernel.execute(as(ids.author), { type: 'OpenChatLease', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: uuid() } }), 'CALLER_NOT_AUTHENTICATED');
});

const L = {};
test('Л.12: выдача аренды — номер и поколение от базы, личность только от посредника', async () => {
  L.wiG = await newItem();
  L.wiP = await newItem();
  gate.wcRules = hex(40);
  await refused(() => lease('p1', 'OpenChatLease', { work_item_id: L.wiP }), 'LEASE_RULES_CHANGED');
  gate.wcRules = null;
  await refused(() => lease('x1', 'OpenChatLease', { work_item_id: L.wiP }), 'LEASE_ROLE_NOT_IN_RULES');
  await refused(() => lease('op', 'OpenChatLease', { work_item_id: L.wiP }), 'OPERATOR_TICKET_REQUIRED'); // RG24-03: ядро отклоняет до базы
  L.g = ok(await lease('g1', 'OpenChatLease', { work_item_id: L.wiG }));
  // Поля заказчика, участника, роли и сессии в запросе не действуют.
  L.p = ok(await lease('p1', 'OpenChatLease', { work_item_id: L.wiP, role_key: R01, session: 'evil' },
    { tenant_id: ids.tenantB, actor_id: 'claude:evil' }));
  assert.equal(L.p.chat_number, 'A00001');
  assert.equal(L.p.generation, 1);
  assert.equal(L.p.code_commit, CODE);
  const [row] = await pg('SELECT tenant_id, role_key, holder_session FROM bem_control.chat_lease WHERE lease_id = $1', [L.p.lease_id]);
  assert.deepEqual(row, { tenant_id: ids.tenantA, role_key: R02, holder_session: 'sess-p1' });
  const other = await newItem();
  await refused(() => lease('p2', 'OpenChatLease', { work_item_id: other }), 'LEASE_ROLE_BUSY');
  await refused(() => lease('q1', 'OpenChatLease', { work_item_id: L.wiP }), 'LEASE_WORK_BUSY');
  const seen = ok(await kernel.execute(as(ids.author), { type: 'GetChatLease', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { role_key: R02 } }));
  assert.equal(seen.lease_id, L.p.lease_id);
  await refused(() => kernel.execute(as(ids.author), { type: 'GetChatLease', actor_id: ids.author, tenant_id: ids.tenantB,
    payload: { lease_id: L.p.lease_id } }), 'NOT_FOUND');
});

test('RG13-01: итог, память и следующий шаг пишет только держатель; поля аренды ставит база', async () => {
  const rec = (via, extra = {}) => lease(via, 'RecordLeaseEvidence', { lease_id: L.p.lease_id, generation: 1,
    kind: 'TASK_RESULT', content_sha256: hex(64), ...extra });
  await refused(() => rec('g1'), 'LEASE_NOT_HOLDER');
  await refused(() => rec('p2'), 'LEASE_NOT_HOLDER');
  await refused(() => rec('p1', { generation: 2 }), 'LEASE_GENERATION_MISMATCH');
  await refused(() => rec('b1'), 'LEASE_NOT_FOUND');
  await refused(() => rec('p1', { kind: 'REPORTED_UP' }), 'LEASE_EVIDENCE_BAD_KIND');
  await refused(() => rec('p1', { lease_id: uuid() }), 'LEASE_NOT_FOUND');
  L.result = ok(await rec('p1', { payload: { session: 'sess-g1', lease_id: uuid(), generation: 9, note: 'итог' } })).evidence_id;
  const [ev] = await pg('SELECT payload FROM bem_core.evidence WHERE id = $1', [L.result]);
  assert.equal(ev.payload.session, 'sess-p1');
  assert.equal(ev.payload.lease_id, L.p.lease_id);
  assert.equal(ev.payload.generation, 1);
  assert.equal(ev.payload.note, 'итог');
  L.memory = ok(await rec('p1', { kind: 'ROLE_MEMORY' })).evidence_id;
  L.next = ok(await rec('p1', { kind: 'NEXT_STEP' })).evidence_id;
});

test('RG13-02/RG13-03: отчёт выше — адресат закреплён при создании, завершение по порядку и с той же квитанцией', async () => {
  const done = (via, extra = {}) => lease(via, 'CompleteChatLease', { lease_id: L.p.lease_id, generation: 1,
    result_evidence_id: L.result, memory_evidence_id: L.memory, next_evidence_id: L.next, report_id: L.report ?? uuid(), ...extra });
  await refused(() => done('p1'), 'LEASE_WORK_NOT_DONE');
  await finish(L.wiP);
  await refused(() => done('p1'), 'LEASE_EVIDENCE_MISSING');
  await refused(() => done('p1', { result_evidence_id: L.memory, memory_evidence_id: L.result }), 'LEASE_EVIDENCE_MISSING');

  const sum = hex(64);
  await refused(() => lease('g1', 'FileLeaseReport', { lease_id: L.p.lease_id, generation: 1, report_sha256: sum }), 'LEASE_NOT_HOLDER');
  L.report = ok(await lease('p1', 'FileLeaseReport', { lease_id: L.p.lease_id, generation: 1, report_sha256: sum })).report_id;
  const [rep] = await pg('SELECT recipient_role_key, recipient_lease_id, recipient_session FROM bem_control.lease_report WHERE report_id = $1',
    [L.report]);
  assert.deepEqual(rep, { recipient_role_key: R01, recipient_lease_id: L.g.lease_id, recipient_session: 'sess-g1' });
  await refused(() => done('p1'), 'LEASE_REPORT_NOT_ACKNOWLEDGED');

  const ack = (via, s = sum) => lease(via, 'AcknowledgeReport', { report_id: L.report, report_sha256: s });
  await refused(() => ack('p1'), 'REPORT_NOT_RECIPIENT');
  await refused(() => ack('q1'), 'REPORT_NOT_RECIPIENT');
  await refused(() => ack('g2'), 'REPORT_NOT_RECIPIENT');
  await refused(() => ack('op'), 'REPORT_NOT_RECIPIENT');
  await refused(() => ack('g1', hex(64)), 'REPORT_SHA_MISMATCH');
  await refused(() => ack('b1'), 'REPORT_NOT_FOUND');
  const a1 = ok(await ack('g1')).ack_evidence_id;
  const before = await snap();
  assert.equal(ok(await ack('g1')).ack_evidence_id, a1, 'повтор адресатом — то же подтверждение');
  assert.deepEqual(await snap(), before);

  await refused(() => done('g1'), 'LEASE_NOT_HOLDER');
  await refused(() => done('p1', { generation: 2 }), 'LEASE_GENERATION_MISMATCH');
  await refused(() => done('b1'), 'LEASE_NOT_FOUND');
  const receipt = ok(await done('p1')).receipt;
  const snap2 = await snap();
  assert.equal(ok(await done('p1')).receipt, receipt, 'повтор с теми же номерами — та же квитанция');
  assert.deepEqual(await snap(), snap2, 'повтор ничего не пишет');
  await refused(() => done('p1', { memory_evidence_id: L.next, next_evidence_id: L.memory }), 'LEASE_COMPLETION_MISMATCH');
  await refused(() => done('p1', { generation: 2 }), 'LEASE_GENERATION_MISMATCH');
  await refused(() => lease('p1', 'RecordLeaseEvidence', { lease_id: L.p.lease_id, generation: 1, kind: 'NEXT_STEP',
    content_sha256: hex(64) }), 'LEASE_NOT_OPEN');
  const [row] = await pg('SELECT status, completion_evidence_id, report_id FROM bem_control.chat_lease WHERE lease_id = $1', [L.p.lease_id]);
  assert.deepEqual(row, { status: 'COMPLETED', completion_evidence_id: receipt, report_id: L.report });
  // Следующий чат роли — следующий номер и поколение.
  L.wiP2 = await newItem();
  L.p2 = ok(await lease('p1', 'OpenChatLease', { work_item_id: L.wiP2 }));
  assert.equal(L.p2.chat_number, 'A00002');
  assert.equal(L.p2.generation, 2);
});

test('RG13-02: отчёт оператору подтверждается подписью; сменившийся адресат — отказ', async () => {
  const rec = (kind) => lease('g1', 'RecordLeaseEvidence', { lease_id: L.g.lease_id, generation: 1, kind, content_sha256: hex(64) });
  const gr = ok(await rec('TASK_RESULT')).evidence_id;
  const gm = ok(await rec('ROLE_MEMORY')).evidence_id;
  const gn = ok(await rec('NEXT_STEP')).evidence_id;
  const sum = hex(64);
  const rep = ok(await lease('g1', 'FileLeaseReport', { lease_id: L.g.lease_id, generation: 1, report_sha256: sum })).report_id;
  const [row] = await pg('SELECT recipient_role_key, recipient_session FROM bem_control.lease_report WHERE report_id = $1', [rep]);
  assert.deepEqual(row, { recipient_role_key: 'OPERATOR', recipient_session: null });
  await refused(() => lease('g2', 'AcknowledgeReport', { report_id: rep, report_sha256: sum }), 'REPORT_NOT_RECIPIENT');
  // RG14-01: подтверждение за оператора общей ролью ядра напрямую — отказ, база не меняется.
  const opSig = { namespace: 'zavod-report-ack@v1', key_fingerprint: FP, signed_ticket_sha256: hex(64),
    ticket: { tenant_id: ids.tenantA, report_id: rep, report_sha256: sum } };
  const beforeOp = await snap();
  const eOp = await direct('bem_kernel_rw', 'SELECT bem_control.acknowledge_lease_report($1, $2, $3, $4, $5, $6)',
    [ids.tenantA, rep, sum, 'OPERATOR', 'OPERATOR', opSig]);
  assert.match(String(eOp?.message), /REPORT_OPERATOR_ACK_UNTRUSTED/);
  assert.deepEqual(await snap(), beforeOp, 'путь оператора ролью ядра: база изменилась');
  ok(await lease('op', 'AcknowledgeReport', { report_id: rep, report_sha256: sum, ticket: '{}', signature: 's' }));
  const [ack] = await pg('SELECT ack_session FROM bem_control.lease_report WHERE report_id = $1', [rep]);
  assert.equal(ack.ack_session, 'OPERATOR');

  // Отчёт второй роли адресован открытому чату ГД и подтверждён им; затем чат ГД завершается.
  const sum2 = hex(64);
  const rep2 = ok(await lease('p1', 'FileLeaseReport', { lease_id: L.p2.lease_id, generation: 2, report_sha256: sum2 })).report_id;
  ok(await lease('g1', 'AcknowledgeReport', { report_id: rep2, report_sha256: sum2 }));
  const recP = (kind) => lease('p1', 'RecordLeaseEvidence', { lease_id: L.p2.lease_id, generation: 2, kind, content_sha256: hex(64) });
  const [pr, pm, pn] = [ok(await recP('TASK_RESULT')).evidence_id, ok(await recP('ROLE_MEMORY')).evidence_id,
    ok(await recP('NEXT_STEP')).evidence_id];
  await finish(L.wiP2);
  await finish(L.wiG);
  ok(await lease('g1', 'CompleteChatLease', { lease_id: L.g.lease_id, generation: 1, result_evidence_id: gr,
    memory_evidence_id: gm, next_evidence_id: gn, report_id: rep }));
  // RG14-02: повтор подтверждения ушедшим чатом — отказ, а не прежнее подтверждение.
  await refused(() => lease('g1', 'AcknowledgeReport', { report_id: rep2, report_sha256: sum2 }), 'REPORT_RECIPIENT_CHANGED');
  // RG14-03: завершение по отчёту, подтверждённому ушедшим чатом, — отказ; нужен новый отчёт.
  const doneP = (report_id) => lease('p1', 'CompleteChatLease', { lease_id: L.p2.lease_id, generation: 2,
    result_evidence_id: pr, memory_evidence_id: pm, next_evidence_id: pn, report_id });
  await refused(() => doneP(rep2), 'LEASE_REPORT_RECIPIENT_CHANGED');
  await refused(() => lease('p1', 'FileLeaseReport', { lease_id: L.p2.lease_id, generation: 2, report_sha256: hex(64) }),
    'REPORT_RECIPIENT_NOT_AVAILABLE');
  // Новый чат ГД (поколение 2) получает новый отчёт, подтверждает его — завершение проходит.
  L.wiG2 = await newItem();
  const g2 = ok(await lease('g2', 'OpenChatLease', { work_item_id: L.wiG2 }));
  assert.equal(g2.generation, 2);
  L.g2 = g2;
  const sum3 = hex(64);
  const rep3 = ok(await lease('p1', 'FileLeaseReport', { lease_id: L.p2.lease_id, generation: 2, report_sha256: sum3 })).report_id;
  await refused(() => lease('g1', 'AcknowledgeReport', { report_id: rep3, report_sha256: sum3 }), 'REPORT_NOT_RECIPIENT');
  ok(await lease('g2', 'AcknowledgeReport', { report_id: rep3, report_sha256: sum3 }));
  ok(await doneP(rep3));
});

test('RG12-04: две одновременные выдачи одной роли — одна аренда, второй отказ LEASE_ROLE_BUSY', async () => {
  const [w1, w2] = [await newItem(), await newItem()];
  const res = await Promise.all([lease('q1', 'OpenChatLease', { work_item_id: w1 }), lease('q2', 'OpenChatLease', { work_item_id: w2 })]);
  assert.equal(res.filter((x) => x.ok).length, 1, JSON.stringify(res));
  assert.equal(res.find((x) => !x.ok).error.code, 'LEASE_ROLE_BUSY');
  const rows = await pg("SELECT count(*)::int AS n FROM bem_control.chat_lease WHERE tenant_id = $1 AND role_key = $2", [ids.tenantA, R03]);
  assert.equal(rows[0].n, 1);
});

// ---------- RG15-03: гонки при смене адресата (порядок задаёт удержанная транзакция, а не случай) ----------

// Чат готовится к завершению: итог, память, следующий шаг, работа принята.
async function ready(via, ls) {
  const rec = (kind) => lease(via, 'RecordLeaseEvidence', { lease_id: ls.lease_id, generation: ls.generation, kind,
    content_sha256: hex(64) });
  const ev = { result_evidence_id: ok(await rec('TASK_RESULT')).evidence_id,
    memory_evidence_id: ok(await rec('ROLE_MEMORY')).evidence_id, next_evidence_id: ok(await rec('NEXT_STEP')).evidence_id };
  const [{ work_item_id }] = await pg('SELECT work_item_id FROM bem_control.chat_lease WHERE lease_id = $1', [ls.lease_id]);
  await finish(work_item_id);
  return ev;
}
async function report(via, ls, ackVia, ackExtra = {}) {
  const sum = hex(64);
  const id = ok(await lease(via, 'FileLeaseReport', { lease_id: ls.lease_id, generation: ls.generation, report_sha256: sum })).report_id;
  if (ackVia) ok(await lease(ackVia, 'AcknowledgeReport', { report_id: id, report_sha256: sum, ...ackExtra }));
  return { id, sum };
}
const completeArgs = (ls, session, ev, reportId) => [ids.tenantA, ls.lease_id, ls.generation, session,
  ev.result_evidence_id, ev.memory_evidence_id, ev.next_evidence_id, reportId];
// RG16-01: считаются только соединения, которые ждут именно держателя (его номер процесса базы), а не любые блокировки.
async function lockWaiters(holderPid) {
  const [{ n }] = await pg(`SELECT count(*)::int AS n FROM pg_stat_activity
    WHERE datname = current_database() AND $1 = ANY (pg_blocking_pids(pid))`, [holderPid]);
  return n;
}
async function untilWaiting(holderPid, n) {
  for (let i = 0; i < 200; i += 1) {
    if (await lockWaiters(holderPid) >= n) return;
    await new Promise((r) => setTimeout(r, 50));
  }
  throw new Error(`за 10 с не дождались ${n} ожидающих блокировку`);
}
// Транзакция-держатель: завершает чат функцией базы и не фиксирует, пока ждущие не встанут в очередь блокировки.
async function heldCompletion(args, during) {
  return withRole('bem_kernel_rw', async (c) => {
    await c.query('BEGIN');
    try {
      await c.query("SELECT set_config('app.actor_id', $1, true), set_config('app.tenant_id', $2, true)", [ids.author, ids.tenantA]);
      await c.query('SELECT bem_control.complete_chat_lease($1, $2, $3, $4, $5, $6, $7, $8)', args);
      const [{ pid }] = (await c.query('SELECT pg_backend_pid() AS pid')).rows;
      const pending = during();
      await untilWaiting(pid, pending.length);
      await c.query('COMMIT');
      return Promise.all(pending);
    } catch (e) { await c.query('ROLLBACK').catch(() => {}); throw e; }
  });
}
const statusOf = async (leaseId) => (await pg('SELECT status FROM bem_control.chat_lease WHERE lease_id = $1', [leaseId]))[0].status;

test('RG15-03: подчинённый завершается, пока адресат держит чат; адресат уходит после — оба завершены', async () => {
  // Адресат — открытый чат ГД поколения 2 (L.g2). Новый чат второй роли — поколение 3.
  const p3 = ok(await lease('p2', 'OpenChatLease', { work_item_id: await newItem() }));
  assert.equal(p3.generation, 3);
  const evP = await ready('p2', p3);
  const repP = await report('p2', p3, 'g2');
  const evG = await ready('g2', L.g2);
  const repG = await report('g2', L.g2, 'op', { ticket: '{}', signature: 's' });
  // Держатель завершает подчинённого (его запись блокирует строку адресата на чтение); завершение адресата ждёт.
  const [gDone] = await heldCompletion(completeArgs(p3, 'sess-p2', evP, repP.id), () => [
    lease('g2', 'CompleteChatLease', { lease_id: L.g2.lease_id, generation: 2, ...evG, report_id: repG.id })]);
  ok(gDone);
  assert.equal(await statusOf(p3.lease_id), 'COMPLETED');
  assert.equal(await statusOf(L.g2.lease_id), 'COMPLETED');
});

test('RG15-03: адресат уходит, пока подчинённый завершается и подтверждение идёт, — оба отказа, база не меняется', async () => {
  const g3 = ok(await lease('g1', 'OpenChatLease', { work_item_id: await newItem() }));
  assert.equal(g3.generation, 3);
  const p4 = ok(await lease('p1', 'OpenChatLease', { work_item_id: await newItem() }));
  const evP = await ready('p1', p4);
  const repP = await report('p1', p4, 'g1');          // подтверждён адресатом g3 (сессия sess-g1)
  const repWait = await report('p1', p4, null);       // второй отчёт тому же адресату, ещё не подтверждён
  const evG = await ready('g1', g3);
  const repG = await report('g1', g3, 'op', { ticket: '{}', signature: 's' });
  const before = await snap();
  let after;
  // Держатель завершает адресата; завершение подчинённого и подтверждение второго отчёта ждут его строку.
  const [pDone, ackLate] = await heldCompletion(completeArgs(g3, 'sess-g1', evG, repG.id), () => [
    lease('p1', 'CompleteChatLease', { lease_id: p4.lease_id, generation: p4.generation, ...evP, report_id: repP.id }),
    lease('g1', 'AcknowledgeReport', { report_id: repWait.id, report_sha256: repWait.sum })]);
  assert.equal(pDone.ok, false, JSON.stringify(pDone));
  assert.equal(pDone.error.code, 'LEASE_REPORT_RECIPIENT_CHANGED');
  assert.equal(ackLate.ok, false, JSON.stringify(ackLate));
  assert.equal(ackLate.error.code, 'REPORT_RECIPIENT_CHANGED');
  assert.equal(await statusOf(g3.lease_id), 'COMPLETED');
  assert.equal(await statusOf(p4.lease_id), 'OPEN');
  // Изменилось только то, что записало завершение адресата: его строка аренды и его квитанция.
  after = await snap();
  const changed = Object.keys(after).filter((t) => JSON.stringify(after[t]) !== JSON.stringify(before[t])).sort();
  assert.deepEqual(changed, ['bem_control.chat_lease', 'bem_core.evidence'].sort(), `изменились: ${changed}`);
  assert.equal(after['bem_core.evidence'].n, before['bem_core.evidence'].n + 1, 'одна новая запись — квитанция адресата');
});
