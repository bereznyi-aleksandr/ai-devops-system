// ДОКУМЕНТ: src/kernel.mjs
// ВЕРСИЯ: v0.9  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 02:21 +03:00 (v0.9: ChatGPT R14B RG14-01 — ActivateRules и
//   AcknowledgeReport оператора идут отдельным пулом входной роли bem_rules_gate (opts.rulesConnection /
//   opts.rulesPool), личность клиента сверяется так же, как у bem_kernel_rw; без пула — RULES_GATE_UNSET;
//   v0.8.1: RulesError из rules_error.mjs — ядро в контейнере рабочего не тянет engine/src/sshsig.mjs; v0.8: пакеты Z-RULES-01 и
//   Z-HANDOFF-01, проект v1.2 — ActivateRules (факты GitHub, git и подпись оператора собирает src/rules_gate.mjs,
//   не веря вызывающему), GetActiveRules, GetChatLease; команды аренды OpenChatLease, RecordLeaseEvidence,
//   FileLeaseReport, AcknowledgeReport, CompleteChatLease принимаются только через посредника transport.verify,
//   без него CALLER_NOT_AUTHENTICATED до базы; закрытые для RecordEvidence виды доказательств;
//   v0.7: аудит E4-6 —
//   M-E46-02 роль вызывающего обязательна всегда (флага requireRole нет), ROLE_REQUIRED до базы;
//   M-E46-01 команда ReleaseAndTransition: выпуск предмета, переход работы в RELEASED и строка outbox
//   одной транзакцией; обычный Transition в RELEASED запрещён (RELEASE_VIA_RELEASE_COMMAND); найдено при
//   проверке: доставщик падал на строке, исчерпавшей попытки (тупик пишет доказательство и требует контекст
//   заказчика и участника) — итог строки теперь пишется в своей транзакции с контекстом её заказчика и
//   автора команды, сбой одной строки не останавливает проход (DISPATCH_FINISH_FAILED); v0.6: этап 4 E4-7 — роль вызывающего сверяется
//   с машинным списком src/roles.mjs (таблица 3.1): неизвестная — ROLE_UNKNOWN, сверх канона — ROLE_FORBIDDEN;
//   при requireRole роль обязательна; v0.5: этап 4 E4-5 —
//   команда чтения GetUsage для предела попыток и расхода SR-07; записи не меняются; v0.4: аудит E3-5 —
//   M-E35-01 роль проверяется на том же клиенте в каждой транзакции и у доставщика; M-E35-05 SR-10
//   закрыт по умолчанию; v0.3: аудит Z4 M-Z4-01 — отметка
//   начала отправки несёт экземпляр среды исполнения; v0.2: Z-EXT-01 — отметка начала отправки, аудит Z2 M-Z2-02)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: BEM Control Kernel Завода — единственный писатель bem_core (H1.31 §5).
//   Пишет только через функции bem_control, ролью bem_kernel_rw, с контекстом
//   SET LOCAL app.actor_id / app.tenant_id в каждой транзакции (H1.31 §6.3).
// ОГРАНИЧЕНИЯ: назначение проверяющих, участники, заказчики, доверенности, тупик и
//   сверка неизвестного исхода — путь управления (bem_governance), не Kernel.
//   Проверку подлинности вызывающего делает транспорт; Kernel принимает уже
//   проверенного вызывающего (caller) и требует caller.actor_id === req.actor_id.

import pg from 'pg';
import { randomUUID } from 'node:crypto';
import { hostname } from 'node:os';
import { allowedFrom, STATUSES, INITIAL_STATUS } from './transitions.mjs';
import { findSecret, isStopped, stopState } from './guards.mjs';
import { authorize } from './roles.mjs';
import { RulesError } from './rules_error.mjs';

export const KERNEL_VERSION = '0.9.0';
export const KERNEL_ROLE = 'bem_kernel_rw';
// RG14-01: входная роль проверки правил — только она вызывает activate_rules и путь оператора в
// acknowledge_lease_report. Общая роль ядра включить правила и подтвердить отчёт за оператора не может.
export const RULES_GATE_ROLE = 'bem_rules_gate';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SHA256 = /^[0-9a-f]{64}$/;
const ROLE_KEY = /^0[1-9]_[^/\\]{1,60}$/;

// Виды доказательств, которые пишет только ядро внутри своих команд (проект §2.1, RG13-01, RG13-02).
export const RESERVED_EVIDENCE_KINDS = Object.freeze(['RULES_PR_MERGED', 'RULES_OPERATOR_SIGNATURE', 'RULES_ACTIVATED',
  'CHAT_LEASE_OPENED', 'CHAT_LEASE_COMPLETED', 'TASK_RESULT', 'ROLE_MEMORY', 'NEXT_STEP', 'REPORTED_UP',
  'REPORT_FILED', 'REPORT_ACKNOWLEDGED']);
