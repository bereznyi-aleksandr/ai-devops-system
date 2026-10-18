// ДОКУМЕНТ: tests/transport.test.mjs
// ВЕРСИЯ: v0.3  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 10:30 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 11:38 +03:00 (v0.3: ChatGPT R25 RG25-01 — смена участника оператора
//   между проверкой и командой и во время команды; v0.2 11:12: ChatGPT R24 — RG24-01 отзыв между
//   проверкой и командой и отзыв во время команды; RG24-02 повторное предъявление отозванного пропуска без новых строк
//   доказательства; RG24-03 путь оператора без билета и для команды без билета; тест отзыва во время команды — на своей роли 04)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: проверки пакета Z-TRANSPORT-01 на PostgreSQL 16 (проект v0.4 §3, §5): цепочка выдачи пропуска
//   (билет оператора → ГД → роль ниже → та же роль); получение без кода, с чужим кодом, для чужой сессии; истёкшая
//   подготовка; подготовка не держателем и не начальником; билет на чужую роль и повтор билета; подменённые поля
//   запроса не действуют; пропуск и код не лежат в базе открытым текстом; обычные отказы — база без изменений;
//   два события безопасности — меняются ровно оговорённые строки; гонка двух получений; отзыв при завершении
//   аренды, по билету оператора, через 30 суток; сквозной путь через местный вход и клиента.
// ОГРАНИЧЕНИЯ: стенд PG16 с H1.31 + Z-EXT-01 + Z-EXT-02 + Z-EXT-03; живая база не трогается.

import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes, generateKeyPairSync } from 'node:crypto';
import net from 'node:net';
import { Kernel } from '../src/kernel.mjs';
import { RulesError } from '../src/rules_gate.mjs';
import { createTransport, secretHash, newSecret } from '../src/transport.mjs';
import { createGateServer } from '../src/gate_server.mjs';
import { createGateClient } from '../src/gate_client.mjs';
import { CONN, bootFixture, withRole, assignAuditor, runStopFile, uuid, asRole } from './helpers.mjs';

const hex = (n) => randomBytes(n / 2).toString('hex');
const CHECKS = ['static', 'pg16', 'engine-pg', 'engine-pg-probes'];
const APP = 15368;
const FP = `SHA256:${'A'.repeat(43)}`;
const R01 = '01_Куратор_ГД';
const R02 = '02_Куратор_производства';
const R03 = '03_Куратор_качества_и_безопасности';
const R04 = '04_Куратор_проверки_отзыва';
const PARENTS = { [R01]: 'OPERATOR', [R02]: R01, [R03]: R01, [R04]: R01 };
const CODE = hex(40);
const isoNow = (ms = 0) => new Date(Date.now() + ms).toISOString().replace(/\.\d+Z$/, 'Z');

let ids;
let kernel;
let transport;
const sn = (x) => `sess-${x}-${ids.run}`;
const as = (actor, role = 'kernel') => ({ actor_id: actor, role });

