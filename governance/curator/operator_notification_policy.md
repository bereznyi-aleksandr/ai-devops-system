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

```text
DIRECTOR_CURATOR
```

Not GitHub mailbox watcher.

## Initiator-Sensitive Return Rule

DIRECTOR_CURATOR must preserve who initiated the task.

Allowed initiators:

- OPERATOR
- EXTERNAL_AUDITOR_GPT
- EXTERNAL_AUDITOR_CLAUDE- any approved EXTERNAL_AUDITOR_* role

### If initiator is OPERATOR

Return mode:

```text
DIRECT_OPERATOR_REPORT
```

Rules:

- no mailbox is required;
- no external auditor wake-up is required;
- INTERNAL_AUDITOR notifies DIRECTOR_CURATOR that the task is complete;
- DIRECTOR_CURATOR sends result directly to OPERATOR;
- report uses the mandatory operator format.

### If initiator is EXTERNAL_AUDITOR_*

Return mode:

```text
MAILBOX_AND_OPERATOR_WAKE
```

Rules:

- INTERNAL_AUDITOR writes verified result to the initiator's mailbox return path;
- INTERNAL_AUDITOR notifies DIRECTOR_CURATOR that the task is complete;
- DIRECTOR_CURATOR sends a short Telegram wake-up to OPERATOR;
- wake-up must say exactly which external auditor must be opened.

Example for GPT:

```text
BEM-931 | RESULT READY

ДЛЯ КОГО:
EXTERNAL_AUDITOR_GPT

ЧТО ОТКРЫТЫ:
Open GPT Custom GPT

MAILBOX:
governance/audit_mailbox/director_curator_to_external_auditor_gpt/<file>.md
```

Example for Claude:

```text
BEM-931 | RESULT READY

ДЛЯ КОГО:
EXTERNAL_AUDITOR_CLAUDE
ЧТО ОТКРЫТЬ:
Open Claude Chat

MAILBOX:
governance/audit_mailbox/director_curator_to_external_auditor_claude/<file>.md
```

## GitHub Mailbox Notifier Status

The GitHub Actions mailbox notifier is deprecated for normal operator notifications.

Allowed use:

- manual diagnostic fallback;
- emergency recovery if DIRECTOR_CURATOR notification is broken.

Forbidden use:

- routine operator notification for every mailbox event;
- raw mailbox spam to operator.
