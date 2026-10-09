// ДОКУМЕНТ: src/kernel.mjs
// ВЕРСИЯ: v0.5  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 06:20 +03:00 (v0.5: этап 4 E4-5 —
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

export const KERNEL_VERSION = '0.5.0';
export const KERNEL_ROLE = 'bem_kernel_rw';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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
    this.stopFile = opts.stopFile || null;
    this.log = opts.log || (() => {});
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
  async _assertClientIdentity(client) {
    const { rows } = await client.query(
      `SELECT current_user AS cu, session_user AS su, r.rolsuper, r.rolbypassrls, r.rolcreaterole
         FROM pg_roles r WHERE r.rolname = session_user`);
    const r = rows[0];
    if (!r || r.cu !== KERNEL_ROLE || r.su !== KERNEL_ROLE) {
      throw new KernelError('KERNEL_WRONG_ROLE', `connected as ${r?.su}/${r?.cu}, need ${KERNEL_ROLE}`);
    }
    if (r.rolsuper || r.rolbypassrls || r.rolcreaterole) {
      throw new KernelError('KERNEL_ROLE_TOO_STRONG', `${KERNEL_ROLE} has elevated attributes`);
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

  async close() { await this.pool.end(); }

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
  async _tx(actorId, tenantId, fn) {
    const client = await this.pool.connect();
    let broken = false;
    try {
      await client.query('BEGIN');
      await this._assertClientIdentity(client);
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
      need(caller && typeof caller.actor_id === 'string', 'UNAUTHENTICATED', 'no caller');
      need(caller.actor_id === req.actor_id, 'ACTOR_MISMATCH', 'caller differs from request actor');
      needUuid(req.tenant_id, 'tenant_id');
      const secret = findSecret(req);
      need(!secret, 'SECRET_IN_REQUEST', `pattern ${secret} (value not logged, SR-01)`);
      const handler = HANDLERS[req.type];
      need(handler, 'UNKNOWN_COMMAND', String(req.type));
      const p = req.payload || {};
      const result = await this._tx(req.actor_id, req.tenant_id, (c) => handler(c, req, p));
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
      const fin = await db.query('SELECT bem_control.finish_outbox_row($1, $2, $3, $4, $5) AS ok',
        [row.outbox_id, row.lease_epoch, worker, outcome, detail]);
      results.push({ outbox_id: row.outbox_id, outcome, finished: fin.rows[0].ok });
    }
    return { stopped: false, claimed: rows.length, results };
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
};

export const COMMAND_TYPES = Object.freeze(Object.keys(HANDLERS));
