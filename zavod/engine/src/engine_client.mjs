// ДОКУМЕНТ: zavod/engine/src/engine_client.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 06:10 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 06:10 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: клиент REST Flowable 8.0.0 для Завода (этап 4). Движок слушает только 127.0.0.1;
//   учётку движка знает только Kernel-оркестратор (H1.31 §12.1 п.5: REST движка закрыт для всех,
//   кроме Kernel). Развёртывание модели — только через deployChecked: сначала наш проверщик графа.
// ОГРАНИЧЕНИЯ: пароль движка приходит параметром, нигде не выводится и не пишется в журнал.

import { checkGraph } from './graph_check.mjs';

export class EngineError extends Error {
  constructor(code, message, extra = {}) { super(`${code}: ${message}`); this.code = code; Object.assign(this, extra); }
}

export class EngineClient {
  // base: http://127.0.0.1:<порт>/flowable-rest
  constructor({ base, user, pass }) {
    const u = new URL(base);
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(u.hostname)) throw new EngineError('ENGINE_NOT_LOCAL', u.hostname);
    if (!user || !pass) throw new EngineError('ENGINE_AUTH_MISSING', 'user/pass required');
    this.base = base.replace(/\/$/, '');
    Object.defineProperty(this, '_auth', { value: 'Basic ' + Buffer.from(`${user}:${pass}`).toString('base64'), enumerable: false });
  }

  async api(method, path, body) {
    const headers = { Authorization: this._auth };
    let payload;
    if (body instanceof FormData) payload = body;
    else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
    const r = await fetch(this.base + path, { method, headers, body: payload });
    const text = await r.text();
    let json = null;
    try { json = text ? JSON.parse(text) : null; } catch { /* not json */ }
    return { status: r.status, json, text: text.slice(0, 400) };
  }

  async must(method, path, body, ok = [200, 201, 204]) {
    const r = await this.api(method, path, body);
    if (!ok.includes(r.status)) throw new EngineError('ENGINE_HTTP', `${method} ${path} -> ${r.status} ${r.text}`, { status: r.status });
    return r.json;
  }

  // H1.31 §12.1 п.6: модель уходит в движок только после PASS нашего проверщика.
  async deployChecked(name, xml) {
    const g = checkGraph(xml);
    if (!g.ok) throw new EngineError('GRAPH_CHECK_FAILED', g.errs.join('; '), { errs: g.errs });
    const fd = new FormData();
    fd.append('file', new Blob([xml], { type: 'text/xml' }), name);
    return this.must('POST', '/service/repository/deployments', fd);
  }

  static vars(o) {
    return Object.entries(o).map(([name, value]) => ({
      name, value, type: typeof value === 'number' ? 'integer' : typeof value === 'boolean' ? 'boolean' : 'string',
    }));
  }

  startByMessage(message, variables, businessKey) {
    return this.must('POST', '/service/runtime/process-instances', { message, businessKey, variables: EngineClient.vars(variables) });
  }

  async acquire(topic, workerId, lockDuration = 'PT60S', n = 10) {
    return (await this.must('POST', '/external-job-api/acquire/jobs', { topic, lockDuration, numberOfTasks: n, workerId })) ?? [];
  }

  completeJob(jobId, workerId, variables = {}) {
    return this.must('POST', `/external-job-api/acquire/jobs/${jobId}/complete`, { workerId, variables: EngineClient.vars(variables) });
  }

  async executions(q) {
    const qs = new URLSearchParams({ size: '500', ...q }).toString();
    return (await this.must('GET', `/service/runtime/executions?${qs}`))?.data ?? [];
  }

  async processVars(pid) {
    const list = (await this.must('GET', `/service/runtime/process-instances/${pid}/variables`)) ?? [];
    return Object.fromEntries(list.map((v) => [v.name, v.value]));
  }

  async processInstances(q = {}) {
    const qs = new URLSearchParams({ size: '500', ...q }).toString();
    return (await this.must('GET', `/service/runtime/process-instances?${qs}`))?.data ?? [];
  }

  // Адресная доставка (§12.1 п.4): только по идентификатору исполнения, без рассылки-сигнала.
  messageToExecution(executionId, messageName) {
    return this.must('PUT', `/service/runtime/executions/${executionId}`, { action: 'messageEventReceived', messageName });
  }

  trigger(executionId, variables) {
    return this.must('PUT', `/service/runtime/executions/${executionId}`, { action: 'trigger', variables: EngineClient.vars(variables) });
  }

  async tasks(q) {
    const qs = new URLSearchParams({ size: '500', ...q }).toString();
    return (await this.must('GET', `/service/runtime/tasks?${qs}`))?.data ?? [];
  }

  completeTask(taskId, variables) {
    return this.must('POST', `/service/runtime/tasks/${taskId}`, { action: 'complete', variables: EngineClient.vars(variables) });
  }

  async historicProcess(q) {
    const qs = new URLSearchParams({ size: '500', ...q }).toString();
    return (await this.must('GET', `/service/history/historic-process-instances?${qs}`))?.data ?? [];
  }

  async history(processInstanceId) {
    const qs = new URLSearchParams({ processInstanceId, size: '2000', sort: 'startTime', order: 'asc' }).toString();
    return (await this.must('GET', `/service/history/historic-activity-instances?${qs}`))?.data ?? [];
  }

  async deployments() {
    return (await this.must('GET', '/service/repository/deployments?size=500'))?.data ?? [];
  }
}
