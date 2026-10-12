// ДОКУМЕНТ: zavod/engine/ci/e5_tenant_isolation.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 06:49 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: проверка оркестратора v0.8 — аудит ChatGPT v0.7, MAJOR: захват задания движка не знает заказчика.
//   Заказчик B: 12 работ стоят на подзадаче s2 (больше пачки захвата 10) и одна — на узле 2; его оркестратор
//   подзадачи не берёт. Заказчик A: одна работа. Оркестратор A обязан довести свою работу до узла 15 сквозь чужие
//   задания, ни одно чужое не продвинуть, не оставить захваченным и не оборвать проход. Затем обычный оркестратор B
//   доводит свои работы дальше: отпущенные задания пригодны.
// ВЫЗОВ и СРЕДА: как ci/e5_system_check_gate.mjs.
// ОГРАНИЧЕНИЯ: рабочий — заглушка без моделей и сети; секретов в выводе нет.

import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { Kernel } from '../../kernel/src/kernel.mjs';
import { CONN, bootFixture, assignAuditor, runStopFile } from '../../kernel/tests/helpers.mjs';
import { EngineClient } from '../src/engine_client.mjs';
import { Orchestrator, ORCH_VERSION, EXEC_TOPICS } from '../src/orchestrator.mjs';

const pg = createRequire(new URL('../../kernel/package.json', import.meta.url))('pg');
const OUT = process.env.E43_OUT || join(process.cwd(), 'e43_out');
mkdirSync(OUT, { recursive: true });
const LOG = join(OUT, 'e5_tenant_isolation.log');
const log = (...a) => { const s = a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '); console.log(s); appendFileSync(LOG, s + '\n'); };
let FAIL = 0;
const checks = [];
function check(id, ok, detail) { checks.push({ id, ok: !!ok, detail }); log(`${ok ? 'CHECK_PASS' : 'CHECK_FAIL'} ${id}:`, detail); if (!ok) FAIL = 1; }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

log(`=== E5 tenant isolation (orch ${ORCH_VERSION})`, new Date().toISOString());
const engine = new EngineClient({ base: process.env.ZAVOD_ENGINE_BASE || 'http://127.0.0.1:8091/flowable-rest',
  user: process.env.ZAVOD_ENGINE_USER, pass: process.env.ZAVOD_ENGINE_PASS });
const ids = await bootFixture();
const kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-e5iso-stop-') });
await kernel.assertIdentity();
const defs = await engine.api('GET', '/service/repository/process-definitions?key=bem_work');
if (!(defs.json?.data?.length > 0)) await engine.deployChecked('zavod_bem_work.bpmn20.xml',
  readFileSync(new URL('../bpmn/bem_work.bpmn20.xml', import.meta.url), 'utf8'));

const usage = { input_tokens: 1000, output_tokens: 200, measured_by: 'LOCAL_ESTIMATE' };
const mk = (tenantId, actor) => new Orchestrator({
  kernel, engine, actor, tenantId, providers: ['anthropic'], log: () => {},
  governance: { assignAuditors: async (t, s) => { for (const a of [ids.audOpenai, ids.audAnthropic]) await assignAuditor(t, s, a); } },
  egress: async () => ({ outcome: 'SENT', detail: {} }),
  runWorker: async () => ({ outcome: 'OK', usage }),
});
const orchA = mk(ids.tenantA, ids.author);
// Заказчик B «застрял»: его оркестратор подзадачи не берёт, они ждут в очереди движка.
const orchBstalled = mk(ids.tenantB, ids.author2);
const ownAcquire = orchBstalled.acquireOwn.bind(orchBstalled);
orchBstalled.acquireOwn = async (topic) => (EXEC_TOPICS.includes(topic) ? [] : ownAcquire(topic));

const sa = new pg.Client({ ...CONN, user: process.env.E43_EXPORT_USER || 'postgres' });
await sa.connect();
const statusOf = async (wi) => (await sa.query('SELECT status FROM bem_core.work_item WHERE id = $1', [wi])).rows[0]?.status;
async function pumpUntil(orch, what, pred, ms = 240000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { await orch.pump(); if (await pred()) return true; await sleep(300); }
  log(`  !! не дождались: ${what}`); return false;
}
const at = (pid, act) => async () => (await engine.executions({ processInstanceId: pid, activityId: act })).length > 0;
// Подпроцессы bem_subtask заказчика B и их задания движка (с данными о захвате).
async function subOf(pid) { return engine.processInstances({ superProcessInstanceId: pid }); }
async function jobsOf(pids) {
  const out = [];
  for (const pid of pids) {
    const r = await engine.api('GET', `/external-job-api/jobs?processInstanceId=${pid}`);
    out.push(...(r.json?.data ?? []));
  }
  return out;
}

const NB = 12;
const bOrders = [];
for (let i = 0; i < NB; i += 1) bOrders.push(await orchBstalled.startWork({ criticality: 'NORMAL', note: `E5 iso B${i}` }));
const bAtS2 = async () => { for (const o of bOrders) if ((await subOf(o.pid)).length === 0) return false; return true; };
check('iso_b_waiting_at_s2', await pumpUntil(orchBstalled, 'B на s2', bAtS2), `работ B на подзадаче: ${NB}`);
const bLate = await orchBstalled.startWork({ criticality: 'NORMAL', note: 'E5 iso B late' });   // стоит на узле 2
const bSubs = [];
for (const o of bOrders) bSubs.push(...(await subOf(o.pid)).map((p) => p.id));
const bStatus0 = [];
for (const o of [...bOrders, bLate]) bStatus0.push(await statusOf(o.work_item_id));
const bJobs0 = await jobsOf([...bSubs, bLate.pid]);
log('B: подпроцессов', bSubs.length, 'заданий', bJobs0.length, 'статусы', [...new Set(bStatus0)].join(','));

const a = await orchA.startWork({ criticality: 'NORMAL', note: 'E5 iso A' });
let crashed = null;
let reached = false;
try { reached = await pumpUntil(orchA, 'A на n15', at(a.pid, 'n15')); } catch (e) { crashed = `${e?.code || ''} ${String(e?.message || e).slice(0, 160)}`; }
check('iso_a_pump_not_aborted', crashed === null, crashed ?? 'проход оркестратора A не оборвался');
check('iso_a_reaches_n15', reached, `своя работа A дошла до узла 15 сквозь ${bJobs0.length} чужих заданий`);
check('iso_a_no_refusals', orchA.refused.length === 0, `отказы A: ${orchA.refused.length}`);
check('iso_a_released_foreign', orchA.released >= bJobs0.length, `A отпустил чужих: ${orchA.released} (чужих в очереди ${bJobs0.length})`);
const touchedB = orchA.handled.filter((h) => h.pid === bLate.pid || bSubs.includes(h.pid) || bOrders.some((o) => o.pid === h.pid));
check('iso_a_handled_only_own', touchedB.length === 0, `обработано A чужих: ${touchedB.length}`);
const bJobs1 = await jobsOf([...bSubs, bLate.pid]);
const locked = bJobs1.filter((j) => j.lockOwner);
check('iso_foreign_not_locked', bJobs1.length === bJobs0.length && bJobs1.every((j) => 'lockOwner' in j) && locked.length === 0,
  `заданий B: было ${bJobs0.length}, стало ${bJobs1.length}; захвачены: ${locked.length}`);
const bStatus1 = [];
for (const o of [...bOrders, bLate]) bStatus1.push(await statusOf(o.work_item_id));
check('iso_foreign_status_unchanged', JSON.stringify(bStatus1) === JSON.stringify(bStatus0), `статусы B: ${[...new Set(bStatus1)].join(',')}`);
check('iso_foreign_late_still_n2', await at(bLate.pid, 'n2')(), 'поздняя работа B стоит на узле 2');

// Обычный оркестратор B: отпущенные задания пригодны, работы B идут дальше.
const orchB = mk(ids.tenantB, ids.author2);
const bDone = async () => {
  for (const o of bOrders) if ((await subOf(o.pid)).length > 0) return false;
  return !(await at(bLate.pid, 'n2')());
};
check('iso_b_continues', await pumpUntil(orchB, 'B дальше', bDone), 'подзадачи B выполнены, поздняя работа B ушла с узла 2');
check('iso_b_untouched_a', orchB.handled.every((h) => h.pid !== a.pid), 'B не трогал работу A');
await sa.end();

writeFileSync(join(OUT, 'e5_tenant_isolation_result.json'), JSON.stringify({ result: FAIL ? 'FAIL' : 'PASS', orch: ORCH_VERSION, checks }, null, 1));
await kernel.close();
log(`=== E5_TENANT_ISOLATION_RESULT=${FAIL ? 'FAIL' : 'PASS'} (${checks.filter((c) => c.ok).length}/${checks.length})`);
process.exit(FAIL);
