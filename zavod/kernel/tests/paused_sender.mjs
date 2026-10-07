// ДОКУМЕНТ: tests/paused_sender.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 17:55 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 17:55 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: дочерний процесс теста E4-8 / M-Z4-01. Запущен надзирателем (src/fencer.mjs) как
//   экземпляр среды одной попытки. Доставщик Kernel ставит отметку начала отправки, после чего
//   процесс замирает ПЕРЕД вызовом адаптера и ждёт команды GO. Адаптер-заглушка — дописать строку
//   в файл-счётчик: одна строка = один внешний эффект.
// ВЫЗОВ: fork(paused_sender.mjs, [counterFile, worker, lease, outboxId]) с ZAVOD_RUNTIME_INSTANCE.

import { appendFileSync } from 'node:fs';
import { Kernel } from '../src/kernel.mjs';
import { CONN } from './helpers.mjs';

const [counterFile, worker, lease, mine] = process.argv.slice(2);
const go = new Promise((resolve) => process.on('message', (m) => { if (m === 'GO') resolve(); }));
const kernel = new Kernel({ connection: CONN });

await kernel.dispatchOnce(async (row) => {
  // Чужие строки сразу возвращаются как FAILED, чтобы не держать их (как claim() в ext01).
  if (row.outbox_id !== mine) return { outcome: 'FAILED', detail: { released_by_test: 'paused_sender' } };
  process.send({ ev: 'MARKED', outbox_id: row.outbox_id, lease_epoch: String(row.lease_epoch),
    runtime_instance: process.env.ZAVOD_RUNTIME_INSTANCE });
  await go;                                   // пауза исполнителя после отметки
  appendFileSync(counterFile, `${process.env.ZAVOD_RUNTIME_INSTANCE}\n`);   // внешний эффект
  return { outcome: 'SENT', detail: { stub: true } };
}, { limit: 500, lease, worker });
process.send({ ev: 'DONE' });
await kernel.close();
