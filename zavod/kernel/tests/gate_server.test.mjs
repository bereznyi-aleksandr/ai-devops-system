// ДОКУМЕНТ: tests/gate_server.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 10:15 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 10:15 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: проверки местного входа привратника без базы (проект Z-TRANSPORT-01 v0.3 §3.4, §5): только
//   127.0.0.1; занятый порт — отказ старта; чужой метод, путь, тип тела, большое тело, нет X-Zavod-Gate, есть
//   Origin — отказы; подпись /hello и чужой ключ; предел попыток; чужой пользователь ОС и нет файла остановки.

import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import net from 'node:net';
import { generateKeyPairSync } from 'node:crypto';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createGateServer, createLimiter, MAX_BODY, ENROLL_PER_SESSION, ENROLL_TOTAL } from '../src/gate_server.mjs';
import { createGateClient } from '../src/gate_client.mjs';

const dir = mkdtempSync(join(tmpdir(), 'zavod-gate-'));
const STOP = join(dir, 'stop.json');
writeFileSync(STOP, '{"stopped":false}');
const gateKey = generateKeyPairSync('ed25519');
const otherKey = generateKeyPairSync('ed25519');

async function freePort() {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => resolve(p)); });
  });
}

async function startGate(extra = {}) {
  const port = await freePort();
  const seen = [];
  const gate = createGateServer({ port, privateKey: gateKey.privateKey, stopFile: STOP,
    onCommand: async (b) => { seen.push(b); return { status: 200, body: { ok: true, echo: b.type } }; }, ...extra });
  await gate.start();
  return { gate, port, seen };
}

// Сырой запрос: заголовки и тело как заданы, без добавок клиента.
function raw(port, { method = 'POST', path = '/command', headers = {}, body = '' } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port, method, path, headers }, (res) => {
      const c = [];
      res.on('data', (d) => c.push(d));
      res.on('end', () => {
        let j = null;
        try { j = JSON.parse(Buffer.concat(c).toString('utf8')); } catch { j = null; }
        resolve({ status: res.statusCode, body: j, headers: res.headers });
      });
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

const GOOD = { 'content-type': 'application/json', 'x-zavod-gate': '1' };

test('слушает только 127.0.0.1; верный запрос доходит до onCommand; ответ без разрешений CORS', async () => {
  const { gate, port, seen } = await startGate();
  try {
    assert.equal(gate.server.address().address, '127.0.0.1');
    const r = await raw(port, { headers: GOOD, body: JSON.stringify({ type: 'Ping' }) });
    assert.equal(r.status, 200);
    assert.equal(r.body.echo, 'Ping');
    assert.equal(seen.length, 1);
    assert.equal(r.headers['access-control-allow-origin'], undefined);
  } finally { await gate.close(); }
});

test('отказы границы: метод, путь, тип тела, заголовок, Origin, плохой JSON, большое тело', async () => {
  const { gate, port, seen } = await startGate();
  try {
    const body = JSON.stringify({ type: 'Ping' });
    const cases = [
      [{ method: 'GET', headers: GOOD }, 405, 'GATE_METHOD'],
      [{ method: 'OPTIONS', headers: { ...GOOD, origin: 'https://x.example' } }, 403, 'GATE_ORIGIN_FORBIDDEN'],
      [{ path: '/internal/health', headers: GOOD, body }, 404, 'GATE_PATH'],
      [{ path: '/command?x=1', headers: GOOD, body }, 404, 'GATE_PATH'],
      [{ headers: { 'content-type': 'text/plain', 'x-zavod-gate': '1' }, body }, 415, 'GATE_CONTENT_TYPE'],
      [{ headers: { 'content-type': 'application/json' }, body }, 403, 'GATE_HEADER_REQUIRED'],
      [{ headers: { ...GOOD, 'x-zavod-gate': '0' }, body }, 403, 'GATE_HEADER_REQUIRED'],
      [{ headers: { ...GOOD, origin: 'null' }, body }, 403, 'GATE_ORIGIN_FORBIDDEN'],
      [{ headers: GOOD, body: '{bad' }, 400, 'GATE_BAD_JSON'],
      [{ headers: GOOD, body: '[1]' }, 400, 'GATE_BAD_JSON'],
      [{ headers: GOOD, body: 'x'.repeat(MAX_BODY + 1) }, 413, 'GATE_BODY_TOO_LARGE'],
    ];
    for (const [req, status, code] of cases) {
      const r = await raw(port, req);
      assert.equal(r.status, status, code);
      assert.equal(r.body.code, code);
    }
    // большое тело без длины в заголовке (по частям) — тот же отказ
    const chunked = await new Promise((resolve) => {
      const req = http.request({ host: '127.0.0.1', port, method: 'POST', path: '/command',
        headers: { ...GOOD, 'transfer-encoding': 'chunked' } }, (res) => { res.resume(); resolve(res.statusCode); });
      req.on('error', () => resolve('reset'));
      for (let i = 0; i < 80; i++) req.write('x'.repeat(1024));
      req.end();
    });
    assert.ok(chunked === 413 || chunked === 'reset', String(chunked));
    assert.equal(seen.length, 0, 'ни один отвергнутый запрос не дошёл до onCommand');
  } finally { await gate.close(); }
});

test('занятый порт — отказ старта (второй привратник и чужой слушатель на всех адресах)', async () => {
  const { gate, port } = await startGate();
  try {
    const second = createGateServer({ port, privateKey: gateKey.privateKey, stopFile: STOP, onCommand: async () => ({}) });
    await assert.rejects(second.start(), (e) => e.code === 'GATE_PORT_BUSY');
  } finally { await gate.close(); }
  const port2 = await freePort();
  const squatter = net.createServer();
  await new Promise((r) => squatter.listen({ port: port2, host: '0.0.0.0' }, r));
  try {
    const g = createGateServer({ port: port2, privateKey: gateKey.privateKey, stopFile: STOP, onCommand: async () => ({}) });
    await assert.rejects(g.start(), (e) => e.code === 'GATE_PORT_BUSY');
  } finally { await new Promise((r) => squatter.close(r)); }
});

test('чужой пользователь ОС и нет файла остановки — отказ старта', async () => {
  const port = await freePort();
  const a = createGateServer({ port, privateKey: gateKey.privateKey, stopFile: STOP, expectedUser: 'zavod-kernel-not-me',
    onCommand: async () => ({}) });
  await assert.rejects(a.start(), (e) => e.code === 'GATE_WRONG_OS_USER');
  const b = createGateServer({ port, privateKey: gateKey.privateKey, stopFile: join(dir, 'missing.json'), onCommand: async () => ({}) });
  await assert.rejects(b.start(), (e) => e.code === 'GATE_STOP_FILE_REQUIRED');
  const c = createGateServer({ port, privateKey: gateKey.privateKey, onCommand: async () => ({}) });
  await assert.rejects(c.start(), (e) => e.code === 'GATE_STOP_FILE_REQUIRED');
});

test('/hello: подпись сходится с открытым ключом; чужой ключ — клиент ничего не отправляет', async () => {
  const { gate, port, seen } = await startGate();
  try {
    const good = createGateClient({ port, publicKey: gateKey.publicKey });
    assert.equal(await good.hello(), true);
    const r = await good.command({ type: 'EnrollSession', payload: { session: 'local_a' } });
    assert.equal(r.status, 200);
    assert.equal(seen.length, 1);
    const bad = createGateClient({ port, publicKey: otherKey.publicKey });
    await assert.rejects(bad.command({ type: 'EnrollSession', payload: { session: 'local_a', claim_code: 'x' } }),
      (e) => e.code === 'GATE_NOT_AUTHENTIC');
    assert.equal(seen.length, 1, 'при чужом ключе команда не ушла');
    // плохое одноразовое число и лишние поля — отказ
    for (const b of [{ nonce: 'abc' }, { nonce: 'a'.repeat(64), x: 1 }, {}]) {
      const h = await raw(port, { path: '/hello', headers: GOOD, body: JSON.stringify(b) });
      assert.equal(h.body.code, 'GATE_BAD_NONCE');
    }
  } finally { await gate.close(); }
});

test('самозванец на порту без ключа привратника: клиент отказывает до отправки', async () => {
  const port = await freePort();
  const got = [];
  const fake = http.createServer((req, res) => {
    const c = [];
    req.on('data', (d) => c.push(d));
    req.on('end', () => {
      got.push(req.url);
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ ok: true, namespace: 'zavod-gate-hello@v1', port, signature: Buffer.alloc(64).toString('base64') }));
    });
  });
  await new Promise((r) => fake.listen(port, '127.0.0.1', r));
  try {
    const cl = createGateClient({ port, publicKey: gateKey.publicKey });
    await assert.rejects(cl.command({ type: 'Ping' }), (e) => e.code === 'GATE_NOT_AUTHENTIC');
    assert.deepEqual(got, ['/hello'], 'на /command ничего не ушло');
  } finally { await new Promise((r) => fake.close(r)); }
});

