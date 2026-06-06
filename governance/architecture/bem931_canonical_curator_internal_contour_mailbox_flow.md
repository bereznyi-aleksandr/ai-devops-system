# BEM-931 | Universal Curator / Internal Contour / Mailbox Flow

Updated: 2026-06-06
Status: canonical draft
Owner: DIRECTOR_CURATOR
Applies to: OPERATOR and any EXTERNAL_AUDITOR

## Purpose

This document fixes the universal routing scheme for tasks that enter the Director Curator.

The initiator may be:

- OPERATOR
- EXTERNAL_AUDITOR_GPT
- EXTERNAL_AUDITOR_CLAUDE- any other approved EXTERNAL_AUDITOR_* role

The initiator must be preserved through the whole flow.

The return path depends on the initiator:

- if initiator is OPERATOR, result returns directly to OPERATOR as a curated report;
- if initiator is EXTERNAL_AUDITOR_*, result is written to that auditor's mailbox and the OPERATOR is notified which external auditor must be opened.

## Roles

### OPERATOR

Strategic human operator.

Can initiate a task directly.

If OPERATOR is the initiator:
- DIRECTOR_CURATOR returns the result directly to OPERATOR;
- mailbox is not required;
- OPERATOR receives only a curated report in canonical format.

### EXTERNAL_AUDITOR

Any approved external audit role.

Examples:
- EXTERNAL_AUDITOR_GPT
- EXTERNAL_AUDITOR_CLAUDE

If EXTERNAL_AUDITOR is the initiator:
- DIRECTOR_CURATOR preserves initiator metadata;
- INTERNAL_AUDITOR writes the verified result to the initiator's mailbox return path;
- DIRECTOR_CURATOR notifies OPERATOR which external auditor chat must be opened.

### DIRECTOR_CURATOR

Curator of the General Director.

Responsibilities:
- receives requests from OPERATOR or any EXTERNAL_AUDITOR;
- preserves initiator_role, initiator_return_mode, initiator_mailbox_return_path if present;
- escalates strategic decisions to GENERAL_DIRECTOR;
- creates tasks for INTERNAL_CONTOUR;
- receives completion notice from INTERNAL_AUDITOR;
- returns the result using the correct return path.

### GENERAL_DIRECTOR

Decision owner.

Allowed decisions:
- APPROVED
- APPROVED_WITH_NOTES
IChANGE_REQUIRED
- BLOCKED
- NEED_INTERNAL_AUDIT

### INTERNAL_CONTOUR

Internal execution system.

Roles:
- ANALYST
- AUDITOR
- EXECUTOR

Canonical loop:

1. ANALYST prepares TASK_DRAFT.
2. AUDITOR reviews TASK_DRAFT.
3. If AUDITOR returns CHANGE_REQUIRED, task returns to ANALYST.
4. If AUDITOR returns BLOCKED, task stops.
5. If AUDITOR returns APPROVED_FOR_EXECUTION, task goes to EXECUTOR.
6. EXECUTOR performs only the approved task.
7. EXECUTOR sends EXECUTION_RESULT to AUDITOR.
8. AUDITOR reviews EXECUTION_RESULT.
9. If AUDITOR returns CHANGE_REQUIRED, result goes back to ANALYST with audit remarks.
10. ANALYST updates the task and sends it again to AUDITOR.
11. Loop continues until ACCEPTED or BLOCKED.
12. Only after ACCEPTED, AUDITOR sends completion feedback to DIRECTOR_CURATOR.
13. Only after ACCEPTED, AUDITOR writes to mailbox if the initiator return mode requires mailbox.

## Universal Return Modes

### Mode A: OPERATOR initiated task

Used when:
- initiator_role = OPERATOR

Return path:

OPERATOR
-> DIRECTOR_CURATOR
-> GENERAL_DIRECTOR if needed
-> INTERNAL_CONTOUR
-> INTERNAL_AUDITOR
-> DIRECTOR_CURATOR
-> OPERATOR

Mailbox:
- not required;
- not used for normal completion;
- result is delivered as a curator report.

Operator message:
- no raw mailbox;
- no internal logs;
- only canonical report.

### Mode B: External auditor initiated task

Used when:
- initiator_role starts with EXTERNAL_AUDITOR_

Return path:

EXTERNAL_AUDITOR_*
-> DIRECTOR_CURATOR
-> GENERAL_DIRECTOR if needed
-> INTERNAL_CONTOUR
-> INTERNAL_AUDITOR
-> DIRECTOR_CURATOR
-> OPERATOR notification
-> OPERATOR opens the initiating external auditor
-> EXTERNAL_AUDITOR_* reads mailbox

Mailbox:
- required;
- INTERNAL_AUDITOR writes verified result to initiator_mailbox_return_path.

Operator message:
- must say which external auditor to open;
- must include exact mailbox path or file;
- must not include raw mailbox content.

## Request Metadata Requirement

Every request to DIRECTOR_CURATOR must include initiator metadata.

For OPERATOR:

```json
{
  "initiator_role": "OPERATOR",
  "initiator_return_mode": "DIRECT_OPERATOR_REPORT",
  "initiator_chat_required": "none",
  "initiator_mailbox_return_path": "none",
  "initiator_request_id": "BEM-931"
}
```

For GPT:

```json
{
  "initiator_role": "EXTERNAL_AUDITOR_GPT",
  "initiator_return_mode": "MAILBOX_AND_OPERATOR_WAKE",
  "initiator_chat_required": "Open GPT Custom GPT",
  "initiator_mailbox_return_path": "governance/audit_mailbox/director_curator_to_external_auditor_gpt/",
  "initiator_request_id": "BEM-931"
}
```

For Claude:

```json
{
  "initiator_role": "EXTERNAL_AUDITOR_CLAUDE",
  "initiator_return_mode": "MAILBOX_AND_OPERATOR_WAKE",
  "initiator_chat_required": "Open Claude Chat",
  "initiator_mailbox_return_path": "governance/audit_mailbox/director_curator_to_external_auditor_claude/",
  "initiator_request_id": "BEM-931"
}
```

## Operator Direct Report Format

For OPERATOR-initiated tasks, DIRECTOR_CURATOR sends only:

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

If operator decision is required, replace the final line with one concrete question.

## External Auditor Wake Message Format

For EXTERNAL_AUDITOR initiated tasks, DIRECTOR_CURATOR may send a short Telegram notification:

```text
BEM-931 | RESULT READY

ДЛЯ КОГО:
EXTERNAL_AUDITOR_GPT

ЧТО ОТКРЫТЫ:
Open GPT Custom GPT

MAILBOX:
governance/audit_mailbox/director_curator_to_external_auditor_gpt/<file>.md
P����
