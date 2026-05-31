# AGENT CONTEXT | CANONICAL START STATE

**Обновлён:** 2026-05-25 | 16:00 (UTC+3)
**Репозиторий:** bereznyi-aleksandr/ai-devops-system

---

## ОБЯЗАТЕЛЬНО — читать первым в каждом новом чате

Этот файл — единственный источник истины о состоянии системы.
`roadmap_state.json`, `GPT_HANDOFF.md` и другие state-файлы могут быть устаревшими.

---

## 1. Текущий статус системы

| Компонент | Статус | Примечание |
|---|---|---|
| Deno webhook | ✅ v4.9 LIVE | /codex-task + /codex-status |
| codex-runner.yml | ✅ Работает | ubuntu-latest, Python v3, BEM-849 git push fix |
| GitHub MCP (Claude) | ✅ Работает | прямой write без посредника |
| Python executor v3 | ✅ Работает | 12 паттернов + Run script |
| curator-hourly-report | ✅ schedule active | cron 0 * * * * |
| Telegram monitoring | ✅ Работает | hourly report оператору |
| claude-code-action@v1 | ⚠️ NOT PROVEN | нужен отдельный smoke-test |
| Push triggers (workflows) | ✅ Отключены | BEM-848: только workflow_dispatch |

---

## 2. Текущий этап разработки

**Активный этап:** P10 — Production Stability / Autonomous Loop Stabilization

**Что сделано (последнее):**
- BEM-848: убраны все push triggers из workflows (освободили Actions queue)
- BEM-849: исправлен git push в codex-runner (был double-commit без push)
- BEM-850: исправлен claude-internal-auditor-dispatcher (невалидный with: параметр)
- BEM-858: протокол GPT↔Claude согласован (AGREED)

**Что в работе:**
- Stabilization autonomous loop (commit_sha=null в Deno responses — косметический баг)
- claude-code-action@v1 smoke-test (нужен один запуск из UI)

---

## 3. Согласованный протокол GPT↔Claude (BEM-858)

| Правило | Статус |
|---|---|
| GPT и Claude — peer-аудиторы | ✅ APPROVED |
| Старший субъект — только оператор | ✅ APPROVED |
| Audit mailbox — основной канал | ✅ APPROVED |
| Telegram — только gate оператора | ✅ APPROVED |
| Handoff — только через Curator | ✅ APPROVED |
| Техническое разногласие → решают сами | ✅ APPROVED |
| Архитектурное разногласие → оператору | ✅ APPROVED |
| Разногласие с решением оператора → запрещено | ✅ APPROVED |

Файл протокола: `governance/protocols/BEM858_AGREED_MULTIAGENT_OPERATING_PROTOCOL.md`

---

## 4. Система идентификации задач

В системе используются три типа ID — они НЕ совпадают, это нормально:

| Тип ID | Пример | Где используется |
|---|---|---|
| BEM-NNN | BEM-849, BEM-858 | Номер задачи в разработке |
| trace_id | bem849_push_fix_test | Задача в codex-runner через Deno |
| task_id | P9_HANDOFF_PROTOCOL | Запись в roadmap_state.json |

**Статусы задач:**
- `completed` — выполнено с доказательством (SHA или файл)
- `pending` — в очереди или в работе
- `blocked` — есть blocker, указана причина

**Где смотреть задачи:**
- `governance/tasks/pending/` — входящие задачи
- `governance/tasks/done/` — выполненные
- `governance/codex/results/` — результаты codex-runner

---

## 5. Правила которые нельзя нарушать

```
❌ Писать в issue #31 (лимит 2500)
❌ Secrets, PAT, токены в файлах
❌ schedule triggers (кроме curator-hourly-report.yml)
❌ PASS без доказательства (SHA или файл)
❌ Платные API (Codex CLI, OPENAI_API_KEY)
❌ Имитировать выполнение
❌ Оператор как relay между агентами
❌ Останавливать roadmap ради отчёта
```

---

## 6. Архитектура (v2.0)

