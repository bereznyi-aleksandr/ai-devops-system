// ДОКУМЕНТ: tests/paused_sender.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 17:55 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 21:15 +03:00 (v0.2: аудит Z5 M-Z5-01 —
//   после отметки исполнитель порождает потомка с доступом к адаптеру, отделённого через setsid;
//   связь с надзирателем — строки JSON в stdout и файл GO, без IPC: исполнитель запущен через sudo)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: дочерний процесс теста E4-8 / M-Z5-01. Запущен надзирателем (src/fencer.mjs) в своей
//   единице исполнения. Доставщик Kernel ставит отметку начала отправки; затем (descendant=1)
//   исполнитель порождает потомка, который тоже ждёт файл GO и потом вызывает адаптер, и сам
//   замирает ПЕРЕД адаптером до появления файла GO. Адаптер-заглушка — дописать строку в
//   файл-счётчик: одна строка = один внешний эффект.
// ВЫЗОВ: node paused_sender.mjs <counterFile> <worker> <lease> <outboxId> <goFile> <descendant 0|1>

import { appendFileSync, existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { Kernel } from '../src/kernel.mjs';
import { CONN } from './helpers.mjs';

const [counterFile, worker, lease, mine, goFile, descendant] = process.argv.slice(2);
const rt = process.env.ZAVOD_RUNTIME_INSTANCE;
const say = (m) => process.stdout.write(`${JSON.stringify(m)}\n`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitGo() { while (!existsSync(goFile)) await sleep(50); }

// Потомок: отдельная сессия (setsid), ждёт GO и вызывает тот же адаптер.
const DESCENDANT = `
const { appendFileSync, existsSync } = require('node:fs');
const [counter, go, rt] = process.argv.slice(1);
const t = setInterval(() => { if (existsSync(go)) { appendFileSync(counter, 'descendant:' + rt + '\\n'); clearInterval(t); } }, 50);
`;

say({ ev: 'READY', pid: process.pid, runtime_instance: rt });
const kernel = new Kernel({ connection: CONN });
await kernel.dispatchOnce(async (row) => {
  // Чужие строки сразу возвращаются как FAILED, чтобы не держать их (как claim() в ext01).
  if (row.outbox_id !== mine) return { outcome: 'FAILED', detail: { released_by_test: 'paused_sender' } };
  if (descendant === '1') {
    const d = spawn(process.execPath, ['-e', DESCENDANT, counterFile, goFile, rt], { detached: true, stdio: 'ignore' });
    d.unref();
    say({ ev: 'DESCENDANT', pid: d.pid });
  }
  say({ ev: 'MARKED', outbox_id: row.outbox_id, lease_epoch: String(row.lease_epoch), runtime_instance: rt });
  await waitGo();                                // пауза исполнителя после отметки
  appendFileSync(counterFile, `${rt}\n`);        // внешний эффект
  return { outcome: 'SENT', detail: { stub: true } };
}, { limit: 500, lease, worker });
say({ ev: 'DONE' });
await kernel.close();
