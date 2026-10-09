// ДОКУМЕНТ: zavod/engine/src/orchestrator.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 06:15 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 06:15 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: оркестратор Kernel над движком (Завод, этап 4, E4-3). Движок хранит только положение
//   в графе H1.31 §12; каждое изменение работы (статус, доказательство, предмет, вердикт, выпуск,
//   внешнее действие) делает Kernel своими командами. Экземпляр процесса запускает только Kernel и
//   только сообщением bemIntake, после записи работы (§12.1 п.5). Задание движка закрывается только
//   после успеха команды Kernel; отказ Kernel — задание не закрывается, ошибка наверх.
// ОГРАНИЧЕНИЯ: назначение проверяющих — путь управления (bem_governance): оркестратор вызывает
//   переданный обработчик governance.assignAuditors и сам ролью управления не пользуется.
//   Отступление DEV-E43-02: §12.2 узел 17 требует выпуск и строку outbox в одной транзакции;
//   Kernel v0.4 даёт их двумя командами (ReleaseSubject, затем Transition с outbox) — строка outbox
//   создаётся только после успешного выпуска, обратного порядка нет. Объединение — отдельная задача.

import { randomUUID } from 'node:crypto';
import { TOPICS } from './graph_check.mjs';
import { EngineError } from './engine_client.mjs';

export const ORCH_VERSION = '0.1.0';
export const EXEC_TOPICS = Object.freeze(['exec-anthropic', 'exec-openai']);
const ALL_TOPICS = Object.freeze([...new Set(Object.values(TOPICS)), ...EXEC_TOPICS]);

export class Orchestrator {
  // kernel: Kernel; engine: EngineClient; actor: исполнитель-автор работы (делегирован Kernel);
  // tenantId: заказчик; governance: { assignAuditors(tenantId, subjectId) }; egress(row): внешний исполнитель.
  constructor({ kernel, engine, actor, tenantId, governance, egress, providers = ['anthropic', 'openai'], log = () => {} }) {
    Object.assign(this, { kernel, engine, actor, tenantId, governance, egress, providers, log });
    this.workerId = `zavod-kernel-orch-${process.pid}`;
    this.transitions = [];      // { work_item_id, from, to, command_id, node }
    this.pendingAcks = new Set(); // подпроцессы, у которых результат записан и ждёт подтверждения
    this.handled = [];          // { node, pid, ok }
  }

  async cmd(type, payload, { caller = this.actor, command_id } = {}) {
    const req = { type, actor_id: caller, tenant_id: this.tenantId, payload };
    if (command_id) req.command_id = command_id;
    const r = await this.kernel.execute({ actor_id: caller }, req);
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
  async startWork({ work_item_id = randomUUID(), criticality = 'NORMAL', note = 'E4-3' } = {}) {
    await this.cmd('CreateWorkItem', { work_item_id, criticality, evidence: { zavod: 'E4-3', note } });
    const pi = await this.engine.startByMessage('bemIntake', { workKey: work_item_id, tenantId: this.tenantId, pass: 0 }, work_item_id);
    return { work_item_id, pid: pi.id };
  }

  // Один проход по всем темам. Возвращает число обработанных заданий и подтверждений.
  async pump() {
    let n = 0;
    for (const topic of ALL_TOPICS) {
      const jobs = await this.engine.acquire(topic, this.workerId);
      for (const job of jobs) {
        const vars = await this.engine.processVars(job.processInstanceId);
        const out = await this.handle(topic, job, vars);
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

  async handle(topic, job, v) {
    const node = job.elementId;
    if (EXEC_TOPICS.includes(topic)) {
      // Подзадача у поставщика: учебная заглушка без модели; результат — запись Evidence через Kernel.
      if (node !== 's2' || `exec-${v.provider}` !== topic) throw new EngineError('JOB_UNEXPECTED', `${topic} ${node}`);
      await this.evidence('E43_SUBTASK_RESULT', { work_item_id: v.workKey, provider: v.provider, sub_index: v.subIndex, stub: true });
      this.pendingAcks.add(job.processInstanceId);
      return {};
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
        await this.evidence('E43_MERGED', { work_item_id: wi, head_sha: v.headSha });
        return {};
      }
      case 'n11': {
        await this.evidence('E43_SYSTEM_CHECK', { work_item_id: wi, head_sha: v.headSha, result: 'PASS', stub: true });
        return {};
      }
      case 'n12': {
        const subject_id = randomUUID();
        await this.cmd('PublishSubject', { subject_id, work_item_id: wi, head_sha: v.headSha, criticality: v.criticality,
          scope: 'WORKING', authors: [this.actor], evidence: { zavod: 'E4-3', node } });
        return { subjectId: subject_id };
      }
      case 'n14': {
        await this.move(wi, 'IN_REVIEW', node);
        await this.governance.assignAuditors(this.tenantId, v.subjectId);
        return {};
      }
      case 'n17': {
        const rel = await this.cmd('ReleaseSubject', { subject_id: v.subjectId, head_sha: v.headSha });
        if (rel.released !== true) throw new EngineError('RELEASE_FAILED', JSON.stringify(rel));
        const t = await this.move(wi, 'RELEASED', node, { outbox_kind: 'zavod.e43.deliver',
          outbox_payload: { subject_id: v.subjectId, head_sha: v.headSha } });
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

  // Узел 15: вердикты проверяющих пишет Kernel (вызывающий — проверяющий), затем статус работы,
  // затем движок продвигается адресно по исполнению узла 15.
  async deliverVerdict(pid, auditors, verdict) {
    const v = await this.engine.processVars(pid);
    const ex = (await this.engine.executions({ processInstanceId: pid, activityId: 'n15' }))[0];
    if (!ex) throw new EngineError('NOT_WAITING_AUDIT', pid);
    for (const aud of auditors) {
      await this.cmd('RecordVerdict', { subject_id: v.subjectId, head_sha: v.headSha, verdict,
        evidence: { zavod: 'E4-3', reviewed: v.headSha } }, { caller: aud });
    }
    if (verdict === 'ACCEPT') await this.move(v.workKey, 'ACCEPTED', 'n15');
    if (verdict === 'BLOCKED') await this.move(v.workKey, 'BLOCKED', 'n15');
    await this.engine.trigger(ex.id, { verdict });
  }

  // Узел 19: решение оператора — Kernel OperatorDecision от человека; отмена — переход CANCELLED.
  async operatorDecision(pid, human, choice) {
    if (!['CONTINUE', 'CANCEL'].includes(choice)) throw new EngineError('BAD_CHOICE', choice);
    const v = await this.engine.processVars(pid);
    const task = (await this.engine.tasks({ processInstanceId: pid, taskDefinitionKey: 'n19' }))[0];
    if (!task) throw new EngineError('NO_OPERATOR_TASK', pid);
    await this.cmd('OperatorDecision', { decision_code: 'ZAVOD-E43-N19', decision: choice, note: v.workKey }, { caller: human });
    if (choice === 'CANCEL') await this.move(v.workKey, 'CANCELLED', 'n19');
    await this.engine.completeTask(task.id, { operatorChoice: choice });
  }
}
