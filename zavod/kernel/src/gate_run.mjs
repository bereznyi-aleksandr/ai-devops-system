// ДОКУМЕНТ: src/gate_run.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-23 04:37 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-23 04:37 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия 8bfd707d-8484-45cc-ada5-59e2fe47219b)
// НАЗНАЧЕНИЕ: протокол v2.8 Р.5 — перезапуск привратника до пяти раз с перерывом в одну минуту (план Z-INSTALL-01 D19).
//   Задача Windows сама не перезапускает процесс, вышедший с ненулевым кодом: её настройка RestartCount касается только
//   сбоя запуска (опыт CI 39881988908: база остановлена, за 7 минут один отказ, задача в состоянии Ready).
//   Этот процесс запускает src/gate_main.mjs дочерним; после выхода с ненулевым кодом, если файл остановки = RUN,
//   ждёт минуту и запускает снова, не больше пяти раз подряд. Счёт сбрасывается, если привратник проработал не меньше
//   десяти минут. Выход привратника с кодом 0 и файл остановки не RUN — без перезапуска.
// ЗАПУСК: node src/gate_run.mjs C:\ZavodKernel\app\gate.json
// ОГРАНИЧЕНИЯ: ключей не читает — только gate.json (пути) и файл остановки; журнал — те же строки JSON, что у gate_main.

import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseConfig } from './gate_main.mjs';
import { stopState } from './guards.mjs';

export const MAX_RESTARTS = 5;
export const RESTART_DELAY_MS = 60_000;
export const RESET_AFTER_MS = 600_000;

// superviseGate(o) -> код выхода. o.runOnce() — один запуск привратника (промис с кодом выхода);
// o.mayRestart() — причина из файла остановки ('RUN' разрешает перезапуск). Остальное — для испытаний.
export async function superviseGate(o) {
  const { runOnce, mayRestart, log = () => {}, now = Date.now,
    sleep = (ms) => new Promise((r) => setTimeout(r, ms)),
    maxRestarts = MAX_RESTARTS, delayMs = RESTART_DELAY_MS, resetAfterMs = RESET_AFTER_MS } = o;
  let restarts = 0;
  for (;;) {
    const started = now();
    const code = await runOnce();
    if (code === 0) { log({ ev: 'gate_run_exit', code }); return 0; }
    if (now() - started >= resetAfterMs) restarts = 0;
    let reason = mayRestart();
    if (reason !== 'RUN') { log({ ev: 'gate_run_stopped', code, reason }); return code; }
    if (restarts >= maxRestarts) { log({ ev: 'gate_run_gave_up', code, restarts }); return code; }
    restarts += 1;
    log({ ev: 'gate_run_restart', code, attempt: restarts, delay_ms: delayMs });
    await sleep(delayMs);
    // Файл остановки мог смениться за время ожидания: STOP — без нового запуска.
    reason = mayRestart();
    if (reason !== 'RUN') { log({ ev: 'gate_run_stopped', code, reason }); return code; }
  }
}

// Причина из файла остановки по gate.json; gate.json не читается или неверен — его код (перезапуска нет).
export function stopReasonFor(configPath, read = readFileSync) {
  try { return stopState(parseConfig(read(configPath, 'utf8')).stopFile).reason; } catch (e) { return e.code || 'GATE_CONFIG'; }
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const log = (o) => process.stdout.write(JSON.stringify({ t: new Date().toISOString(), ...o }) + '\n');
  const path = process.argv[2] || '';
  const main = fileURLToPath(new URL('./gate_main.mjs', import.meta.url));
  let child = null;
  const runOnce = () => new Promise((resolve) => {
    child = spawn(process.execPath, path ? [main, path] : [main], { stdio: 'inherit', windowsHide: true });
    child.once('error', () => resolve(1));
    child.once('exit', (code) => { child = null; resolve(code ?? 1); });
  });
  // Сигнал остановки передаётся привратнику; после него перезапусков нет.
  let signalled = null;
  const forward = (sig) => { signalled = sig; if (child) child.kill(sig); };
  process.on('SIGINT', forward);
  process.on('SIGTERM', forward);
  process.exitCode = await superviseGate({ runOnce, mayRestart: () => (signalled ? `SIGNAL_${signalled}` : stopReasonFor(path)), log });
}
