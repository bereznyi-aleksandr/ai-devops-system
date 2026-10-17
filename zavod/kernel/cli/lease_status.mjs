// ДОКУМЕНТ: cli/lease_status.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 00:08 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 00:08 +03:00 (v0.1: пакет Z-HANDOFF-01, проект v1.2 §4)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: местный вход только для чтения: состояние аренды чата роли (GetChatLease) — номер чата, поколение,
//   OPEN/COMPLETED и квитанция завершения. Ничего не пишет.
// ЗАПУСК: PGHOST=127.0.0.1 PGPORT=<порт> PGDATABASE=bem KERNEL_STOP_FILE=<путь> node cli/lease_status.mjs
//   --tenant <uuid> --actor <участник> --role <роль Kernel> (--lease <uuid> | --role-key <01_…>)
// ВЫХОД: одна строка JSON; код 0 — аренда найдена, 1 — отказ (код в поле error.code), 2 — аргументы.
// ОГРАНИЧЕНИЯ: видит только аренды своего заказчика; команды аренды отсюда недоступны (проект §3.2).

import { Kernel } from '../src/kernel.mjs';

function arg(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : undefined;
}
const tenant = arg('tenant');
const actor = arg('actor');
const role = arg('role');
const leaseId = arg('lease');
const roleKey = arg('role-key');
const out = (o, code) => { process.stdout.write(JSON.stringify(o) + '\n'); process.exitCode = code; };
if (!tenant || !actor || !role || (!leaseId && !roleKey) || !process.env.KERNEL_STOP_FILE) {
  out({ ok: false, error: { code: 'BAD_ARGS', message: '--tenant --actor --role (--lease | --role-key) and KERNEL_STOP_FILE required' } }, 2);
} else {
  const kernel = new Kernel({ connection: { host: process.env.PGHOST || '127.0.0.1', port: Number(process.env.PGPORT || 5432),
    database: process.env.PGDATABASE || 'bem', max: 1 }, stopFile: process.env.KERNEL_STOP_FILE });
  try {
    const r = await kernel.execute({ actor_id: actor, role }, { type: 'GetChatLease', actor_id: actor, tenant_id: tenant,
      payload: leaseId ? { lease_id: leaseId } : { role_key: roleKey } });
    out(r, r.ok ? 0 : 1);
  } finally {
    await kernel.close();
  }
}
