# BEM-931 | Canonical Curator / Internal Contour / Mailbox Flow

Updated: 2026-06-06
Status: canonical draft
Owner: EXTERNAL_AUDITOR_GPT

## Purpose

This document fixes the communication scheme for BEM-931.

The system uses the standard internal contour flow and adds two external-integration outputs:

1. INTERNAL_AUDITOR writes the verified result to mailbox for EXTERNAL_AUDITOR_GPT.
2. DIRECTOR_CURATOR notifies OPERATOR that a result is ready for external review.

GitHub Actions must not be the primary operator-notification authority for mailbox events.

## Roles

### OPERATOR

Strategic human operator.

Responsibilities:
- sets strategic direction;
- receives only short curated notifications;
- reviews final DOCX/ZIP package if requested.

### EXTERNAL_AUDITOR_GPT

This Custom GPT chat.

Responsibilities:
- sends requests to DIRECTOR_CURATOR;
- reads mailbox after operator opens this chat;
- reviews the internal contour result;
- prepares final operator package if protocol is approved.

### DIRECTOR_CURATOR

Curator of the General Director.

Responsibilities:
- receives request from EXTERNAL_AUDITOR_GPT;
- escalates strategic decisions to GENERAL_DIRECTOR;
- creates tasks for INTERNAL_CONTOUR;
- receives completion notice from INTERNAL_AUDITOR;
- sends a short Telegram notification to OPERATOR when external review is required.

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
7. EXECUTOR returns EXECUTION_RESULT to AUDITOR.
8. AUDITOR reviews EXECUTION_RESULT.
9. If AUDITOR returns CHANGE_REQUIRED, result goes back to ANALYST for rework planning.
10. ANALYST updates the task and sends it again to AUDITOR.
11. Loop continues until ACCEPTED or BLOCKED.
12. Only after ACCEPTED, AUDITOR sends completion feedback to DIRECTOR_CURATOR.
13. Only after ACCEPTED, AUDITOR writes verified result to mailbox.

## Added External Integration

The standard internal contour already ends with:

AUDITOR -> DIRECTOR_CURATOR

For external audit tasks, two additional actions are required after ACCEPTED:

1. AUDITOR -> MAILBOX
   The auditor writes the verified result for EXTERNAL_AUDITOR_GPT.

2. DIRECTOR_CURATOR -> OPERATOR
   The curator sends a short Telegram notification:
   "For external auditor GPT, a result is ready. Open Custom GPT and read mailbox file: <path>."

## Canonical BEM-931 Flow

1. OPERATOR asks EXTERNAL_AUDITOR_GPT to coordinate BEM-931.

2. EXTERNAL_AUDITOR_GPT sends request to DIRECTOR_CURATOR.

3. DIRECTOR_CURATOR checks the request and, if strategic, escalates to GENERAL_DIRECTOR.

4. GENERAL_DIRECTOR decides:
   - APPROVED
   - APPROVED_WITH_NOTES
   - CHANGE_REQUIRED
   - BLOCKED
   - NEED_INTERNAL_AUDIT

5. If internal audit is required:
   DIRECTOR_CURATOR creates task for INTERNAL_CONTOUR.

6. INTERNAL_CONTOUR executes standard loop:
   ANALYST -> AUDITOR -> EXECUTOR -> AUDITOR
   with returns through ANALYST when rework is required.

7. When result is ACCEPTED:
   AUDITOR notifies DIRECTOR_CURATOR.

8. For external review:
   AUDITOR also writes verified result to mailbox.

9. DIRECTOR_CURATOR sends Telegram notification to OPERATOR.

10. OPERATOR opens EXTERNAL_AUDITOR_GPT.

11. EXTERNAL_AUDITOR_GPT reads mailbox via MCP.

12. EXTERNAL_AUDITOR_GPT either:
   - accepts the result and prepares DOCX/ZIP;
   - sends CHANGE_REQUIRED back to DIRECTOR_CURATOR;
   - asks OPERATOR one specific question if operator decision is required.

## Acceptance Criteria

A BEM-931 result is valid only if:

- task was routed through DIRECTOR_CURATOR;
- strategic decision was owned by GENERAL_DIRECTOR when required;
- internal work followed ANALYST -> AUDITOR -> EXECUTOR -> AUDITOR;
- executor did not receive an unaudited analyst task;
- auditor accepted the final execution result;
- auditor notified DIRECTOR_CURATOR;
- auditor wrote verified result to mailbox;
- curator notified OPERATOR to open EXTERNAL_AUDITOR_GPT;
- EXTERNAL_AUDITOR_GPT reviewed the mailbox result.

## Deprecated Behavior

Deprecated:
- mailbox GitHub Action directly notifying OPERATOR for normal mailbox traffic;
- raw mailbox events sent to OPERATOR;
- treating gpt_to_claude / claude_to_gpt as the canonical business role names.

Allowed only as fallback:
- GitHub Actions mailbox notifier may be used manually for diagnostics.
