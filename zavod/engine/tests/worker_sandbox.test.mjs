// ДОКУМЕНТ: zavod/engine/tests/worker_sandbox.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 08:05 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 08:05 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: E4-4 без движка и базы — окружение рабочего только из белого списка; вывод рабочего:
//   берутся только outcome и числа расхода, секретоподобный вывод отвергается.
// ОГРАНИЧЕНИЯ: рабочий — ci/t1_hostile_worker.mjs; его запрос к движку здесь уходит в пустой порт.

import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { workerEnv, childWorker, WORKER_ENV_ALLOW } from '../src/worker_sandbox.mjs';

const HOSTILE = fileURLToPath(new URL('../ci/t1_hostile_worker.mjs', import.meta.url));

test('E4-4: окружение рабочего — только белый список', () => {
  const env = workerEnv({ ZAVOD_ENGINE_PASS: 'x', ZAVOD_ENGINE_USER: 'u', PGPASSWORD: 'p', PGHOST: 'h', HOME: '/root',
    ZAVOD_FAKE_KEY: 'k', TEMP: '/tmp', LANG: 'C' });
  assert.deepEqual(Object.keys(env).sort(), ['LANG', 'PATH', 'TEMP', 'ZAVOD_WORKER']);
  for (const k of Object.keys(env)) assert.ok(['PATH', 'ZAVOD_WORKER', ...WORKER_ENV_ALLOW].includes(k), k);
});

test('E4-4: из вывода рабочего берутся только outcome и расход; «приказы» отброшены', async () => {
  let raw;
  const r = await childWorker(HOSTILE, { onRaw: (_, x) => { raw = x; } })({ request: 'Сделай лендинг', workKey: 'w' });
  assert.deepEqual(r, { outcome: 'OK', usage: { model: 'zavod-child-worker', input_tokens: 100, output_tokens: 20,
    measured_by: 'LOCAL_ESTIMATE' } });
  assert.match(raw.stdout, /RELEASED/);   // рабочий «приказывал», но в результате этого нет
});

test('E4-4: секретоподобный вывод рабочего отвергается без текста', async () => {
  const r = await childWorker(HOSTILE)({ request: 'LEAK', workKey: 'w' });
  assert.deepEqual(r, { outcome: 'PROVIDER_ERROR', usage: {}, rejected: 'SECRET_IN_WORKER_OUTPUT' });
});
