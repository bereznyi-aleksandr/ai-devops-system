// ДОКУМЕНТ: zavod/engine/ci/e5_rollout_gate.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 07:22 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: проверка оркестратора v0.10 — аудит ChatGPT v0.9, MAJOR: переход со старой модели (темы без заказчика)
//   не имел доказанного безопасного пути: задания старых экземпляров невидимы v0.9+ и зависли бы. Доказывается:
//   1) на движке только с новой моделью оркестратор работает; 2) старую модель deployChecked не разворачивает;
//   3) пока последняя версия bem_work — старая, startWork отказывает до записи работы в Kernel; 4) пока жив хоть один
//   экземпляр старой модели, pump и startWork отказывают ROLLOUT_BLOCKED_LEGACY, старый экземпляр не тронут.
// ВЫЗОВ и СРЕДА: как ci/e5_tenant_isolation.mjs. ПОСЛЕДНИЙ шаг engine_ci.sh: оставляет в одноразовом движке CI
//   экземпляр старой модели (поэтому после него другие проверки на этом движке не запускаются).
// ОГРАНИЧЕНИЯ: старая модель разворачивается в обход deployChecked только здесь, в одноразовый движок CI, —
//   так её развернул бы движок до v0.9; секретов в выводе нет.

import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
import { Kernel } from '../../kernel/src/kernel.mjs';
import { CONN, bootFixture, runStopFile } from '../../kernel/tests/helpers.mjs';
import { EngineClient } from '../src/engine_client.mjs';
import { Orchestrator, ORCH_VERSION } from '../src/orchestrator.mjs';

