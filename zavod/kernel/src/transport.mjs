// ДОКУМЕНТ: src/transport.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 10:30 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 10:30 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: посредник Z-TRANSPORT-01 (проект v0.4 §3.1–§3.3) между местным входом и ядром.
//   handle(body) — разбор запроса входа: EnrollSession (получение пропуска по одноразовому коду) или команда аренды.
//   verify(req) — для ядра: заказчик, участник, роль и сессия из записи пропуска в базе, не из запроса.
//   auth из запроса убирается до ядра; пропуск и код в базе — только SHA-256 сырых 32 байт; в журнал не пишутся.
// ОГРАНИЧЕНИЯ: оператор пропуска не имеет — его команды (подтверждение отчёта, выдача роли под оператором, отзыв)
//   несут подписанный билет, подпись проверяет ядро (src/rules_gate.mjs), запись — пул bem_rules_gate.

import { createHash, randomBytes } from 'node:crypto';
import { TRANSPORT_COMMANDS } from './kernel.mjs';

const HEX64 = /^[0-9a-f]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const OPERATOR_TYPES = Object.freeze(['AcknowledgeReport', 'PrepareEnrollment', 'RevokeSession']);
const BODY_KEYS = new Set(['type', 'command_id', 'payload', 'auth']);

// SHA-256 сырых байт секрета, заданного 64 шестнадцатеричными знаками (32 байта).
export const secretHash = (hex) => createHash('sha256').update(Buffer.from(hex, 'hex')).digest('hex');
export const newSecret = () => randomBytes(32).toString('hex');

const validSession = (s) => typeof s === 'string' && s.trim().length > 0 && s.length <= 200 && s !== 'OPERATOR';

export function createTransport({ kernel, log = () => {} }) {
  const auths = new WeakMap();

  // Одна короткая транзакция на проверенном клиенте ядра (роль bem_kernel_rw сверяется до запроса).
  async function tx(sql, args) {
    return kernel._withClient(async (c) => {
      await c.query('BEGIN');
      try {
        const { rows } = await c.query(sql, args);
        await c.query('COMMIT');
        return rows;
      } catch (e) {
        try { await c.query('ROLLBACK'); } catch { /* клиент сломан — пул его не вернёт */ }
        throw e;
      }
    });
  }

  // Ядру — запрос без auth; auth живёт только в WeakMap посредника.
  function accept(body) {
    const req = Object.freeze({ type: body.type, command_id: body.command_id, payload: body.payload || {} });
    auths.set(req, body.auth);
    return req;
  }

  async function verify(req) {
    const auth = auths.get(req);
    if (!auth || typeof auth !== 'object') return null;
    if (auth.operator === true && Object.keys(auth).length === 1) {
      // Билет оператора: личность «оператор заказчика»; подпись билета проверит обработчик ядра.
      if (!OPERATOR_TYPES.includes(req.type)) return null;
      const tenant = req.payload.tenant_id;
      if (typeof tenant !== 'string' || !UUID.test(tenant)) return null;
      const rows = await tx("SELECT actor_id FROM bem_control.role_actor WHERE tenant_id = $1 AND role_key = 'OPERATOR'",
        [tenant]);
      if (!rows[0]) return null;
      return { tenant_id: tenant, actor_id: rows[0].actor_id, role_key: 'OPERATOR', session: 'OPERATOR' };
    }
    if (Object.keys(auth).length !== 2 || !validSession(auth.session) || typeof auth.pass !== 'string'
      || !HEX64.test(auth.pass)) return null;
    const rows = await tx('SELECT * FROM bem_control.lookup_session_credential($1, $2)', [auth.session, secretHash(auth.pass)]);
    const r = rows[0];
    if (!r || r.out_code !== 'OK') { log({ ev: 'pass_refused', code: r?.out_code || 'PASS_UNKNOWN' }); return null; }
    return { tenant_id: r.out_tenant_id, actor_id: r.out_actor_id, role_key: r.out_role_key, session: r.out_session };
  }

  // Получение пропуска (§3.1 шаг 2). Пропуск отдаётся один раз; в базе — только его SHA-256.
  async function enroll(payload) {
    if (!payload || typeof payload !== 'object' || Object.keys(payload).length !== 2 || !validSession(payload.session)
      || typeof payload.claim_code !== 'string' || !HEX64.test(payload.claim_code)) {
      return { ok: false, error: { code: 'ENROLL_BAD_REQUEST' } };
    }
    const pass = newSecret();
    const rows = await tx('SELECT * FROM bem_control.claim_session_enrollment($1, $2, $3)',
      [payload.session, secretHash(payload.claim_code), secretHash(pass)]);
    const r = rows[0];
    if (!r || r.out_code !== 'OK') {
      log({ ev: 'enroll_refused', code: r?.out_code || 'ENROLL_FAILED' });
      return { ok: false, error: { code: r?.out_code || 'ENROLL_FAILED' } };
    }
    log({ ev: 'enrolled', role: r.out_role_key, tenant: r.out_tenant_id });
    return { ok: true, result: { pass, tenant_id: r.out_tenant_id, role_key: r.out_role_key } };
  }

  // Обработчик местного входа (gate_server onCommand): только получение пропуска и команды аренды.
  async function handle(body) {
    if (!body || typeof body !== 'object' || Object.keys(body).some((k) => !BODY_KEYS.has(k))) {
      return { status: 400, body: { ok: false, error: { code: 'GATE_BAD_REQUEST' } } };
    }
    if (body.type === 'EnrollSession') {
      if (body.auth !== undefined) return { status: 400, body: { ok: false, error: { code: 'GATE_BAD_REQUEST' } } };
      const r = await enroll(body.payload);
      return { status: r.ok ? 200 : 403, body: r };
    }
    if (!TRANSPORT_COMMANDS.includes(body.type)) {
      return { status: 403, body: { ok: false, error: { code: 'GATE_COMMAND_NOT_ALLOWED' } } };
    }
    if (body.payload !== undefined && (body.payload === null || typeof body.payload !== 'object' || Array.isArray(body.payload))) {
      return { status: 400, body: { ok: false, error: { code: 'GATE_BAD_REQUEST' } } };
    }
    const r = await kernel.execute(null, accept(body));
    return { status: r.ok ? 200 : 403, body: r };
  }

  return { verify, enroll, handle, accept };
}
