// ДОКУМЕНТ: tests/fencer.test.mjs
// ВЕРСИЯ: v0.4.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 17:55 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 09:00 +03:00 (v0.4.1: проба
//   FENCE_UNIT_UNSUPPORTED выключает и единицу-контейнер; v0.4: слияние —
//   v0.3 (этап 3, аудит E3-5 M-E35-02): надзиратель и запись ограждения идут от штатного входа оператора H1.31
//   (своя роль входа, член bem_governance, связанный участник, OPERATOR), не от bem_bootstrap_admin; вход
//   первой установки, Kernel и postgres надзиратель не принимает; член governance без OPERATOR —
//   AUTHORITY_REQUIRED; v0.3 (этап 4): те же тесты на Windows Job Object; вид единицы и способ берутся
//   из найденной единицы. v0.2: аудит Z5 —
//   M-Z5-01: живой потомок исполнителя, ограждение всей единицы cgroup v2, мутация «только родитель»;
//   M-Z5-02: только оператор (bem_governance + полномочие OPERATOR) пишет ограждение, точный список)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: сценарий E4-8 на настоящих процессах. Исполнитель ставит отметку начала отправки,
//   порождает потомка с доступом к адаптеру (отдельная сессия setsid) и замирает; аренда истекает →
//   UNKNOWN_OUTCOME; сверка без ограждения — отказ; живая единица — отказ без записи в базу;
//   мутация «завершить только родителя» — отказ, потомок жив и даёт эффект; настоящее ограждение
//   единицы — в ней нет ни одного процесса, GO эффекта не даёт, новая попытка — ровно один эффект.
//   Тесты на процессах требуют единицу: Linux cgroup v2 (ZAVOD_CGROUP_ROOT) или Windows Job Object
//   (win/zavod_jobhost.exe); при CI=true пропуск запрещён (падение).
//   Проверки базы (E4-7) от процессов не зависят и идут везде.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Kernel } from '../src/kernel.mjs';
import { SendSupervisor, CgroupUnit, JobObjectUnit, pidAlive } from '../src/fencer.mjs';
import { CONN, bootFixture, withRole, uuid, operatorLogin } from './helpers.mjs';

let ids;
let kernel;
let sup;
let dir;
let op;      // вход оператора с полномочием OPERATOR (кластер)
let opNo;    // тот же вид входа без полномочия
const as = (actor) => ({ actor_id: actor });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CHILD = fileURLToPath(new URL('./paused_sender.mjs', import.meta.url));
const UNIT = CgroupUnit.supported() ? { kind: 'CGROUP_V2', method: 'CGROUP_KILLED' }
  : JobObjectUnit.supported() ? { kind: 'JOB_OBJECT', method: 'JOB_OBJECT_TERMINATED' } : null;
const IN_CI = process.env.CI === 'true';
// Пропуск теста на процессах вне Linux допустим только локально; в CI — падение.
const unitSkip = UNIT ? false : (IN_CI ? false : 'нет единицы исполнения (cgroup v2 / Job Object) — только локально');

before(async () => {
  ids = await bootFixture();
  dir = mkdtempSync(join(tmpdir(), 'zavod-fencer-'));
  const stopFile = join(dir, 'KERNEL_STOP');
  writeFileSync(stopFile, 'RUN\n');
  kernel = new Kernel({ connection: CONN, stopFile });
  await kernel.assertIdentity();
  op = await operatorLogin();
  opNo = await operatorLogin({ withOperator: false });
  sup = new SendSupervisor({ connection: { ...CONN, user: op.role } });
});
after(async () => {
  for (const r of sup?.runtimes.values() ?? []) {
    try { if (r.unit.populated()) await r.unit.kill(5000); } catch { /* единица уже пуста */ }
  }
  await sup?.close();
  await kernel?.close();
});