// Подставные проверки правил: подпись билета «верна», если текст билета — 'good'.
const gate = {
  next: null,
  collectActivation(args) { return gate.next(args); },
  checkWorkingCopy(r) { return { code_commit: CODE, rules_commit: r }; },
  verifyReportAck({ tenantId, reportId, reportSha256 }) {
    return { namespace: 'zavod-report-ack@v1', key_fingerprint: FP, signed_ticket_sha256: hex(64),
      ticket: { tenant_id: tenantId, report_id: reportId, report_sha256: reportSha256 } };
  },
  nonce: null,
  verifyEnrollTicket({ ticketText }) {
    if (ticketText !== 'good') throw new RulesError('RULES_SIGNATURE_INVALID', 'zavod-session-enroll@v1');
    return { nonce: gate.nonce ?? hex(32), expires_at: isoNow(3600_000) };
  },
  verifyRevokeTicket({ ticketText }) {
    if (ticketText !== 'good') throw new RulesError('RULES_SIGNATURE_INVALID', 'zavod-session-revoke@v1');
    return { nonce: hex(32), expires_at: isoNow(3600_000) };
  },
};

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
const okk = (r) => { assert.equal(r.ok, true, JSON.stringify(r.error)); return r.result; };
async function newItem(tenant = ids.tenantA) {
  const wi = uuid();
  okk(await kernel.execute(as(ids.author), { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: tenant,
    payload: { work_item_id: wi, evidence: { test: 'create' } } }));
  return wi;
}
async function finish(wi, tenant = ids.tenantA) {
  let rev = 1;
  for (const s of ['PLANNED', 'IN_PROGRESS', 'IN_REVIEW', 'ACCEPTED']) {
    okk(await kernel.execute(as(ids.author), { type: 'Transition', actor_id: ids.author, tenant_id: tenant, command_id: uuid(),
      payload: { work_item_id: wi, expected_revision: rev, new_status: s, evidence: { test: s } } }));
    rev += 1;
  }
}
async function activateRules(tenant) {
  const wi = await newItem(tenant);
  const subj = uuid();
  const head = hex(40);
  okk(await kernel.execute(as(ids.author), { type: 'PublishSubject', actor_id: ids.author, tenant_id: tenant,
    payload: { subject_id: subj, work_item_id: wi, head_sha: head, criticality: 'CRITICAL', scope: 'BEM954_PROTOCOL',
      authors: [ids.author], evidence: { test: 'rules subject' } } }));
  for (const aud of [ids.audOpenai, ids.audAnthropic]) {
    await assignAuditor(tenant, subj, aud);
    okk(await kernel.execute(as(aud, 'auditor'), { type: 'RecordVerdict', actor_id: aud, tenant_id: tenant,
      payload: { subject_id: subj, head_sha: head, verdict: 'ACCEPT', evidence: { reviewed: head } } }));
  }
  okk(await kernel.execute(as(ids.author), { type: 'ReleaseSubject', actor_id: ids.author, tenant_id: tenant,
    payload: { subject_id: subj, head_sha: head } }));
  const f = facts({ tenant, subject: subj, head });
  gate.next = () => f;
  okk(await kernel.execute(as(ids.author), { type: 'ActivateRules', actor_id: ids.author, tenant_id: tenant,
    payload: { pr_number: 7, subject_id: subj, ticket: '{}', signature: 'sig' } }));
}

// Снимок всей базы (как RG15-02): число строк и отпечаток каждой таблицы.
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
const changed = (a, b) => Object.keys(b).filter((t) => JSON.stringify(a[t]) !== JSON.stringify(b[t])).sort();
const pg = (sql, args) => withRole('postgres', async (c) => (await c.query(sql, args)).rows);

const send = (body) => transport.handle(body);
// Обычный отказ: ожидаемый код и неизменная база.
async function refusedSame(fn, code) {
  const before = await snap();
  const r = await fn();
  const got = r.body?.error?.code;
  assert.equal(r.body?.ok, false, `ожидался отказ ${code}, получено ${JSON.stringify(r.body)}`);
  assert.equal(got, code, JSON.stringify(r.body));
  assert.deepEqual(await snap(), before, `${code}: база изменилась после обычного отказа`);
  return r;
}
const cmd = (s, type, payload) => send({ type, command_id: uuid(), payload, auth: { session: s.session, pass: s.pass } });
const claim = (session, code) => send({ type: 'EnrollSession', payload: { session, claim_code: code } });
function opPrepare(role, session, code, ticket = 'good', tenant = ids.tenantA) {
  return send({ type: 'PrepareEnrollment', payload: { tenant_id: tenant, role_key: role, session,
    claim_sha256: secretHash(code), ticket, signature: 's' }, auth: { operator: true } });
}
function prepare(by, role, session, code) {
  return cmd(by, 'PrepareEnrollment', { role_key: role, session, claim_sha256: secretHash(code) });
}
async function enrolled(session, prep) {
  const code = newSecret();
  const r = await prep(code);
  assert.equal(r.body.ok, true, JSON.stringify(r.body));
  const c = await claim(session, code);
  assert.equal(c.body.ok, true, JSON.stringify(c.body));
  return { session, pass: c.body.result.pass, code, enrollment: r.body.result.enrollment_id };
}

const S = {};
before(async () => {
  ids = await bootFixture();
  await withRole('bem_bootstrap_admin', async (c) => {
    for (const a of [ids.author, ids.humanA]) {
      await c.query("SELECT bem_control.grant_delegation('bem_rules_gate', $1, $2)", [a, `zavod transport test ${ids.run}`]);
    }
  });
  kernel = new Kernel({ connection: CONN, rulesConnection: CONN, stopFile: runStopFile('zavod-transport-'), rules: gate });
  transport = createTransport({ kernel });
  kernel.transport = transport;
  await kernel.assertIdentity();
  await withRole('postgres', async (c) => {
    await c.query('SET ROLE bem_governance');
    for (const r of [R01, R02, R03, R04]) await c.query('SELECT bem_control.set_role_actor($1, $2, $3)', [ids.tenantA, r, ids.author]);
    await c.query("SELECT bem_control.set_role_actor($1, 'OPERATOR', $2)", [ids.tenantA, ids.humanA]);
  });
  await activateRules(ids.tenantA);
});
after(async () => { await kernel?.close(); });

