// ДОКУМЕНТ: zavod/engine/src/orchestrator.mjs
// ВЕРСИЯ: v0.8  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 06:15 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 06:49 +03:00 (v0.8: аудит ChatGPT v0.7, MAJOR —
//   захват задания движка не знает заказчика: оркестратор брал чужое задание, держал его захваченным и обрывал
//   проход на TENANT_MISMATCH/NOT_FOUND. Теперь заказчик задания определяется до любой работы (у подпроцесса
//   bem_subtask — по родительскому экземпляру), чужие задания отпускаются (unacquire) без продвижения, захват
//   повторяется, пока пачка полная, чтобы чужие не заслонили свои; v0.7: пилот — условие выхода узла 11 (§12.2:
//   «тесты пройдены»): при системной проверке не PASS итог ACCEPT проверяющих превращается в REVISE (возврат к 6),
//   доказательство ZAVOD_P1_SYSTEM_CHECK_GATE; без этого пилот p1_20261011_real дошёл до узла 17 с FAIL 16/17 и
//   выпуск был отклонён только защитой prepareRelease; v0.6: этап 5,
//   пилот P1 — необязательный объект pilot: head_sha берётся из результата рабочего (узел 9), системная
//   проверка узла 11 — pilot.systemCheck, предмет узла 12 — ZAVOD_PRODUCT_RELEASE, узел 17 — pilot.prepareRelease
//   (решение оператора W3 и манифест SR-13 до ReleaseAndTransition), вердикты — по одному на проверяющего
//   (deliverVerdicts, id записей — audit_record_id), блокировка задания движка у пилота 12 часов (рабочий и решение W3 длятся часами); без pilot поведение v0.5 не меняется; v0.5: аудит E4-6 —
//   M-E46-01 узел 17 — одна команда Kernel ReleaseAndTransition (выпуск, RELEASED, outbox в одной транзакции),
//   отступление DEV-E43-02 снято; M-E46-02 роль шагов — поле kernelRole без подстановки в cmd; v0.4: E4-4 — текст заявки
//   (request) пишется в доказательство CreateWorkItem, Kernel проверяет его на секреты (SECRET_IN_REQUEST); в движок
//   текст не попадает; рабочий получает его в пакете задачи как данные; v0.3: E4-7 — роль вызывающего в каждой
//   команде Kernel: kernel, auditor, operator; v0.2: E4-5 — SR-07:
//   каждая попытка рабочего пишется в журнал расхода (RecordUsage); предел неудачных попыток и бюджет
//   токенов на работу; превышение — работа BLOCKED через Kernel, задание движка снимается без повторов;
//   рабочий для работы не в PLANNED/IN_PROGRESS не запускается)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf, до v0.5; сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1, v0.6–v0.8)
// НАЗНАЧЕНИЕ: оркестратор Kernel над движком (Завод, этап 4, E4-3). Движок хранит только положение
//   в графе H1.31 §12; каждое изменение работы (статус, доказательство, предмет, вердикт, выпуск,
//   внешнее действие) делает Kernel своими командами. Экземпляр процесса запускает только Kernel и
//   только сообщением bemIntake, после записи работы (§12.1 п.5). Задание движка закрывается только
//   после успеха команды Kernel; отказ Kernel — задание не закрывается, ошибка наверх.
// ОГРАНИЧЕНИЯ: назначение проверяющих — путь управления (bem_governance): оркестратор вызывает
//   переданный обработчик governance.assignAuditors и сам ролью управления не пользуется.
//   Узел 17 (§12.2): выпуск и строка outbox — одна транзакция Kernel (ReleaseAndTransition, M-E46-01).

import { randomUUID } from 'node:crypto';
import { TOPICS } from './graph_check.mjs';
import { EngineError } from './engine_client.mjs';