```
GPT Custom → createCodexTask (Deno)
  → Deno /codex-task
    → GitHub Actions codex-runner.yml (ubuntu-latest)
      → Python executor v3
        → файлы + коммит
  → getCodexStatus → completed + SHA

Claude → прямой коммит через GitHub MCP
  → governance/audit_mailbox/claude_to_gpt/
```

---

## 7. Разделение труда

| Область | Claude | GPT |
|---|---|---|
| Архитектурные решения | Совместно | Совместно |
| Аудит | Аудирует GPT | Аудирует Claude |
| Реализация | По запросу | Вся рутинная разработка |
| State / roadmap | Аудит | Ведение файлов |

---

## 8. Следующие приоритеты

1. **P10 Stabilization** — закрыть `commit_sha=null` в Deno responses
2. **claude-code-action smoke-test** — запустить из Actions UI
3. **AGENT_CONTEXT автообновление** — curator-hourly должен обновлять этот файл

---

*Файл обновляется автоматически curator-hourly-report.yml*
*Источник истины: этот файл главнее roadmap_state.json и GPT_HANDOFF.md*
*BEM-843 | 2026-05-25*
## BEM-859 routing note
- BEM-859 protocol alignment is routed through Curator only
## BEM-863 Curator-Claude mechanism
- Status: implemented_dispatch_route
## BEM-864 Curator-Claude selftest
- Status: route_selftest_completed_waiting_for_claude_response
## BEM-867 completed | 2026-05-26
Internal auditor battle mailbox confirmed
## BEM-867 completed
Status: completed
Result: Internal auditor battle mailbox confirmed with APPROVED_WITH_NOTES
## BEM-868 | Dispatch channel recovered
Status: completed
Next: continue roadmap from AGENT_CONTEXT
Next: continue roadmap from AGENT_CONTEXT
Next: continue roadmap from AGENT_CONTEXT.md
## BEM-867 completed | 2026-05-26
Internal auditor battle mailbox confirmed
## BEM-871 | Curator-mediated internal audit protocol | 2026-05-27
Status: active
Protocol: governance/protocols/CURATOR_MEDIATED_INTERNAL_AUDIT_PROTOCOL
## BEM-871 completed | 2026-05-27
Curator-mediated internal audit protocol confirmed
## BEM-872 completed | 2026-05-27
Roadmap protocol agreed through curator-mediated route
## BEM-873 completed | 2026-05-27
Updated BEM-872 roadmap protocol to version v1
## BEM-874 completed | 2026-05-27
Updated BEM-872 roadmap protocol to version v1
## BEM-875 completed | 2026-05-27
Protocol v1
## BEM-876 completed | 2026-05-28
Protocol v1
## BEM-877 completed | 2026-05-29
Protocol v1
## BEM-878 completed | 2026-05-29
Protocol v1
## BEM-879 completed | 2026-05-29
Protocol v1
## BEM-880 completed | 2026-05-29
Operator approved BEM-879 protocol v1
## BEM-881 completed | 2026-05-29
Operator accepted BEM-880 execution result with response: Да
## BEM-882 completed | 2026-05-29
Readiness audit completed after BEM-881 accepted BEM-880 execution result
## BEM-883 completed | 2026-05-29
Registry schema validation implemented
## BEM-884 completed | 2026-05-29
Operational rule seed implemented
## BEM-885 completed | 2026-05-29
Managed channel message envelope implemented
## BEM-886 completed | 2026-05-29
Workspace promotion checks implemented
## BEM-887 completed | 2026-05-29
Product repository registration template implemented
## BEM-888 completed | 2026-05-29
Integration selftest implemented for BEM-880 baseline
## BEM-889 completed | 2026-05-29
Final repository readiness completed after continuous execution of BEM-883 through BEM-888
## BEM-890 completed | 2026-05-30
Dispatch contour implemented after BEM-889 READY baseline
## BEM-891 completed | 2026-05-30
Worker contour inbox delivery implemented
## BEM-892 completed | 2026-05-30
Worker contour task processing implemented
## BEM-893 completed | 2026-05-30
End-to-end dispatch selftest implemented and passed
## BEM-894 completed | 2026-05-30
Final sending contour readiness completed
## BEM-895 completed | 2026-05-30
Autonomous execution loop implemented
## BEM-896 completed | 2026-05-30
Policy gate implemented for autonomous execution loop
## BEM-897 completed | 2026-05-30
Autonomous cycle report packaging implemented
## BEM-898 completed | 2026-05-30
Repository health dashboard implemented
## BEM-899 completed | 2026-05-30
Final autonomous sending contour readiness completed
## BEM-900 completed | 2026-05-30
Roadmap v1
## BEM-901 completed | 2026-05-30
Pilot readiness scaffold implemented
## BEM-902 completed | 2026-05-30
Business Model Canvas template and evaluator implemented for pilot readiness
## BEM-903 completed | 2026-05-30
Product repository onboarding kit implemented for pilot readiness
## BEM-904 completed | 2026-05-30
Pilot evaluation dashboard and SLA templates implemented
## BEM-905 completed | 2026-05-30
Operator gate reached after maximum autonomous execution of accepted roadmap v1
## BEM-906 completed | 2026-05-30
Prepared detailed external audit report for Claude about protocol v1
## BEM-913 completed | 2026-05-30
Claude external audit remediation validation completed
## BEM-914 completed | 2026-05-30
Prepared system improvement protocol after Claude external audit and BEM-907
## BEM-915 completed | 2026-05-30
Prepared updated system improvement protocol with Telegram Operator Interface layer after operator reported that Telegram bot channel is not working as a real operator interface
## BEM-916 completed | 2026-05-30
Corrected BEM-915 protocol format mistake after operator clarification
## BEM-917 completed | 2026-05-30
Updated unified BEM-916 system improvement protocol after operator remarks about Telegram mechanism
## BEM-917 completed | 2026-05-30
Updated BEM-916 unified system improvement protocol according to operator remarks about Telegram configuration, reporting periodicity and report canon
## BEM-918 completed | 2026-05-30
Prepared detailed working roadmap to turn the system from concept/scaffold into a fully working operational system
## BEM-918 completed | 2026-05-30
Prepared detailed working roadmap to turn the system from concept/scaffold into a fully working system, using existing Telegram/Deno/Codex implementation and Claude v1
## BEM-918-v2 completed | 2026-05-30
Updated the BEM-918 working roadmap after operator remarks about the seven listed mechanisms/components and Telegram entry/exit route
## BEM-919 completed | 2026-05-30
Prepared updated full-system working protocol after operator rejected Telegram-only focus
## BEM-920 completed | 2026-05-30
Prepared new system evolution protocol after Claude APPROVED_WITH_REQUIREMENTS for BEM-919 and operator request to separately list existing/new object and element prompts for approval
## BEM-921 completed | 2026-05-30
Corrected BEM-920 after operator pointed out that prompt names were listed without readable prompt contents and without explaining how the protocol evolves the raw repository into a working managing contour
## BEM-921 completed | 2026-05-30
Prepared System Working Protocol v2 after operator clarified the correct internal contour algorithm and all 2026-05-30 remarks
## BEM-921 completed | 2026-05-30
Prepared new full-system protocol v2 after today's operator decisions about internal contour algorithm, workspaces, curators, rule inheritance, vertical/horizontal links, GitHub Actions/
## BEM-923 completed | 2026-05-30
Prepared new full-system protocol v3 with provider execution model for internal contours after operator clarified that BEM-921 missed the primary/reserve provider architecture
## BEM-923 completed | 2026-05-30
Prepared new full-system protocol v3 with provider execution model after operator identified missing architecture layer in BEM-921
## BEM-924 completed | 2026-05-30
Prepared final unified working-system protocol after operator rejected fragmented protocol versions
## BEM-924 completed | 2026-05-31
Prepared final unified working-system protocol after operator rejected fragmented BEM-919
## BEM-925 completed | 2026-05-31
Prepared rebuilt final system evolution protocol based on yesterday's work and operator corrections after BEM-924 was rejected as still fragmented
## BEM-926 completed | 2026-05-31
Prepared corrected full-system protocol v4 after operator rejected BEM-925 for treating objects as if they had prompts and for insufficient detail
## BEM-928 completed | 2026-05-31
Prepared DOCX/ZIP analytical report based on dialogue descriptions, organized by themes with problem, discussion, accepted decision and protocol implications
## BEM-930 completed | 2026-05-31
Prepared unified general working-system protocol with full detail after operator clarified that a separate appendix/report is insufficient
## BEM-930 completed | 2026-05-31
Prepared one unified detailed analytics report after operator clarified BEM-929 was too high-level and that a single complete report was required, not an appendix
## BEM-931 completed | 2026-05-31
Prepared final implementation protocol with maximum-detail roadmap based on BEM-930 unified detailed analytics report