test('§4: участника роли пишет только путь управления; таблицы выдачи и пропусков закрыты на запись', async () => {
  const e = await withRole('bem_kernel_rw', (c) => c.query('SELECT bem_control.set_role_actor($1, $2, $3)',
    [ids.tenantA, R02, ids.author]).then(() => null, (x) => x));
  assert.match(String(e?.message), /permission denied/);
  for (const t of ['role_actor', 'session_enrollment', 'session_credential']) {
    const [r] = await pg(`SELECT has_table_privilege('bem_kernel_rw', 'bem_control.${t}', 'INSERT') AS i,
      has_table_privilege('bem_kernel_rw', 'bem_control.${t}', 'UPDATE') AS u`);
    assert.deepEqual(r, { i: false, u: false }, t);
  }
});

test('§3.1: цепочка выдачи — билет оператора → ГД; ГД → роль ниже; держатель → та же роль; поля запроса не действуют', async () => {
  // Без билета и с неверной подписью — отказ, база не меняется.
  await refusedSame(() => opPrepare(R01, sn('g1'), newSecret(), 'bad'), 'RULES_SIGNATURE_INVALID');
  await refusedSame(() => opPrepare(R02, sn('p1'), newSecret()), 'ENROLL_TICKET_NOT_FOR_ROLE');
  S.g1 = await enrolled(sn('g1'), (code) => opPrepare(R01, sn('g1'), code));
  assert.equal(S.g1.pass.length, 64);
  // Повтор того же одноразового номера билета — отказ.
  const used = (await pg('SELECT ticket_nonce FROM bem_control.session_enrollment WHERE enrollment_id = $1', [S.g1.enrollment]))[0].ticket_nonce;
  gate.nonce = used;
  await refusedSame(() => opPrepare(R01, sn('g9'), newSecret()), 'ENROLL_TICKET_REUSED');
  gate.nonce = null;

  S.wiG = await newItem();
  // Подменённые заказчик, роль и сессия в запросе не действуют: аренда — роли и сессии из пропуска.
  S.leaseG = okk((await send({ type: 'OpenChatLease', command_id: uuid(), payload: { work_item_id: S.wiG,
    tenant_id: ids.tenantB, role_key: R03, session: 'evil', actor_id: 'claude:evil' },
    auth: { session: sn('g1'), pass: S.g1.pass } })).body);
  const [row] = await pg('SELECT tenant_id, role_key, holder_session FROM bem_control.chat_lease WHERE lease_id = $1', [S.leaseG.lease_id]);
  assert.deepEqual(row, { tenant_id: ids.tenantA, role_key: R01, holder_session: sn('g1') });

  // Держатель ГД готовит выдачу роли ниже; та роль — следующей сессии той же роли.
  S.p1 = await enrolled(sn('p1'), (code) => prepare(S.g1, R02, sn('p1'), code));
  S.wiP = await newItem();
  S.leaseP = okk((await cmd(S.p1, 'OpenChatLease', { work_item_id: S.wiP })).body);
  S.p2 = await enrolled(sn('p2'), (code) => prepare(S.p1, R02, sn('p2'), code));
  const [en] = await pg('SELECT prepared_by, prepared_by_session FROM bem_control.session_enrollment WHERE enrollment_id = $1', [S.p2.enrollment]);
  assert.deepEqual(en, { prepared_by: 'SAME_ROLE', prepared_by_session: sn('p1') });
});

