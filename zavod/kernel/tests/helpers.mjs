// ДОКУМЕНТ: tests/helpers.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 23:12 +03:00 (v0.2: аудит E3-5 —
//   runStopFile: Kernel без стоп-файла RUN закрыт (M-E35-05); operatorLogin: штатный вход оператора
//   H1.31 — своя роль входа, член bem_governance, связанный участник, полномочие OPERATOR (M-E35-02))
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: стенд тестов Kernel. Участники и заказчики создаются штатными функциями
//   управления от bem_bootstrap_admin (как fixture_boot R46). Kernel этой ролью не пользуется.
// ОГРАНИЧЕНИЯ: только тестовый стенд 127.0.0.1 с trust; секретов нет. Имена уникальны
//   на каждый прогон, поэтому повторный прогон на той же базе не конфликтует.

import pg from 'pg';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export const CONN = {
  host: process.env.PGHOST || '127.0.0.1',
  port: Number(process.env.PGPORT || 54337),
  database: process.env.PGDATABASE || 'bem',
};

export function asRole(user) { return new pg.Client({ ...CONN, user }); }

export async function withRole(user, fn) {
  const c = asRole(user);
  await c.connect();
  try { return await fn(c); } finally { await c.end(); }
}

// Создаёт двух заказчиков, авторов anthropic/openai, проверяющих и человека-оператора.
export async function bootFixture() {
  const run = randomUUID().slice(0, 8);
  const ids = {
    run,
    tenantA: randomUUID(), tenantB: randomUUID(),
    humanA: `human:op-${run}`, humanAUser: randomUUID(),
    humanB: `human:opb-${run}`, humanBUser: randomUUID(),
    author: `claude:author-${run}`, author2: `codex:author-${run}`,
    audOpenai: `codex:aud-${run}`, audAnthropic: `claude:aud-${run}`,
  };
  await withRole('bem_bootstrap_admin', async (c) => {
    const q = (sql, args) => c.query(sql, args);
    await q('SELECT bem_control.create_actor($1, $2, $3, NULL)', [ids.humanA, 'human', ids.humanAUser]);
    await q('SELECT bem_control.create_actor($1, $2, $3, NULL)', [ids.humanB, 'human', ids.humanBUser]);
    for (const [a, prov] of [[ids.author, 'anthropic'], [ids.author2, 'openai'],
      [ids.audOpenai, 'openai'], [ids.audAnthropic, 'anthropic']]) {
      await q('SELECT bem_control.create_actor($1, $2, NULL, NULL)', [a, prov]);
    }
    await q('SELECT bem_control.create_tenant($1, $2, $3, $4, $5)',
      [ids.tenantA, `zavod test A ${run}`, ids.humanA, ids.humanAUser, { zavod: 'stage3-test' }]);
    await q('SELECT bem_control.create_tenant($1, $2, $3, $4, $5)',
      [ids.tenantB, `zavod test B ${run}`, ids.humanB, ids.humanBUser, { zavod: 'stage3-test' }]);
    for (const a of [ids.author, ids.author2, ids.audOpenai, ids.audAnthropic, ids.humanA, ids.humanB]) {
      await q("SELECT bem_control.grant_delegation('bem_kernel_rw', $1, $2)", [a, `zavod stage3 test ${run}`]);
    }
  });
  return ids;
}

export async function assignAuditor(tenant, subject, auditor) {
  return withRole('bem_bootstrap_admin', async (c) => {
    await c.query("SELECT set_config('app.tenant_id', $1, false)", [tenant]);
    return c.query('SELECT bem_control.assign_auditor($1, $2, $3, $4)', [tenant, subject, auditor, { zavod: 'assign' }]);
  });
}

export const uuid = randomUUID;

// SR-10: стоп-файл со строкой RUN в своей папке прогона (файл не удаляется, P4.702).
export function runStopFile(prefix = 'zavod-stop-') {
  const f = join(mkdtempSync(join(tmpdir(), prefix)), 'KERNEL_STOP');
  writeFileSync(f, 'RUN\n');
  return f;
}

// M-E35-02: вход оператора по канону H1.31 §16 (стенд с trust, без пароля). Роль входа создаёт
// администратор кластера (postgres), участника и полномочие — штатные функции управления.
// Полномочие OPERATOR — на весь кластер (tenant NULL): оператор по должности работает во всех
// заказчиках (H1.31, триггер EVIDENCE_ACTOR_NOT_IN_TENANT). withOperator=false — тот же вход без
// полномочия OPERATOR (для отказа AUTHORITY_REQUIRED).
export async function operatorLogin({ withOperator = true } = {}) {
  const tag = randomUUID().slice(0, 8);
  const role = `zavod_op_${tag}`;
  const actor = `human:zavod-op-${tag}`;
  await withRole('postgres', async (c) => {
    await c.query(`CREATE ROLE ${role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT IN ROLE bem_governance`);
    await c.query(`GRANT CONNECT ON DATABASE ${CONN.database} TO ${role}`);
  });
  await withRole('bem_bootstrap_admin', async (c) => {
    await c.query('SELECT bem_control.create_actor($1, $2, $3, $4)', [actor, 'human', randomUUID(), role]);
    if (withOperator) await c.query("SELECT bem_control.grant_authority($1, 'OPERATOR', NULL)", [actor]);
  });
  return { role, actor };
}