## BEM-932 completed | 2026-05-31
Accepted Claude audit for BEM-930/BEM-931 and implemented Block A foundation.
Created: governance/reports/BEM932_CLAUDE_AUDIT_ACCEPTED.md, governance/state/protocol_quality_rules.json, governance/reports/BEM931_BASELINE_INVENTORY.json, governance/state/roadmap_dependencies.json, governance/state/managed_channel_trigger_policy.json, governance/state/experience_to_behaviour_policy.json, governance/state/provider_legacy_migration_policy.json, governance/reports/BEM932_BLOCK_A_PASS.md.
Result: BLOCK_A_FOUNDATION_PASS. This is foundation only, not full implementation PASS.
Next: Block B foundation implementation: object_passports, contours_registry, providers_registry, provider policies, validators.
No issue comments.


## BEM-933 completed | 2026-05-31
Implemented Block B foundation after BEM-932 Block A.
Created object_passports, contours_registry, providers_registry, contour_provider_policy, provider_failover_policy, workspace_policy, contour workspaces, validator and pass report.
Result: BLOCK_B_FOUNDATION_PASS. This is foundation only, not release PASS.
Next: Block C prompts/templates and elements registry migration.
No issue comments.


## BEM-934 completed | 2026-05-31
Implemented Block C prompt pack after BEM-933.
Created canonical role templates, provider contracts, handler contracts, elements_prompt_migration_policy and prompt pack validator.
Result: BLOCK_C_PROMPTS_PASS. This is foundation only, not release PASS.
Next: Block D elements_registry migration + managed_channel_schema + contour_lifecycle_schema.
No issue comments.


