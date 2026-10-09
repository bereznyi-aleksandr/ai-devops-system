// ДОКУМЕНТ: zavod/catalog/P1_telegram_bot/acceptance/telegram_stub.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:46 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 07:46 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: заглушка Telegram Bot API для приёмки P1 (E5-4) без настоящего токена и без сети:
//   127.0.0.1, пути /bot<токен>/<метод>, тела JSON, form-urlencoded и multipart (sendDocument).
//   Длинный опрос getUpdates, sendMessage, sendDocument, answerCallbackQuery, getMe, deleteWebhook,
//   setMyCommands. Каждый вызов записывается (calls) — по ним приёмка проверяет ответы, список методов
//   и отсутствие токена в исходящих данных. Неизвестный токен — 401, как у настоящего API.
// ОГРАНИЧЕНИЯ: подмножество Bot API, нужное брифу P1; поведение настоящего Telegram проверяется после OD-3.

import { createServer } from 'node:http';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseMultipart(buf, boundary) {
  const out = {};
  const sep = Buffer.from(`--${boundary}`);
  let pos = buf.indexOf(sep);
  while (pos !== -1) {
    const start = pos + sep.length;
    if (buf.slice(start, start + 2).toString() === '--') break;
    const next = buf.indexOf(sep, start);
    if (next === -1) break;
    const part = buf.slice(start + 2, next - 2); // без \r\n после разделителя и перед следующим
    const h = part.indexOf('\r\n\r\n');
    const head = part.slice(0, h).toString('utf8');
    const body = part.slice(h + 4);
    const name = /name="([^"]+)"/.exec(head)?.[1];
    const filename = /filename="([^"]*)"/.exec(head)?.[1];
    if (name) out[name] = filename !== undefined ? { filename, content: body } : body.toString('utf8');
    pos = next;
  }
  return out;
}

function parseBody(req, buf) {
  const type = req.headers['content-type'] || '';
  let p = {};
  if (type.startsWith('application/json')) p = buf.length ? JSON.parse(buf.toString('utf8')) : {};
  else if (type.startsWith('application/x-www-form-urlencoded')) p = Object.fromEntries(new URLSearchParams(buf.toString('utf8')));
  else if (type.startsWith('multipart/form-data')) p = parseMultipart(buf, /boundary=([^;]+)/.exec(type)[1].replace(/"/g, ''));
  const url = new URL(req.url, 'http://x');
  for (const [k, v] of url.searchParams) if (!(k in p)) p[k] = v;
  if (typeof p.reply_markup === 'string') { try { p.reply_markup = JSON.parse(p.reply_markup); } catch { /* как есть */ } }
  return p;
}

export class TelegramStub {
  constructor() {
    this.bots = new Map(); // токен → { id, updates, nextUpdate, nextMessage }
    this.calls = [];
    this.server = null;
  }

  addBot(token, id) {
    this.bots.set(token, { id, updates: [], nextUpdate: 1, nextMessage: 1 });
  }

  async start() {
    this.server = createServer((req, res) => {
      const chunks = [];
      req.on('data', (c) => chunks.push(c));
      req.on('end', () => this.handle(req, Buffer.concat(chunks)).then(
        (r) => { res.writeHead(r.status, { 'content-type': 'application/json' }); res.end(JSON.stringify(r.body)); },
        (e) => { res.writeHead(500); res.end(JSON.stringify({ ok: false, description: String(e.message) })); }));
    });
    await new Promise((r) => this.server.listen(0, '127.0.0.1', r));
    this.base = `http://127.0.0.1:${this.server.address().port}`;
    return this.base;
  }

  close() {
    this.closed = true;
    this.server?.closeAllConnections?.();
    return new Promise((r) => (this.server ? this.server.close(() => r()) : r()));
  }

  async handle(req, buf) {
    const m = /^\/bot([^/]+)\/([A-Za-z]+)/.exec(new URL(req.url, 'http://x').pathname);
    if (!m) return { status: 404, body: { ok: false, error_code: 404, description: 'Not Found' } };
    const [, token, method] = m;
    const bot = this.bots.get(token);
    const params = parseBody(req, buf);
    const call = { token, method, params, raw: buf.toString('latin1'), url: req.url };
    this.calls.push(call);
    if (!bot) return { status: 401, body: { ok: false, error_code: 401, description: 'Unauthorized' } };
    const ok = (result) => ({ status: 200, body: { ok: true, result } });
    switch (method) {
      case 'getMe': return ok({ id: bot.id, is_bot: true, first_name: 'P1 test', username: `p1_test_${bot.id}_bot` });
      case 'deleteWebhook': case 'setMyCommands': case 'answerCallbackQuery': return ok(true);
      case 'getUpdates': {
        const offset = Number(params.offset || 0);
        const wait = Math.min(Number(params.timeout || 0), 2) * 1000;
        const t0 = Date.now();
        let ready = bot.updates.filter((u) => u.update_id >= offset);
        while (!ready.length && Date.now() - t0 < wait && !this.closed) {
          await sleep(50);
          ready = bot.updates.filter((u) => u.update_id >= offset);
        }
        return ok(ready.slice(0, Number(params.limit || 100)));
      }
      case 'sendMessage': case 'sendDocument': {
        const message = { message_id: bot.nextMessage++, date: Math.floor(Date.now() / 1000),
          chat: { id: Number(params.chat_id), type: 'private' } };
        if (method === 'sendMessage') message.text = String(params.text ?? '');
        else message.document = { file_id: `doc-${message.message_id}`, file_name: params.document?.filename };
        call.result = message;
        return ok(message);
      }
      default: return { status: 400, body: { ok: false, error_code: 400, description: `method ${method} not in stub` } };
    }
  }

  pushText(token, chatId, text) {
    const bot = this.bots.get(token);
    bot.updates.push({ update_id: bot.nextUpdate++, message: { message_id: 100000 + bot.nextUpdate,
      date: Math.floor(Date.now() / 1000), chat: { id: chatId, type: 'private' },
      from: { id: chatId, is_bot: false, first_name: 'Client' }, text } });
  }

  pushCallback(token, chatId, data, messageId) {
    const bot = this.bots.get(token);
    bot.updates.push({ update_id: bot.nextUpdate++, callback_query: { id: `cb-${bot.nextUpdate}`, data,
      from: { id: chatId, is_bot: false, first_name: 'Client' },
      message: { message_id: messageId, date: Math.floor(Date.now() / 1000), chat: { id: chatId, type: 'private' } } } });
  }

  // Исходящие ответы бота в чат (sendMessage и sendDocument).
  outbound(token, chatId) {
    return this.calls.filter((c) => c.token === token && ['sendMessage', 'sendDocument'].includes(c.method)
      && Number(c.params.chat_id) === chatId);
  }
}
