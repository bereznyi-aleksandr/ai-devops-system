// ДОКУМЕНТ: src/gate_client.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 10:15 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 10:15 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: клиент привратника для мода и проверок (проект Z-TRANSPORT-01 v0.3 §3.4): сначала /hello со свежим
//   одноразовым числом и проверка подписи открытым ключом из правил (zavod/rules/GATE_KEY.pub), и только после
//   этого отправка команды с кодом выдачи или пропуском. Подпись не сошлась — ничего не отправляется.
// ОГРАНИЧЕНИЯ: пропуск и код выдачи клиент не хранит и не пишет в журнал; держит их вызывающий.

import { randomBytes, verify as edVerify, createPublicKey } from 'node:crypto';
import { GATE_HOST, HELLO_NAMESPACE, helloMessage } from './gate_server.mjs';

export class GateClientError extends Error {
  constructor(code) { super(code); this.code = code; }
}

const HEADERS = { 'content-type': 'application/json', 'x-zavod-gate': '1' };

// createGateClient({ port, publicKey, fetchImpl? }) -> { hello, command }
export function createGateClient({ port, publicKey, fetchImpl = fetch }) {
  const key = typeof publicKey === 'string' || Buffer.isBuffer(publicKey) ? createPublicKey(publicKey) : publicKey;
  const base = `http://${GATE_HOST}:${port}`;
  const post = async (path, body) => {
    const r = await fetchImpl(base + path, { method: 'POST', headers: HEADERS, body: JSON.stringify(body),
      signal: AbortSignal.timeout(10_000) });
    let data = null;
    try { data = await r.json(); } catch { data = null; }
    return { status: r.status, body: data };
  };

  async function hello() {
    const nonce = randomBytes(32).toString('hex');
    const r = await post('/hello', { nonce });
    const b = r.body;
    if (r.status !== 200 || !b || b.ok !== true || b.namespace !== HELLO_NAMESPACE || b.port !== port
      || typeof b.signature !== 'string') throw new GateClientError('GATE_HELLO_REFUSED');
    let ok = false;
    try { ok = edVerify(null, helloMessage(port, nonce), key, Buffer.from(b.signature, 'base64')); } catch { ok = false; }
    if (!ok) throw new GateClientError('GATE_NOT_AUTHENTIC');
    return true;
  }

  // Каждая команда — после свежего /hello: самозванец на порту не получит ни кода выдачи, ни пропуска.
  async function command(body) {
    await hello();
    return post('/command', body);
  }

  return { hello, command };
}
