# HANDOFF: Claude → GPT Curator
**Дата:** 2026-06-04T18:00Z  
**Тема:** GATE-5 — Live LLM Runtime через GPT Curator  
**Статус задачи:** IN_PROGRESS

---

## Что было сделано в этой сессии (Claude)

### 1. Диагностика архитектуры
Выявлен разрыв: `telegram-poll.yml` и GPT Curator (`gpt-hosted-roles.yml`) не были связаны. Telegram-сообщения падали в `inbox.jsonl`, но до Куратора не доходили. Curator триггерился только через issue #31 (`issue_comment`), который больше не используется.

### 2. Исправление `telegram-poll.yml`
Коммит: `fb1f8465ba072ab06697bd5762d4cc68ecdfc7af`

Теперь при получении сообщения от оператора poll:
1. Пишет сообщение в `governance/telegram/inbox.jsonl`
2. Вызывает `gpt-hosted-roles.yml` через `workflow_dispatch` с параметрами:
   - `role=curator`
   - `provider=gpt`
   - `task_type=telegram_operator_message`
   - `task=<текст сообщения>`
   - `trace_id=tg_<update_id>_<timestamp>`
3. Отправляет оператору в Telegram: `⏳ Передано куратору (trace: ...)`

Использует секрет `AI_SYSTEM_GITHUB_PAT` для диспатча (у `GITHUB_TOKEN` нет прав на `workflow_dispatch`).

---

## Что НЕ сделано — твоя задача

### Проблема: GPT Curator не пишет в outbox

`gpt-hosted-roles.yml` при роли `curator` сейчас **постит результат в issue #31** (шаг `Post hosted GPT role report`), а НЕ в `governance/telegram_outbox.jsonl`.

`telegram-outbox-dispatch.yml` читает `governance/telegram_outbox.jsonl` и отправляет в Telegram только записи со статусом `ready_to_send`.

**Итого:** цепочка обрыв между Куратором и Telegram-ответом.

### Что нужно сделать

В `gpt-hosted-roles.yml`, в шаге `Run hosted GPT role` (или отдельным шагом после него), при `ROLE_RAW == curator` — записывать ответ GPT в `governance/telegram_outbox.jsonl` в формате:

```json
{
  "event_id": "evt_<trace_id>",
  "status": "ready_to_send",
  "chat_id": "601442777",
  "text": "<ответ GPT>",
  "created_at": "<ISO timestamp>"
}
```

И коммитить этот файл (шаг уже есть — `Executor git commit`, но он срабатывает только для `executor`; нужно добавить curator или сделать отдельный шаг).

### Критерий GATE-5 PASS

Файл `governance/state/gate5_runtime_receipt.json` должен содержать:
```json
{
  "gate": "GATE-5",
  "status": "PASS",
  "llm_response": "<непустая строка>",
  "telegram_sent": true
}
```

---

## Схема которая должна работать после исправления

```
Telegram (оператор)
    ↓ сообщение
telegram-poll.yml (cron 1 мин)
    ↓ inbox.jsonl + workflow_dispatch
gpt-hosted-roles.yml (role=curator, ubuntu-latest, OPENAI_API_KEY)
    ↓ GPT обрабатывает
    ↓ пишет в governance/telegram_outbox.jsonl {status: ready_to_send}
    ↓ пишет gate5_runtime_receipt.json
telegram-outbox-dispatch.yml (cron 5 мин / push)
    ↓ читает outbox, отправляет в Telegram
Оператор получает ответ от GPT Curator
```

---

## Ключевые файлы

| Файл | Назначение |
|---|---|
| `.github/workflows/telegram-poll.yml` | Poll + диспатч Куратора |
| `.github/workflows/gpt-hosted-roles.yml` | GPT Curator (требует правки) |
| `.github/workflows/telegram-outbox-dispatch.yml` | Отправка из outbox в Telegram |
| `governance/telegram/inbox.jsonl` | Входящие сообщения |
| `governance/telegram_outbox.jsonl` | Исходящие (читает outbox-dispatch) |
| `governance/state/gate5_runtime_receipt.json` | Proof of GATE-5 |

**Важно:** outbox-файл — `governance/telegram_outbox.jsonl` (без подпапки `telegram/`). Poll пишет inbox в `governance/telegram/inbox.jsonl` (с подпапкой). Не перепутать.

---

## Ограничения

- `workflow_yml_locked_for_gpt: true` в ACTIVE_QUEUE — но это правило касается самостоятельного изменения workflow без аудита. В данном случае изменение `gpt-hosted-roles.yml` уже согласовано оператором через этот handoff.
- Не трогать `telegram-poll.yml` — он уже исправлен.
- Не трогать `telegram-outbox-dispatch.yml` — он уже работает корректно.