export const ORCH_VERSION = '0.8.0';
export const PILOT_SCOPE = 'ZAVOD_PRODUCT_RELEASE';
export const DEFAULT_LIMITS = Object.freeze({ maxFailedAttempts: 3, tokenBudget: 200000 });
export const EXEC_TOPICS = Object.freeze(['exec-anthropic', 'exec-openai']);
const ALL_TOPICS = Object.freeze([...new Set(Object.values(TOPICS)), ...EXEC_TOPICS]);
const REFUSE_CODES = new Set(['SR07_BLOCKED', 'WORK_NOT_RUNNABLE']);
const ACQUIRE_BATCH = 10;     // v0.8: размер пачки захвата
const ACQUIRE_ROUNDS = 20;    // v0.8: не больше пачек на тему за проход (200 заданий)

// Учебная заглушка рабочего: без модели и сети, расход — оценка.
export async function stubWorker() {
  return { outcome: 'OK', usage: { model: 'zavod-stub', input_tokens: 1000, output_tokens: 200, context_estimate: 1200,
    context_limit: 200000, measured_by: 'LOCAL_ESTIMATE' } };
}

export class Orchestrator {
  // kernel: Kernel; engine: EngineClient; actor: исполнитель-автор работы (делегирован Kernel);
  // tenantId: заказчик; governance: { assignAuditors(tenantId, subjectId) }; egress(row): внешний исполнитель.
  // runWorker({ provider, workKey, subIndex, attempt_no, request }) → { outcome: 'OK'|'PROVIDER_ERROR', usage: {...} };
  // по умолчанию — учебная заглушка без модели. limits — SR-07.
  constructor({ kernel, engine, actor, tenantId, governance, egress, providers = ['anthropic', 'openai'],
    runWorker = stubWorker, limits = DEFAULT_LIMITS, log = () => {}, pilot = null }) {
    // pilot (v0.6, этап 5): { systemCheck({ orch, work_item_id, head_sha }) → { result: 'PASS'|'FAIL', ... },
    //   prepareRelease({ orch, work_item_id, subject_id, head_sha, command_id }) → { outbox_kind, outbox_payload } }
    Object.assign(this, { kernel, engine, actor, tenantId, governance, egress, providers, runWorker, limits, log, pilot });
    this.heads = new Map();     // work_item_id → head_sha из результата рабочего (только pilot)
    this.kernelRole = 'kernel';  // роль шагов оркестратора по таблице 3.1; Kernel без роли отказывает
    this.workerId = `zavod-kernel-orch-${process.pid}`;
    this.transitions = [];      // { work_item_id, from, to, command_id, node }
    this.pendingAcks = new Set(); // подпроцессы, у которых результат записан и ждёт подтверждения
    this.handled = [];          // { node, pid, ok }
    this.refused = [];          // { node, pid, code, reason } — задания, снятые без повторов (SR-07)
    this.released = 0;          // v0.8: отпущено чужих заданий (другой заказчик или заказчик не определён)
    this.requests = new Map();  // work_item_id → текст заявки (данные для рабочего, не команды)
  }

  // role — роль вызывающего по таблице 3.1 (src/roles.mjs Kernel); шаги оркестратора — роль kernel.
  async cmd(type, payload, { caller = this.actor, role = this.kernelRole, command_id } = {}) {
    const req = { type, actor_id: caller, tenant_id: this.tenantId, payload };
    if (command_id) req.command_id = command_id;
    const r = await this.kernel.execute({ actor_id: caller, role }, req);
    if (!r.ok) throw new EngineError('KERNEL_REJECTED', `${type}: ${r.error.code} ${r.error.message}`, { kernelCode: r.error.code });
    return r.result;
  }

  async status(wi) { return this.cmd('GetWorkItem', { work_item_id: wi }); }

  async move(wi, to, node, extra = {}) {
    const cur = await this.status(wi);
    const command_id = randomUUID();
    const r = await this.cmd('Transition', { work_item_id: wi, expected_revision: cur.revision, new_status: to,
      evidence: { zavod: 'E4-3', node, from: cur.status }, ...extra }, { command_id });
    this.transitions.push({ work_item_id: wi, from: cur.status, to, command_id, node, outbox_id: r.outbox_id ?? null });
    return r;
  }

  evidence(kind, payload) { return this.cmd('RecordEvidence', { kind, payload }); }

