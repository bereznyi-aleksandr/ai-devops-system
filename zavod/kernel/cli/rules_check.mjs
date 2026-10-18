// ДОКУМЕНТ: cli/rules_check.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 00:08 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 00:08 +03:00 (v0.1: пакет Z-RULES-01, проект v1.2 §4)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: местный вход только для чтения: действующая версия правил заказчика (GetActiveRules) и итог проверки
//   перед арендой (src/rules_gate.mjs checkWorkingCopy) для рабочей копии. Ничего не пишет: изменяющих команд нет.
// ЗАПУСК: PGHOST=127.0.0.1 PGPORT=<порт> PGDATABASE=bem KERNEL_STOP_FILE=<путь> node cli/rules_check.mjs
//   --tenant <uuid> --actor <участник> --role <роль Kernel> --repo-dir <рабочая копия> [--no-fetch]
// ВЫХОД: одна строка JSON; код 0 — правила действуют и копия совпадает, 1 — отказ (код в поле error.code), 2 — аргументы.
// ОГРАНИЧЕНИЯ: посредника нет, поэтому команды аренды отсюда недоступны (проект §3.2). Токен GitHub не нужен.

import { Kernel } from '../src/kernel.mjs';
import { createRulesGate } from '../src/rules_gate.mjs';

function arg(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : undefined;
}
const tenant = arg('tenant');
const actor = arg('actor');
const role = arg('role');
const repoDir = arg('repo-dir');
const out = (o, code) => { process.stdout.write(JSON.stringify(o) + '\n'); process.exitCode = code; };
if (!tenant || !actor || !role || !repoDir || !process.env.KERNEL_STOP_FILE) {
  out({ ok: false, error: { code: 'BAD_ARGS', message: '--tenant --actor --role --repo-dir and KERNEL_STOP_FILE required' } }, 2);
} else {
  const kernel = new Kernel({ connection: { host: process.env.PGHOST || '127.0.0.1', port: Number(process.env.PGPORT || 5432),
    database: process.env.PGDATABASE || 'bem', max: 1 }, stopFile: process.env.KERNEL_STOP_FILE });
  try {
    const r = await kernel.execute({ actor_id: actor, role }, { type: 'GetActiveRules', actor_id: actor, tenant_id: tenant, payload: {} });
    if (!r.ok) {
      out(r, 1);
    } else {
      const gate = createRulesGate({ repoDir, fetch: !process.argv.includes('--no-fetch') });
      try {
        out({ ok: true, active: r.result, worktree: gate.checkWorkingCopy(r.result.rules_commit) }, 0);
      } catch (e) {
        out({ ok: false, active: r.result, error: { code: e.code || 'RULES_CHECK_FAILED', message: e.message } }, 1);
      }
    }
  } finally {
    await kernel.close();
  }
}
