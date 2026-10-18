// ДОКУМЕНТ: src/gate_server.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 10:15 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 10:15 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: местный вход привратника Z-TRANSPORT-01 (проект v0.3 §3.4): только 127.0.0.1, только
//   POST /command и POST /hello, тело до 64 КБ JSON, обязательный X-Zavod-Gate: 1, отказ при Origin, без CORS,
//   10 секунд на запрос, предел попыток получения пропуска; /hello подписан ключом привратника (Ed25519).
//   Занятый порт — отказ старта. Сам вход ничего не решает о правах: тело команды уходит в onCommand.
// ОГРАНИЧЕНИЯ: проверка пропуска и ядро — в transport.mjs и kernel.mjs; здесь только граница входа.

import http from 'node:http';
import net from 'node:net';
import { existsSync } from 'node:fs';
import { userInfo } from 'node:os';
import { sign as edSign } from 'node:crypto';

export const GATE_HOST = '127.0.0.1';
export const HELLO_NAMESPACE = 'zavod-gate-hello@v1';
export const MAX_BODY = 64 * 1024;
export const REQUEST_MS = 10_000;
export const ENROLL_PER_SESSION = 10;
export const ENROLL_TOTAL = 30;
const WINDOW_MS = 60_000;
const NONCE_RE = /^[0-9a-f]{64}$/;

// Подписываемый текст /hello: пространство имён, порт и одноразовое число клиента — подпись нельзя
// переиграть на другом порту или с другим числом.
export function helloMessage(port, nonce) {
  return Buffer.from(`${HELLO_NAMESPACE}\n${port}\n${nonce}\n`, 'utf8');
}

export class GateStartError extends Error {
  constructor(code, detail) { super(`${code}: ${detail}`); this.code = code; }
}

// Счётчик попыток в памяти: окно 60 секунд, база не меняется (§3.4).
export function createLimiter({ perSession = ENROLL_PER_SESSION, total = ENROLL_TOTAL, windowMs = WINDOW_MS,
  now = Date.now } = {}) {
  let all = [];
  const bySession = new Map();
  const trim = (list, t) => list.filter((x) => t - x < windowMs);
  return {
    allow(session) {
      const t = now();
      all = trim(all, t);
      const mine = trim(bySession.get(session) || [], t);
      if (all.length >= total || mine.length >= perSession) { bySession.set(session, mine); return false; }
      all.push(t); mine.push(t); bySession.set(session, mine);
      return true;
    },
  };
}

function probeWildcard(port) {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.once('error', (e) => reject(new GateStartError(e.code === 'EADDRINUSE' ? 'GATE_PORT_BUSY' : 'GATE_LISTEN_FAILED', String(port))));
    s.listen({ host: '0.0.0.0', port, exclusive: true }, () => s.close(() => resolve()));
  });
}

function send(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
  res.end(body);
}

function isLoopback(addr) {
  return addr === '127.0.0.1' || addr === '::ffff:127.0.0.1';
}

