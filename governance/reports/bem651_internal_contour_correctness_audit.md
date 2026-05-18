# BEM-651 | Internal Contour Correctness Audit

Дата: 2026-05-18 | 15:29 (UTC+3)

## Verdict
The internal contour worked correctly as a file-based governed contour with GPT reserve execution. It did not prove independent live multi-agent execution for each role, and it did not prove Claude primary runtime.

Status: correct_file_based_internal_contour_with_runtime_caveats
Blocker: null

## 1. Step-by-step chain
### 1. Operator → GPT Curator
- Expected: Operator sets task; Curator forms structured package.
- Actual: BEM-648 created curator inbox package.
- Result: PASS
- Evidence: governance/curator/inbox/bem648_completion_plan_to_internal_contour.json
- Note: This is file-based Curator routing, executed by GPT reserve via restored codex-runner.

### 2. Curator → Role Orchestrator
- Expected: Curator does not bypass router.
- Actual: Matching package was placed in role_orchestrator/inbox.
- Result: PASS
- Evidence: governance/role_orchestrator/inbox/bem648_completion_plan_to_internal_contour.json
- Note: Correct role-bus path was used.

### 3. Role Orchestrator → Internal Task Registry
- Expected: Task is registered in internal_contour/tasks before role execution.
- Actual: Internal task file was created.
- Result: PASS
- Evidence: governance/internal_contour/tasks/bem648_completion_plan_to_internal_contour.json
- Note: Correct internal registry artifact exists.

### 4. Task Registry → Analyst GPT
- Expected: Analyst prepares plan; Analyst does not contact external auditor directly.
- Actual: Analyst plan artifact exists in internal_contour/analyst/plans.
- Result: PASS
- Evidence: governance/internal_contour/analyst/plans/bem648_completion_plan_to_internal_contour.json
- Note: Matches corrected architecture.

### 5. Analyst → Internal Auditor
- Expected: Analyst sends to internal_contour/auditor/inbox, not audit_mailbox.
- Actual: Internal auditor inbox package exists.
- Result: PASS
- Evidence: governance/internal_contour/auditor/inbox/bem648_completion_plan_to_internal_contour_review.json
- Note: This repairs previous BEM-605 misroute.

### 6. Internal Auditor controls
- Expected: Internal Auditor checks controls, provider route, role-bus boundary, acceptance.
- Actual: BEM-649 internal auditor verdict exists and status is approved_with_operational_watch.
- Result: PASS
- Evidence: governance/internal_contour/auditor/reports/bem649_internal_auditor_verdict.json
- Note: Auditor did not claim Claude primary; it accepted reserve policy and operational watch.

### 7. Internal Auditor → Executor
- Expected: Executor receives package after auditor verdict/controls.
- Actual: Executor inbox exists; executor result exists.
- Result: PASS
- Evidence: governance/internal_contour/executor/reports/bem649_executor_completion_result.json
- Note: Executor executed via GPT reserve/Deno transport as recorded, not via Claude primary.

### 8. Selftest controls C1-C7
- Expected: Mandatory controls must pass before completion.
- Actual: BEM-649 controls status is pass.
- Result: PASS
- Evidence: governance/state/bem649_execute_completion_controls.json
- Note: Controls passed; operational watches are non-blocking by policy.

### 9. Final completion report
- Expected: Final monitoring report with evidence map.
- Actual: BEM-650 report state exists and status completed.
- Result: PASS
- Evidence: governance/state/bem650_final_completion_report_internal_contour.json
- Note: Final report was created after controls, not before.

## 2. Architecture compliance
### Role-bus instead of mailbox for internal roles
- Expected: Internal communication via governance/internal_contour/* and role_orchestrator.
- Actual: BEM-648 created packages in curator, role_orchestrator, tasks, analyst, auditor, executor paths.
- Result: PASS
- Evidence: BEM-648 packages

### Mailbox boundary
- Expected: audit_mailbox only for Internal Auditor ↔ External Auditor.
- Actual: Role communication canon and auditor interaction canon exist; old BEM-605 misuse annotated as misroute.
- Result: PASS
- Evidence: ROLE_COMMUNICATION_CANON.md + INTERNAL_EXTERNAL_AUDITOR_INTERACTION_CANON.md

### Provider evidence honesty
- Expected: Do not claim Claude primary unless Claude runtime artifact exists.
- Actual: Provider closure says reserve_validated_primary_unavailable; executor result says gpt_reserve_execution_via_deno_transport.
- Result: PASS
- Evidence: bem632_close_provider_route_and_delivery_status.json + bem649_executor_completion_result.json

### Deno role clarity
- Expected: Deno is transport adapter, not internal Executor role.
- Actual: Canon documents Deno as transport; executor result records deno_role=transport_adapter_only.
- Result: PASS
- Evidence: ROLE_COMMUNICATION_CANON.md + executor result

### Controls and selftest
- Expected: C1-C7 controls executed and passed.
- Actual: BEM-649 status pass; auditor verdict approved_with_operational_watch.
- Result: PASS
- Evidence: bem649_execute_completion_controls.json

### Write-channel recovery
- Expected: codex-runner restored before further work.
- Actual: BEM-646 smoke pass; BEM-647 roadmap resumed.
- Result: PASS
- Evidence: BEM-646/BEM-647 states

### True independent multi-agent runtime
- Expected: Separate live agents execute roles autonomously.
- Actual: Current run used file-based role artifacts executed by GPT reserve through codex-runner; not proof of separate live Analyst/Auditor/Executor runtimes.
- Result: GAP
- Evidence: ROLE_EXECUTION_EVIDENCE_CANON.md + executor result

### Telegram/Claude operational proofs
- Expected: Delivery confirmed and/or Claude runtime proven for primary route.
- Actual: Controls allow operational watch; architecture closed through reserve route.
- Result: PASS
- Evidence: BEM-649 operational_watch + BEM-632 provider policy

## 3. Mechanism health
- Deno /codex-task: PASS | Write-channel restored after Claude fixed codex-runner.yml. | evidence: BEM-646 workflow_dispatch_status=204 and smoke commit
- codex-runner.yml: PASS | Runner executed BEM-648, BEM-649, BEM-650 successfully. | evidence: governance/state/bem646_post_repair_codex_runner_smoke.json
- Python executor: PASS_WITH_LIMITS | Executor works but requires safe subset; prior failures showed blocked constructs. | evidence: BEM-648..650 commits
- Internal role-bus: PASS | Correct file lanes now used. | evidence: BEM-648 package chain
- Audit mailbox: PASS_AS_BOUNDARY | Reserved for auditor-to-auditor sync, not internal role traffic. | evidence: BEM-625/BEM-628 canons
- Provider gate: PASS_AS_POLICY | Primary not proven, reserve route valid and honestly reported. | evidence: BEM-632 closure policy
- Telegram delivery proof: WATCH | Not architecture blocker; remains operational monitoring item. | evidence: BEM-649 operational_watch
- Claude runtime proof: WATCH | Not required for reserve route, but required before selecting Claude primary. | evidence: BEM-649 operational_watch

## 4. Direct answer
Внутренний контур отработал корректно в текущей реализации: это file-based governed contour, выполненный GPT reserve через восстановленный codex-runner. Цепочка role-bus соответствует исправленной архитектуре. Mailbox больше не используется как внутренний role-bus. Но это не является доказательством, что каждую роль исполнил отдельный live-agent; для этого нужен следующий уровень — runtime agents / provider-specific execution proofs.

## 5. Remaining watches
- Claude primary runtime proof: required only before selecting Claude primary; current route valid through reserve.
- Telegram delivery proof: operational watch, not architecture blocker.