test('§3.1: подготовка не держателем и не начальником, занятая роль, сессия с пропуском — отказ без изменений', async () => {
  // p2 имеет пропуск, но аренды нет — не держатель.
  await refusedSame(() => prepare(S.p2, R02, sn('p3'), newSecret()), 'ENROLL_NOT_AUTHORIZED');
  // p1 держит R02, но R03 ему не подчинена; R01 — его начальник, а не подчинённый.
  await refusedSame(() => prepare(S.p1, R03, sn('q1'), newSecret()), 'ENROLL_NOT_AUTHORIZED');
  await refusedSame(() => prepare(S.p1, R01, sn('g2'), newSecret()), 'ENROLL_NOT_AUTHORIZED');
  await refusedSame(() => prepare(S.p1, R02, sn('p1'), newSecret()), 'ENROLL_SELF');
  await refusedSame(() => prepare(S.g1, R03, sn('p2'), newSecret()), 'ENROLL_SESSION_HAS_PASS');
  // Одна ожидающая на роль.
  const pend = okk((await prepare(S.g1, R03, sn('q1'), newSecret())).body);
  await refusedSame(() => prepare(S.g1, R03, sn('q2'), newSecret()), 'ENROLL_BUSY');
  // Истёкшая освобождает место (переводится в EXPIRED при следующей подготовке).
  await pg("UPDATE bem_control.session_enrollment SET expires_at = now() - interval '1 second' WHERE enrollment_id = $1", [pend.enrollment_id]);
  S.q2code = newSecret();
  S.q2en = okk((await prepare(S.g1, R03, sn('q2'), S.q2code)).body);
  const [old] = await pg('SELECT status FROM bem_control.session_enrollment WHERE enrollment_id = $1', [pend.enrollment_id]);
  assert.equal(old.status, 'EXPIRED');
});

test('§3.3 RG21-01: получение без кода, с чужим кодом, для чужой сессии, после срока — обычный отказ, ничего не отзывается', async () => {
  await refusedSame(() => send({ type: 'EnrollSession', payload: { session: sn('q2') } }), 'ENROLL_BAD_REQUEST');
  await refusedSame(() => claim(sn('q2'), newSecret()), 'ENROLL_BAD_CODE');
  await refusedSame(() => claim(sn('q2'), S.p2.code), 'ENROLL_BAD_CODE');
  await refusedSame(() => claim(sn('nobody'), S.q2code), 'ENROLL_NOT_FOUND');
  await refusedSame(() => claim(sn('p2'), S.q2code), 'ENROLL_BAD_CODE');
  await refusedSame(() => send({ type: 'EnrollSession', payload: { session: sn('q2'), claim_code: S.q2code }, auth: {} }), 'GATE_BAD_REQUEST');
  const [st] = await pg('SELECT status FROM bem_control.session_enrollment WHERE enrollment_id = $1', [S.q2en.enrollment_id]);
  assert.equal(st.status, 'PENDING', 'ожидающая запись цела после чужих попыток');
  // Срок вышел — обычный отказ, запись не меняется.
  await pg("UPDATE bem_control.session_enrollment SET expires_at = now() - interval '1 second' WHERE enrollment_id = $1", [S.q2en.enrollment_id]);
  await refusedSame(() => claim(sn('q2'), S.q2code), 'ENROLL_EXPIRED');
  // Пропуск: неверный, чужой сессии, без auth, с лишним полем — отказ до базы ядра, база без изменений.
  const lease = { work_item_id: uuid() };
  await refusedSame(() => cmd({ session: sn('p2'), pass: newSecret() }, 'OpenChatLease', lease), 'CALLER_NOT_AUTHENTICATED');
  await refusedSame(() => cmd({ session: sn('p2'), pass: S.p1.pass }, 'OpenChatLease', lease), 'CALLER_NOT_AUTHENTICATED');
  await refusedSame(() => send({ type: 'OpenChatLease', payload: lease }), 'CALLER_NOT_AUTHENTICATED');
  await refusedSame(() => send({ type: 'OpenChatLease', payload: lease, auth: { session: sn('p2'), pass: S.p2.pass, role_key: R01 } }),
    'CALLER_NOT_AUTHENTICATED');
  await refusedSame(() => send({ type: 'OpenChatLease', payload: lease, auth: { operator: true } }), 'CALLER_NOT_AUTHENTICATED');
  await refusedSame(() => send({ type: 'CreateWorkItem', payload: {}, auth: { session: sn('p2'), pass: S.p2.pass } }), 'GATE_COMMAND_NOT_ALLOWED');
  await refusedSame(() => send({ type: 'OpenChatLease', payload: lease, auth: { session: sn('p2'), pass: S.p2.pass }, tenant_id: ids.tenantB }),
    'GATE_BAD_REQUEST');
});

