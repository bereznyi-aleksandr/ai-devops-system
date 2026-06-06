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
1. EXTERNAL_AUDITOR_GPTsends message/task through DIRECTOR_CURATOR.
2. DIRECTOR_CURATOR distinguishes working task vs strategic approval.
3. GENERAL_DIRECTOR approves/rejects strategic protocol if required.
4. DIRECTOR_CURATOR assigns to INTERNAL_CONTOUR.
5. INTERNAL_ANALYST prepares task for implementation.
6. INTERNAL_ANALYST sends prepared task to INTERNAL_AUDITOR for pre-execution review.
7. INTERNAL_AUDITOR approves the task or returns it to ANALYST with CHANGE_REQUIRED.
8. If pre-execution review is approved, INTERNAL_EXECUTOR receives the task.
9. INTERNAL_EXECUTOR implements the task.
10. INTERNAL_EXECUTOR sends result to INTERNAL_AUDITOR.
11. INTERNAL_AUDITOR approves the result or returns it to ANALYST with CHANGE_REQUIRED.
12. If result is approved, INTERNAL_AUDITOR writes the verdict to mailbox.
13. MAILBOX_WATCHER detects the verdict.
14. EXTERNAL_AUDITOR_GPT is notified to read mailbox through MCP.
15. Operator receives only final/periodic clean report if needed.

## Internal Contour Review Rule

Analyst does not send tasks directly to Executor.

The only valid internal path is:

If review fails:

Analyst -> Auditor -> Analyst

Then Analyst repairs the task and returns it to Auditor.

If review passes:

Analyst -> Auditor -> Executor -> Auditor

Then Auditor either:
- approves and writes verdict to mailbox; or
- returns to Analyst with CHANGE_REQUIRED.

## Wake Rule

Mailbox watcher should wake the external GPT/operator when there is new mailbox input for GPT.

It should not wake operator for normal mailbox traffic unless manual custom GPT action is required.