// Команды аренды: личность вызывающего (заказчик, участник, роль Завода, сессия) — только от посредника.
export const TRANSPORT_COMMANDS = Object.freeze(['OpenChatLease', 'RecordLeaseEvidence', 'FileLeaseReport',
  'AcknowledgeReport', 'CompleteChatLease']);

export class KernelError extends Error {
  constructor(code, message, extra = {}) {
    super(`${code}: ${message}`);
    this.code = code;
    Object.assign(this, extra);
  }
}

// Ошибка базы → код Kernel. Текст исключения bem_control начинается с кода в верхнем регистре.
function mapDbError(err) {
  if (err instanceof KernelError) return err;
  if (err instanceof RulesError) return new KernelError(err.code, err.message);
  if (err && err.code === '42501') return new KernelError('PERMISSION_DENIED', err.message, { sqlstate: err.code });
  const m = /^([A-Z][A-Z0-9_]{3,})(?::|\b)/.exec(err?.message || '');
  if (err && err.code === '23503') return new KernelError('NOT_FOUND', 'referenced row not visible in this tenant', { sqlstate: err.code });
  if (m) return new KernelError(m[1], err.message.slice(m[0].length).trim(), { sqlstate: err.code });
  return new KernelError('DB_ERROR', err?.message || String(err), { sqlstate: err?.code });
}

function need(cond, code, msg) { if (!cond) throw new KernelError(code, msg); }
// Клиент с чужой или слишком сильной ролью уничтожается, а не возвращается в пул.
const IDENTITY_CODES = new Set(['KERNEL_WRONG_ROLE', 'KERNEL_ROLE_TOO_STRONG']);
const isIdentityError = (e) => e instanceof KernelError && IDENTITY_CODES.has(e.code);
function needUuid(v, name) { need(typeof v === 'string' && UUID.test(v), 'BAD_REQUEST', `${name} must be uuid`); }

export class Kernel {
  // opts: { pool?, connection?, stopFile?, log? }
  constructor(opts = {}) {
    this.pool = opts.pool || new pg.Pool({ ...(opts.connection || {}), user: KERNEL_ROLE, max: opts.max || 5 });
    // RG14-01: отдельный пул bem_rules_gate. Его вход выдаётся только изолированной проверке правил; без него
    // ActivateRules и подтверждение отчёта оператором — RULES_GATE_UNSET.
    this.rulesPool = opts.rulesPool || (opts.rulesConnection
      ? new pg.Pool({ ...opts.rulesConnection, user: RULES_GATE_ROLE, max: 2 }) : null);
    this.stopFile = opts.stopFile || null;
    // M-E46-02: роль вызывающего обязательна всегда; отключить проверку нельзя (opts.requireRole не читается).
    this.log = opts.log || (() => {});
    // Z-RULES-01: проверки правил (src/rules_gate.mjs createRulesGate). Без них ActivateRules — RULES_GATE_UNSET.
    this.rules = opts.rules || null;
    // Z-HANDOFF-01: посредник { verify(req) -> { tenant_id, actor_id, role_key, session } }. Местные входы его не
    // имеют, поэтому команды аренды у них закрыты (проект §3.2).
    this.transport = opts.transport || null;
    // Только для теста перезапуска E3-3: вызывается внутри транзакции перед COMMIT.
    this._beforeCommit = typeof opts.testBeforeCommit === 'function' ? opts.testBeforeCommit : null;
    this.startedAt = new Date().toISOString();
    this.runtimeInstance = `process:${hostname()}:${process.pid}:${randomUUID()}`;
    this.lastCommandAt = null;
    this.counters = { ok: 0, rejected: 0 };
  }

  // E3-1: Kernel работает только ролью bem_kernel_rw без SUPERUSER/BYPASSRLS/CREATEROLE.
  // Аудит E3-5 M-E35-01: проверка идёт на том самом клиенте, которым выполняется работа, —
  // в каждой транзакции команды и в каждом проходе доставщика, а не один раз при старте.
  // Подменённый или неверно настроенный пул (вход postgres, SET ROLE на владельца) даёт отказ
  // до первого изменения данных.
  async _assertClientIdentity(client, role = KERNEL_ROLE) {
    const { rows } = await client.query(
      `SELECT current_user AS cu, session_user AS su, r.rolsuper, r.rolbypassrls, r.rolcreaterole
         FROM pg_roles r WHERE r.rolname = session_user`);
    const r = rows[0];
    if (!r || r.cu !== role || r.su !== role) {
      throw new KernelError('KERNEL_WRONG_ROLE', `connected as ${r?.su}/${r?.cu}, need ${role}`);
    }
    if (r.rolsuper || r.rolbypassrls || r.rolcreaterole) {
      throw new KernelError('KERNEL_ROLE_TOO_STRONG', `${role} has elevated attributes`);
    }
  }