test('§3.3: событие (а) — верный код после выдачи: отзыв, конфликт и одна строка доказательства; событие (б) — строка один раз (RG24-02)', async () => {
  const s = await enrolled(sn('q3'), (code) => prepare(S.g1, R03, sn('q3'), code));
  const before = await snap();
  const r = await claim(sn('q3'), s.code);
  assert.equal(r.body.error.code, 'ENROLL_REPLAY');
  const after1 = await snap();
  assert.deepEqual(changed(before, after1), ['bem_control.session_credential', 'bem_control.session_enrollment', 'bem_core.evidence']);
  assert.equal(after1['bem_core.evidence'].n - before['bem_core.evidence'].n, 1);
  const [c] = await pg('SELECT revoke_reason FROM bem_control.session_credential WHERE session = $1', [sn('q3')]);
  assert.equal(c.revoke_reason, 'CLAIM_REPLAY');
  const [e] = await pg('SELECT status FROM bem_control.session_enrollment WHERE enrollment_id = $1', [s.enrollment]);
  assert.equal(e.status, 'CONFLICT');
  // Отозванный пропуск: отказ ядра, одна строка доказательства и счётчик в строке пропуска.
  const r2 = await cmd(s, 'OpenChatLease', { work_item_id: uuid() });
  assert.equal(r2.body.error.code, 'CALLER_NOT_AUTHENTICATED');
  const after2 = await snap();
  assert.deepEqual(changed(after1, after2), ['bem_control.session_credential', 'bem_core.evidence']);
  assert.equal(after2['bem_core.evidence'].n - after1['bem_core.evidence'].n, 1);
  // RG24-02: повторные предъявления новых строк доказательства не дают — растёт только счётчик.
  for (let i = 0; i < 3; i += 1) {
    assert.equal((await cmd(s, 'OpenChatLease', { work_item_id: uuid() })).body.error.code, 'CALLER_NOT_AUTHENTICATED');
  }
  const after3 = await snap();
  assert.deepEqual(changed(after2, after3), ['bem_control.session_credential']);
  assert.equal(after3['bem_core.evidence'].n, after2['bem_core.evidence'].n);
  const [seen] = await pg('SELECT revoked_seen_count AS n FROM bem_control.session_credential WHERE session = $1', [sn('q3')]);
  assert.equal(seen.n, 4);
  const [ev] = await pg(`SELECT payload->>'event' AS e FROM bem_core.evidence WHERE kind = 'SESSION_SECURITY_EVENT'
    AND payload->>'session' = $1 ORDER BY created_at DESC LIMIT 1`, [sn('q3')]);
  assert.equal(ev.e, 'REVOKED_PASS_PRESENTED');
});

test('§5: гонка двух получений одной выдачи — одно получение, второе — событие безопасности, пропуск отозван', async () => {
  const code = newSecret();
  const en = okk((await prepare(S.g1, R03, sn('q4'), code)).body);
  const holder = asRole('postgres');
  await holder.connect();
  try {
    await holder.query('BEGIN');
    await holder.query('SELECT 1 FROM bem_control.session_enrollment WHERE enrollment_id = $1 FOR UPDATE', [en.enrollment_id]);
    const both = Promise.all([claim(sn('q4'), code), claim(sn('q4'), code)]);
    await new Promise((r) => setTimeout(r, 500));
    await holder.query('COMMIT');
    const codes = (await both).map((r) => (r.body.ok ? 'OK' : r.body.error.code)).sort();
    assert.deepEqual(codes, ['ENROLL_REPLAY', 'OK']);
  } finally { await holder.end(); }
  const [c] = await pg('SELECT revoke_reason FROM bem_control.session_credential WHERE session = $1', [sn('q4')]);
  assert.equal(c.revoke_reason, 'CLAIM_REPLAY');
});

test('§3: пропуск и код выдачи не лежат в базе открытым текстом', async () => {
  const secrets = [S.g1.pass, S.g1.code, S.p1.pass, S.p1.code, S.p2.pass, S.p2.code];
  const found = await withRole('postgres', async (c) => {
    const { rows: tabs } = await c.query(`SELECT format('%I.%I', schemaname, tablename) AS t FROM pg_tables
      WHERE schemaname NOT IN ('pg_catalog', 'information_schema')`);
    const hits = [];
    for (const { t } of tabs) {
      const { rows } = await c.query(`SELECT count(*)::int AS n FROM ${t} x WHERE ${secrets.map((_, i) => `strpos(x::text, $${i + 1}) > 0`).join(' OR ')}`, secrets);
      if (rows[0].n) hits.push(t);
    }
    return hits;
  });
  assert.deepEqual(found, []);
  const [h] = await pg('SELECT pass_sha256 FROM bem_control.session_credential WHERE session = $1', [sn('p1')]);
  assert.equal(h.pass_sha256, secretHash(S.p1.pass));
});