  // §12.1 п.5: сначала работа в Kernel, затем старт экземпляра сообщением bemIntake.
  async startWork({ work_item_id = randomUUID(), criticality = 'NORMAL', note = 'E4-3', request = null } = {}) {
    const evidence = request === null ? { zavod: 'E4-3', note } : { zavod: 'E4-3', note, request: String(request) };
    await this.cmd('CreateWorkItem', { work_item_id, criticality, evidence });
    if (request !== null) this.requests.set(work_item_id, String(request));
    const pi = await this.engine.startByMessage('bemIntake', { workKey: work_item_id, tenantId: this.tenantId, pass: 0 }, work_item_id);
    return { work_item_id, pid: pi.id };
  }

  // Один проход по всем темам. Возвращает число обработанных заданий и подтверждений.
  async pump() {
    let n = 0;
    for (const topic of ALL_TOPICS) {
      const own = await this.acquireOwn(topic);
      for (let i = 0; i < own.length; i += 1) {
        const { job, vars } = own[i];
        let out;
        try {
          out = await this.handle(topic, job, vars);
        } catch (e) {
          if (!REFUSE_CODES.has(e?.code)) {
            // v0.8: ещё не начатые свои задания отпускаются, а не висят захваченными до конца блокировки.
            for (const r of own.slice(i + 1)) await this.engine.unacquireJob(r.job.id, this.workerId);
            throw e;
          }
          // SR-07: задание снимается без повторов; движок не продвигается, работа ждёт решения.
          await this.engine.failJob(job.id, this.workerId, `${e.code}: ${e.message}`.slice(0, 250));
          this.refused.push({ node: job.elementId, pid: job.processInstanceId, code: e.code, reason: e.message });
          n += 1;
          continue;
        }
        await this.engine.completeJob(job.id, this.workerId, out);
        this.handled.push({ node: job.elementId, pid: job.processInstanceId, topic });
        n += 1;
      }
    }
    for (const sub of [...this.pendingAcks]) {
      const ex = (await this.engine.executions({ processInstanceId: sub, activityId: 's3' }))[0];
      if (!ex) continue;
      await this.engine.messageToExecution(ex.id, 'subtaskAck');
      this.pendingAcks.delete(sub);
      n += 1;
    }
    return n;
  }

  // v0.8: задания движка общие для всех заказчиков, а захват не отбирает по заказчику. Поэтому: захватить пачку,
  // определить заказчика каждого задания до любой работы, чужие сразу отпустить без продвижения. Пачка полная —
  // захват повторяется (чужие ещё держатся и не возвращаются снова), чтобы чужие не заслонили свои.
  // Ошибка при разборе — отпускаются все захваченные этим проходом, ошибка наверх.
  async acquireOwn(topic) {
    const held = [];
    const own = [];
    try {
      for (let round = 0; round < ACQUIRE_ROUNDS; round += 1) {
        // v0.6: у пилота шаги длинные (рабочий — часы, решение оператора W3) — блокировка задания 12 часов.
        const jobs = await this.engine.acquire(topic, this.workerId, this.pilot ? 'PT12H' : undefined, ACQUIRE_BATCH);
        held.push(...jobs);
        for (const job of jobs) {
          const { vars, tenant } = await this.jobTenant(job);
          if (tenant === this.tenantId) own.push({ job, vars });
        }
        if (jobs.length < ACQUIRE_BATCH) break;
      }
    } catch (e) {
      for (const job of held) await this.engine.unacquireJob(job.id, this.workerId);
      throw e;
    }
    const mine = new Set(own.map((o) => o.job.id));
    for (const job of held) {
      if (mine.has(job.id)) continue;
      await this.engine.unacquireJob(job.id, this.workerId);
      this.released += 1;
    }
    return own;
  }

  // v0.8: заказчик задания. У подпроцесса bem_subtask своей переменной tenantId нет — берётся у родителя.
  async jobTenant(job) {
    const vars = await this.engine.processVars(job.processInstanceId);
    if (vars.tenantId !== undefined) return { vars, tenant: vars.tenantId };
    const parent = (await this.engine.processInstances({ subProcessInstanceId: job.processInstanceId }))[0];
    const pv = parent ? await this.engine.processVars(parent.id) : {};
    return { vars, tenant: pv.tenantId ?? null };
  }

