// ДОКУМЕНТ: src/gate_main.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 13:52 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 13:52 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.2 §4.A — точка входа «ядро + привратник» под учётной записью
//   zavod-kernel: Kernel (пулы bem_kernel_rw и bem_rules_gate по клиентским сертификатам, проверка сервера базы
//   по своему CA и адресу — verify-full), проверка правил (git из bin, GitHub без входа), посредник, местный вход
//   127.0.0.1, доставщик outbox (заглушка Egress, как в server.mjs), GET /internal/health.
//   Порядок старта: настройки → учётная запись ОС → файл остановки → личность ролей в базе → занятие порта.
//   Любой отказ — код выхода 3 и строка журнала с кодом, без путей ключей и без содержимого.
// ЗАПУСК: node src/gate_main.mjs C:\ZavodKernel\app\gate.json
// ОГРАНИЧЕНИЯ: секретов в gate.json нет — только пути; ключи читает этот процесс, в журнал они не пишутся.
//   MODE=active этот файл не включает.

import http from 'node:http';
import tls from 'node:tls';
import { readFileSync, existsSync } from 'node:fs';
import { isAbsolute } from 'node:path';
import { userInfo } from 'node:os';
import { createPrivateKey } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { Kernel } from './kernel.mjs';
import { createRulesGate, gitRunner } from './rules_gate.mjs';
import { createTransport } from './transport.mjs';
import { createGateServer } from './gate_server.mjs';
import { anonGh } from './github_anon.mjs';

export class GateMainError extends Error {
  constructor(code, detail) { super(`${code}: ${detail}`); this.code = code; }
}

const KEYS = new Set(['db', 'kernelCert', 'rulesCert', 'gate', 'stopFile', 'expectedUser', 'rules', 'health', 'dispatchMs']);
const fail = (code, detail) => { throw new GateMainError(code, detail); };
const absFile = (v, name) => {
  if (typeof v !== 'string' || !isAbsolute(v)) fail('GATE_CONFIG_PATH', name);
  return v;
};
const port = (v, name) => {
  if (!Number.isInteger(v) || v < 1024 || v > 65535) fail('GATE_CONFIG_PORT', name);
  return v;
};
const pair = (v, name) => {
  if (!v || typeof v !== 'object' || Object.keys(v).sort().join() !== 'cert,key') fail('GATE_CONFIG_CERT', name);
  return { cert: absFile(v.cert, `${name}.cert`), key: absFile(v.key, `${name}.key`) };
};

// Разбор gate.json: неизвестный ключ, относительный путь, чужой адрес базы — отказ (а не значение по умолчанию).
export function parseConfig(text) {
  let c;
  try { c = JSON.parse(text); } catch { fail('GATE_CONFIG_JSON', 'bad json'); }
  if (!c || typeof c !== 'object' || Array.isArray(c)) fail('GATE_CONFIG_JSON', 'not an object');
  for (const k of Object.keys(c)) if (!KEYS.has(k)) fail('GATE_CONFIG_UNKNOWN_KEY', k);
  const db = c.db || {};
  if (db.host !== '127.0.0.1') fail('GATE_CONFIG_DB_HOST', String(db.host));
  if (typeof db.database !== 'string' || !/^[a-z_][a-z0-9_]{0,62}$/.test(db.database)) fail('GATE_CONFIG_DB_NAME', 'database');
  const rules = c.rules || {};
  if (typeof rules.repo !== 'string' || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(rules.repo)) fail('GATE_CONFIG_RULES', 'repo');
  if (typeof c.expectedUser !== 'string' || !c.expectedUser.trim()) fail('GATE_CONFIG_USER', 'expectedUser');
  const gate = c.gate || {};
  const health = c.health || {};
  const cfg = {
    db: { host: '127.0.0.1', port: port(db.port, 'db.port'), database: db.database, ca: absFile(db.ca, 'db.ca') },
    kernelCert: pair(c.kernelCert, 'kernelCert'),
    rulesCert: pair(c.rulesCert, 'rulesCert'),
    gate: { port: port(gate.port, 'gate.port'), key: absFile(gate.key, 'gate.key') },
    health: { port: port(health.port, 'health.port') },
    stopFile: absFile(c.stopFile, 'stopFile'),
    expectedUser: c.expectedUser,
    rules: { repo: rules.repo, repoDir: absFile(rules.repoDir, 'rules.repoDir'), git: absFile(rules.git, 'rules.git'),
      bootstrapKeyFile: rules.bootstrapKeyFile === undefined ? null : absFile(rules.bootstrapKeyFile, 'rules.bootstrapKeyFile') },
    dispatchMs: c.dispatchMs === undefined ? 5000 : c.dispatchMs,
  };
  if (!Number.isInteger(cfg.dispatchMs) || cfg.dispatchMs < 500) fail('GATE_CONFIG_DISPATCH', 'dispatchMs');
  if (new Set([cfg.db.port, cfg.gate.port, cfg.health.port]).size !== 3) fail('GATE_CONFIG_PORT', 'ports must differ');
  return Object.freeze(cfg);
}