async function outboxRow(kind) {
  const wi = uuid();
  let r = await kernel.execute(as(ids.author), { type: 'CreateWorkItem', actor_id: ids.author, tenant_id: ids.tenantA,
    payload: { work_item_id: wi, evidence: { test: 'fencer' } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  r = await kernel.execute(as(ids.author), { type: 'Transition', actor_id: ids.author, tenant_id: ids.tenantA,
    command_id: uuid(), payload: { work_item_id: wi, expected_revision: 1, new_status: 'PLANNED',
      evidence: { test: 'fencer outbox' }, outbox_kind: kind, outbox_payload: { t: kind } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  return withRole('postgres', async (c) =>
    (await c.query('SELECT id FROM bem_core.outbox WHERE work_item_id = $1', [wi])).rows[0].id);
}
const rowOf = (id) => withRole('postgres', async (c) => (await c.query(
  'SELECT status, lease_epoch, send_started_epoch, send_runtime_instance, result FROM bem_core.outbox WHERE id = $1',
  [id])).rows[0]);
const fenceRows = (id) => withRole('postgres', async (c) =>
  (await c.query('SELECT runtime_instance, method FROM bem_control.outbox_send_fence WHERE outbox_id = $1', [id])).rows);
const kq = (sql, args) => withRole('bem_kernel_rw', async (c) => (await c.query(sql, args)).rows[0]);
const gov = (sql, args, role = op.role) => withRole(role, async (c) => {
  await c.query("SELECT set_config('app.tenant_id', $1, false)", [ids.tenantA]);
  return (await c.query(sql, args)).rows[0];
});
const reconcile = (id, outcome) => gov('SELECT bem_control.reconcile_unknown_outcome($1, $2, $3, $4) AS s',
  [ids.tenantA, id, outcome, { test: 'fencer reconcile' }]);
const dbFence = (id, epoch, worker, rt, ev, method = 'CGROUP_KILLED', role = op.role) => gov(
  'SELECT bem_control.record_outbox_fence($1, $2, $3, $4, $5, $6, $7) AS e',
  [ids.tenantA, id, epoch, worker, rt, method, ev], role);
// Захват другим исполнителем: чужие строки сразу возвращаются как FAILED.
async function claim(worker, lease, mine) {
  return withRole('bem_kernel_rw', async (c) => {
    const { rows } = await c.query('SELECT * FROM bem_control.claim_outbox_batch(500, $1::interval, $2)', [lease, worker]);
    for (const x of rows.filter((x) => x.outbox_id !== mine)) {
      await c.query('SELECT bem_control.finish_outbox_row($1, $2, $3, \'FAILED\', $4)',
        [x.outbox_id, x.lease_epoch, worker, { released_by_test: 'fencer' }]);
    }
    return rows.find((x) => x.outbox_id === mine);
  });
}
const effects = (file) => (existsSync(file) ? readFileSync(file, 'utf8').split('\n').filter(Boolean) : []);
const key = (id, epoch, runtimeInstance) => ({ tenantId: ids.tenantA, outboxId: id, leaseEpoch: epoch, worker: 'w1', runtimeInstance });

// Попытка в своей единице: отметка поставлена, потомок с адаптером жив, исполнитель замер; аренда истекла.
async function pausedAttempt(tag) {
  const counter = join(dir, `effects-${tag}-${ids.run}.txt`);
  const go = join(dir, `GO-${tag}-${ids.run}`);
  const id = await outboxRow(`zavod.fencer.${tag}.${ids.run}`);
  const { runtimeInstance } = sup.spawnAttempt(CHILD, [counter, 'w1', '1 second', id, go, '1']);
  const desc = sup.waitMessage(runtimeInstance, 'DESCENDANT');
  const m = await sup.waitMessage(runtimeInstance, 'MARKED');
  const { pid: descPid } = await desc;
  assert.equal(m.outbox_id, id);
  assert.equal(m.runtime_instance, runtimeInstance);
  assert.equal((await rowOf(id)).send_runtime_instance, runtimeInstance, 'mark pinned to this runtime instance');
  await sleep(1500);
  assert.equal(await claim('w2', '30 seconds', id), undefined);
  const st = await rowOf(id);
  assert.equal(st.status, 'UNKNOWN_OUTCOME');
  assert.equal(st.result.runtime_instance, runtimeInstance);
  return { id, epoch: m.lease_epoch, runtimeInstance, descPid, counter, go };
}

test('M-Z5-01 / E4-8: живой потомок; ограждение всей единицы; GO эффекта не даёт; эффект ровно один',
  { skip: unitSkip }, async () => {
    assert.ok(UNIT, 'CI must run the process-tree test: cgroup v2 or Job Object unit is required');
    const a = await pausedAttempt('tree');
    assert.equal(pidAlive(a.descPid), true, 'descendant with adapter access is alive');
    await assert.rejects(reconcile(a.id, 'CONFIRMED_NOT_SENT'), /RECONCILE_NOT_FENCED/);

    // Негативная проба: единица жива (родитель и потомок) — отказ, база не тронута.
    await assert.rejects(sup.fence(key(a.id, a.epoch, a.runtimeInstance), { terminate: false }), /FENCE_RUNTIME_ALIVE/);
    assert.deepEqual(await fenceRows(a.id), []);
    await assert.rejects(reconcile(a.id, 'CONFIRMED_NOT_SENT'), /RECONCILE_NOT_FENCED/);
    await assert.rejects(sup.fence(key(a.id, a.epoch, 'runtime:unknown')), /FENCE_RUNTIME_UNKNOWN/);

    // Настоящее ограждение: cgroup.kill, единица пуста, затем запись.
    const f = await sup.fence(key(a.id, a.epoch, a.runtimeInstance));
    assert.ok(f.evidenceId);
    assert.equal(f.evidence.unit_kind, UNIT.kind);
    assert.equal(f.evidence.unit_empty_observed, true);
    assert.equal(f.evidence.terminated_by, 'fencer');
    assert.ok(f.evidence.pids_before.includes(a.descPid), 'descendant was inside the unit');
    assert.equal(pidAlive(a.descPid), false, 'descendant is gone');
    assert.deepEqual(await fenceRows(a.id), [{ runtime_instance: a.runtimeInstance, method: UNIT.method }]);

    // Поздняя команда «продолжай» ни родителю, ни потомку эффекта не даёт: их нет.
    writeFileSync(a.go, 'GO\n');
    await sleep(600);
    assert.equal(effects(a.counter).length, 0, 'fenced unit never reached the adapter');

    assert.equal((await reconcile(a.id, 'CONFIRMED_NOT_SENT')).s, 'PENDING');
    const d = await kernel.dispatchOnce(async (row) => {
      if (row.outbox_id !== a.id) return { outcome: 'FAILED', detail: { released_by_test: 'fencer' } };
      writeFileSync(a.counter, 'retry\n', { flag: 'a' });
      return { outcome: 'SENT', detail: { stub: true } };
    }, { limit: 500, worker: 'w3' });
    assert.ok(d.results.some((x) => x.outbox_id === a.id && x.finished === true));
    assert.deepEqual(effects(a.counter), ['retry'], 'exactly one external effect');
    assert.equal((await rowOf(a.id)).status, 'SENT');
  });

test('M-Z5-01 мутация E4-8: «завершить только родителя» — отказ, потомок жив и даёт эффект',
  { skip: unitSkip }, async () => {
    assert.ok(UNIT, 'CI must run the parent-only mutation test');
    const a = await pausedAttempt('mut');
    await assert.rejects(sup.fence(key(a.id, a.epoch, a.runtimeInstance), { strategy: 'leader-only' }),
      /FENCE_RUNTIME_ALIVE/);
    const rec = sup.runtimes.get(a.runtimeInstance);
    assert.ok(rec.exit, 'leader process has exited');
    assert.equal(pidAlive(a.descPid), true, 'descendant survived the parent-only kill');
    assert.deepEqual(await fenceRows(a.id), []);
    await assert.rejects(reconcile(a.id, 'CONFIRMED_NOT_SENT'), /RECONCILE_NOT_FENCED/);
    // Опасность доказана: выживший потомок отправляет.
    writeFileSync(a.go, 'GO\n');
    for (let i = 0; i < 40 && effects(a.counter).length === 0; i += 1) await sleep(50);
    assert.deepEqual(effects(a.counter), [`descendant:${a.runtimeInstance}`]);
    // Уборка: единица гасится целиком; строка остаётся UNKNOWN_OUTCOME (эффект был).
    await rec.unit.kill(5000);
    assert.equal(rec.unit.populated(), false);
    assert.equal((await rowOf(a.id)).status, 'UNKNOWN_OUTCOME');
  });

test('FENCE_UNIT_UNSUPPORTED: без единицы исполнения попытка не запускается', () => {
  const s = new SendSupervisor({ connection: { ...CONN, user: op.role }, cgroupRoot: '', jobHost: '', containerImage: '' });
  assert.throws(() => s.spawnAttempt(CHILD, []), /FENCE_UNIT_UNSUPPORTED/);
  return s.close();
});

test('M-Z4-01 / M-Z5-01 / M-Z5-02 / E4-7: база принимает ограждение только от оператора, того же экземпляра, пустой единицы',
  async () => {
    const id = await outboxRow(`zavod.fencer.db.${ids.run}`);
    const rt = `runtime:${uuid()}`;
    const row = await claim('w1', '1 second', id);
    const epoch = row.lease_epoch;
    assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id, epoch, 'w1', rt])).ok, true);
    // В том же поколении другой экземпляр отметку не ставит; пустой экземпляр — отказ.
    assert.equal((await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok',
      [id, epoch, 'w1', 'runtime:other'])).ok, false);
    await assert.rejects(kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok',
      [id, epoch, 'w1', ' ']), /RUNTIME_INSTANCE_REQUIRED/);
    await sleep(1500);
    assert.equal(await claim('w2', '30 seconds', id), undefined);
    assert.equal((await rowOf(id)).status, 'UNKNOWN_OUTCOME');
    const good = { observer: 'fencer:test', exit_observed: true, exit_observed_at: new Date().toISOString(),
      runtime_instance: rt, unit_kind: 'CGROUP_V2', unit_id: '/sys/fs/cgroup/zavod/test', unit_empty_observed: true };
    await assert.rejects(dbFence(id, epoch, 'w1', 'runtime:other', { ...good, runtime_instance: 'runtime:other' }),
      /FENCE_RUNTIME_MISMATCH/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, exit_observed: false }), /FENCE_EVIDENCE_INCOMPLETE/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, exit_observed: 'true' }), /FENCE_EVIDENCE_INCOMPLETE/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, exit_observed_at: '' }), /FENCE_EVIDENCE_INCOMPLETE/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, runtime_instance: 'runtime:other' }),
      /FENCE_EVIDENCE_INCOMPLETE/);
    // M-Z5-01: единица не пуста, не та или не указана — отказ; способ «один процесс» запрещён схемой.
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, unit_empty_observed: false }), /FENCE_UNIT_NOT_EMPTY/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, unit_empty_observed: 'true' }), /FENCE_UNIT_NOT_EMPTY/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, unit_id: ' ' }), /FENCE_UNIT_NOT_EMPTY/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, unit_kind: 'PROCESS' }), /FENCE_UNIT_NOT_EMPTY/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, good, 'CONTAINER_TERMINATED'), /FENCE_UNIT_NOT_EMPTY/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, good, 'PROCESS_TERMINATED'), /FENCE_METHOD_FORBIDDEN/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, observer: 'w1' }), /FENCE_SELF_REPORT/);
    await assert.rejects(dbFence(id, epoch, 'w1', rt, { ...good, observer: rt }), /FENCE_SELF_REPORT/);
    // E4-7 / M-Z5-02: Kernel (через него — любой рабочий) записать ограждение не может вовсе.
    await assert.rejects(kq('SELECT bem_control.record_outbox_fence($1, $2, $3, $4, $5, $6, $7)',
      [ids.tenantA, id, epoch, 'w1', rt, 'CGROUP_KILLED', good]), (e) => e.code === '42501');
    // M-E35-02: член bem_governance без полномочия OPERATOR — отказ; вход первой установки тоже не оператор.
    await assert.rejects(dbFence(id, epoch, 'w1', rt, good, 'CGROUP_KILLED', opNo.role), /AUTHORITY_REQUIRED/);
    assert.deepEqual(await fenceRows(id), []);
    // Точный список вызывающих: владелец функции и bem_governance (канон §16 «Оператор»).
    const acl = await withRole('postgres', async (c) => (await c.query(
      `SELECT array_agg(a.grantee::regrole::text ORDER BY a.grantee::regrole::text) AS g
         FROM pg_proc p, aclexplode(p.proacl) a
        WHERE p.oid = 'bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)'::regprocedure
          AND a.privilege_type = 'EXECUTE'`)).rows[0].g);
    assert.deepEqual(acl, ['bem_control_owner', 'bem_governance']);
    const src = await withRole('postgres', async (c) => (await c.query(
      "SELECT prosrc FROM pg_proc WHERE oid = 'bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)'::regprocedure"))
      .rows[0].prosrc);
    assert.match(src, /assert_authority\('OPERATOR', p_tenant_id\)/);
    assert.deepEqual(await fenceRows(id), []);
    // Оператор с полным доказательством пустой единицы — принято.
    assert.ok((await dbFence(id, epoch, 'w1', rt, good)).e);
    assert.deepEqual(await fenceRows(id), [{ runtime_instance: rt, method: 'CGROUP_KILLED' }]);
    assert.equal((await reconcile(id, 'CONFIRMED_NOT_SENT')).s, 'PENDING');
  });

test('M-E35-02 надзиратель принимает только вход оператора из bem_governance', async () => {
  for (const user of ['bem_bootstrap_admin', 'bem_kernel_rw', 'bem_engine_rw', 'postgres']) {
    assert.throws(() => new SendSupervisor({ connection: { ...CONN, user } }), /FENCER_WRONG_ROLE/, user);
  }
  assert.throws(() => new SendSupervisor({ connection: { ...CONN } }), /FENCER_CONNECTION_REQUIRED/);
  // Вход вне bem_governance — отказ до гашения единицы.
  const plain = `zavod_plain_${uuid().slice(0, 8)}`;
  await withRole('postgres', async (c) => {
    await c.query(`CREATE ROLE ${plain} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS`);
    await c.query(`GRANT CONNECT ON DATABASE ${CONN.database} TO ${plain}`);
  });
  const s = new SendSupervisor({ connection: { ...CONN, user: plain }, cgroupRoot: '' });
  await assert.rejects(s.assertOperatorIdentity(), /FENCER_WRONG_ROLE/);
  await s.close();
  // Штатный вход оператора проходит; полномочие OPERATOR сверяет сама база (см. тест E4-7).
  assert.equal(await sup.assertOperatorIdentity(), op.role);
});