  async handle(topic, job, v) {
    const node = job.elementId;
    if (EXEC_TOPICS.includes(topic)) {
      if (node !== 's2' || `exec-${v.provider}` !== topic) throw new EngineError('JOB_UNEXPECTED', `${topic} ${node}`);
      return this.runSubtask(job, v);
    }
    if (TOPICS[node] !== topic) throw new EngineError('JOB_UNEXPECTED', `${topic} ${node}`);
    const wi = v.workKey;
    if (v.tenantId !== this.tenantId) throw new EngineError('TENANT_MISMATCH', `${v.tenantId}`);
    switch (node) {
      case 'n2': {
        if (!/^[0-9a-f-]{36}$/i.test(wi ?? '')) throw new EngineError('BAD_WORK_KEY', String(wi));
        await this.evidence('E43_NORMALIZED', { work_item_id: wi, node });
        return {};
      }
      case 'n3': {
        await this.status(wi);   // работа видна только своему заказчику (H1.31 §8.2)
        await this.evidence('E43_TENANT_RESOLVED', { work_item_id: wi, tenant_id: this.tenantId });
        return {};
      }
      case 'n4': {
        const s = await this.status(wi);
        return { criticality: s.criticality };
      }
      case 'n6': {
        const s = await this.status(wi);
        const to = { NEW: 'PLANNED', BLOCKED: 'PLANNED', IN_REVIEW: 'IN_PROGRESS' }[s.status];
        if (!to) throw new EngineError('PLAN_FROM_BAD_STATUS', s.status);
        await this.move(wi, to, node);
        const pass = (v.pass ?? 0) + 1;
        return { pass, subtaskCount: this.providers.length, providers: this.providers.join(','),
          headSha: `e43-${wi.slice(0, 8)}-p${pass}-${randomUUID().slice(0, 8)}` };
      }
      case 'n8': {
        const s = await this.status(wi);
        if (s.status === 'PLANNED') await this.move(wi, 'IN_PROGRESS', node);
        await this.evidence('E43_RESULTS_COLLECTED', { work_item_id: wi, pass: v.pass });
        return {};
      }
      case 'n9': {
        if (this.pilot) {
          const head = this.heads.get(wi);
          if (!/^[0-9a-f]{40}$/.test(head || '')) throw new EngineError('NO_WORKER_HEAD', `${wi}`);
          await this.evidence('ZAVOD_P1_MERGED', { work_item_id: wi, head_sha: head });
          return { headSha: head };
        }
        await this.evidence('E43_MERGED', { work_item_id: wi, head_sha: v.headSha });
        return {};
      }
      case 'n11': {
        if (this.pilot) {
          const r = await this.pilot.systemCheck({ orch: this, work_item_id: wi, head_sha: v.headSha });
          await this.evidence('ZAVOD_P1_SYSTEM_CHECK', { work_item_id: wi, head_sha: v.headSha, ...r });
          return { systemCheck: r.result };
        }
        await this.evidence('E43_SYSTEM_CHECK', { work_item_id: wi, head_sha: v.headSha, result: 'PASS', stub: true });
        return {};
      }
      case 'n12': {
        const subject_id = randomUUID();
        await this.cmd('PublishSubject', { subject_id, work_item_id: wi, head_sha: v.headSha, criticality: v.criticality,
          scope: this.pilot ? PILOT_SCOPE : 'WORKING', authors: [this.actor], evidence: { zavod: this.pilot ? 'E5' : 'E4-3', node } });
        return { subjectId: subject_id };
      }
      case 'n14': {
        await this.move(wi, 'IN_REVIEW', node);
        await this.governance.assignAuditors(this.tenantId, v.subjectId);
        return {};
      }
      case 'n17': {
        // M-E46-01: выпуск, RELEASED и outbox — одна команда, одна транзакция Kernel.
        const command_id = randomUUID();
        // v0.6: у пилота решение оператора (W3) и манифест (SR-13) пишутся до выпуска; манифест называет command_id строки outbox.
        const rel = this.pilot
          ? await this.pilot.prepareRelease({ orch: this, work_item_id: wi, subject_id: v.subjectId, head_sha: v.headSha, command_id })
          : { outbox_kind: 'zavod.e43.deliver', outbox_payload: { subject_id: v.subjectId, head_sha: v.headSha } };
        const cur = await this.status(wi);
        const t = await this.cmd('ReleaseAndTransition', { work_item_id: wi, subject_id: v.subjectId, head_sha: v.headSha,
          expected_revision: cur.revision, outbox_kind: rel.outbox_kind,
          outbox_payload: rel.outbox_payload,
          evidence: { zavod: 'E4-3', node, from: cur.status } }, { command_id });
        if (t.released !== true) throw new EngineError('RELEASE_FAILED', JSON.stringify(t));
        this.transitions.push({ work_item_id: wi, from: cur.status, to: 'RELEASED', command_id, node,
          outbox_id: t.outbox_id ?? null });
        return { outboxId: t.outbox_id };
      }
      case 'n18': {
        const d = await this.kernel.dispatchOnce(this.egress, { worker: this.workerId });
        const mine = d.results?.find((r) => r.outbox_id === v.outboxId);
        if (!mine || !mine.finished) throw new EngineError('EGRESS_NOT_FINISHED', JSON.stringify(d));
        return { egressOutcome: mine.outcome };
      }
      default:
        throw new EngineError('JOB_UNEXPECTED', `${topic} ${node}`);
    }
  }

