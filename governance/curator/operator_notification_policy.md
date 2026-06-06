# BEM-931 | Operator Notification Policy

Updated: 2026-06-06
Owner: Curator
Channel: Telegram
Format: plaintext canon

## Purpose

Operator receives only curated canonical summaries.

Operator must not receive:
- raw mailbox messages;
- raw watcher reports;
- raw logs;
- internal prompts;
- risks section unless it is part of checklist;
- repository-change dumps;
- mailbox dumps.

## Mandatory Operator Report Format

Every regular operator report must contain only:

```text
BEM-HOURLY | OPERATOR REPORT | <timestamp UTC+3>

ЭТАП:
X/Y (Z%)

ДОРОЖНАЯ КАРТА:
X/Y (Z%)

ЧЕК-ЛИСТ:
[x] <сделано>
[ ] <не сделано>
[!] <блокер>

ВОПРОС ОПЕРАТОРУ:
нет
```

If operator action is required, replace the final line with exactly one question:

```text
ВОПРОС ОПЕРАТОРУ:
<один конкретный вопрос>
```

## Rule

No other sections are allowed in regular hourly operator reports.

Allowed sections:
- ЭТАП
- ДОРОЖНАЯ КАРТА
- ЧЕК-ЛИСТ
- ВОПРОС ОПЕРАТОРУ

Forbidden sections:
- изменения за час
- mailbox
- риски
- active queue
- raw logs
- detailed internals

## Agent Communication

Mailbox is for agent-to-agent coordination.

Canonical agent communication loop:
1. GPT sends message/task through curator.
2. Curator assigns work to internal contour.
3. Internal contour completes work.
4. Auditor writes result to mailbox.
5. Mailbox watcher detects result.
6. Watcher wakes hosted GPT role.
7. Hosted GPT role reads mailbox and continues protocol.
8. Operator receives only final/periodic clean report if needed.

## Wake Rule

Mailbox watcher should wake the hosted GPT role when there is new mailbox input for GPT.

It should not wake operator for normal mailbox traffic.