  // Проверенный клиент на время fn; сломанный клиент в пул не возвращается.
  async _withClient(fn) {
    const client = await this.pool.connect();
    let broken = false;
    try {
      await this._assertClientIdentity(client);
      return await fn(client);
    } catch (e) {
      broken = isIdentityError(e);
      throw e;
    } finally {
      client.release(broken);
    }
  }

  async assertIdentity() {
    return this._withClient(async (client) => {
      // Без расширения Z-EXT-01 доставщик не может отметить начало отправки — работать нельзя.
      const ext = await client.query(
        "SELECT to_regprocedure('bem_control.mark_outbox_send_started(uuid,bigint,text,text)') IS NOT NULL AS ok");
      if (!ext.rows[0].ok) throw new KernelError('KERNEL_EXT_MISSING', 'Z-EXT-01 not installed');
      return true;
    });
  }

  async close() { await this.pool.end(); if (this.rulesPool) await this.rulesPool.end(); }

  health() {
    return {
      service: 'zavod-kernel', version: KERNEL_VERSION, started_at: this.startedAt,
      last_command_at: this.lastCommandAt, stopped: isStopped(this.stopFile),
      stop_reason: stopState(this.stopFile).reason,
      counters: { ...this.counters },
    };
  }

  // Одна транзакция = один контекст. set_config(..., true) — это SET LOCAL.
  // M-E35-01: роль сверяется на этом же клиенте сразу после BEGIN, до контекста и обработчика.
  // gate = true: клиент пула bem_rules_gate (RG14-01), личность сверяется с этой ролью.
  async _tx(actorId, tenantId, fn, gate = false) {
    need(!gate || this.rulesPool, 'RULES_GATE_UNSET', 'kernel has no rules gate connection');
    const client = await (gate ? this.rulesPool : this.pool).connect();
    let broken = false;
    try {
      await client.query('BEGIN');
      await this._assertClientIdentity(client, gate ? RULES_GATE_ROLE : KERNEL_ROLE);
      await client.query(`SELECT set_config('app.actor_id', $1, true), set_config('app.tenant_id', $2, true)`,
        [actorId, tenantId ?? '']);
      const out = await fn(client);
      if (this._beforeCommit) await this._beforeCommit(out);
      await client.query('COMMIT');
      return out;
    } catch (e) {
      try { await client.query('ROLLBACK'); } catch { broken = true; }
      if (isIdentityError(e)) broken = true;
      throw e;
    } finally {
      client.release(broken);
    }
  }

  // Главный вход. caller — уже проверенный транспортом вызывающий: { actor_id }.
  // req — CommandRequest: { type, actor_id, tenant_id, command_id?, payload }.
  async execute(caller, req) {
    try {
      need(req && typeof req === 'object', 'BAD_REQUEST', 'request must be object');
      const ss = stopState(this.stopFile);
      need(!ss.stopped, 'KERNEL_STOPPED', `SR-10 ${ss.reason}`);
      if (TRANSPORT_COMMANDS.includes(req.type)) return await this._executeVerified(req);
      need(caller && typeof caller.actor_id === 'string', 'UNAUTHENTICATED', 'no caller');
      need(caller.actor_id === req.actor_id, 'ACTOR_MISMATCH', 'caller differs from request actor');
      need(typeof caller.role === 'string' && caller.role.length > 0, 'ROLE_REQUIRED', 'caller role required');
      try { authorize(caller.role, req.type); } catch (e) { throw new KernelError(e.code, e.message.replace(/^[A-Z_]+: /, '')); }
      needUuid(req.tenant_id, 'tenant_id');
      const secret = findSecret(req);
      need(!secret, 'SECRET_IN_REQUEST', `pattern ${secret} (value not logged, SR-01)`);
      const handler = HANDLERS[req.type];
      need(handler, 'UNKNOWN_COMMAND', String(req.type));
      const p = req.payload || {};
      const result = await this._tx(req.actor_id, req.tenant_id, (c) => handler(c, req, p, this),
        req.type === 'ActivateRules');
      this.counters.ok += 1;
      this.lastCommandAt = new Date().toISOString();
      this.log({ ev: 'command_ok', type: req.type, actor: req.actor_id, tenant: req.tenant_id });
      return { ok: true, result };
    } catch (e) {
      const err = mapDbError(e);
      this.counters.rejected += 1;
      this.log({ ev: 'command_rejected', type: req?.type, code: err.code });
      return { ok: false, error: { code: err.code, message: err.message } };
    }
  }