test('§3.1 шаг 3: отзыв при завершении аренды в той же транзакции; по билету оператора; через 30 суток', async () => {
  // p1 завершает аренду по полному порядку Л.12: три записи, отчёт ГД, подтверждение, работа принята.
  const rec = (kind) => cmd(S.p1, 'RecordLeaseEvidence', { lease_id: S.leaseP.lease_id, generation: S.leaseP.generation,
    kind, content_sha256: hex(64) });
  const [pr, pm, pn] = [okk((await rec('TASK_RESULT')).body).evidence_id, okk((await rec('ROLE_MEMORY')).body).evidence_id,
    okk((await rec('NEXT_STEP')).body).evidence_id];
  const sum = hex(64);
  const rep = okk((await cmd(S.p1, 'FileLeaseReport', { lease_id: S.leaseP.lease_id, generation: S.leaseP.generation,
    report_sha256: sum })).body).report_id;
  okk((await cmd(S.g1, 'AcknowledgeReport', { report_id: rep, report_sha256: sum })).body);
  await finish(S.wiP);
  const done = okk((await cmd(S.p1, 'CompleteChatLease', { lease_id: S.leaseP.lease_id, generation: S.leaseP.generation,
    result_evidence_id: pr, memory_evidence_id: pm, next_evidence_id: pn, report_id: rep })).body);
  assert.equal(done.pass_revoked, 1);
  const [c] = await pg('SELECT revoke_reason FROM bem_control.session_credential WHERE session = $1', [sn('p1')]);
  assert.equal(c.revoke_reason, 'LEASE_COMPLETED');
  assert.equal((await cmd(S.p1, 'OpenChatLease', { work_item_id: await newItem() })).body.error.code, 'CALLER_NOT_AUTHENTICATED');
  // Та же сессия после новой выдачи снова работает: старая закрытая аренда новый пропуск не гасит.
  const again = await enrolled(sn('p1'), (code) => prepare(S.g1, R02, sn('p1'), code));
  const l2 = okk((await cmd(again, 'OpenChatLease', { work_item_id: await newItem() })).body);
  assert.ok(l2.lease_id);
  // Отзыв «по завершению» при открытой аренде — отказ базы.
  const e = await withRole('bem_kernel_rw', async (cl) => {
    await cl.query('BEGIN');
    try {
      await cl.query("SELECT set_config('app.actor_id', $1, true), set_config('app.tenant_id', $2, true)", [ids.author, ids.tenantA]);
      await cl.query("SELECT bem_control.revoke_session_credential($1, $2, 'LEASE_COMPLETED')", [ids.tenantA, sn('g1')]);
      return null;
    } catch (x) { return x; } finally { await cl.query('ROLLBACK'); }
  });
  assert.match(String(e?.message), /REVOKE_LEASE_NOT_COMPLETED/);
  // Билет оператора: неверная подпись — отказ; верная — отзыв.
  await refusedSame(() => send({ type: 'RevokeSession', payload: { tenant_id: ids.tenantA, session: sn('p2'), ticket: 'bad', signature: 's' },
    auth: { operator: true } }), 'RULES_SIGNATURE_INVALID');
  await refusedSame(() => cmd(S.g1, 'RevokeSession', { session: sn('p2') }), 'REVOKE_OPERATOR_ONLY');
  const rv = okk((await send({ type: 'RevokeSession', payload: { tenant_id: ids.tenantA, session: sn('p2'), ticket: 'good',
    signature: 's' }, auth: { operator: true } })).body);
  assert.equal(rv.revoked, 1);
  assert.equal((await cmd(S.p2, 'OpenChatLease', { work_item_id: await newItem() })).body.error.code, 'CALLER_NOT_AUTHENTICATED');
  // 30 суток без открытой аренды — пропуск недействителен (обычный отказ).
  const s = await enrolled(sn('q5'), (code) => prepare(S.g1, R03, sn('q5'), code));
  await pg("UPDATE bem_control.session_credential SET issued_at = now() - interval '31 days' WHERE session = $1", [sn('q5')]);
  await refusedSame(() => cmd(s, 'OpenChatLease', { work_item_id: uuid() }), 'CALLER_NOT_AUTHENTICATED');
});

