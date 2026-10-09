// ДОКУМЕНТ: tests/roles.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:10 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 07:10 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: критерий E4-7 протокола Z1 v1.9 — машинный список ролей Kernel (src/roles.mjs) сверен с
//   таблицей 3.1 (копия canon/Z1_v1_9_table_3_1.md, сумма закреплена); неизвестная роль и право сверх
//   канона — отказ до базы; надзиратель: EXECUTE record_outbox_fence только у bem_control_owner и
//   bem_governance (вызов Kernel — 42501 и вход без OPERATOR — AUTHORITY_REQUIRED проверяет fencer.test.mjs).
// ОГРАНИЧЕНИЯ: стенд PG16 с H1.31 + Z-EXT-01, как остальные тесты Kernel.

import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { Kernel, COMMAND_TYPES } from '../src/kernel.mjs';
import { ROLES, authorize, TABLE_3_1_SECTION_SHA256 } from '../src/roles.mjs';
import { CONN, bootFixture, withRole, runStopFile, uuid } from './helpers.mjs';

const CANON = readFileSync(new URL('../canon/Z1_v1_9_table_3_1.md', import.meta.url), 'utf8');
const SECTION = CANON.slice(CANON.indexOf('-->\n\n') + 5);

test('E4-7: копия таблицы 3.1 совпадает с протоколом v1.9 (сумма раздела)', () => {
  assert.equal(createHash('sha256').update(SECTION).digest('hex'), TABLE_3_1_SECTION_SHA256);
});

test('E4-7: роли машинного списка = строки таблицы 3.1, без лишних и без пропущенных', () => {
  const rows = SECTION.split('\n').filter((l) => l.startsWith('| ') && !l.startsWith('| Роль Z1') && !/^\|[-| ]+\|$/.test(l));
  const tableRoles = new Set(rows.map((l) => l.split('|')[1].trim()));
  const listRoles = new Set(Object.values(ROLES).map((r) => r.z1));
  assert.deepEqual([...listRoles].sort(), [...tableRoles].sort());
});

test('E4-7: права ролей — только известные команды Kernel; ключевые права канона у единственной роли', () => {
  for (const [role, r] of Object.entries(ROLES)) {
    for (const c of r.commands) assert.ok(COMMAND_TYPES.includes(c), `${role}: неизвестная команда ${c}`);
    for (const c of COMMAND_TYPES) {
      if (r.commands.includes(c)) assert.equal(authorize(role, c), true);
      else assert.throws(() => authorize(role, c), { code: 'ROLE_FORBIDDEN' }, `${role} -> ${c}`);
    }
  }
  const holders = (c) => Object.keys(ROLES).filter((k) => ROLES[k].commands.includes(c)).sort();
  assert.deepEqual(holders('RecordVerdict'), ['auditor']);
  assert.deepEqual(holders('OperatorDecision'), ['operator']);
  for (const c of ['Transition', 'PublishSubject', 'ReleaseSubject']) assert.deepEqual(holders(c), ['kernel'], c);
  // «писать состояние напрямую» запрещено директорам и кураторам; надзиратель команд не вызывает.
  for (const k of ['general_director', 'director_production', 'director_quality', 'director_product', 'worker_curator',
    'analyst_executor', 'auditor', 'operator']) assert.ok(!ROLES[k].commands.includes('Transition'), k);
  for (const k of ['fencer', 'egress', 'dispatcher', 'watchdog']) assert.deepEqual([...ROLES[k].commands], [], k);
  for (const bad of ['admin', 'root', 'Оператор', '', undefined, 'kernel ', '__proto__', 'toString'])
    assert.throws(() => authorize(bad, 'GetWorkItem'), { code: 'ROLE_UNKNOWN' }, String(bad));
});

let ids;
let kernel;
before(async () => {
  ids = await bootFixture();
  kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-roles-'), requireRole: true });
  await kernel.assertIdentity();
});
after(async () => { await kernel?.close(); });

const call = (actor, role, type, payload) => kernel.execute(role === null ? { actor_id: actor } : { actor_id: actor, role },
  { type, actor_id: actor, tenant_id: ids.tenantA, command_id: uuid(), payload });

test('E4-7: Kernel отказывает до базы — без роли, с неизвестной ролью, с правом сверх канона', async () => {
  const wi = uuid();
  const create = (role) => call(ids.author, role, 'CreateWorkItem', { work_item_id: wi, evidence: { t: 'roles' } });
  assert.equal((await create(null)).error.code, 'ROLE_REQUIRED');
  assert.equal((await create('superuser')).error.code, 'ROLE_UNKNOWN');
  assert.equal((await create('auditor')).error.code, 'ROLE_FORBIDDEN');
  assert.equal((await create('analyst_executor')).error.code, 'ROLE_FORBIDDEN');
  // Ни одна из попыток не создала работу.
  const g = await call(ids.author, 'kernel', 'GetWorkItem', { work_item_id: wi });
  assert.equal(g.ok, false);
  assert.equal(g.error.code, 'NOT_FOUND');
  // Штатный путь: Kernel создаёт; директор писать состояние напрямую не может.
  assert.equal((await call(ids.author, 'kernel', 'CreateWorkItem', { work_item_id: wi, evidence: { t: 'roles' } })).ok, true);
  const tr = await call(ids.author, 'director_production', 'Transition', { work_item_id: wi, expected_revision: 1,
    new_status: 'PLANNED', evidence: { t: 'roles' } });
  assert.equal(tr.error.code, 'ROLE_FORBIDDEN');
  const after = await call(ids.author, 'kernel', 'GetWorkItem', { work_item_id: wi });
  assert.equal(after.result.status, 'NEW');
  assert.equal(after.result.revision, 1);
  // Решение оператора от роли не-оператора — отказ до проверки человека в базе.
  const od = await call(ids.humanA, 'general_director', 'OperatorDecision', { decision_code: 'OD-X' });
  assert.equal(od.error.code, 'ROLE_FORBIDDEN');
});

test('E4-7: надзиратель — EXECUTE record_outbox_fence только у bem_control_owner и bem_governance', async () => {
  const rows = await withRole('postgres', async (c) => (await c.query(`
    SELECT DISTINCT r.rolname
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
      CROSS JOIN pg_roles r
     WHERE n.nspname = 'bem_control' AND p.proname = 'record_outbox_fence'
       AND has_function_privilege(r.oid, p.oid, 'EXECUTE')
       AND NOT r.rolsuper
       AND r.rolname NOT IN (SELECT m.rolname FROM pg_roles m
                              JOIN pg_auth_members am ON am.member = m.oid
                              JOIN pg_roles g ON g.oid = am.roleid AND g.rolname = 'bem_governance')
     ORDER BY 1`)).rows.map((x) => x.rolname));
  // Члены bem_governance (входы операторов) наследуют право группы и в список не входят.
  assert.deepEqual(rows, ['bem_control_owner', 'bem_governance']);
});