  // Команда аренды (проект §3.2): заказчик, участник, роль Завода и сессия — из посредника, а не из запроса.
  async _executeVerified(req) {
    try {
      need(this.transport && typeof this.transport.verify === 'function', 'CALLER_NOT_AUTHENTICATED', 'no transport');
      let v;
      try { v = await this.transport.verify(req); } catch { v = null; }
      need(v && typeof v.tenant_id === 'string' && UUID.test(v.tenant_id) && typeof v.actor_id === 'string'
        && v.actor_id.length > 0 && typeof v.role_key === 'string' && (ROLE_KEY.test(v.role_key) || v.role_key === 'OPERATOR')
        && typeof v.session === 'string' && v.session.trim().length > 0, 'CALLER_NOT_AUTHENTICATED', 'transport refused');
      const secret = findSecret(req);
      need(!secret, 'SECRET_IN_REQUEST', `pattern ${secret} (value not logged, SR-01)`);
      const verified = Object.freeze({ tenant_id: v.tenant_id, actor_id: v.actor_id, role_key: v.role_key,
        session: v.session });
      const vreq = { type: req.type, tenant_id: verified.tenant_id, actor_id: verified.actor_id,
        command_id: req.command_id, payload: req.payload || {}, verified };
      const result = await this._tx(vreq.actor_id, vreq.tenant_id, (c) => HANDLERS[req.type](c, vreq, vreq.payload, this),
        req.type === 'AcknowledgeReport' && verified.role_key === 'OPERATOR');
      this.counters.ok += 1;
      this.lastCommandAt = new Date().toISOString();
      this.log({ ev: 'command_ok', type: req.type, actor: vreq.actor_id, tenant: vreq.tenant_id });
      return { ok: true, result };
    } catch (e) {
      const err = mapDbError(e);
      this.counters.rejected += 1;
      this.log({ ev: 'command_rejected', type: req?.type, code: err.code });
      return { ok: false, error: { code: err.code, message: err.message } };
    }
  }

  // Доставщик (H1.31 §7.4): внутренний модуль Kernel, то же подключение.
  // egress(row) — внешний исполнитель без доступа к базе; возвращает { outcome, detail }.
  // runtimeInstance (M-Z4-01) — экземпляр среды исполнения этой попытки. Под надзирателем
  // (src/fencer.mjs) его задаёт надзиратель через ZAVOD_RUNTIME_INSTANCE, по одному на попытку.
  // Без надзирателя — экземпляр этого процесса; такой экземпляр надзиратель не знает и оградить
  // не может, поэтому неясный исход такой строки обратно в очередь не вернётся (только UNRESOLVED).
  async dispatchOnce(egress, { limit = 10, lease = '60 seconds', worker = 'kernel-dispatcher',
    runtimeInstance = process.env.ZAVOD_RUNTIME_INSTANCE || this.runtimeInstance } = {}) {
    const ss = stopState(this.stopFile);
    if (ss.stopped) return { stopped: true, stop_reason: ss.reason, claimed: 0 };
    // M-E35-01: весь проход — одна проверенная сессия bem_kernel_rw (захват, отметка, итог).
    return this._withClient((db) => this._dispatchWith(db, egress, { limit, lease, worker, runtimeInstance }));
  }

  async _dispatchWith(db, egress, { limit, lease, worker, runtimeInstance }) {
    const { rows } = await db.query('SELECT * FROM bem_control.claim_outbox_batch($1, $2::interval, $3)',
      [limit, lease, worker]);
    const results = [];
    for (const row of rows) {
      // Z-EXT-01: отметка начала отправки ДО внешнего вызова. Не удалась (аренда
      // потеряна) — не отправлять: строкой уже распоряжается другой исполнитель или сверка.
      const mark = await db.query('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok',
        [row.outbox_id, row.lease_epoch, worker, runtimeInstance]);
      if (!mark.rows[0].ok) {
        results.push({ outbox_id: row.outbox_id, outcome: 'NOT_SENT_LEASE_LOST', finished: false });
        continue;
      }
      let outcome = 'UNKNOWN_OUTCOME';
      let detail = {};
      try {
        const r = await egress(row);
        outcome = r?.outcome || 'UNKNOWN_OUTCOME';
        detail = r?.detail || {};
      } catch (e) {
        outcome = 'UNKNOWN_OUTCOME';   // H1.31 §7.1: неоднозначный исход не повторяется сам
        detail = { error: String(e?.message || e).slice(0, 200) };
      }
      if (findSecret(detail)) detail = { redacted: 'SECRET_IN_EGRESS_DETAIL' };
      try {
        const finished = await this._finishRow(db, row, worker, outcome, detail);
        results.push({ outbox_id: row.outbox_id, outcome, finished });
      } catch (e) {
        // Сбой записи итога одной строки не останавливает проход. Строка остаётся LEASED с отметкой
        // начала отправки; по истечении аренды она уходит в UNKNOWN_OUTCOME и сама не повторяется.
        if (isIdentityError(e)) throw e;
        const err = mapDbError(e);
        this.log({ ev: 'dispatch_finish_failed', outbox_id: row.outbox_id, code: err.code });
        results.push({ outbox_id: row.outbox_id, outcome, finished: false, error: 'DISPATCH_FINISH_FAILED',
          cause: err.code });
      }
    }
    return { stopped: false, claimed: rows.length, results };
  }

