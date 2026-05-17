# BEM-548.2 | Role-Orchestrator Workflow Parity

Дата: 2026-05-17 | 14:53 (UTC+3)

## Source of truth
BEM-543 corrected sequence:
external -> curator_intake -> curator_assignment -> role-orchestrator -> analyst -> auditor -> executor -> auditor_final -> curator_closure.

## Routing rules
| Latest record | Condition | Next role |
|---|---|---|
| curator_assignment | task_type=development | analyst |
| curator_assignment | task_type=audit | auditor |
| curator_assignment | task_type=hotfix | auditor |
| analysis | status=completed | auditor |
| audit | decision=PASS_TO_EXECUTOR | executor |
| execution | status=completed | auditor_final |
| audit | decision=FINAL_PASS | curator_closure |
| any failed/cancelled/timeout | any | curator |

## Output
Every decision writes `role_orchestrator_decision` to `governance/transport/results.jsonl` and updates `governance/state/role_cycle_state.json`.