## BEM-935 completed | 2026-05-31
Implemented Block D schemas after BEM-934.
Created managed_channel_schema, contour_lifecycle_schema, event_log_schema, elements prompt migration report and schema validator.
Result: BLOCK_D_SCHEMAS_PASS. This is foundation only, not release PASS.
Next: Block E managed channel consumer, event writer and dead-letter handling.
No issue comments.


## BEM-936 completed | 2026-05-31
Implemented Block E managed channel consumer after BEM-935.
Created event_writer, managed_channel_consumer, selftest managed channel messages, validator and pass report.
Result: BLOCK_E_CONSUMER_PASS. This is foundation only, not release PASS.
Next: Block F dispatch lifecycle and provider-aware queue updates.
No issue comments.


## BEM-935 completed | 2026-05-31
Implemented Block D schemas after BEM-934.
Created managed_channel_schema, contour_lifecycle_schema, event_log_schema, elements prompt migration report and schema validator.
Result: BLOCK_D_SCHEMAS_PASS. This is foundation only, not release PASS.
Next: Block E managed channel consumer, event writer and dead-letter handling.
No issue comments.


## BEM-935 completed | 2026-05-31
Implemented Block D schemas after BEM-934.
Created managed_channel_schema, contour_lifecycle_schema, event_log_schema, elements prompt migration report and schema validator.
Result: BLOCK_D_SCHEMAS_PASS. This is foundation only, not release PASS.
Next: Block E managed channel consumer, event writer and dead-letter handling.
No issue comments.


