// ДОКУМЕНТ: src/server.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:30 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 22:46 +03:00 (v0.2: аудит E3-5 M-E35-05 —
//   KERNEL_STOP_FILE обязателен: без него процесс не стартует и к базе не подключается)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: процесс Kernel: проверка роли при старте, GET /internal/health на 127.0.0.1
//   (H1.31 §7.7, сигнал 1), цикл доставщика outbox. Приём команд по сети — этап 4
//   (нужна проверка подлинности вызывающего; до неё сетевого входа команд нет).
// ЗАПУСК: PGHOST=127.0.0.1 PGPORT=54337 PGDATABASE=bem KERNEL_STOP_FILE=<путь> node src/server.mjs
// ОГРАНИЧЕНИЯ: Egress здесь — заглушка, которая ничего не отправляет и отвечает UNKNOWN_OUTCOME;
//   настоящий Egress — отдельный процесс без доступа к базе (H1.31 §7.8).

import http from 'node:http';
import { Kernel } from './kernel.mjs';

const HOST = '127.0.0.1';
const PORT = Number(process.env.KERNEL_HEALTH_PORT || 18954);
const TICK_MS = Number(process.env.KERNEL_DISPATCH_MS || 5000);

const log = (o) => process.stdout.write(JSON.stringify({ t: new Date().toISOString(), ...o }) + '\n');
// SR-10 (M-E35-05): выключатель обязателен. Без пути процесс завершается с кодом 3 до подключения
// к базе; при нечитаемом или неизвестном файле Kernel стартует остановленным (stopState).
if (!process.env.KERNEL_STOP_FILE || !process.env.KERNEL_STOP_FILE.trim()) {
  log({ ev: 'kernel_refused', code: 'KERNEL_STOP_FILE_REQUIRED' });
  process.exit(3);
}
const kernel = new Kernel({
  connection: {
    host: process.env.PGHOST || '127.0.0.1',
    port: Number(process.env.PGPORT || 5432),
    database: process.env.PGDATABASE || 'bem',
  },
  stopFile: process.env.KERNEL_STOP_FILE,
  log,
});

await kernel.assertIdentity();
log({ ev: 'stop_state', reason: kernel.health().stop_reason });
let lastDispatch = null;

// Заглушка Egress: внешних действий нет, исход честно неизвестен (не SENT).
const stubEgress = async () => ({ outcome: 'UNKNOWN_OUTCOME', detail: { egress: 'stub-no-delivery' } });

const timer = setInterval(async () => {
  try {
    const r = await kernel.dispatchOnce(stubEgress, { limit: 10 });
    lastDispatch = new Date().toISOString();
    if (r.claimed) log({ ev: 'dispatch', claimed: r.claimed });
  } catch (e) {
    log({ ev: 'dispatch_error', code: e.code || 'ERROR' });
  }
}, TICK_MS);

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/internal/health') {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ ...kernel.health(), last_dispatch_at: lastDispatch }));
    return;
  }
  res.writeHead(404, { 'content-type': 'application/json' });
  res.end('{"error":"NOT_FOUND"}');
});
server.listen(PORT, HOST, () => log({ ev: 'kernel_started', health: `http://${HOST}:${PORT}/internal/health` }));

const shutdown = async (sig) => {
  log({ ev: 'kernel_stopping', sig });
  clearInterval(timer);
  server.close();
  await kernel.close();
  process.exit(0);
};
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