test('сквозной путь: местный вход → посредник → ядро; клиент проверяет подпись /hello', async () => {
  const key = generateKeyPairSync('ed25519');
  const port = await new Promise((resolve) => { const s = net.createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => resolve(p)); }); });
  const g = createGateServer({ port, privateKey: key.privateKey, stopFile: runStopFile('zavod-gate-'), onCommand: (b) => transport.handle(b) });
  await g.start();
  try {
    const client = createGateClient({ port, publicKey: key.publicKey });
    const code = newSecret();
    okk((await client.command({ type: 'PrepareEnrollment', command_id: uuid(), payload: { role_key: R03, session: sn('q6'),
      claim_sha256: secretHash(code) }, auth: { session: sn('g1'), pass: S.g1.pass } })).body);
    const got = await client.command({ type: 'EnrollSession', payload: { session: sn('q6'), claim_code: code } });
    assert.equal(got.status, 200);
    const pass = got.body.result.pass;
    const wi = await newItem();
    const l = await client.command({ type: 'OpenChatLease', command_id: uuid(), payload: { work_item_id: wi }, auth: { session: sn('q6'), pass } });
    assert.equal(l.status, 200, JSON.stringify(l.body));
    const [row] = await pg('SELECT role_key, holder_session FROM bem_control.chat_lease WHERE lease_id = $1', [l.body.result.lease_id]);
    assert.deepEqual(row, { role_key: R03, holder_session: sn('q6') });
  } finally { await g.close(); }
});

const opRevoke = (session) => send({ type: 'RevokeSession', payload: { tenant_id: ids.tenantA, session, ticket: 'good',
  signature: 's' }, auth: { operator: true } });

test('RG24-01: отзыв между проверкой пропуска и командой — команда отклонена, база без изменений, кроме отзыва', async () => {
  const s = await enrolled(sn('q7'), (code) => prepare(S.g1, R03, sn('q7'), code));
  const wi = await newItem();
  const real = kernel.transport;
  let afterRevoke;
  let first = true;
  // Отзыв срабатывает один раз — после проверки пропуска команды; сам отзыв идёт обычным путём посредника.
  kernel.transport = { verify: async (req) => {
    const v = await real.verify(req);
    if (first) {
      first = false;
      assert.equal(okk((await opRevoke(sn('q7'))).body).revoked, 1);
      afterRevoke = await snap();
    }
    return v;
  } };
  let r;
  try {
    r = await kernel.execute(null, real.accept({ type: 'OpenChatLease', command_id: uuid(), payload: { work_item_id: wi },
      auth: { session: s.session, pass: s.pass } }));
  } finally { kernel.transport = real; }
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'CALLER_NOT_AUTHENTICATED');
  assert.deepEqual(await snap(), afterRevoke, 'команда после отзыва ничего не записала');
  const rows = await pg('SELECT 1 FROM bem_control.chat_lease WHERE holder_session = $1', [sn('q7')]);
  assert.equal(rows.length, 0);
});

test('RG24-01: отзыв во время команды ждёт её конца (строка пропуска под блокировкой на чтение)', async () => {
  const s = await enrolled(sn('q8'), (code) => prepare(S.g1, R04, sn('q8'), code)); // своя роль: R03 держит аренда сквозного теста
  const wi = await newItem();
  let revoke;
  let doneEarly = false;
  kernel._beforeCommit = async () => {
    kernel._beforeCommit = null;
    revoke = opRevoke(sn('q8')).then((x) => { doneEarly = true; return x; });
    await new Promise((res) => setTimeout(res, 700));
    assert.equal(doneEarly, false, 'отзыв не должен пройти до конца команды');
  };
  let lease;
  try {
    lease = okk((await cmd(s, 'OpenChatLease', { work_item_id: wi })).body);
  } finally { kernel._beforeCommit = null; }
  assert.equal(okk((await revoke).body).revoked, 1);
  const [row] = await pg('SELECT holder_session FROM bem_control.chat_lease WHERE lease_id = $1', [lease.lease_id]);
  assert.equal(row.holder_session, sn('q8'));
  assert.equal((await cmd(s, 'RecordLeaseEvidence', { lease_id: lease.lease_id, generation: lease.generation,
    kind: 'TASK_RESULT', content_sha256: hex(64) })).body.error.code, 'CALLER_NOT_AUTHENTICATED');
});

