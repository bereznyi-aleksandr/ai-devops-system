# Cloudflare Worker: деплой и настройка

## Что это

Worker получает сообщение от Telegram мгновенно (webhook) →
диспатчит GitHub Actions codex-local.yml с role=curator.
Cron `telegram-poll.yml` после этого можно отключить.

## Деплой — 4 шага

### Шаг 1: Создать Worker

1. Зайти на https://dash.cloudflare.com
2. Workers & Pages → Create → Create Worker
3. Назвать: `tg-curator-webhook`
4. Нажать Edit Code
5. Вставить содержимое `telegram-webhook.js` полностью
6. Нажать Deploy

### Шаг 2: Добавить секреты в Worker

В настройках Worker → Settings → Variables → Add variable (тип: Secret):

| Переменная | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен бота (из Telegram @BotFather) |
| `GH_PAT` | GitHub Personal Access Token (тот же что AI_SYSTEM_GITHUB_PAT) |
| `GH_REPO` | `bereznyi-aleksandr/ai-devops-system` |

### Шаг 3: Зарегистрировать webhook в Telegram

Выполнить один раз (заменить значения):

```bash
curl "https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url=https://tg-curator-webhook.{CF_SUBDOMAIN}.workers.dev/webhook"
```

Проверить что webhook зарегистрирован:
```bash
curl "https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

### Шаг 4: Отключить cron polling (опционально)

После успешного теста webhook — отключить `telegram-poll.yml`:
добавить в начало файла `if: false` на job уровне,
или удалить `schedule` триггер оставив только `workflow_dispatch`.

## Как работает после деплоя

```
Оператор пишет в Telegram
    ↓ (мгновенно, <1 сек)
Cloudflare Worker получает POST от Telegram
    ↓
Worker диспатчит codex-local.yml (role=curator, task=текст сообщения)
    ↓
Worker отправляет подтверждение оператору: "⚡ Получено. Передано куратору"
    ↓
GitHub Actions запускает Codex CLI как curator
    ↓
Codex выполняет задачу → отправляет результат в Telegram через curl
```

## Переменные которые Worker передаёт в GitHub Actions

```json
{
  "role": "curator",
  "provider": "gpt_codex",
  "trace_id": "tg_12345_20260608T170000Z",
  "task_type": "telegram_operator_message",
  "task": "текст сообщения оператора",
  "chat_id": "601442777",
  "message_id": "456"
}
```

`chat_id` и `message_id` теперь доступны Codex curator для ответа напрямую.