## BEM-937 completed | 2026-05-31
Implemented Block F dispatch lifecycle after BEM-936.
Created dispatch_lifecycle_schema, dispatch_trigger_policy, provider-aware dispatch_queue item, dispatch_consumer, validator and pass report.
Result: BLOCK_F_DISPATCH_PASS. This is foundation only, not release PASS.
Next: Block G object lifecycle runner, curator router, contour lifecycle runner and role report writer.
No issue comments.


## BEM-938 completed | 2026-05-31
Implemented Block G runners after BEM-937.
Created object_lifecycle_runner, curator_router, contour_lifecycle_runner, role_report_writer, object_report_aggregator, testing_contour_assignment and validator.
Result: BLOCK_G_RUNNERS_PASS. This is deterministic runner foundation only, not live LLM runtime PASS and not release PASS.
Next: Block H Telegram envelope, mapping, report period config and report templates.
No issue comments.


## BEM-936 completed | 2026-05-31
Implemented Block E managed channel mechanics after BEM-935.
Created event_writer, managed_channel_consumer, dead-letter log, processed log, consumer status, static selftest and validator.
Result: BLOCK_E_CHANNEL_MECHANICS_PASS. This is mechanics baseline, not release PASS.
Next: Block F dispatch lifecycle and provider-aware dispatch consumer.
No issue comments.


## BEM-939 completed | 2026-05-31
Implemented Block H Telegram/reporting after BEM-938.
Created telegram_input_envelope_schema, telegram_to_managed_channel_mapping, report_period_config, canonical report templates, telegram_input_mapper and validator.
Result: BLOCK_H_TELEGRAM_PASS. This is mock/foundation only, not production Telegram PASS and not release PASS.
Next: Block I proof and CI hardening: release_proof_manifest, non-null SHA policy, proof validator.
No issue comments.


## BEM-937 completed | 2026-05-31
Implemented Block F dispatch lifecycle after BEM-936.
Created provider-aware dispatch_lifecycle_schema, dispatch_consumer, processed/dead-letter logs, status, static test and validator.
Result: BLOCK_F_DISPATCH_LIFECYCLE_PASS. This is lifecycle baseline, not release PASS.
Next: Block G object/contour lifecycle runners and report writers.
No issue comments.


## BEM-940 completed | 2026-05-31
Implemented Block I proof hardening after BEM-939.
Created release_proof_manifest_schema, release_proof_manifest draft, proof_policy, validate_release_proof and proof_manifest_updater.
Result: BLOCK_I_PROOF_HARDENING_PASS. commit_sha remains null, therefore this is not release PASS.
Next: Block J E2E mock tests and production status split.
No issue comments.


## BEM-941 completed | 2026-05-31
Implemented Block J E2E foundation after BEM-940.
Created E2E mock test files, provider failover E2E, managed channel E2E, canonical report test, e2e_run_manifest and telegram_e2e_status with production_status=null.
Result: BLOCK_J_E2E_FOUNDATION_PASS. This is not production PASS.
Next: Block K operator gates and production gate records.
No issue comments.


## BEM-942 completed | 2026-05-31
Implemented Block K operator gates after BEM-941.
Created production_operator_gate, secret_names, issue31 write policy, schedule/daemon gate, Telegram production gate, live LLM runtime gate and validator.
Result: BLOCK_K_OPERATOR_GATES_PASS. Operator approvals are still required for production actions.
Next: Block L Claude re-audit checklist, evidence index and audit bundle baseline.
No issue comments.


## BEM-943 completed | 2026-05-31
Implemented Block L audit baseline after BEM-942.
Created Claude re-audit checklist, evidence index, audit bundle manifest and validator.
Result: BLOCK_L_AUDIT_BASELINE_PASS. This is foundation evidence, not external audit PASS.
Next: Block M validation harness and roadmap status rollup.
No issue comments.


## BEM-944 completed | 2026-05-31
Implemented Block M validation harness and roadmap status rollup after BEM-943.
Created validate_foundation_all, roadmap_status_rollup and roadmap status report.
Result: BLOCK_M_VALIDATION_HARNESS_PASS. This is foundation validation harness, not release PASS.
Next: Block N final consolidation, release decision draft and operator/Claude re-audit handoff.
No issue comments.


