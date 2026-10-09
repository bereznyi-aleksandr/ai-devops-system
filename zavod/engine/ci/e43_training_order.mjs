// ДОКУМЕНТ: zavod/engine/ci/e43_training_order.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 06:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 06:40 +03:00 (v0.2: проверка журнала расхода SR-07; v0.1: E4-3)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: критерий E4-3 протокола Z1 v1.9 — учебный заказ на заглушке продукта проходит узлы 1–20
//   графа H1.31 §12; все переходы — через Kernel. Два заказа:
//     A (NORMAL): вердикт REVISE → возврат к 6; BLOCKED → решение оператора CONTINUE → 6; ACCEPT → 17 → 18 → 20.
//     B (CRITICAL): вердикт BLOCKED → решение оператора CANCEL → 20.
//   Вместе A и B проходят все 20 узлов и все 24 потока. Доказательство — выгрузка command_log и история
//   движка (файлы в папке E43_OUT), плюс проверки с ожидаемым итогом.
// ВЫЗОВ: node ci/e43_training_order.mjs  (из zavod/engine)
// СРЕДА: ZAVOD_ENGINE_BASE, ZAVOD_ENGINE_USER, ZAVOD_ENGINE_PASS (одноразовая учётка, не выводится);
//   PGHOST/PGPORT/PGDATABASE — стенд H1.31 + Z-EXT-01; E43_OUT — папка доказательств.
// ОГРАНИЧЕНИЯ: заглушка продукта — без моделей и платных маршрутов; секретов в выводе нет.