test('RG24-03: «оператор» без билета, для команды без билета, без повторной проверки — отказ без изменений', async () => {
  // Посредник: без билета или подписи путь оператора не открывается.
  await refusedSame(() => send({ type: 'RevokeSession', payload: { tenant_id: ids.tenantA, session: sn('g1') },
    auth: { operator: true } }), 'CALLER_NOT_AUTHENTICATED');
  await refusedSame(() => send({ type: 'PrepareEnrollment', payload: { tenant_id: ids.tenantA, role_key: R01, session: sn('g7'),
    claim_sha256: hex(64), ticket: 'good' }, auth: { operator: true } }), 'CALLER_NOT_AUTHENTICATED');
  await refusedSame(() => send({ type: 'OpenChatLease', payload: { tenant_id: ids.tenantA, work_item_id: uuid(), ticket: 'good',
    signature: 's' }, auth: { operator: true } }), 'CALLER_NOT_AUTHENTICATED');
  // Ядро: личность «оператор» для команды без билета и личность без повторной проверки не принимаются.
  const [{ actor_id: op }] = await pg("SELECT actor_id FROM bem_control.role_actor WHERE tenant_id = $1 AND role_key = 'OPERATOR'",
    [ids.tenantA]);
  const real = kernel.transport;
  const fake = (v) => { kernel.transport = { verify: async () => v }; };
  try {
    fake({ tenant_id: ids.tenantA, actor_id: op, role_key: 'OPERATOR', session: 'OPERATOR', hold: async () => {} });
    await refusedSame(async () => ({ body: await kernel.execute(null, { type: 'OpenChatLease', payload: { work_item_id: uuid() } }) }),
      'OPERATOR_TICKET_REQUIRED');
    fake({ tenant_id: ids.tenantA, actor_id: ids.author, role_key: R01, session: sn('g1') });
    await refusedSame(async () => ({ body: await kernel.execute(null, { type: 'OpenChatLease', payload: { work_item_id: uuid() } }) }),
      'CALLER_NOT_AUTHENTICATED');
  } finally { kernel.transport = real; }
});

// RG25-01: смена участника оператора путём управления.
const setOperator = (actor) => withRole('postgres', async (c) => {
  await c.query('SET ROLE bem_governance');
  await c.query("SELECT bem_control.set_role_actor($1, 'OPERATOR', $2)", [ids.tenantA, actor]);
});

test('RG25-01: смена участника оператора между проверкой и командой — команда по билету отклонена, база без изменений', async () => {
  const s = await enrolled(sn('q9'), (code) => prepare(S.g1, R03, sn('q9'), code));
  assert.ok(s.pass);
  const real = kernel.transport;
  let afterChange;
  kernel.transport = { verify: async (req) => {
    const v = await real.verify(req);
    await setOperator(ids.author);
    afterChange = await snap();
    return v;
  } };
  let r;
  try {
    r = await kernel.execute(null, real.accept({ type: 'RevokeSession', command_id: uuid(), payload: { tenant_id: ids.tenantA,
      session: sn('q9'), ticket: 'good', signature: 's' }, auth: { operator: true } }));
  } finally { kernel.transport = real; await setOperator(ids.humanA); }
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'CALLER_NOT_AUTHENTICATED');
  const [c] = await pg('SELECT revoked_at FROM bem_control.session_credential WHERE session = $1', [sn('q9')]);
  assert.equal(c.revoked_at, null, 'пропуск не отозван');
  assert.ok(afterChange);
});

test('RG25-01: смена участника оператора во время команды ждёт её конца (строка участника под блокировкой на чтение)', async () => {
  const s = await enrolled(sn('q10'), (code) => prepare(S.g1, R04, sn('q10'), code));
  assert.ok(s.pass);
  let change;
  let doneEarly = false;
  kernel._beforeCommit = async () => {
    kernel._beforeCommit = null;
    change = setOperator(ids.author).then(() => { doneEarly = true; });
    await new Promise((res) => setTimeout(res, 700));
    assert.equal(doneEarly, false, 'смена участника не должна пройти до конца команды');
  };
  let rv;
  try {
    rv = okk((await opRevoke(sn('q10'))).body);
  } finally { kernel._beforeCommit = null; }
  await change;
  try {
    assert.equal(rv.revoked, 1);
    const [a] = await pg("SELECT actor_id FROM bem_control.role_actor WHERE tenant_id = $1 AND role_key = 'OPERATOR'", [ids.tenantA]);
    assert.equal(a.actor_id, ids.author, 'смена прошла после команды');
  } finally { await setOperator(ids.humanA); }
});
