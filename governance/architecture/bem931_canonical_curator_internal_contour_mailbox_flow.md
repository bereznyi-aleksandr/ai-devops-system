# BEM-931 | Canonical Curator / Internal Contour / Mailbox Flow

Updated: 2026-06-06
Status: canonical draft
Owner: DIRECTOR_CURATOR
Applies to: any EXTERNAL_AUDITOR

## Purpose

This document fixes the universal communication scheme for external audit tasks.

The scheme is not hard-bound to GPT.

Any external auditor may initiate a task:
- EXTERNAL_AUDITOR_GPT
- EXTERNAL_AUDITOR_CLAUDE
- any other approved EXTERNAL_AUDITOR_* role

The initiator must be preserved throughout the whole flow.

## Roles

### OPERATOR

Strategic human operator.

Responsibilities:
- sets strategic direction;
- receives short curated notifications;
- opens the external auditor chat specified by the curator;
- reviews final DOCX/ZIP packae if requested.

### EXTERNAL_AUDITOR

Any approved external audit role.

Examples:
- EXTERNAL_AUDITOR_GPT
- EXTERNAL_AUDITOR_CLAUDE

Responsibilities:
- sends request to DIRECTOR_CURATOR;
- must declare its role/chat_id/mailbox return path as initiator_role and initiator_channel;
- reads mailbox after OPERATOR opens the specified chat;
- reviews the internal contour result;
- either accepts the result, returns CHANGE_REQUIRED, or asks OPERATOR one question.

### DIRECTOR_CURATOR

Curator of the General Director.

Responsibilities:
- receives request from any EXTERNAL_AUDITOR;
- preserves initiator_role, initiator_chat_required, and initiator_mailbox_path;
- escalates strategic decisions to GENERAL_DIRECTOR;
- creates tasks for INTERNAL_CONTOUR;
- receives completion notice from INTERNAL_AUDITOR;
- sends a short Telegram notification to OPERATOR;
- the notification must say which external auditor must be opened.

### GENERAL_DIRECTOR

Decision owner.

Allowed decisions:
- APPROVED
- APPROVED_WITH_NOTES
- CHANGE_REQUIRED
- BLOCKED
- NEED_INTERNAL_AUDIT

### INTERNAL_CONTOUR

Internal execution system.

Roles:
- ANALYST
- AUDITOR
- EXECUTOR

Canonical work loop:

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
13. Only after ACCEPTED, AUDITOR writes verified result to the initiator's mailbox.

## Universal External Audit Integration

The standard internal contour already ends with:

AUDITOR -> DIRECTOR_CURATOR

For an external audit task, two additional actions are required after ACCEPTED:

1. AUDITOR -> MAILBOX
   The auditor writes the verified result to the original initiator's return path.

   Examples of return paths:
   - for EXTERNAL_AUDITOR_GPT: governance/audit_mailbox/director_curator_to_external_auditor_gpt/
   - for EXTERNAL_AUDITOR_CLAUDE: governance/audit_mailbox/director_curator_to_external_auditor_claude/

2. DIRECTOR_CURATOR -> OPERATOR
   The curator sends a short Telegram notification.
   The notification must specify the exact external auditor to wake.

   Example:
   "For EXTERNAL_AUDITOR_GPT, a result is ready. Open GPT Custom GPT and read mailbox file: <path>."

   Example:
   "For EXTERNAL_AUDITOR_CLAUDE, a result is ready. Open Claude Chat and read mailbox file: <path>."

## Universal Flow


1. OPERATOR asks one EXTERNAL_AUDITOR to coordinate a task.

2. The initiating EXTERNAL_AUDITOR sends request to DIRECTOR_CURATOR and includes initiator metadata:
   - initiator_role
   - initiator_chat_required
   - initiator_mailbox_return_path
   - initiator_request_id

3. DIRECTOR_CURATOR preserves this initiator metadata.

4. DIRECTOR_CURATOR checks the request and, if strategic, escalates to GENERAL_DIRECTOR.

5. GENERAL_DIRECTOR decides:

   - APPROVED
   - APPROVED_WITH_NOTES
   - CHANGE_REQUIRED
   - BLOCKED
   - NEED_INTERNAL_AUDIT

6. If internal work is required, DIRECTOR_CURATOR creates a task for INTERNAL_CONTOUR.

7. INTERNAL_CONTOUR executes the canonical loop:

   ANALYST
   -> AUDITOR
   -> EXECUTOR
   -> AUDITOR

   with rework returns through:

   AUDITOR
   -> ANALYST
   -> AUDITOR
   -> EXECUTOR
   -> AUDITOR

8. When result is ACCEPTED:

   INTERNAL_AUDITOR
   -> DIRECTOR_CURATOR

9. For external review:

   INTERNAL_AUDITOR
   -> initiator_mailbox_return_path

10F​. DIRECTOR_CURATOR notifies OPERATOR and specifies which external auditor must be opened.

11. OPERATOR opens the specified external auditor chat.

12. The initiating EXTERNAL_AUDITOR reads mailbox via its available tools/MCP.

13. The initiating EXTERNAL_AUDITOR either:
   - accepts the result and prepares final package;
   - sends CHANGE_REQUIRED back to DIRECTOR_CURATOR;
   - asks OPERATOR one specific question.

## Request Metadata Requirement

Every external auditor request to DIRECTOR_CURATOR must include:

```json
{
  "initiator_role": "EXTERNAL_AUDITOR_GPT",
  "initiator_chat_required": "Open GPT Custom GPT",
  "initiator_mailbox_return_path": "governance/audit_mailbox/director_curator_to_external_auditor_gpt/",
  "initiator_request_id": "BEM-931"
}
```

For Claude:

```json
{
  "initiator_role": "EXTERNAL_AUDITOR_CLAUDE",
  "initiator_chat_required": "Open Claude Chat",
  "initiator_mailbox_return_path": "governance/audit_mailbox/director_curator_to_external_auditor_claude/",
  "initiator_request_id": "BEM-931"
}
```

## Acceptance Criteria

A result is valid only if:

- task was routed through DIRECTOR_CURATOR;
- initiator_role and initiator_mailbox_return_path were preserved;
- strategic decision was owned by GENERAL_DIRECTOR when required;
- internal work followed ANALYST -> AUDITOR -> EXECUTOR -> AUDITOR;
- executor did not receive an unaudited analyst task;
- auditor accepted the final execution result;
- auditor notified DIRECTOR_CURATOR;
- auditor wrote verified result to the initiator's mailbox return path;
- curator notified OPERATOR and specified the correct external auditor to wake;
- the initiating EXTERNAL_AUDITOR reviewed the mailbox result.

## Deprecated Behavior

Deprecated:
- hard-coding GPT as the only external auditor;
- hard-coding Claude as the only external auditor;
- mailbox GitHub Action directly notifying OPERATOR for normal mailbox traffic;
- raw mailbox events sent to OPERATOR;
- treating gpt_to_claude / claude_to_gpt as the canonical business role names.

Allowed only as fallback:
- GitHub Actions mailbox notifier may be used manually for diagnostics or emergency recovery.