import { readFileSync, writeFileSync, appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { Kernel } from '../../kernel/src/kernel.mjs';
import { CONN, bootFixture, assignAuditor, runStopFile, uuid } from '../../kernel/tests/helpers.mjs';
import { EngineClient } from '../src/engine_client.mjs';
import { Orchestrator } from '../src/orchestrator.mjs';
import { NODES, FLOWS } from '../src/graph_check.mjs';

// pg — из зависимостей Kernel (zavod/kernel/package-lock.json), своей блокировки у engine нет.
const pg = createRequire(new URL('../../kernel/package.json', import.meta.url))('pg');
const OUT = process.env.E43_OUT || join(process.cwd(), 'e43_out');
mkdirSync(OUT, { recursive: true });
const LOG = join(OUT, 'e43_training_order.log');
const log = (...a) => { const s = a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '); console.log(s); appendFileSync(LOG, s + '\n'); };
let FAIL = 0;
const checks = [];
function check(id, ok, detail) {
  checks.push({ id, ok: !!ok, detail });
  log(`${ok ? 'CHECK_PASS' : 'CHECK_FAIL'} ${id}:`, detail);
  if (!ok) FAIL = 1;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

log('=== E4-3 training order', new Date().toISOString());
const engine = new EngineClient({ base: process.env.ZAVOD_ENGINE_BASE || 'http://127.0.0.1:8091/flowable-rest',
  user: process.env.ZAVOD_ENGINE_USER, pass: process.env.ZAVOD_ENGINE_PASS });
const ids = await bootFixture();
const kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-e43-stop-'), requireRole: true });
await kernel.assertIdentity();
const egressCalls = [];
const orch = new Orchestrator({
  kernel, engine, actor: ids.author, tenantId: ids.tenantA,
  governance: { assignAuditors: async (t, s) => { for (const a of [ids.audOpenai, ids.audAnthropic]) await assignAuditor(t, s, a); } },
  egress: async (row) => { egressCalls.push({ outbox_id: row.outbox_id, work_item_id: row.work_item_id }); return { outcome: 'SENT', detail: { stub: 'zavod-e43-product-stub' } }; },
  log,
});

// 1. Развёртывание: испорченная копия не доходит до движка; эталон — после PASS проверщика.
const XML = readFileSync(new URL('../bpmn/bem_work.bpmn20.xml', import.meta.url), 'utf8');
const before = (await engine.deployments()).length;
let refused = null;
try { await engine.deployChecked('bad.bpmn20.xml', XML.replace('targetRef="n8"/>', 'targetRef="n9"/>')); } catch (e) { refused = e.code; }
check('e43_bad_graph_not_deployed', refused === 'GRAPH_CHECK_FAILED' && (await engine.deployments()).length === before,
  `refused=${refused}, deployments ${before} -> ${(await engine.deployments()).length}`);
const dep = await engine.deployChecked('zavod_bem_work.bpmn20.xml', XML);
check('e43_graph_deployed_after_check', !!dep?.id, `deployment ${dep?.id}`);

async function pumpUntil(what, pred, ms = 60000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    await orch.pump();
    if (await pred()) return true;
    await sleep(300);
  }
  log(`  !! не дождались: ${what}`);
  return false;
}
const atN15 = (pid) => async () => (await engine.executions({ processInstanceId: pid, activityId: 'n15' })).length > 0;
const atN19 = (pid) => async () => (await engine.tasks({ processInstanceId: pid, taskDefinitionKey: 'n19' })).length > 0;
const ended = (pid) => async () => (await engine.processInstances({ id: pid })).length === 0;
const auditors = [ids.audOpenai, ids.audAnthropic];

// 2. Заказ A.
const A = await orch.startWork({ criticality: 'NORMAL', note: 'E4-3 order A' });
log('order A', A);
check('e43_A_reach_n15_pass1', await pumpUntil('A n15 #1', atN15(A.pid)), 'A дошёл до ожидания аудита (проход 1)');
await orch.deliverVerdict(A.pid, auditors, 'REVISE');
check('e43_A_reach_n15_pass2', await pumpUntil('A n15 #2', atN15(A.pid)), 'после REVISE — снова 6…15 (проход 2)');
await orch.deliverVerdict(A.pid, auditors, 'BLOCKED');
check('e43_A_reach_n19', await pumpUntil('A n19', atN19(A.pid)), 'после BLOCKED — задача оператора 19');
await orch.operatorDecision(A.pid, ids.humanA, 'CONTINUE');
check('e43_A_reach_n15_pass3', await pumpUntil('A n15 #3', atN15(A.pid)), 'после CONTINUE — снова 6…15 (проход 3)');
await orch.deliverVerdict(A.pid, auditors, 'ACCEPT');
check('e43_A_ended', await pumpUntil('A end', ended(A.pid)), 'после ACCEPT — 17 → 18 → 20, экземпляр завершён');

// 3. Заказ B.
const B = await orch.startWork({ criticality: 'CRITICAL', note: 'E4-3 order B' });
log('order B', B);
check('e43_B_reach_n15', await pumpUntil('B n15', atN15(B.pid)), 'B дошёл до ожидания аудита');
await orch.deliverVerdict(B.pid, auditors, 'BLOCKED');
check('e43_B_reach_n19', await pumpUntil('B n19', atN19(B.pid)), 'B: задача оператора 19');
await orch.operatorDecision(B.pid, ids.humanA, 'CANCEL');
check('e43_B_ended', await pumpUntil('B end', ended(B.pid)), 'B: отмена → 20, экземпляр завершён');

// 4. История движка: узлы и потоки.
const hist = {};
for (const [k, o] of Object.entries({ A, B })) {
  const main = await engine.history(o.pid);
  const subs = await engine.historicProcess({ superProcessInstanceId: o.pid });
  hist[k] = { pid: o.pid, work_item_id: o.work_item_id, main, subs: {} };
  for (const s of subs) hist[k].subs[s.id] = await engine.history(s.id);
}
writeFileSync(join(OUT, 'e43_engine_history.json'), JSON.stringify(hist, null, 1));
const nodesOf = (h) => new Set(h.main.filter((x) => x.activityType !== 'sequenceFlow').map((x) => x.activityId));
const flowsOf = (h) => new Set(h.main.filter((x) => x.activityType === 'sequenceFlow').map((x) => x.activityId));
const allNodes = new Set([...nodesOf(hist.A), ...nodesOf(hist.B)]);
const allFlows = new Set([...flowsOf(hist.A), ...flowsOf(hist.B)]);
const wantNodes = Object.keys(NODES);
const wantFlows = Object.keys(FLOWS);
check('e43_A_nodes_1_20', wantNodes.every((n) => nodesOf(hist.A).has(n)), `A: ${[...nodesOf(hist.A)].sort().join(',')}`);
check('e43_all_nodes_covered', wantNodes.every((n) => allNodes.has(n)) && [...allNodes].every((n) => wantNodes.includes(n)),
  `узлы ${allNodes.size} из ${wantNodes.length}`);
check('e43_all_flows_covered', wantFlows.every((f) => allFlows.has(f)) && [...allFlows].every((f) => wantFlows.includes(f)),
  `потоки ${[...allFlows].filter((f) => wantFlows.includes(f)).length} из ${wantFlows.length}; лишние: ${[...allFlows].filter((f) => !wantFlows.includes(f)).join(',') || '—'}`);
const n7A = hist.A.main.filter((x) => x.activityId === 'n7').length;
const subsA = Object.keys(hist.A.subs).length;
check('e43_A_subtasks_per_pass', subsA === 3 * 2, `подпроцессов у A: ${subsA} (3 прохода × 2 поставщика); записей n7: ${n7A}`);

// 5. Kernel: статусы, command_log, outbox — выгрузка ролью postgres (только чтение для доказательства).
const sa = new pg.Client({ ...CONN, user: process.env.E43_EXPORT_USER || 'postgres' });
await sa.connect();
const wis = [A.work_item_id, B.work_item_id];
const st = (await sa.query('SELECT id, status, revision, criticality FROM bem_core.work_item WHERE id = ANY($1)', [wis])).rows;
const cl = (await sa.query('SELECT * FROM bem_core.command_log WHERE work_item_id = ANY($1) ORDER BY created_at, command_id', [wis])).rows;
const ob = (await sa.query('SELECT * FROM bem_core.outbox WHERE work_item_id = ANY($1)', [wis])).rows;
const usage = (await sa.query('SELECT work_item_id, attempt_no, provider, outcome FROM bem_core.usage_record WHERE work_item_id = ANY($1)', [wis])).rows;
await sa.end();
const uA = usage.filter((r) => r.work_item_id === A.work_item_id && r.outcome === 'OK').length;
const uB = usage.filter((r) => r.work_item_id === B.work_item_id && r.outcome === 'OK').length;
check('e43_usage_recorded', uA === 6 && uB === 2 && usage.length === 8, `расход: A ${uA} попыток OK (3 прохода × 2), B ${uB}; всего строк ${usage.length}`);
writeFileSync(join(OUT, 'e43_command_log.json'), JSON.stringify({ work_items: st, command_log: cl, outbox: ob, kernel_transitions: orch.transitions }, null, 1));
const stOf = (id) => st.find((r) => r.id === id)?.status;
check('e43_A_released', stOf(A.work_item_id) === 'RELEASED', `A status ${stOf(A.work_item_id)}`);
check('e43_B_cancelled', stOf(B.work_item_id) === 'CANCELLED', `B status ${stOf(B.work_item_id)}`);
const clIds = new Set(cl.map((r) => r.command_id));
check('e43_every_transition_in_command_log', orch.transitions.length > 0 && orch.transitions.every((t) => clIds.has(t.command_id)) && cl.length === orch.transitions.length,
  `переходов Kernel ${orch.transitions.length}, строк command_log ${cl.length}`);
const pathA = orch.transitions.filter((t) => t.work_item_id === A.work_item_id).map((t) => t.to).join('>');
check('e43_A_status_path', pathA === 'PLANNED>IN_PROGRESS>IN_REVIEW>IN_PROGRESS>IN_REVIEW>BLOCKED>PLANNED>IN_PROGRESS>IN_REVIEW>ACCEPTED>RELEASED', pathA);
const pathB = orch.transitions.filter((t) => t.work_item_id === B.work_item_id).map((t) => t.to).join('>');
check('e43_B_status_path', pathB === 'PLANNED>IN_PROGRESS>IN_REVIEW>BLOCKED>CANCELLED', pathB);
// Доставщик Kernel общий: на долгоживущем стенде он забирает и чужие давние строки outbox (на чистой базе CI их нет).
const own = egressCalls.filter((c) => wis.includes(c.work_item_id));
check('e43_egress_once', own.length === 1 && own[0].work_item_id === A.work_item_id && ob.length === 1 && ob[0].status === 'SENT',
  `внешних действий по заказам: ${own.length} (чужих строк стенда: ${egressCalls.length - own.length}); outbox: ${ob.map((r) => `${r.work_item_id === A.work_item_id ? 'A' : 'B'}:${r.kind}:${r.status}`).join(',')}`);

writeFileSync(join(OUT, 'e43_result.json'), JSON.stringify({ result: FAIL ? 'FAIL' : 'PASS', checks, orders: { A, B } }, null, 1));
await kernel.close();
log(`=== E43_RESULT=${FAIL ? 'FAIL' : 'PASS'} (${checks.filter((c) => c.ok).length}/${checks.length})`);
process.exit(FAIL);