  // SR-07: попытки рабочего до успеха или до предела. Каждая попытка — строка журнала расхода.
  limitReason(u) {
    if (u.failed >= this.limits.maxFailedAttempts) return `failed attempts ${u.failed} >= ${this.limits.maxFailedAttempts}`;
    if (u.tokens > this.limits.tokenBudget) return `tokens ${u.tokens} > budget ${this.limits.tokenBudget}`;
    return null;
  }

  async runSubtask(job, v) {
    const wi = v.workKey;
    const s = await this.status(wi);
    if (!['PLANNED', 'IN_PROGRESS'].includes(s.status)) throw new EngineError('WORK_NOT_RUNNABLE', `${wi} ${s.status}`);
    for (;;) {
      const u = await this.cmd('GetUsage', { work_item_id: wi });
      const why = this.limitReason(u);
      if (why) {
        await this.move(wi, 'BLOCKED', 's2', { evidence: { zavod: 'SR-07', node: 's2', reason: why, usage: u } });
        await this.evidence('SR07_LIMIT_EXCEEDED', { work_item_id: wi, reason: why, usage: u, limits: this.limits });
        throw new EngineError('SR07_BLOCKED', why, { work_item_id: wi });
      }
      const attempt_no = u.last_attempt + 1;
      let r;
      try {
        r = await this.runWorker({ provider: v.provider, workKey: wi, subIndex: v.subIndex, attempt_no,
          request: this.requests.get(wi) ?? null });
      } catch (e) {
        r = { outcome: 'PROVIDER_ERROR', usage: {}, error: String(e?.message || e).slice(0, 200) };
      }
      const outcome = r?.outcome === 'OK' ? 'OK' : 'PROVIDER_ERROR';
      const us = r?.usage || {};
      await this.cmd('RecordUsage', { work_item_id: wi, attempt_no, provider: v.provider, model: us.model || 'zavod-stub',
        input_tokens: us.input_tokens ?? 0, output_tokens: us.output_tokens ?? 0, cached_tokens: us.cached_tokens ?? 0,
        tool_overhead: us.tool_overhead ?? 0, context_estimate: us.context_estimate ?? 0, context_limit: us.context_limit ?? 0,
        measured_by: us.measured_by === 'PROVIDER_REPORTED' ? 'PROVIDER_REPORTED' : 'LOCAL_ESTIMATE', outcome });
      if (outcome !== 'OK') continue;
      if (this.pilot) this.heads.set(wi, r?.head_sha ?? null);
      const after = await this.cmd('GetUsage', { work_item_id: wi });
      if (this.limitReason(after)) continue;   // результат записан, но бюджет превышен — на следующем круге BLOCKED
      await this.evidence('E43_SUBTASK_RESULT', { work_item_id: wi, provider: v.provider, sub_index: v.subIndex, attempt_no });
      this.pendingAcks.add(job.processInstanceId);
      return {};
    }
  }