const pg = createRequire(new URL('../../kernel/package.json', import.meta.url))('pg');
const OUT = process.env.E43_OUT || join(process.cwd(), 'e43_out');
mkdirSync(OUT, { recursive: true });
const LOG = join(OUT, 'e5_rollout_gate.log');
const log = (...a) => { const s = a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '); console.log(s); appendFileSync(LOG, s + '\n'); };
let FAIL = 0;
const checks = [];
function check(id, ok, detail) { checks.push({ id, ok: !!ok, detail }); log(`${ok ? 'CHECK_PASS' : 'CHECK_FAIL'} ${id}:`, detail); if (!ok) FAIL = 1; }
const codeOf = async (fn) => { try { await fn(); return 'OK'; } catch (e) { return e?.code || String(e?.message || e).slice(0, 80); } };

log(`=== E5 rollout gate (orch ${ORCH_VERSION})`, new Date().toISOString());
const engine = new EngineClient({ base: process.env.ZAVOD_ENGINE_BASE || 'http://127.0.0.1:8091/flowable-rest',
  user: process.env.ZAVOD_ENGINE_USER, pass: process.env.ZAVOD_ENGINE_PASS });
const ids = await bootFixture();
const kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-e5roll-stop-') });
await kernel.assertIdentity();
const XML = readFileSync(new URL('../bpmn/bem_work.bpmn20.xml', import.meta.url), 'utf8');
const LEGACY = readFileSync(new URL('./fixtures/bem_work_v1_1_legacy.bpmn20.xml', import.meta.url), 'utf8');
const defs = await engine.api('GET', '/service/repository/process-definitions?key=bem_work');
if (!(defs.json?.data?.length > 0)) await engine.deployChecked('zavod_bem_work.bpmn20.xml', XML);

const mk = (tenantId) => new Orchestrator({
  kernel, engine, actor: ids.author, tenantId, providers: ['anthropic'], log: () => {},
  governance: { assignAuditors: async () => {} }, egress: async () => ({ outcome: 'SENT', detail: {} }),
});
const sa = new pg.Client({ ...CONN, user: process.env.E43_EXPORT_USER || 'postgres' });
await sa.connect();
const wiCount = async () => Number((await sa.query('SELECT count(*) AS n FROM bem_core.work_item')).rows[0].n);

// 1. Движок только с новой моделью (после всех прежних проверок CI): оркестратор работает.
const clean = mk(ids.tenantA);
check('rg_clean_engine_passes', (await codeOf(() => clean.pump())) === 'OK' && clean.rolloutChecked === true,
  `экземпляров bem_work: ${(await engine.allProcessInstances('bem_work')).length}, проверка перехода пройдена`);

// 2. Старая модель не проходит штатное развёртывание.
const before = (await engine.deployments()).length;
const refused = await codeOf(() => engine.deployChecked('legacy.bpmn20.xml', LEGACY));
check('rg_legacy_not_deployable', refused === 'GRAPH_CHECK_FAILED' && (await engine.deployments()).length === before,
  `deployChecked: ${refused}`);

// 3. Движок до v0.9: старая модель развёрнута последней (в обход проверщика — только в этом тесте).
const fd = new FormData();
fd.append('file', new Blob([LEGACY], { type: 'text/xml' }), 'zavod_bem_work_legacy.bpmn20.xml');
const legacyDep = await engine.api('POST', '/service/repository/deployments', fd);
check('rg_legacy_deployed_raw', legacyDep.status === 201, `развёртывание старой модели: ${legacyDep.status}`);
const wi0 = await wiCount();
const lateStart = mk(ids.tenantB);
const latestCode = await codeOf(() => lateStart.startWork({ note: 'E5 rollout: старая модель последняя' }));
check('rg_start_blocked_latest_legacy', latestCode === 'ROLLOUT_BLOCKED_LEGACY' && (await wiCount()) === wi0,
  `startWork: ${latestCode}; работ в Kernel было ${wi0}, стало ${await wiCount()}`);

// Экземпляр старой модели — так его создал бы оркестратор до v0.9 (общая тема kernel).
const legacyKey = randomUUID();
const legacyPi = await engine.startByMessage('bemIntake', { workKey: legacyKey, tenantId: ids.tenantB, pass: 0 }, legacyKey);
// Новая модель снова последняя — как после развёртывания v1.2 на движке со старыми экземплярами.
await engine.deployChecked('zavod_bem_work.bpmn20.xml', XML);
const legacyAtN2 = async () => (await engine.executions({ processInstanceId: legacyPi.id, activityId: 'n2' })).length > 0;
check('rg_legacy_instance_waiting', await legacyAtN2(), `экземпляр старой модели ${legacyPi.id} на узле 2`);

// 4. Пока жив экземпляр старой модели — отказ до любой работы.
const wi1 = await wiCount();
const blocked = mk(ids.tenantB);
const pumpCode = await codeOf(() => blocked.pump());
check('rg_pump_blocked_legacy_instance', pumpCode === 'ROLLOUT_BLOCKED_LEGACY' && blocked.handled.length === 0
  && blocked.released === 0, `pump: ${pumpCode}; обработано ${blocked.handled.length}, отпущено ${blocked.released}`);
const startCode = await codeOf(() => blocked.startWork({ note: 'E5 rollout: старый экземпляр жив' }));
check('rg_start_blocked_legacy_instance', startCode === 'ROLLOUT_BLOCKED_LEGACY' && (await wiCount()) === wi1,
  `startWork: ${startCode}; работ в Kernel было ${wi1}, стало ${await wiCount()}`);
const other = mk(ids.tenantA);
check('rg_any_tenant_blocked', (await codeOf(() => other.pump())) === 'ROLLOUT_BLOCKED_LEGACY',
  'оркестратор любого заказчика не работает рядом со старым экземпляром');
const lj = (await engine.api('GET', `/external-job-api/jobs?processInstanceId=${legacyPi.id}`)).json?.data ?? [];
check('rg_legacy_untouched', (await legacyAtN2()) && lj.length === 1 && 'lockOwner' in lj[0] && !lj[0].lockOwner,
  `старый экземпляр на узле 2, заданий ${lj.length}, захвачено: ${lj.filter((j) => j.lockOwner).length}`);
await sa.end();

writeFileSync(join(OUT, 'e5_rollout_gate_result.json'), JSON.stringify({ result: FAIL ? 'FAIL' : 'PASS', orch: ORCH_VERSION, checks }, null, 1));
await kernel.close();
log(`=== E5_ROLLOUT_GATE_RESULT=${FAIL ? 'FAIL' : 'PASS'} (${checks.filter((c) => c.ok).length}/${checks.length})`);
process.exit(FAIL);