// Подключение к базе: только TLS, сервер проверяется по своему CA и по адресу 127.0.0.1 в сертификате (verify-full),
// вход — клиентским сертификатом роли.
export function connectionFor(cfg, which, read = readFileSync) {
  const p = which === 'rules' ? cfg.rulesCert : cfg.kernelCert;
  return { host: cfg.db.host, port: cfg.db.port, database: cfg.db.database,
    ssl: { ca: read(cfg.db.ca), cert: read(p.cert), key: read(p.key), rejectUnauthorized: true,
      // pg подключает TLS поверх своего сокета без host: Node сверял бы сертификат с localhost. Сверка — строго с адресом базы.
      checkServerIdentity: (_h, cert) => tls.checkServerIdentity(cfg.db.host, cert) } };
}

// startGate(cfg, deps) -> { close, kernel, gate }. deps — для испытаний (свои подключение, ядро, git, gh, учётка).
export async function startGate(cfg, deps = {}) {
  const log = deps.log || (() => {});
  const osUser = (deps.userInfo || userInfo)().username;
  // Учётная запись ОС — до любого чтения ключей и подключения к базе.
  if (osUser.toLowerCase() !== cfg.expectedUser.toLowerCase()) fail('GATE_WRONG_OS_USER', osUser);
  if (!existsSync(cfg.stopFile)) fail('GATE_STOP_FILE_REQUIRED', 'stop file missing');
  const read = deps.readFile || readFileSync;
  const privateKey = deps.gateKey || createPrivateKey(read(cfg.gate.key));
  if (privateKey.asymmetricKeyType !== 'ed25519') fail('GATE_KEY_TYPE', String(privateKey.asymmetricKeyType));
  const bootstrapKeyLine = cfg.rules.bootstrapKeyFile ? read(cfg.rules.bootstrapKeyFile, 'utf8').trim() : null;
  const rules = deps.rules || createRulesGate({ repoDir: cfg.rules.repoDir, repo: cfg.rules.repo,
    gh: deps.gh || anonGh(), git: deps.git || gitRunner(cfg.rules.repoDir, cfg.rules.git), bootstrapKeyLine });
  const kernel = new Kernel({
    connection: deps.connection || connectionFor(cfg, 'kernel', read),
    rulesConnection: deps.rulesConnection || connectionFor(cfg, 'rules', read),
    stopFile: cfg.stopFile, rules, log,
  });
  const transport = createTransport({ kernel, log });
  kernel.transport = transport;
  let gate = null;
  let health = null;
  let timer = null;
  const close = async () => {
    if (timer) clearInterval(timer);
    if (gate) await gate.close();
    if (health) await new Promise((r) => health.close(() => r()));
    await kernel.close();
  };
  try {
    await kernel.assertIdentity();
    // Вход повторно сверяет настоящую учётку ОС; подставную учётку испытания (deps.userInfo) проверяет только startGate выше.
    gate = createGateServer({ port: cfg.gate.port, privateKey, expectedUser: deps.userInfo ? null : cfg.expectedUser, stopFile: cfg.stopFile,
      onCommand: (b) => transport.handle(b), log });
    await gate.start();
  } catch (e) {
    await close().catch(() => {});
    throw e;
  }
  let lastDispatch = null;
  const stubEgress = async () => ({ outcome: 'UNKNOWN_OUTCOME', detail: { egress: 'stub-no-delivery' } });
  timer = setInterval(async () => {
    try {
      const r = await kernel.dispatchOnce(stubEgress, { limit: 10 });
      lastDispatch = new Date().toISOString();
      if (r.claimed) log({ ev: 'dispatch', claimed: r.claimed });
    } catch (e) {
      log({ ev: 'dispatch_error', code: e.code || 'ERROR' });
    }
  }, cfg.dispatchMs);
  health = http.createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/internal/health') {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ ...kernel.health(), last_dispatch_at: lastDispatch, gate_port: cfg.gate.port, os_user: osUser }));
      return;
    }
    res.writeHead(404, { 'content-type': 'application/json' });
    res.end('{"error":"NOT_FOUND"}');
  });
  await new Promise((resolve, reject) => {
    health.once('error', reject);
    health.listen({ host: '127.0.0.1', port: cfg.health.port, exclusive: true }, resolve);
  }).catch(async (e) => { await close().catch(() => {}); throw new GateMainError('GATE_HEALTH_PORT', String(e.code)); });
  log({ ev: 'gate_main_started', gate_port: cfg.gate.port, health_port: cfg.health.port });
  return { close, kernel, gate };
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const log = (o) => process.stdout.write(JSON.stringify({ t: new Date().toISOString(), ...o }) + '\n');
  const path = process.argv[2] || process.env.ZAVOD_GATE_CONFIG;
  try {
    if (!path || !isAbsolute(path)) fail('GATE_CONFIG_REQUIRED', 'absolute path to gate.json');
    const cfg = parseConfig(readFileSync(path, 'utf8'));
    const g = await startGate(cfg, { log });
    const shutdown = async (sig) => { log({ ev: 'gate_main_stopping', sig }); await g.close(); process.exit(0); };
    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
  } catch (e) {
    log({ ev: 'gate_main_refused', code: e.code || 'GATE_MAIN_FAILED' });
    process.exit(3);
  }
}
