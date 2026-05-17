# BEM-544 | Telegram Live Setup Operator Actions

Дата: 2026-05-17 | 14:36 (UTC+3)

## Что сделано
- `.github/workflows/telegram-outbox-sender.yml` готов к live отправке.
- `scripts/telegram_outbox_pick.py` выбирает queued message.
- `scripts/telegram_delivery_record.py` пишет delivery result.
- Токены не записываются в файлы.

## Что требуется от оператора
Нужно добавить в GitHub Actions Secrets:

| Secret | Что положить |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен бота |
| `TELEGRAM_CHAT_ID` | id чата/канала/группы |

Токен в чат GPT присылать не нужно.