## BEM-945 completed | 2026-05-31
Implemented Block N final handoff after BEM-944.
Created final foundation handoff, operator_gate_boundary, roadmap_status_final, external audit handoff and validator.
Result: BLOCK_N_HANDOFF_PASS. BEM-931 foundation roadmap is 14/14 by files. Release PASS is still false because commit_sha is null and production/operator/audit gates remain.
Next: operator/external auditor decision: production Telegram test, live LLM runtime, schedule/daemon, non-null CI/Git SHA and Claude re-audit.
No issue comments.


## BEM-945 completed | 2026-05-31
Implemented Block N final consolidation after BEM-944.
Created foundation execution summary, release decision draft, operator handoff, Claude re-audit handoff and updated roadmap_status_rollup to 14/14 foundation blocks.
Result: CONDITIONAL_FOUNDATION_PASS for BEM-931 foundation roadmap. Release PASS remains BLOCKED because commit_sha is null, production Telegram is not verified, live LLM runtime is operator-gated and external Claude re-audit is required.
Next: external Claude re-audit and CI/Git SHA proof resolution.
No issue comments.


## BEM-946 in progress/completed | 2026-05-31
Operator provided GitHub Actions screenshots showing Codex Runner failed after local completed summary because git push was rejected: remote main had work not present locally.
Decision: workflow failure overrides local completed summary. Local SHA is not release proof if push failed.
Implemented push conflict policy and safe push helper with fetch/rebase/retry.
Created BEM946_PUSH_FAILURE_DIAGNOSIS, push_conflict_policy and git_push_with_retry helper.
Next: verify BEM-946 task result and then re-run/fix final proof if needed.
No issue comments.


## BEM-947 completed | 2026-05-31
Recorded post-push reverify after operator screenshots showed BEM-945 GitHub job failed on push despite local completed summary.
Created BEM947_POST_PUSH_REVERIFY, post_push_reverify_status and operator screenshot response.
Result: POST_PUSH_REVERIFY_RECORDED. Foundation remains 14/14 by files, but release PASS remains false until remote/non-null SHA, production Telegram gate, live LLM gate and external re-audit.
No issue comments.


## BEM-946 in progress | 2026-05-31
Operator screenshot confirmed Codex Runner push rejection: remote main advanced and local runner push was rejected.
Correction: treat BEM-932..945 as local/workflow artifacts until remote proof exists. Create push rejected diagnosis, push retry plan and remote proof policy.
Next: patch codex-runner.yml push step with fetch/rebase/retry and rehydrate foundation files after push fix.
No issue comments.
### BEM-955 | AGENT CONTEXT UPDATE AFTER EXECUTOR PROBE | 2026-05-31 | 13:23 (UTC+3)
- BEM-948: Claude remarks response task completed in
### BEM-975 | CANONICAL SHA GATE REPORT | 2026-05-31 | 15:18 (UTC+3)
- Completed
### BEM-977 | CLAUDE RE-AUDIT CHECKLIST STATE | 2026-05-31 | 15:22 (UTC+3)
-
### BEM-978 | RELEASE DECISION NO_PASS | 2026-05-31 | 15:23 (UTC+3)
- Claude re-audit preparation stage completed: 3/3 (100%)
### BEM-979 | PRODUCTION GATES REGISTER | 2026-05-31 | 15:25 (UTC+3)
-
### BEM-980 | REPORT CANON CORRECTION | 2026-05-31 | 15:27 (UTC+3)
- Corrected report canon after operator objection
### BEM-981 | OPERATOR-SAFE PRODUCTION CHECKLIST | 2026-05-31 | 15:40 (UTC+3)
-
### BEM-982 | TELEGRAM STATUS SPLIT | 2026-05-31 | 15:42 (UTC+3)
-
### BEM-983 | LIVE LLM
### BEM-984 | EXTERNAL CLAUDE RE-AUDIT STATUS | 2026-05-31 | 15:45 (UTC+3)
-
### BEM-985 | BLOCKER DASHBOARD CANONICAL | 2026-05-31 | 15:47 (UTC+3)
-