  // Узел 15: вердикты проверяющих пишет Kernel (вызывающий — проверяющий), затем статус работы,
  // затем движок продвигается адресно по исполнению узла 15.
  async deliverVerdict(pid, auditors, verdict) {
    const v = await this.engine.processVars(pid);
    const ex = (await this.engine.executions({ processInstanceId: pid, activityId: 'n15' }))[0];
    if (!ex) throw new EngineError('NOT_WAITING_AUDIT', pid);
    for (const aud of auditors) {
      await this.cmd('RecordVerdict', { subject_id: v.subjectId, head_sha: v.headSha, verdict,
        evidence: { zavod: 'E4-3', reviewed: v.headSha } }, { caller: aud, role: 'auditor' });
    }
    if (verdict === 'ACCEPT') await this.move(v.workKey, 'ACCEPTED', 'n15');
    if (verdict === 'BLOCKED') await this.move(v.workKey, 'BLOCKED', 'n15');
    await this.engine.trigger(ex.id, { verdict });
  }

  // v0.6 (пилот): у каждого проверяющего свой вердикт и своё доказательство. Итог для движка: ACCEPT — только если
  // приняли все; BLOCKED — если хоть один BLOCKED; иначе REVISE. Вердикт пишет Kernel от имени проверяющего.
  async deliverVerdicts(pid, items) {
    const v = await this.engine.processVars(pid);
    const ex = (await this.engine.executions({ processInstanceId: pid, activityId: 'n15' }))[0];
    if (!ex) throw new EngineError('NOT_WAITING_AUDIT', pid);
    const ids = [];
    for (const it of items) {
      if (!['ACCEPT', 'REVISE', 'BLOCKED'].includes(it.verdict)) throw new EngineError('BAD_VERDICT', it.verdict);
      const r = await this.cmd('RecordVerdict', { subject_id: v.subjectId, head_sha: v.headSha, verdict: it.verdict,
        evidence: { zavod: 'E5', reviewed: v.headSha, ...(it.evidence || {}) } }, { caller: it.auditor, role: 'auditor' });
      ids.push(r?.audit_record_id ?? null);
    }
    const all = items.map((x) => x.verdict);
    let verdict = all.every((x) => x === 'ACCEPT') ? 'ACCEPT' : all.includes('BLOCKED') ? 'BLOCKED' : 'REVISE';
    // v0.7: §12.2 узел 11 — без PASS системной проверки работа не принята, даже если приняли все проверяющие.
    if (verdict === 'ACCEPT' && this.pilot && v.systemCheck !== 'PASS') {
      verdict = 'REVISE';
      await this.evidence('ZAVOD_P1_SYSTEM_CHECK_GATE', { work_item_id: v.workKey, head_sha: v.headSha,
        system_check: v.systemCheck ?? null, auditors: all, verdict });
    }
    if (verdict === 'ACCEPT') await this.move(v.workKey, 'ACCEPTED', 'n15');
    if (verdict === 'BLOCKED') await this.move(v.workKey, 'BLOCKED', 'n15');
    await this.engine.trigger(ex.id, { verdict });
    return { verdict, verdict_ids: ids };
  }

  // Узел 19: решение оператора — Kernel OperatorDecision от человека; отмена — переход CANCELLED.
  async operatorDecision(pid, human, choice) {
    if (!['CONTINUE', 'CANCEL'].includes(choice)) throw new EngineError('BAD_CHOICE', choice);
    const v = await this.engine.processVars(pid);
    const task = (await this.engine.tasks({ processInstanceId: pid, taskDefinitionKey: 'n19' }))[0];
    if (!task) throw new EngineError('NO_OPERATOR_TASK', pid);
    await this.cmd('OperatorDecision', { decision_code: 'ZAVOD-E43-N19', decision: choice, note: v.workKey }, { caller: human, role: 'operator' });
    if (choice === 'CANCEL') await this.move(v.workKey, 'CANCELLED', 'n19');
    await this.engine.completeTask(task.id, { operatorChoice: choice });
  }
}
