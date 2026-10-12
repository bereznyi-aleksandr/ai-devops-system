// ДОКУМЕНТ: tests/e55_crash_child.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-11 18:45 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия по задаче E5-5, заготовка)
// НАЗНАЧЕНИЕ: дочерний процесс теста e55_pilot_release_injection.test.mjs. Как crash_child.mjs, но
//   переход несёт строку outbox выпуска продукта (вид и payload с манифестом SR-13 передаются
//   аргументом base64 JSON), чтобы убийство Kernel падало именно на переходе выпуска. crash_child.mjs
//   (E3-3) не правится: он аудирован и шлёт фиксированный вид notify.send.
// РЕЖИМЫ: before-commit — замереть внутри транзакции после apply_transition;
//         after-commit  — переход зафиксирован, замереть до выдачи ответа.
// ОГРАНИЧЕНИЯ: стенд PG16 с Z-EXT-01; секретов нет.

import { Kernel } from '../src/kernel.mjs';
import { CONN, runStopFile } from './helpers.mjs';

const [mode, actor, tenant, wi, rev, status, cmd, kind, payloadB64] = process.argv.slice(2);
const outboxPayload = JSON.parse(Buffer.from(payloadB64, 'base64').toString('utf8'));
const hang = () => new Promise(() => {});

const kernel = new Kernel({
  connection: CONN,
  stopFile: runStopFile('zavod-e55-crash-'),
  testBeforeCommit: mode === 'before-commit'
    ? async () => { process.stdout.write('IN_TX\n'); await hang(); }
    : null,
});

const r = await kernel.execute({ actor_id: actor, role: 'kernel' }, {
  type: 'Transition', actor_id: actor, tenant_id: tenant, command_id: cmd,
  payload: { work_item_id: wi, expected_revision: Number(rev), new_status: status,
    outbox_kind: kind, outbox_payload: outboxPayload, evidence: { test: 'E5-5' } },
});
if (mode === 'after-commit') {
  process.stdout.write(`COMMITTED ${r.ok}\n`);
  await hang();
}
process.stdout.write(JSON.stringify(r) + '\n');
await kernel.close();