  // Итог строки — своя транзакция с контекстом её заказчика и автора команды, создавшей строку
  // (command_log.outbox_id). Нужен для тупика: finish_outbox_row пишет доказательство OUTBOX_DEAD_LETTER,
  // а запись доказательства требует заказчика и участника (H1.31 evidence_write, current_actor_checked).
  async _finishRow(db, row, worker, outcome, detail) {
    await db.query('BEGIN');
    try {
      await db.query("SELECT set_config('app.tenant_id', $1, true)", [row.tenant_id]);
      const a = await db.query('SELECT actor_id FROM bem_core.command_log WHERE outbox_id = $1 AND tenant_id = $2',
        [row.outbox_id, row.tenant_id]);
      if (a.rows.length === 1) await db.query("SELECT set_config('app.actor_id', $1, true)", [a.rows[0].actor_id]);
      const fin = await db.query('SELECT bem_control.finish_outbox_row($1, $2, $3, $4, $5) AS ok',
        [row.outbox_id, row.lease_epoch, worker, outcome, detail]);
      await db.query('COMMIT');
      return fin.rows[0].ok;
    } catch (e) {
      await db.query('ROLLBACK');
      throw e;
    }
  }
}

const HANDLERS = {
  async CreateWorkItem(c, req, p) {
    needUuid(p.work_item_id, 'work_item_id');
    need(p.evidence && typeof p.evidence === 'object', 'BAD_REQUEST', 'evidence required');
    const { rows } = await c.query('SELECT bem_control.create_work_item($1, $2, $3, $4, $5) AS id',
      [req.tenant_id, p.work_item_id, INITIAL_STATUS, p.criticality || 'NORMAL', p.evidence]);
    return { work_item_id: rows[0].id, status: INITIAL_STATUS, revision: 1 };
  },

  async Transition(c, req, p) {
    needUuid(req.command_id, 'command_id');
    needUuid(p.work_item_id, 'work_item_id');
    need(Number.isInteger(p.expected_revision) && p.expected_revision > 0, 'BAD_REQUEST', 'expected_revision');
    need(STATUSES.includes(p.new_status), 'UNKNOWN_STATUS', String(p.new_status));
    // M-E46-01: в RELEASED ведёт только ReleaseAndTransition — без выпуска предмета перехода нет.
    need(p.new_status !== 'RELEASED', 'RELEASE_VIA_RELEASE_COMMAND', 'use ReleaseAndTransition');
    const from = allowedFrom(p.new_status);
    need(from.length > 0, 'TRANSITION_NOT_ALLOWED', `nothing leads to ${p.new_status}`);
    need(p.evidence && typeof p.evidence === 'object', 'BAD_REQUEST', 'evidence required');
    const hasOutbox = Boolean(p.outbox_kind);
    const { rows } = await c.query(
      'SELECT * FROM bem_control.apply_transition($1, $2, $3, $4, $5, $6, $7, $8, $9)',
      [req.tenant_id, p.work_item_id, p.expected_revision, from, p.new_status, req.command_id,
        hasOutbox ? p.outbox_kind : null, hasOutbox ? (p.outbox_payload || {}) : null, p.evidence]);
    const r = rows[0];
    return { work_item_id: r.work_item_id, new_revision: r.new_revision, outbox_id: r.outbox_id };
  },

  async RecordEvidence(c, req, p) {
    need(typeof p.kind === 'string' && /^[A-Z][A-Z0-9_]{2,63}$/.test(p.kind), 'BAD_REQUEST', 'kind');
    need(!p.kind.startsWith('OPERATOR_'), 'RESERVED_KIND', 'use OperatorDecision');
    need(!RESERVED_EVIDENCE_KINDS.includes(p.kind), 'RESERVED_KIND', `${p.kind} is written by kernel commands only`);
    const { rows } = await c.query('SELECT bem_control.record_evidence($1, $2, $3) AS id',
      [req.tenant_id, p.kind, p.payload || {}]);
    return { evidence_id: rows[0].id };
  },

  // SR-11: решение оператора — запись Evidence с автором-человеком.
  async OperatorDecision(c, req, p) {
    need(/^human:/.test(req.actor_id), 'OPERATOR_MUST_BE_HUMAN', req.actor_id);
    need(typeof p.decision_code === 'string' && p.decision_code.length > 0, 'BAD_REQUEST', 'decision_code');
    const { rows: who } = await c.query(
      `SELECT a.provider::text AS provider FROM bem_control.current_actor_checked($1) x
         JOIN bem_core.actor a ON a.actor_id = x.out_actor_id`, [req.tenant_id]);
    need(who[0]?.provider === 'human', 'OPERATOR_MUST_BE_HUMAN', 'actor provider is not human');
    const { rows } = await c.query('SELECT bem_control.record_evidence($1, $2, $3) AS id',
      [req.tenant_id, 'OPERATOR_DECISION', { decision_code: p.decision_code, decision: p.decision ?? null,
        note: p.note ?? null }]);
    return { evidence_id: rows[0].id };
  },

  async PublishSubject(c, req, p) {
    needUuid(p.subject_id, 'subject_id');
    needUuid(p.work_item_id, 'work_item_id');
    need(Array.isArray(p.authors) && p.authors.length > 0, 'BAD_REQUEST', 'authors');
    const { rows } = await c.query('SELECT bem_control.publish_subject($1, $2, $3, $4, $5, $6, $7, $8) AS ok',
      [req.tenant_id, p.subject_id, p.work_item_id, p.head_sha, p.criticality || 'NORMAL',
        p.scope || 'WORKING', p.authors, p.evidence || {}]);
    return { published: rows[0].ok };
  },

  async RecordVerdict(c, req, p) {
    needUuid(p.subject_id, 'subject_id');
    need(['ACCEPT', 'REVISE', 'REJECT', 'BLOCKED'].includes(p.verdict), 'BAD_REQUEST', 'verdict');
    const { rows } = await c.query('SELECT bem_control.record_audit_verdict($1, $2, $3, $4, $5) AS id',
      [req.tenant_id, p.subject_id, p.head_sha, p.verdict, p.evidence || null]);
    return { audit_record_id: rows[0].id };
  },

  async ReleaseSubject(c, req, p) {
    needUuid(p.subject_id, 'subject_id');
    const { rows } = await c.query('SELECT bem_control.release_subject($1, $2, $3) AS ok',
      [req.tenant_id, p.subject_id, p.head_sha]);
    return { released: rows[0].ok };
  },

  // M-E46-01 (§12.2 узел 17): выпуск предмета, переход работы в RELEASED и строка outbox — одна
  // транзакция _tx: либо всё, либо ничего. Предмет обязан принадлежать этой работе. Повтор с тем же
  // command_id — честный повтор apply_transition: та же строка outbox, второй не появляется.
  // Предмет, выпущенный раньше другой командой, этой командой не «довыпускается» — ALREADY_RELEASED.
  async ReleaseAndTransition(c, req, p) {
    needUuid(req.command_id, 'command_id');
    needUuid(p.work_item_id, 'work_item_id');
    needUuid(p.subject_id, 'subject_id');
    need(typeof p.head_sha === 'string' && p.head_sha.length > 0, 'BAD_REQUEST', 'head_sha');
    need(Number.isInteger(p.expected_revision) && p.expected_revision > 0, 'BAD_REQUEST', 'expected_revision');
    need(typeof p.outbox_kind === 'string' && p.outbox_kind.length > 0, 'BAD_REQUEST', 'outbox_kind required');
    need(p.evidence && typeof p.evidence === 'object', 'BAD_REQUEST', 'evidence required');
    const s = await c.query('SELECT work_item_id FROM bem_core.subject WHERE id = $1 AND tenant_id = $2',
      [p.subject_id, req.tenant_id]);
    need(s.rows.length === 1, 'NOT_FOUND', 'subject not visible');
    need(s.rows[0].work_item_id === p.work_item_id, 'SUBJECT_WORK_MISMATCH', 'subject belongs to another work item');
    const prev = await c.query('SELECT 1 FROM bem_core.command_log WHERE command_id = $1', [req.command_id]);
    const replay = prev.rows.length === 1;
    const rel = await c.query('SELECT bem_control.release_subject($1, $2, $3) AS ok',
      [req.tenant_id, p.subject_id, p.head_sha]);
    need(rel.rows[0].ok === true || replay, 'ALREADY_RELEASED', 'subject released outside this command');
    const { rows } = await c.query(
      'SELECT * FROM bem_control.apply_transition($1, $2, $3, $4, $5, $6, $7, $8, $9)',
      [req.tenant_id, p.work_item_id, p.expected_revision, allowedFrom('RELEASED'), 'RELEASED', req.command_id,
        p.outbox_kind, p.outbox_payload || {}, p.evidence]);
    const r = rows[0];
    return { released: rel.rows[0].ok === true, replay, work_item_id: r.work_item_id, new_revision: r.new_revision,
      outbox_id: r.outbox_id };
  },

  // Журнал расхода (H1.31 §16; SR-07 на этапе 4 читает его для предела).
  async RecordUsage(c, req, p) {
    needUuid(p.work_item_id, 'work_item_id');
    const { rows } = await c.query(
      'SELECT bem_control.record_usage($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) AS id',
      [req.tenant_id, p.work_item_id, p.attempt_no ?? 1, p.provider, p.model, p.input_tokens ?? 0,
        p.output_tokens ?? 0, p.cached_tokens ?? 0, p.tool_overhead ?? 0, p.context_estimate ?? 0,
        p.context_limit ?? 0, p.measured_by || 'LOCAL_ESTIMATE', p.outcome || 'OK']);
    return { usage_id: rows[0].id };
  },

  // SR-07 (этап 4, E4-5): сводка расхода по работе — попытки, неудачные попытки, токены.
  // Только чтение; заказчик сверяется явно и через видимость работы (H1.31 §8.2).
  async GetUsage(c, req, p) {
    needUuid(p.work_item_id, 'work_item_id');
    const wi = await c.query('SELECT 1 FROM bem_core.work_item WHERE id = $1 AND tenant_id = $2', [p.work_item_id, req.tenant_id]);
    need(wi.rows.length === 1, 'NOT_FOUND', 'work item not visible');
    const { rows } = await c.query(
      `SELECT count(*)::int AS attempts,
              count(*) FILTER (WHERE outcome <> 'OK')::int AS failed,
              coalesce(sum(coalesce(input_tokens, 0) + coalesce(output_tokens, 0)), 0)::bigint AS tokens,
              coalesce(max(attempt_no), 0)::int AS last_attempt
         FROM bem_core.usage_record WHERE work_item_id = $1 AND tenant_id = $2`, [p.work_item_id, req.tenant_id]);
    return { ...rows[0], tokens: Number(rows[0].tokens) };
  },

  async GetWorkItem(c, req, p) {
    needUuid(p.work_item_id, 'work_item_id');
    const { rows } = await c.query(
      'SELECT id, status, revision, criticality FROM bem_core.work_item WHERE id = $1', [p.work_item_id]);
    need(rows.length === 1, 'NOT_FOUND', 'work item not visible');   // H1.31 §8.2
    return rows[0];
  },

  // Z-RULES-01 (проект §3.1): включение версии правил. Заявленная роль ничего не даёт: факты GitHub, git и
  // подпись оператора ядро собирает само (src/rules_gate.mjs), база сверяет их ещё раз и проверяет выпуск.
  async ActivateRules(c, req, p, k) {
    need(k.rules && typeof k.rules.collectActivation === 'function', 'RULES_GATE_UNSET', 'kernel has no rules gate');
    needUuid(p.subject_id, 'subject_id');
    need(Number.isInteger(p.pr_number) && p.pr_number > 0, 'BAD_REQUEST', 'pr_number');
    need(typeof p.ticket === 'string' && typeof p.signature === 'string', 'BAD_REQUEST', 'ticket and signature');
    const active = await activeRulesCommit(c, req.tenant_id);
    const f = k.rules.collectActivation({ tenantId: req.tenant_id, prNumber: p.pr_number, subjectId: p.subject_id,
      ticketText: p.ticket, signature: p.signature, activeRulesCommit: active });
    const { rows } = await c.query('SELECT bem_control.activate_rules($1, $2, $3, $4, $5, $6, $7, $8, $9) AS id',
      [req.tenant_id, f.commit, f.head_sha, f.pr_number, f.registry_digest, p.subject_id, f.role_parents,
        f.github, f.signature]);
    return { activation_evidence_id: rows[0].id, rules_commit: f.commit, registry_digest: f.registry_digest,
      previous_rules_commit: active };
  },

  async GetActiveRules(c, req) {
    const { rows } = await c.query(
      `SELECT rules_commit, registry_digest, role_parents, pr_number, pr_url, subject_id, head_sha, key_fingerprint,
              activation_evidence_id, activated_at
         FROM bem_control.rules_activation WHERE tenant_id = $1 AND superseded_at IS NULL`, [req.tenant_id]);
    need(rows.length === 1, 'RULES_NOT_ACTIVE', 'no active rules for tenant');
    return rows[0];
  },

  // Аренда по номеру или последняя аренда роли; только этого заказчика.
  async GetChatLease(c, req, p) {
    const cols = `lease_id, role_key, chat_number, generation, work_item_id, holder_session, rules_commit, code_commit,
                  status, opened_at, closed_at, completion_evidence_id, result_evidence_id, memory_evidence_id,
                  next_evidence_id, report_id`;
    let rows;
    if (p.lease_id !== undefined) {
      needUuid(p.lease_id, 'lease_id');
      ({ rows } = await c.query(`SELECT ${cols} FROM bem_control.chat_lease WHERE tenant_id = $1 AND lease_id = $2`,
        [req.tenant_id, p.lease_id]));
    } else {
      need(typeof p.role_key === 'string' && ROLE_KEY.test(p.role_key), 'BAD_REQUEST', 'lease_id or role_key');
      ({ rows } = await c.query(`SELECT ${cols} FROM bem_control.chat_lease WHERE tenant_id = $1 AND role_key = $2
                                  ORDER BY generation DESC LIMIT 1`, [req.tenant_id, p.role_key]));
    }
    need(rows.length === 1, 'NOT_FOUND', 'lease not visible');
    return rows[0];
  },

  // Команды аренды (проект §3.2): вызываются только из _executeVerified; req.verified — от посредника.
  async OpenChatLease(c, req, p, k) {
    need(k.rules && typeof k.rules.checkWorkingCopy === 'function', 'RULES_GATE_UNSET', 'kernel has no rules gate');
    needUuid(p.work_item_id, 'work_item_id');
    const v = req.verified;
    need(v.role_key !== 'OPERATOR', 'LEASE_BAD_ROLE', 'operator holds no chat lease');
    const active = await activeRulesCommit(c, req.tenant_id);
    need(active, 'LEASE_NO_ACTIVE_RULES', 'no active rules for tenant');
    const gate = k.rules.checkWorkingCopy(active);   // Л.8: проверка перед арендой
    const { rows } = await c.query('SELECT * FROM bem_control.open_chat_lease($1, $2, $3, $4, $5, $6)',
      [req.tenant_id, v.role_key, p.work_item_id, v.session, gate.code_commit, gate.rules_commit]);
    const r = rows[0];
    return { lease_id: r.out_lease_id, generation: r.out_generation, chat_number: r.out_chat_number,
      rules_commit: r.out_rules_commit, code_commit: gate.code_commit };
  },

  async RecordLeaseEvidence(c, req, p) {
    needUuid(p.lease_id, 'lease_id');
    need(Number.isInteger(p.generation) && p.generation > 0, 'BAD_REQUEST', 'generation');
    need(['TASK_RESULT', 'ROLE_MEMORY', 'NEXT_STEP'].includes(p.kind), 'LEASE_EVIDENCE_BAD_KIND', String(p.kind));
    need(typeof p.content_sha256 === 'string' && SHA256.test(p.content_sha256), 'BAD_REQUEST', 'content_sha256');
    need(p.payload === undefined || (p.payload && typeof p.payload === 'object' && !Array.isArray(p.payload)),
      'BAD_REQUEST', 'payload');
    const { rows } = await c.query('SELECT bem_control.record_lease_evidence($1, $2, $3, $4, $5, $6, $7) AS id',
      [req.tenant_id, p.lease_id, p.generation, req.verified.session, p.kind, p.content_sha256, p.payload || {}]);
    return { evidence_id: rows[0].id };
  },

  async FileLeaseReport(c, req, p) {
    needUuid(p.lease_id, 'lease_id');
    need(Number.isInteger(p.generation) && p.generation > 0, 'BAD_REQUEST', 'generation');
    need(typeof p.report_sha256 === 'string' && SHA256.test(p.report_sha256), 'BAD_REQUEST', 'report_sha256');
    const { rows } = await c.query('SELECT bem_control.file_lease_report($1, $2, $3, $4, $5) AS id',
      [req.tenant_id, p.lease_id, p.generation, req.verified.session, p.report_sha256]);
    return { report_id: rows[0].id };
  },

  // Адресат-роль подтверждает своей проверенной сессией; адресат-оператор — подписью билета с телефона.
  async AcknowledgeReport(c, req, p, k) {
    needUuid(p.report_id, 'report_id');
    need(typeof p.report_sha256 === 'string' && SHA256.test(p.report_sha256), 'BAD_REQUEST', 'report_sha256');
    const v = req.verified;
    let sig = null;
    let session = v.session;
    if (v.role_key === 'OPERATOR') {
      need(k.rules && typeof k.rules.verifyReportAck === 'function', 'RULES_GATE_UNSET', 'kernel has no rules gate');
      sig = k.rules.verifyReportAck({ tenantId: req.tenant_id, reportId: p.report_id, reportSha256: p.report_sha256,
        ticketText: p.ticket, signature: p.signature, activeRulesCommit: await activeRulesCommit(c, req.tenant_id) });
      session = 'OPERATOR';
    }
    const { rows } = await c.query('SELECT bem_control.acknowledge_lease_report($1, $2, $3, $4, $5, $6) AS id',
      [req.tenant_id, p.report_id, p.report_sha256, v.role_key, session, sig]);
    return { ack_evidence_id: rows[0].id };
  },

  async CompleteChatLease(c, req, p) {
    needUuid(p.lease_id, 'lease_id');
    need(Number.isInteger(p.generation) && p.generation > 0, 'BAD_REQUEST', 'generation');
    for (const f of ['result_evidence_id', 'memory_evidence_id', 'next_evidence_id', 'report_id']) needUuid(p[f], f);
    const { rows } = await c.query('SELECT bem_control.complete_chat_lease($1, $2, $3, $4, $5, $6, $7, $8) AS id',
      [req.tenant_id, p.lease_id, p.generation, req.verified.session, p.result_evidence_id, p.memory_evidence_id,
        p.next_evidence_id, p.report_id]);
    return { receipt: rows[0].id };
  },
};

async function activeRulesCommit(c, tenantId) {
  const { rows } = await c.query(
    'SELECT rules_commit FROM bem_control.rules_activation WHERE tenant_id = $1 AND superseded_at IS NULL', [tenantId]);
  return rows[0]?.rules_commit ?? null;
}

export const COMMAND_TYPES = Object.freeze(Object.keys(HANDLERS));
