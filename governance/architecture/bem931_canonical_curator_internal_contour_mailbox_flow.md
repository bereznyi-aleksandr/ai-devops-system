# BEM-931 | Canonical Governance Object Model and Routing Flow

Updated: 2026-06-06
Status: canonical draft v2.2
Owner: DIRECTOR_CURATOR
Applies to: OPERATOR, EXTERNAL_AUDITOR_GPT, EXTERNAL_AUDITOR_CLAUDE, GENERAL_DIRECTOR, DIRECTOR, WORKER

## 1. Correction

Previous simplified model was incomplete.

Incorrect current-scope model:
```text
OPERATOR / GPT / DIRECTOR_CURATOR / GENERAL_DIRECTOR / INTERNAL_CONTOUR
```

Correct model:
```text
GOVERNANCE_OBJECT has:
- object_curator
- internal_contours[]
- audit gates
- return path by initiator
```

Current governance-contour objects:
- GENERAL_DIRECTOR
- DIRECTOR
- WORKER

Do not import old conceptual "board of directors" discussion into the current governance-contour implementation.
Product-repository directors are future product scope, not current BEM-931 release scope.

## 2. Initiators

Allowed initiators:
- OPERATOR
- EXTERNAL_AUDITOR_GPT
- EXTERNAL_AUDITOR_CLAUDE
- approved EXTERNAL_AUDITOR_*

Every request to a curator must preserve:

```json
{
  "initiator_role": "OPERATOR | EXTERNAL_AUDITOR_GPT | EXTERNAL_AUDITOR_CLAUDE | EXTERNAL_AUDITOR_*",
  "initiator_return_mode": "DIRECT_OPERATOR_REPORT | MAILBOX_AND_OPERATOR_WAKE",
  "initiator_chat_required": "none | Open GPT Custom GPT | Open Claude Chat | ...",
  "initiator_mailbox_return_path": "none | governance/audit_mailbox/<path>/",
  "initiator_request_id": "BEM-..."
}
```

Requests without initiator metadata are BLOCKED.

## 3. Objects

### 3.1 GENERAL_DIRECTOR

Mandatory:
- GD_CURATOR
- GD internal contours

Current minimum:
- GD_DECISION_CONTOUR: strategic decision / final verdict
- GD_RULES_CONTOUR: protocol, rules, governance policy approval

Allowed verdicts:
- APPROVED
- APPROVED_WITH_NOTES
- CHANGE_REQUIRED
- BLOCKED
- NEED_INTERNAL_AUDIT
- NEED_DIRECTOR_EXECUTION

### 3.2 DIRECTOR

Director is not "domain runners + escalation".
Director is an object.

Mandatory:
- DIR_CURATOR
- DIR_RULES_CONTOUR
- DIR_DECISION_CONTOUR

DIR_RULES_CONTOUR:
- writes and updates rules;
- prepares protocol text;
- updates architecture / policy files.

DIR_DECISION_CONTOUR:
- makes operational decisions inside Director scope;
- routes work;
- escalates to GENERAL_DIRECTOR when needed.

### 3.3 WORKER

Worker is not a single executor role.
Worker is an object.

Mandatory:
- WRK_CURATOR
- internal_contours[]

Worker may have unlimited internal contours.
Default worker has:
- WRK_C1
- WRK_C2
- WRK_C3

Semantics of WRK_C1 / WRK_C2 / WRK_C3 must come from object_passports and contours_registry.
Do not hard-code product semantics until registry defines them.

## 4. Internal contour loop

Every internal contour uses:

```text
ANALYST
-> AUDITOR
-> EXECUTOR
-> AUDITOR
```

Rejected task draft:
```text
AUDITOR
-> ANALYST
-> AUDITOR
```

Rejected execution result:
```text
AUDITOR
-> ANALYST
-> AUDITOR
-> EXECUTOR
-> AUDITOR
```

Rules:
1. ANALYST prepares TASK_DRAFT.
2. AUDITOR reviews TASK_DRAFT before execution.
3. EXECUTOR receives only APPROVED_FOR_EXECUTION.
4. EXECUTOR returns EXECUTION_RESULT to AUDITOR.
5. If execution result is rejected, it returns to ANALYST for re-planning.
6. Only after ACCEPTED may AUDITOR notify the owning object curator.
7. Only after ACCEPTED may AUDITOR write mailbox result if required by initiator_return_mode.

## 5. Return modes

### 5.1 OPERATOR initiated task

```text
OPERATOR
-> responsible CURATOR
-> target object CURATOR
-> selected internal contour
-> AUDITOR ACCEPTED
-> target object CURATOR
-> responsible CURATOR
-> OPERATOR curated report
```

Mailbox:
- not required.

### 5.2 EXTERNAL_AUDITOR initiated task

```text
EXTERNAL_AUDITOR_*
-> responsible CURATOR
-> target object CURATOR
-> selected internal contour
-> AUDITOR ACCEPTED
-> target object CURATOR
-> responsible CURATOR
-> initiating auditor mailbox
-> OPERATOR wake-up naming exact external auditor
-> initiating auditor reads mailbox
```

Mailbox:
- required.

Wake-up must specify:
- EXTERNAL_AUDITOR_GPT -> open GPT Custom GPT;
- EXTERNAL_AUDITOR_CLAUDE -> open Claude Chat.

## 6. Corrected BEM-931 minimal trace

Flat trace is not enough:
```text
GD -> DIR/CUR -> WRK
```

Correct minimal object-contour trace:
```text
OPERATOR_OBJECTIVE
-> GD_OBJECT.GD_CURATOR
-> GD_DECISION_CONTOUR or GD_RULES_CONTOUR
-> AUDITOR gate
-> DIRECTOR_OBJECT.DIR_CURATOR
-> DIR_RULES_CONTOUR or DIR_DECISION_CONTOUR
-> AUDITOR gate
-> WORKER_OBJECT.WRK_CURATOR
-> selected WRK_C*
-> AUDITOR gate
-> result
-> return path by initiator
```

A shorter test is allowed only if marked MINIMAL_TEST_TRACE and must not claim full object-contour implementation.

## 7. Forbidden assumptions

Forbidden:
- treating GPT as canonical executor of the governance contour;
- treating Claude as the only external auditor;
- hard-coding GPT as the only initiator;
- using mailbox for normal OPERATOR-initiated task completion;
- implementing board of directors in current BEM-931 scope;
- importing product-repository directors into current governance repo;
- sending raw mailbox events to OPERATOR as normal path;
- letting EXECUTOR receive unaudited Analyst task;
- treating skeleton runners or mock E2E as Release PASS.

## 8. Acceptance criteria

BEM-931 v2.2 is valid only if:

1. GENERAL_DIRECTOR, DIRECTOR, WORKER are defined.
2. Each object has a curator.
3. Each object has internal_contours[].
4. Director has DIR_RULES_CONTOUR and DIR_DECISION_CONTOUR.
5. Worker supports unlimited contours and default WRK_C1 / WRK_C2 / WRK_C3.
6. Internal contour loop is Analyst -> Auditor -> Executor -> Auditor.
7. Rework returns through Analyst.
8. OPERATOR task returns directly to OPERATOR without mailbox.
9. EXTERNAL_AUDITOR_* task returns to initiating auditor mailbox.
10. Curator wake-up names the exact external auditor to open.
11. Current governance contour excludes board-of-directors implementation.
12. Product-repository directors are future/product scope only.
13. Release PASS remains forbidden until object-contour E2E and receipts are proven.
