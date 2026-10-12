// ДОКУМЕНТ: zavod/engine/ci/e5_system_check_gate.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 06:33 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: проверка оркестратора v0.7 — условие выхода узла 11 (H1.31 §12.2 «тесты пройдены»). Пилот
//   p1_20261011_real: два ACCEPT при системной проверке FAIL довели работу до узла 17; выпуск отклонила только
//   защита prepareRelease, прогон закончился FAIL. Здесь: попытка 1 — проверка FAIL, оба проверяющих ACCEPT →
//   итог REVISE, возврат к 6, prepareRelease не вызван, работа не ACCEPTED, доказательство ZAVOD_P1_SYSTEM_CHECK_GATE;
//   попытка 2 — проверка PASS, оба ACCEPT → узел 17 ровно один раз для второго head, выпуск, одно внешнее действие.
// ВЫЗОВ и СРЕДА: как ci/e45_limits.mjs (тот же движок; граф разворачивается, если ещё нет).
// ОГРАНИЧЕНИЯ: рабочий, системная проверка и внешнее действие — заглушки без моделей и сети; секретов в выводе нет.

import { readFileSync, writeFileSync, appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { Kernel } from '../../kernel/src/kernel.mjs';
import { CONN, bootFixture, assignAuditor, runStopFile } from '../../kernel/tests/helpers.mjs';
import { EngineClient } from '../src/engine_client.mjs';
import { Orchestrator, ORCH_VERSION } from '../src/orchestrator.mjs';

const pg = createRequire(new URL('../../kernel/package.json', import.meta.url))('pg');
const OUT = process.env.E43_OUT || join(process.cwd(), 'e43_out');
mkdirSync(OUT, { recursive: true });
const LOG = join(OUT, 'e5_system_check_gate.log');
const log = (...a) => { const s = a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '); console.log(s); appendFileSync(LOG, s + '\n'); };
let FAIL = 0;
const checks = [];
function check(id, ok, detail) { checks.push({ id, ok: !!ok, detail }); log(`${ok ? 'CHECK_PASS' : 'CHECK_FAIL'} ${id}:`, detail); if (!ok) FAIL = 1; }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

log(`=== E5 system check gate (orch ${ORCH_VERSION})`, new Date().toISOString());
const engine = new EngineClient({ base: process.env.ZAVOD_ENGINE_BASE || 'http://127.0.0.1:8091/flowable-rest',
  user: process.env.ZAVOD_ENGINE_USER, pass: process.env.ZAVOD_ENGINE_PASS });
const ids = await bootFixture();
const kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-e5gate-stop-') });
await kernel.assertIdentity();
const defs = await engine.api('GET', '/service/repository/process-definitions?key=bem_work');
if (!(defs.json?.data?.length > 0)) await engine.deployChecked('zavod_bem_work.bpmn20.xml',
  readFileSync(new URL('../bpmn/bem_work.bpmn20.xml', import.meta.url), 'utf8'));

const H1 = '1'.repeat(40);
const H2 = '2'.repeat(40);
const heads = [H1, H2];
const sysCalls = [];
const relCalls = [];
let egressCalls = 0;
const orch = new Orchestrator({
  kernel, engine, actor: ids.author, tenantId: ids.tenantA, providers: ['anthropic'], log,
  governance: { assignAuditors: async (t, s) => { for (const a of [ids.audOpenai, ids.audAnthropic]) await assignAuditor(t, s, a); } },
  egress: async () => { egressCalls += 1; return { outcome: 'SENT', detail: {} }; },
  runWorker: async ({ attempt_no }) => ({ outcome: 'OK', head_sha: heads[attempt_no - 1] ?? null,
    usage: { input_tokens: 1000, output_tokens: 200, measured_by: 'LOCAL_ESTIMATE' } }),
  pilot: {
    systemCheck: async ({ head_sha }) => { sysCalls.push(head_sha); return { result: head_sha === H2 ? 'PASS' : 'FAIL' }; },
    prepareRelease: async ({ head_sha }) => {
      relCalls.push(head_sha);
      return { outbox_kind: 'zavod.e5.gate', outbox_payload: { head_sha } };
    },
  },
});
const sa = new pg.Client({ ...CONN, user: process.env.E43_EXPORT_USER || 'postgres' });
await sa.connect();
const statusOf = async (wi) => (await sa.query('SELECT status FROM bem_core.work_item WHERE id = $1', [wi])).rows[0]?.status;
const gateEv = async (t) => (await sa.query("SELECT payload FROM bem_core.evidence WHERE tenant_id = $1 AND kind = 'ZAVOD_P1_SYSTEM_CHECK_GATE'", [t])).rows;

async function pumpUntil(what, pred, ms = 90000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { await orch.pump(); if (await pred()) return true; await sleep(300); }
  log(`  !! не дождались: ${what}`); return false;
}
const atN15 = (pid) => async () => (await engine.executions({ processInstanceId: pid, activityId: 'n15' })).length > 0;
const ended = (pid) => async () => (await engine.processInstances({ id: pid })).length === 0;
const both = (verdict, tag) => [ids.audOpenai, ids.audAnthropic].map((auditor) => ({ auditor, verdict, evidence: { gate_test: tag } }));

const o = await orch.startWork({ criticality: 'NORMAL', note: 'E5 system check gate' });
log('order', o);
check('e5g_reach_n15_pass1', await pumpUntil('n15 #1', atN15(o.pid)), `проход 1, проверено ${sysCalls.join(',')}`);
const r1 = await orch.deliverVerdicts(o.pid, both('ACCEPT', 'pass1'));
check('e5g_fail_check_forces_revise', r1.verdict === 'REVISE' && r1.verdict_ids.length === 2,
  `итог прохода 1: ${r1.verdict} при системной проверке FAIL и двух ACCEPT`);
const st1 = await statusOf(o.work_item_id);
check('e5g_not_accepted_after_fail', st1 !== 'ACCEPTED', `статус ${st1}`);
check('e5g_reach_n15_pass2', await pumpUntil('n15 #2', atN15(o.pid)), `после REVISE — снова 6…15; проверено ${sysCalls.join(',')}`);
check('e5g_no_release_on_fail', relCalls.length === 0 && egressCalls === 0, `prepareRelease ${relCalls.length}, внешних действий ${egressCalls}`);
const g = await gateEv(ids.tenantA);
check('e5g_gate_evidence', g.length === 1 && g[0].payload?.head_sha === H1 && g[0].payload?.system_check === 'FAIL',
  `записей ZAVOD_P1_SYSTEM_CHECK_GATE: ${g.length}`);
const r2 = await orch.deliverVerdicts(o.pid, both('ACCEPT', 'pass2'));
check('e5g_pass_check_accepts', r2.verdict === 'ACCEPT', `итог прохода 2: ${r2.verdict}`);
const done = await pumpUntil('завершение', ended(o.pid));
const st2 = await statusOf(o.work_item_id);
check('e5g_released_once_second_head', done && relCalls.length === 1 && relCalls[0] === H2 && egressCalls === 1
  && st2 === 'RELEASED' && orch.refused.length === 0,
  `завершён ${done}; prepareRelease ${relCalls.join(',') || '-'}; внешних ${egressCalls}; статус ${st2}; отказы ${orch.refused.length}`);
check('e5g_checks_both_heads', sysCalls.length === 2 && sysCalls[0] === H1 && sysCalls[1] === H2, `проверки: ${sysCalls.join(',')}`);
await sa.end();

writeFileSync(join(OUT, 'e5_system_check_gate_result.json'), JSON.stringify({ result: FAIL ? 'FAIL' : 'PASS', orch: ORCH_VERSION, checks }, null, 1));
await kernel.close();
log(`=== E5_SYSTEM_CHECK_GATE_RESULT=${FAIL ? 'FAIL' : 'PASS'} (${checks.filter((c) => c.ok).length}/${checks.length})`);
process.exit(FAIL);