// createGateServer({ port, privateKey, onCommand, expectedUser?, stopFile, limiter?, log? }) -> { start, close }
// onCommand(body) -> { status, body }; исключение в нём — 500 без подробностей.
export function createGateServer(opts) {
  const { port, privateKey, onCommand, expectedUser = null, stopFile, log = () => {}, requestMs = REQUEST_MS } = opts;
  const limiter = opts.limiter || createLimiter();
  if (!Number.isInteger(port) || port <= 0 || port > 65535) throw new GateStartError('GATE_PORT_INVALID', String(port));
  if (!privateKey) throw new GateStartError('GATE_KEY_REQUIRED', 'no private key');
  if (typeof onCommand !== 'function') throw new GateStartError('GATE_HANDLER_REQUIRED', 'no onCommand');

  const server = http.createServer({ requestTimeout: requestMs, headersTimeout: requestMs,
    connectionsCheckingInterval: Math.min(1000, requestMs) }, (req, res) => {
    const deny = (status, code) => { log({ ev: 'gate_refused', code }); send(res, status, { ok: false, code }); };
    if (!isLoopback(req.socket.remoteAddress)) return deny(403, 'GATE_NOT_LOOPBACK');
    if (req.headers.origin !== undefined) return deny(403, 'GATE_ORIGIN_FORBIDDEN');
    if (req.method !== 'POST') return deny(405, 'GATE_METHOD');
    if (req.url !== '/command' && req.url !== '/hello') return deny(404, 'GATE_PATH');
    if (req.headers['x-zavod-gate'] !== '1') return deny(403, 'GATE_HEADER_REQUIRED');
    const type = String(req.headers['content-type'] || '').split(';')[0].trim().toLowerCase();
    if (type !== 'application/json') return deny(415, 'GATE_CONTENT_TYPE');
    const declared = Number(req.headers['content-length']);
    if (Number.isFinite(declared) && declared > MAX_BODY) { res.setHeader('connection', 'close'); return deny(413, 'GATE_BODY_TOO_LARGE'); }

    const chunks = [];
    let size = 0;
    let over = false;
    req.on('data', (c) => {
      if (over) return;
      size += c.length;
      if (size > MAX_BODY) { over = true; res.setHeader('connection', 'close'); deny(413, 'GATE_BODY_TOO_LARGE'); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', async () => {
      if (over) return;
      let body;
      try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return deny(400, 'GATE_BAD_JSON'); }
      if (body === null || typeof body !== 'object' || Array.isArray(body)) return deny(400, 'GATE_BAD_JSON');
      if (req.url === '/hello') {
        if (Object.keys(body).length !== 1 || typeof body.nonce !== 'string' || !NONCE_RE.test(body.nonce)) {
          return deny(400, 'GATE_BAD_NONCE');
        }
        const signature = edSign(null, helloMessage(port, body.nonce), privateKey).toString('base64');
        return send(res, 200, { ok: true, namespace: HELLO_NAMESPACE, port, signature });
      }
      if (body.type === 'EnrollSession') {
        const s = body.payload && typeof body.payload.session === 'string' ? body.payload.session : '';
        if (!limiter.allow(s)) return deny(429, 'GATE_RATE_LIMIT');
      }
      try {
        const r = await onCommand(body);
        send(res, r && Number.isInteger(r.status) ? r.status : 200, r && r.body !== undefined ? r.body : { ok: true });
      } catch {
        deny(500, 'GATE_INTERNAL');
      }
    });
  });

  return {
    server,
    // Старт: проверка учётной записи ОС и файла остановки, затем занятие порта; занятый порт — отказ старта.
    start() {
      if (expectedUser !== null && userInfo().username.toLowerCase() !== String(expectedUser).toLowerCase()) {
        return Promise.reject(new GateStartError('GATE_WRONG_OS_USER', userInfo().username));
      }
      if (!stopFile || !existsSync(stopFile)) return Promise.reject(new GateStartError('GATE_STOP_FILE_REQUIRED', String(stopFile)));
      // Windows пускает слушать 127.0.0.1, когда тот же порт уже занят «на всех адресах» (0.0.0.0) — проверено
      // тестом. Поэтому сначала пробное занятие 0.0.0.0: занято — чужой слушатель, отказ старта.
      return probeWildcard(port).then(() => new Promise((resolve, reject) => {
        const onError = (e) => {
          server.off('listening', onListening);
          log({ ev: 'gate_alarm', code: e.code === 'EADDRINUSE' ? 'GATE_PORT_BUSY' : 'GATE_LISTEN_FAILED' });
          reject(new GateStartError(e.code === 'EADDRINUSE' ? 'GATE_PORT_BUSY' : 'GATE_LISTEN_FAILED', String(port)));
        };
        const onListening = () => { server.off('error', onError); resolve(server.address()); };
        server.once('error', onError);
        server.once('listening', onListening);
        server.listen({ host: GATE_HOST, port, exclusive: true });
      }), (e) => {
        log({ ev: 'gate_alarm', code: e.code });
        throw e;
      });
    },
    close() { return new Promise((r) => server.close(() => r())); },
  };
}
