// ДОКУМЕНТ: tests/helpers.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 13:25 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: стенд тестов Kernel. Участники и заказчики создаются штатными функциями
//   управления от bem_bootstrap_admin (как fixture_boot R46). Kernel этой ролью не пользуется.
// ОГРАНИЧЕНИЯ: только тестовый стенд 127.0.0.1 с trust; секретов нет. Имена уникальны
//   на каждый прогон, поэтому повторный прогон на той же базе не конфликтует.

import pg from 'pg';
import { randomUUID } from 'node:crypto';

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
