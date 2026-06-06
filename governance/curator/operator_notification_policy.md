# BEM-931 | Operator Notification Policy

Updated: 2026-06-06
Owner: DIRECTOR_CURATOR
Channel: Telegram
Format: plaintext canon

## Mandatory Operator Message Format

Regular operator reports and notifications must contain only:

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

If an operator decision is required, replace the final line with exactly one question:

```text
ВОПРОС ОПЕРАТОРУ:
<один конкретный вопрос>
```

## Forbidden in Operator Reports

Do not include:
- raw mailbox content;
- mailbox section;
- repository changes section;
- risks section;
- active queue dump;
- logs;
- stack traces;
- internal prompts;
- detailed internal reasoning.

## Canonical Notification Authority

The primary authority for operator notification is:

DIRECTOR_CURATOR

Not GitHub mailbox watcher.

For external audit tasks, the standard path is:

1. INTERNAL_AUDITOR accepts the result.
2. INTERNAL_AUDITOR notifies DIRECTOR_CURATOR that the task is complete.
3. INTERNAL_AUDITOR writes verified result to mailbox for EXTERNAL_AUDITOR_GPT.
4. DIRECTOR_CURATOR sends a short Telegram notification to OPERATOR:
   "For external auditor GPT, a result is ready. Open Custom GPT and read mailbox file: <path>."
5. OPERATOR opens EXTERNAL_AUDITOR_GPT.
6. EXTERNAL_AUDITOR_GPT reads mailbox via MCP.

## GitHub Mailbox Notifier Status

The GitHub Actions mailbox notifier is deprecated for normal operator notifications.

Allowed use:
- manual diagnostic fallback;
- emergency recovery if DIRECTOR_CURATOR notification is broken.

Forbidden use:
- routine operator notification for every mailbox event;
- raw mailbox spam to operator.
