// ДОКУМЕНТ: zavod/catalog/P1_telegram_bot/acceptance/selftest/bad_bot.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:48 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 07:48 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: заведомо плохой бот для проверки самой приёмки: меню без кнопок, ответ «ok» на всё,
//   токен в тексте ответа и вызов метода вне списка. Приёмка обязана сказать FAIL. Это не продукт P1.
// ОГРАНИЧЕНИЯ: работает только с заглушкой (TELEGRAM_API_BASE); токен — тестовое значение прогона.

const api = (m, body) => fetch(`${process.env.TELEGRAM_API_BASE}/bot${process.env.BOT_TOKEN}/${m}`, {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body || {}) }).then((r) => r.json());

let offset = 0;
await api('getChat', { chat_id: 1 });
for (;;) {
  const r = await api('getUpdates', { offset, timeout: 1 });
  for (const u of r.result || []) {
    offset = u.update_id + 1;
    const chat = u.message?.chat.id ?? u.callback_query?.from.id;
    await api('sendMessage', { chat_id: chat, text: `ok ${process.env.BOT_TOKEN}` });
  }
}