test('предел попыток получения пропуска: на сессию и всего; база не участвует', async () => {
  let t = 0;
  const lim = createLimiter({ now: () => t });
  for (let i = 0; i < ENROLL_PER_SESSION; i++) assert.equal(lim.allow('s1'), true);
  assert.equal(lim.allow('s1'), false);
  let ok = ENROLL_PER_SESSION;
  for (let i = 0; i < 40; i++) if (lim.allow('s' + (i + 2))) ok++;
  assert.equal(ok, ENROLL_TOTAL);
  t += 60_001;
  assert.equal(lim.allow('s1'), true, 'окно прошло');

  const { gate, port, seen } = await startGate({ limiter: createLimiter({ perSession: 2, total: 5 }) });
  try {
    const send = () => raw(port, { headers: GOOD, body: JSON.stringify({ type: 'EnrollSession', payload: { session: 'local_z' } }) });
    assert.equal((await send()).status, 200);
    assert.equal((await send()).status, 200);
    const r = await send();
    assert.equal(r.status, 429);
    assert.equal(r.body.code, 'GATE_RATE_LIMIT');
    assert.equal(seen.length, 2);
  } finally { await gate.close(); }
});

test('медленный запрос обрывается по времени', async () => {
  const { gate, port, seen } = await startGate({ requestMs: 300 });
  try {
    const result = await new Promise((resolve) => {
      const req = http.request({ host: '127.0.0.1', port, method: 'POST', path: '/command',
        headers: { ...GOOD, 'content-length': '20' } }, (res) => { res.resume(); resolve(res.statusCode); });
      req.on('error', () => resolve('reset'));
      req.write('{"type":');
      setTimeout(() => { try { req.end('"x"}'); } catch {} }, 3000);
    });
    assert.ok(result === 408 || result === 'reset', String(result));
    assert.equal(seen.length, 0);
  } finally { await gate.close(); }
});
