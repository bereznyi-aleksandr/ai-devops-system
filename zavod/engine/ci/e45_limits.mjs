// ДОКУМЕНТ: zavod/engine/ci/e45_limits.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 06:35 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 06:35 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: критерий E4-5 протокола Z1 v1.9 — предел попыток и учёт расхода (SR-07) срабатывают в тесте.
//   Заказ C: рабочий всегда ошибается → ровно maxFailedAttempts строк расхода PROVIDER_ERROR → работа BLOCKED,
//     задания движка сняты без повторов, второй рабочий не запускается, внешнего действия нет.
//   Заказ D: рабочий успешен, но тратит 150000 токенов при бюджете 200000 → вторая попытка превышает
//     бюджет → BLOCKED; расход записан полностью.
//   После блокировки повторные проходы оркестратора новых попыток и строк расхода не дают.
// ВЫЗОВ и СРЕДА: как ci/e43_training_order.mjs (тот же движок; граф разворачивается, если ещё нет).
// ОГРАНИЧЕНИЯ: рабочие — заглушки без моделей и сети; секретов в выводе нет.

import { readFileSync, writeFileSync, appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { Kernel } from '../../kernel/src/kernel.mjs';
import { CONN, bootFixture, assignAuditor, runStopFile } from '../../kernel/tests/helpers.mjs';
import { EngineClient } from '../src/engine_client.mjs';
import { Orchestrator } from '../src/orchestrator.mjs';

const pg = createRequire(new URL('../../kernel/package.json', import.meta.url))('pg');
const OUT = process.env.E43_OUT || join(process.cwd(), 'e43_out');
mkdirSync(OUT, { recursive: true });
const LOG = join(OUT, 'e45_limits.log');
const log = (...a) => { const s = a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '); console.log(s); appendFileSync(LOG, s + '\n'); };
let FAIL = 0;
const checks = [];
function check(id, ok, detail) { checks.push({ id, ok: !!ok, detail }); log(`${ok ? 'CHECK_PASS' : 'CHECK_FAIL'} ${id}:`, detail); if (!ok) FAIL = 1; }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

log('=== E4-5 SR-07 limits', new Date().toISOString());
const engine = new EngineClient({ base: process.env.ZAVOD_ENGINE_BASE || 'http://127.0.0.1:8091/flowable-rest',
  user: process.env.ZAVOD_ENGINE_USER, pass: process.env.ZAVOD_ENGINE_PASS });
const ids = await bootFixture();
const kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-e45-stop-') });
await kernel.assertIdentity();
const defs = await engine.api('GET', '/service/repository/process-definitions?key=bem_work');
if (!(defs.json?.data?.length > 0)) await engine.deployChecked('zavod_bem_work.bpmn20.xml',
  readFileSync(new URL('../bpmn/bem_work.bpmn20.xml', import.meta.url), 'utf8'));

const limits = { maxFailedAttempts: 3, tokenBudget: 200000 };
let egressCalls = 0;
const base = {
  kernel, engine, actor: ids.author, tenantId: ids.tenantA, limits, log,
  governance: { assignAuditors: async (t, s) => { for (const a of [ids.audOpenai, ids.audAnthropic]) await assignAuditor(t, s, a); } },
  egress: async () => { egressCalls += 1; return { outcome: 'SENT', detail: {} }; },
};
const sa = new pg.Client({ ...CONN, user: process.env.E43_EXPORT_USER || 'postgres' });
await sa.connect();
const usageRows = async (wi) => (await sa.query('SELECT attempt_no, provider, outcome, input_tokens, output_tokens FROM bem_core.usage_record WHERE work_item_id = $1 ORDER BY created_at, attempt_no', [wi])).rows;
const statusOf = async (wi) => (await sa.query('SELECT status FROM bem_core.work_item WHERE id = $1', [wi])).rows[0]?.status;
const evidenceKinds = async (t) => (await sa.query("SELECT kind, payload FROM bem_core.evidence WHERE tenant_id = $1 AND kind = 'SR07_LIMIT_EXCEEDED'", [t])).rows;

async function pumpUntil(orch, what, pred, ms = 60000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { await orch.pump(); if (await pred()) return true; await sleep(300); }
  log(`  !! не дождались: ${what}`); return false;
}
const subPids = async (pid) => (await engine.processInstances({ superProcessInstanceId: pid })).map((p) => p.id);

async function scenario(tag, runWorker, expect, { refusedN, deadN }) {
  const workerCalls = [];
  const orch = new Orchestrator({ ...base, runWorker: async (a) => { workerCalls.push(a); return runWorker(a); } });
  const o = await orch.startWork({ criticality: 'NORMAL', note: `E4-5 order ${tag}` });
  log(`order ${tag}`, o);
  const blocked = await pumpUntil(orch, `${tag} BLOCKED`, async () => (await statusOf(o.work_item_id)) === 'BLOCKED' && orch.refused.length >= refusedN);
  check(`e45_${tag}_blocked`, blocked, `статус ${await statusOf(o.work_item_id)}; снято заданий ${orch.refused.length}: ${orch.refused.map((r) => r.code).join(',')}`);
  const u1 = await usageRows(o.work_item_id);
  const calls1 = workerCalls.length;
  for (let i = 0; i < 5; i++) { await orch.pump(); await sleep(300); }   // повторные проходы — без новых попыток
  const u2 = await usageRows(o.work_item_id);
  check(`e45_${tag}_no_retry_after_block`, u2.length === u1.length && workerCalls.length === calls1,
    `строк расхода ${u1.length} → ${u2.length}; вызовов рабочего ${calls1} → ${workerCalls.length}`);
  expect(o, u2, workerCalls, orch);
  const subs = await subPids(o.pid);
  let dead = 0;
  for (const s of subs) dead += (await engine.deadLetterJobs({ processInstanceId: s })).length;
  const atN8 = (await engine.executions({ processInstanceId: o.pid, activityId: 'n8' })).length;
  check(`e45_${tag}_engine_parked`, (await engine.processInstances({ id: o.pid })).length === 1 && atN8 === 0 && dead === deadN,
    `экземпляр жив, n8 не достигнут (${atN8}), мёртвых заданий ${dead} (надо ${deadN})`);
  return { o, usage: u2, refused: orch.refused, workerCalls: workerCalls.length, transitions: orch.transitions };
}

// Заказ C: каждая попытка — ошибка поставщика.
const C = await scenario('C', async () => ({ outcome: 'PROVIDER_ERROR', usage: { input_tokens: 500, output_tokens: 0 } }),
  (o, u, calls, orch) => {
    check('e45_C_attempts_eq_limit', u.length === limits.maxFailedAttempts && u.every((r) => r.outcome === 'PROVIDER_ERROR')
      && u.map((r) => r.attempt_no).join(',') === '1,2,3', `строки: ${u.map((r) => `${r.attempt_no}:${r.provider}:${r.outcome}`).join(' ')}`);
    check('e45_C_second_worker_not_run', calls.length === limits.maxFailedAttempts && orch.refused.some((r) => r.code === 'WORK_NOT_RUNNABLE'),
      `вызовов рабочего ${calls.length}; отказы ${orch.refused.map((r) => r.code).join(',')}`);
  }, { refusedN: 2, deadN: 2 });

// Заказ D: успешный, но дорогой рабочий.
const D = await scenario('D', async () => ({ outcome: 'OK', usage: { input_tokens: 120000, output_tokens: 30000, measured_by: 'LOCAL_ESTIMATE' } }),
  (o, u) => {
    const tokens = u.reduce((s, r) => s + r.input_tokens + r.output_tokens, 0);
    check('e45_D_budget', u.length === 2 && u.every((r) => r.outcome === 'OK') && tokens === 300000,
      `строк ${u.length}, токенов ${tokens} при бюджете ${limits.tokenBudget}`);
  }, { refusedN: 1, deadN: 1 });

const ev = await evidenceKinds(ids.tenantA);
check('e45_evidence_recorded', ev.length === 2, `записей SR07_LIMIT_EXCEEDED: ${ev.length}`);
check('e45_no_egress', egressCalls === 0, `внешних действий ${egressCalls}`);
const blockedTr = [...C.transitions, ...D.transitions].filter((t) => t.to === 'BLOCKED');
const cl = (await sa.query('SELECT command_id FROM bem_core.command_log WHERE command_id = ANY($1)', [blockedTr.map((t) => t.command_id)])).rows;
check('e45_block_via_kernel', blockedTr.length === 2 && cl.length === 2, `переходов BLOCKED через Kernel ${blockedTr.length}, в command_log ${cl.length}`);
await sa.end();

writeFileSync(join(OUT, 'e45_result.json'), JSON.stringify({ result: FAIL ? 'FAIL' : 'PASS', limits, checks, C, D }, null, 1));
await kernel.close();
log(`=== E45_RESULT=${FAIL ? 'FAIL' : 'PASS'} (${checks.filter((c) => c.ok).length}/${checks.length})`);
process.exit(FAIL);
