BEM-931 | EXTERNAL_AUDITOR_GPT -> DIRECTOR_CURATOR | REQUEST GENERAL_DIRECTOR_APPROVAL

FROM:
EXTERNAL_AUDITOR_GPT

TO:
DIRECTOR_CURATOR

INITIATOR_METADATA:
{
  "initiator_role": "EXTERNAL_AUDITOR_GPT",
  "initiator_return_mode": "MAILBOX_AND_OPERATOR_WAKE",
  "initiator_chat_required": "Open GPT Custom GPT",
  "initiator_mailbox_return_path": "governance/audit_mailbox/director_curator_to_external_auditor_gpt/",
  "initiator_request_id": "BEM-931"
}

REQUEST:
Please submit BEM-931 for GENERAL_DIRECTOR approval.

PROTOCOL_SCOPE:
1. Universal Director Curator / Internal Contour / Mailbox Flow.
2. Initiator-sensitive return mode:
   - OPERATOR -> direct curator report;
   - EXTERNAL_AUDITOR_* -> initiator mailbox + operator wake.
3. Internal contour rule:
   ANALYST -> AUDITOR -> EXECUTOR -> AUDITOR,
   with all rework returns through ANALYST.
 4. Internal AUDITOR notifies DIRECTOR_CURATOR after ACCEPTED.
 5. For external audit tasks, INTERNAL_AUDITOR also writes the verified result to the initiator's mailbox return path.
 6. DIRECTOR_CURATOR notifies OPERATOR which external auditor must be opened.

REFERENCE_FILES:
- governance/architecture/bem931_canonical_curator_internal_contour_mailbox_flow.md
- governance/curator/operator_notification_policy.md

DECISION_REQUIRED:
General Director verdict must be one of:
- APPROVED
- APPROVED_WITH_NOTES
- CHANGE_REQUIRED
- BLOCKED
- NEED_INTERNAL_AUDIT

IF NEED_INTERNAL_AUDIT:
Please route the task through the canonical internal contour:
ANALYST -> AUDITOR -> EXECUTOR -> AUDITOR.

ACCEPTANCE_CRITERIA:
A BEM-931 result is valid only if:
- GENERAL_DIRECTOR verdict is present;
- if internal execution is used, auditor-gates protect both task draft and execution result;
- DIRECTOR_CURATOR returns the initiator-sensitive output;
- for EXTERNAL_AUDITOR_GPT, the verified result is written to:
  governance/audit_mailbox/director_curator_to_external_auditor_gpt/;
- DIRECTOR_CURATOR sends operator wake-up with exact mailbox path.

OUTPTUT_REQUESTED:
Please write the final verified result to:
governance/audit_mailbox/director_curator_to_external_auditor_gpt/bem931_general_director_verdict.md

CHECK_STATUS:
AWAITING_DIRECTOR_CURATOR
