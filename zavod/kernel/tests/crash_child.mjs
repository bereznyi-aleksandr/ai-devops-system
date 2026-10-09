// ДОКУМЕНТ: tests/crash_child.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 23:12 +03:00 (v0.2: стоп-файл RUN — M-E35-05)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: дочерний процесс теста E3-3. Выполняет переход через Kernel и замирает
//   в точке, заданной режимом, чтобы родитель убил процесс жёстко (TerminateProcess / SIGKILL).
// РЕЖИМЫ: before-commit — замереть внутри транзакции после apply_transition;
//         after-commit  — переход зафиксирован, замереть до выдачи ответа.

import { Kernel } from '../src/kernel.mjs';
import { CONN, runStopFile } from './helpers.mjs';

const [mode, actor, tenant, wi, rev, status, cmd] = process.argv.slice(2);
const hang = () => new Promise(() => {});

const kernel = new Kernel({
  connection: CONN,
  stopFile: runStopFile('zavod-crash-'),
  testBeforeCommit: mode === 'before-commit'
    ? async () => { process.stdout.write('IN_TX\n'); await hang(); }
    : null,
});

const r = await kernel.execute({ actor_id: actor }, {
  type: 'Transition', actor_id: actor, tenant_id: tenant, command_id: cmd,
  payload: { work_item_id: wi, expected_revision: Number(rev), new_status: status,
    outbox_kind: 'notify.send', outbox_payload: { crash: mode }, evidence: { crash: mode } },
});
if (mode === 'after-commit') {
  process.stdout.write(`COMMITTED ${r.ok}\n`);
  await hang();
}
process.stdout.write(JSON.stringify(r) + '\n');
await kernel.close();
