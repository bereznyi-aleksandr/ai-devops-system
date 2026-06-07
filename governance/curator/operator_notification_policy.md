# BEM-931 | Политика уведомлений оператора (Operator Notification Policy)

Updated: 2026-06-07
Owner: Куратор директора (DIRECTOR_CURATOR)
Channel: Telegram
Format: plaintext, human-readable, mobile-first

## 1. Главный принцип

Оператор получает не сырой лог и не склеенную строку, а короткий читаемый отчёт.

Запрещено:
- склеивать весь отчёт в одну строку;
- писать чек-лист через пробел;
- добавлять raw mailbox;
- добавлять repository dump;
- добавлять risks/logs/stack traces;
- добавлять внутренние рассуждения.

## 2. Канонический формат обычного отчёта

```text
BEM-HOURLY | ОТЧЁТ ОПЕРАТОРУ
2026-06-07 | 14:00 (UTC+3)

ЭТАП:
2/2 (100%)

ДОРОЖНАЯ КАРТА:
2/2 (100%)

ЧЕК-ЛИСТ:
✅ Gate 5 — GPT MCP/PAT runtime PASS
✅ Gate 6 — Claude external audit receipt PASS
⬜ <не сделано>
⛔ <блокер>

ВОПРОС ОПЕРАТОРУ:
нет
```

## 3. Правила читаемости Telegram

Обязательно:
- каждая секция начинается с новой строки;
- после заголовка секции ставится перенос строки;
- каждый пункт чек-листа находится на отдельной строке;
- каждый пункт начинается с маркера статуса;
- между крупными секциями есть пустая строка;
- общий отчёт желательно держать до 900 символов.

Маркеры:
- `✅` — сделано / принято / подтверждено;
- `⬜` — не сделано / ожидает;
- `⛔` — блокер;
- `⚠️` — требует внимания, но не блокирует.

## 4. Формат вопроса оператору

Если нужен оператор, последняя секция заменяется на один конкретный вопрос:

```text
ВОПРОС ОПЕРАТОРУ:
<один конкретный вопрос>
```

Если вопроса нет:

```text
ВОПРОС ОПЕРАТОРУ:
нет
```

## 5. Инициатор-зависимый возврат

Если инициатор — OPERATOR:
- mailbox не нужен;
- результат возвращается оператору напрямую в формате выше.

Если инициатор — EXTERNAL_AUDITOR_*:
- аудитор пишет результат в mailbox инициатора;
- куратор отправляѵт оператору короткое wake-up сообщение;
- сообщение должно явно назвать, кого открыть: GPT или Claude.

## 6. Формат wake-up для внешнего аудитора

```text
BEM-931 | RESULT READY

ДЛЯ КОГО:
EXTERNAL_AUDITOR_GPT

ЧТО ОТКРЫТЬ:
Open GPT Custom GPT

MAILBOX:
governance/audit_mailbox/director_curator_to_external_auditor_gpt/<file>.md
```

или

```text
BEM-931 | RESULT READY

ДЛЯ КОГО:
EXTERNAL_AUDITOR_CLAUDE

ЧТО ОТКРЫТЬ:
Open Claude Chat

MAILBOX:
governance/audit_mailbox/director_curator_to_external_auditor_claude/<file>.md
```

## 7. Authority

Нормальный источник уведомления оператора:
- Куратор директора (DIRECTOR_CURATOR).

Не нормальный источник:
- GitHub mailbox watcher.

GitHub mailbox watcher допускается только как diagnostic fallback / emergency recovery.
