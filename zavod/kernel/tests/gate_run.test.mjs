// ДОКУМЕНТ: tests/gate_run.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-23 04:37 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-23 04:37 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия 8bfd707d-8484-45cc-ada5-59e2fe47219b)
// НАЗНАЧЕНИЕ: план Z-INSTALL-01 D19 (протокол v2.8 Р.5) — перезапуск привратника: до пяти раз подряд с перерывом,
//   счёт сбрасывается после долгой работы, файл остановки не RUN и выход 0 — без перезапуска. База и сеть не нужны.

import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { superviseGate, stopReasonFor, MAX_RESTARTS, RESTART_DELAY_MS } from '../src/gate_run.mjs';

const harness = (codes, opts = {}) => {
  const ev = [];
  const sleeps = [];
  let t = 0;
  let i = 0;
  const run = superviseGate({
    runOnce: async () => { t += opts.runMs ? opts.runMs(i) : 1000; return codes[i++]; },
    mayRestart: opts.mayRestart || (() => 'RUN'),
    log: (o) => ev.push(o), now: () => t,
    sleep: async (ms) => { sleeps.push(ms); t += ms; },
  });
  return { run, ev, sleeps, runs: () => i };
};

test('gate_run: Р.5 — пять перезапусков через минуту, затем отказ с кодом привратника', async () => {
  const h = harness(Array(10).fill(3));
  assert.equal(await h.run, 3);
  assert.equal(MAX_RESTARTS, 5);
  assert.equal(h.runs(), 6);
  assert.deepEqual(h.sleeps, Array(5).fill(RESTART_DELAY_MS));
  assert.equal(RESTART_DELAY_MS, 60_000);
  assert.deepEqual(h.ev.filter((e) => e.ev === 'gate_run_restart').map((e) => e.attempt), [1, 2, 3, 4, 5]);
  assert.deepEqual(h.ev.at(-1), { ev: 'gate_run_gave_up', code: 3, restarts: 5 });
});

test('gate_run: выход 0 — без перезапуска', async () => {
  const h = harness([3, 0]);
  assert.equal(await h.run, 0);
  assert.equal(h.runs(), 2);
  assert.equal(h.ev.at(-1).ev, 'gate_run_exit');
});

test('gate_run: файл остановки не RUN — без перезапуска (до и после ожидания)', async () => {
  const a = harness([3, 3], { mayRestart: () => 'STOP' });
  assert.equal(await a.run, 3);
  assert.equal(a.runs(), 1);
  assert.deepEqual(a.sleeps, []);
  assert.deepEqual(a.ev, [{ ev: 'gate_run_stopped', code: 3, reason: 'STOP' }]);
  let n = 0;
  const b = harness([3, 3], { mayRestart: () => (n++ === 0 ? 'RUN' : 'STOP') });
  assert.equal(await b.run, 3);
  assert.equal(b.runs(), 1);
  assert.equal(b.ev.at(-1).reason, 'STOP');
});

test('gate_run: после десяти минут работы счёт перезапусков сбрасывается', async () => {
  // Запуски 1–4 — быстрые сбои (перезапуски 1–4), пятый проработал 11 минут (счёт с нуля), затем ещё пять
  // перезапусков и отказ: всего 10 запусков (без сброса было бы 6).
  const h = harness(Array(20).fill(3), { runMs: (i) => (i === 4 ? 11 * 60_000 : 1000) });
  assert.equal(await h.run, 3);
  assert.equal(h.runs(), 10);
  assert.equal(h.ev.at(-1).ev, 'gate_run_gave_up');
});

test('gate_run: gate.json не читается — причина не RUN, перезапуска нет', () => {
  assert.equal(stopReasonFor('', () => { const e = new Error('x'); e.code = 'ENOENT'; throw e; }), 'ENOENT');
  assert.equal(stopReasonFor('C:\\x\\gate.json', () => '{}'), 'GATE_CONFIG_DB_HOST');
});

test('gate_run: запуск без gate.json — привратник отказывает, gate_run выходит его кодом без перезапуска', () => {
  const r = spawnSync(process.execPath, [fileURLToPath(new URL('../src/gate_run.mjs', import.meta.url))], { encoding: 'utf8', timeout: 30_000 });
  assert.equal(r.status, 3);
  const ev = r.stdout.trim().split('\n').map((l) => JSON.parse(l).ev);
  assert.deepEqual(ev, ['gate_main_refused', 'gate_run_stopped']);
});
