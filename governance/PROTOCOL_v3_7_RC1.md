# ПРОТОКОЛ АВТОНОМНОЙ СИСТЕМЫ С ЕДИНЫМ РЕЕСТРОМ
## Версия: v3.7-RC1 (RU)
**Заменяет:** v3.6-RC2  
**Дата:** 2026-04-13  
**Формат выпуска:** SINGLE-FILE CANONICAL MD  
**Статус:** RELEASE CANDIDATE FOR MANAGED AUTOMATED PRODUCTION WITH CODEX CODESPACES RUNTIME

---

## СВОДКА ВЕРСИИ

| Поле | Значение |
|---|---|
| Ключевое изменение | Автономный блок переведен с модели внешнего ORCHESTRATOR-вызова GPT на модель исполнения ролей в GitHub Codespaces runtime |
| Модель ролей | GPT-5.4 Codex |
| Среда исполнения ролей | GitHub Codespaces |
| Роли | EXECUTOR, AUDITOR |
| Кто сохраняет состояние | SYSTEM через главный реестр |
| Кто остается источником истины | Главный реестр и зафиксированные артефакты |
| Что убрано из обязательного runtime-контура | Внешний ORCHESTRATOR как обязательный посредник интеллектуального вызова |
| Что сохраняется | SYSTEM, validator, ledger-writer, router, watchdog, archive, recovery |
| Что не изменяется | Принцип: GPT-роль не изменяет ledger напрямую и не утверждает критический переход состояния |

---

## ИЗМЕНЕНИЯ ОТ v3.6-RC2

| № | Изменение |
|---|---|
| 1 | Переписана цель системы под Codespaces-based автономное исполнение |
| 2 | Переписан раздел ролей: ORCHESTRATOR исключен как обязательная runtime-роль |
| 3 | Переписан физический интерфейс GPT-ролей |
| 4 | Переписана модель активации ролей |
| 5 | Обновлен allowlist workflow под Codespaces runtime |
| 6 | Обновлен cold start |
| 7 | Обновлен раздел миграции |
| 8 | Обновлен CORE domain |
| 9 | Обновлены release criteria |
| 10 | Обновлены границы ответственности GPT-роли |

---

## РАЗДЕЛ 1. ЦЕЛЬ СИСТЕМЫ

| Поле | Значение |
|---|---|
| Цель | Автоматизированная работа двух GPT-ролей через GitHub Codespaces runtime и GitHub-репозиторий |
| Интеллектуальные функции ролей | Анализ, подготовка артефактов, подготовка изменений, проверка, формирование решений |
| Среда исполнения роли | GitHub Codespaces |
| Назначение GitHub-репозитория | Хранение кода, артефактов, истории изменений, проверок и запросов на слияние |
| Назначение SYSTEM | Маршрутизация, валидация, запись в реестр, проверки, контроль зависаний, архивирование, восстановление |
| Источник истины | Главный реестр и зафиксированные артефакты |
| Что не является источником истины | Память GPT-роли, временное состояние Codespaces runtime |
| Целевая модель | Управляемая автоматизация с жестким конечным автоматом |

| Устойчивость системы обеспечивается против | Значение |
|---|---|
| Дрейф | Да |
| Скрытое повреждение данных | Да |
| Рассинхронизация протокола | Да |
| Повторная обработка | Да |
| Маршрутизационные циклы | Да |
| Ложная фиксация выполненного шага | Да |

---

## РАЗДЕЛ 2. СТРУКТУРА ДАННЫХ

| Категория | Путь / правило |
|---|---|
| Canonical state file | `governance/exchange_ledger.csv` |
| Proposal artifacts | `governance/proposals/{task_id}.md` |
| Plan artifacts | `governance/plans/{task_id}.md` |
| Decision artifacts | `governance/decisions/{event_id}.md` |
| Fix artifacts | `governance/fixes/{event_id}.md` |
| Proofs | `governance/proofs/{task_id}/...` |
| Recovery | `governance/recovery/...` |
| Archive | `governance/archive/YYYYMM/...` |
| Operator data | `governance/operator/...` |
| Protocol | `governance/PROTOCOL.md` |

| Branches | Шаблон |
|---|---|
| Implementation branch | `task/{task_id}/implementation` |
| Fix branch | `task/{task_id}/fix-{n}` |
| Rollback branch | `task/{task_id}/rollback-{n}` |

| Rules | Значение |
|---|---|
| Artifact without ledger reference does not exist for the system | Mandatory |
| CODE, CONFIG, DOCUMENT use branch + PR path only | Mandatory |
| ANALYSIS and NO_OP may use artifact-only path | Allowed |
| Routing canon is exchange_ledger.csv only | Mandatory |
| Artifacts are UTF-8 markdown | Mandatory |
| PROTOCOL.md is mandatory and integrity-checked | Mandatory |

---

## РАЗДЕЛ 3. ИНВАРИАНТЫ СИСТЕМЫ

| Код | Инвариант |
|---|---|
| I-01 | one active task |
| I-02 | one active branch |
| I-03 | CODE/CONFIG/DOCUMENT only via PR |
| I-04 | append-only ledger |
| I-05 | single writer: ledger_writer.py |
| I-06 | previous+new row validation |
| I-07 | legacy disabled |
| I-08 | plan-before-code |
| I-09 | review-before-merge |
| I-10 | MERGE_PR -> PR_MERGED -> RUN_AUTO_CHECK |
| I-11 | system-owned merge |
| I-12 | synced branch required |
| I-13 | NO_OP without code mutation allowed |
| I-14 | rollback only via PR |
| I-15 | secrets forbidden |
| I-16 | primary activation through codespaces runtime trigger |
| I-17 | fallback polling only on activation failure |
| I-18 | PR_MERGED observable in ledger |
| I-19 | typed supersession |
| I-20 | CONFIG high-risk gate |
| I-21 | allowed workflow set enforced |
| I-22 | certification gate mandatory |
| I-23 | branch cleanup mandatory |
| I-24 | RESULT_REVIEW only for ANALYSIS and NO_OP |
| I-25 | no orphaned branches |
| I-26 | PROTOCOL.md mandatory |
| I-27 | protocol structural integrity mandatory |
| I-28 | protocol fingerprint lock mandatory |
| I-29 | protocol anchor integrity mandatory |
| I-30 | artifact semantic integrity mandatory |
| I-31 | explicit infra-failure routing mandatory |
| I-32 | rollback post-check ownership singular |
| I-33 | recovery resume contract mandatory |
| I-34 | proof semantic match mandatory |
| I-35 | CORE failure domain escalates faster |
| I-36 | critical system event uniqueness mandatory |
| I-37 | no state transition from GPT text alone |
| I-38 | no state progression on runtime execution failure |
| I-39 | no repeated logical execution without idempotency control |
| I-40 | no routing loop without explicit failure record |

---

## РАЗДЕЛ 4. РОЛИ

| Роль | Полномочия | Ограничения |
|---|---|---|
| EXECUTOR | Формирует предложение, план, изменения, исправления, откаты; в Codespaces runtime изменяет рабочее дерево репозитория в рамках допустимого шага; готовит артефакты | Не выполняет слияние; не утверждает собственные результаты; не изменяет главный реестр напрямую |
| AUDITOR | Проверяет предложения, планы, изменения, исправления, откаты и результаты; анализирует diff, артефакты и проверки; принимает решения APPROVE / REJECT / REVISE / CONFIRM / WAIT / ESCALATE / RECOVER | Не пишет продуктовый код реализации; не выполняет слияние; не изменяет главный реестр напрямую; не утверждает устаревшие артефакты |
| SYSTEM | Валидирует схему и переходы; обеспечивает запись в реестр; контролирует инварианты; запускает проверки; выполняет freeze / unfreeze / recovery / archive | Не принимает продуктовых решений по смыслу задачи |
| OPERATOR | Допускается для первичной настройки среды, аварийного вмешательства и восстановления | Не участвует в штатном рабочем цикле разработки |

---

## РАЗДЕЛ 5. КТО НАЗНАЧАЕТ СЛЕДУЮЩУЮ РОЛЬ

| Контур | Кто назначает |
|---|---|
| Semantic transitions | AUDITOR via decisions artifact |
| Mechanical transitions | Protocol automatically |
| Technical execution | SYSTEM performs allowed technical steps only after validation |

---

## РАЗДЕЛ 6. ФИЗИЧЕСКИЙ ИНТЕРФЕЙС GPT-РОЛЕЙ

| Поле | EXECUTOR | AUDITOR |
|---|---|---|
| Среда исполнения | GitHub Codespaces runtime | GitHub Codespaces runtime |
| Вход | Текущее состояние, артефакты, ограничения, next step, diff/commit/checks при необходимости | Текущее состояние, проверяемый артефакт, diff, reviewed_commit_sha, результаты проверок, история решений |
| Выход | Текст артефакта, список изменений, proof refs, риски, откат, предлагаемое действие | Тип решения, объект проверки, обоснование, условия, назначение следующего шага |

| Разрешено GPT-роли | Значение |
|---|---|
| Читать файлы репозитория | Да |
| Изменять рабочее дерево в Codespaces | Да |
| Запускать допустимые команды | Да |
| Готовить артефакты | Да |

| Запрещено GPT-роли | Значение |
|---|---|
| Писать в главный реестр напрямую | Да |
| Менять системное состояние напрямую | Да |
| Обходить системную валидацию | Да |
| Финально утверждать критический переход состояния | Да |

---

## РАЗДЕЛ 7. ШАБЛОНЫ АРТЕФАКТОВ

| Artifact | Required fields |
|---|---|
| proposal | task_id, proposal_author, ts_utc, task_type, step_name, title, parent_task_id, description, expected_outcome, proof_target, constraints, notes |
| plan | task_id, proposal_ref, plan_author, ts_utc, task_type, approach, files_to_create, files_to_modify, files_to_delete, proof_target, risk_notes, rollback_plan, config_risk_class |
| decision | decision_id, task_id, parent_event_id, decision_author, ts_utc, decision_type, decision, reviewed_ref, reviewed_commit_sha, next_role_assigned, next_action_assigned, rationale, conditions, flags |
| fix | task_id, parent_event_id, fix_author, ts_utc, fix_type, error_class, root_cause, proposed_change, files_affected, proof_target, rollback_plan, notes |

---

## РАЗДЕЛ 8. МОДЕЛЬ АКТИВАЦИИ РОЛЕЙ

| Поле | Значение |
|---|---|
| Основной режим активации | После успешной записи новой строки в главный реестр SYSTEM определяет следующую допустимую роль и запускает соответствующий Codespaces runtime шаг |
| Что делает SYSTEM | Считывает состояние, определяет next role/next action, подготавливает packet, запускает роль в Codespaces, принимает результат, передает его в валидацию, после валидации инициирует запись следующего события |
| Резервный режим | Применяется только при неуспешной активации runtime, сбое Codespaces execution или невозможности безопасного исполнения роли |
| Подтверждение доставки | Не факт старта runtime, а успешное завершение шага с принятием артефакта или корректной фиксацией ошибки в реестре |

| Activation markers | Значение |
|---|---|
| activation_mode | PRIMARY / FALLBACK |
| runtime_mode | CODESPACES |
| fallback_started_at | supported |
| fallback_expiry_at | supported |

---

## РАЗДЕЛ 9. PAYLOAD-СХЕМЫ repository_dispatch

| Payload | Fields |
|---|---|
| write-ledger-row | event_type, actor_role, artifact_path, protocol_event_type, task_id, parent_event_id, artifact_ref, proof_ref, ci_ref, log_ref, error_class, error_details, commit_sha, stall_class, infra_scope, causation_id, correlation_id, idempotency_key, producer, producer_run_id |
| role-activated | event_type, task_id, event_id, next_role, next_action, artifact_ref, commit_sha, correlation_id, producer_run_id |

---

## РАЗДЕЛ 10. ФОРМАТ ГЛАВНОГО РЕЕСТРА

| Поле | Значение |
|---|---|
| Заголовок | `event_id,parent_event_id,task_id,ts_utc,actor_role,event_type,state,decision,result,summary,artifact_ref,proof_ref,ci_ref,log_ref,error_class,error_details,next_role,next_action,protocol_version,commit_sha,stall_class,infra_scope,causation_id,correlation_id,idempotency_key,producer,producer_run_id` |

| Дополнительные поля | Назначение |
|---|---|
| causation_id | Идентификатор события, ставшего причиной текущего |
| correlation_id | Идентификатор единого контура обработки |
| idempotency_key | Защита от повторного выполнения логического действия |
| producer | Источник события |
| producer_run_id | Идентификатор конкретного запуска |

| ledger_writer.py обязан отклонять | Значение |
|---|---|
| duplicate event_id | Да |
| duplicate idempotency_key for same logical action | Да |
| запрещенный routing cycle | Да |
| недопустимый источник события | Да |

| ledger_writer.py обязан делать | Значение |
|---|---|
| читать SHA файла | Да |
| валидировать схему строки | Да |
| валидировать переход | Да |
| повторять при 409 | Да |
| проверять existence referenced artifact | Да |
| проверять artifact semantics | Да |
| применять protocol integrity gate | Да |

---

## РАЗДЕЛ 11. ДОПУСТИМЫЕ event_type

| Actor | Allowed event_type |
|---|---|
| EXECUTOR | TASK_PROPOSED, IMPLEMENTATION_PLAN, IMPLEMENTATION_COMPLETED, ERROR_FIX_PROPOSED, ERROR_FIX_COMPLETED, ROLLBACK_PROPOSED, ROLLBACK_STARTED, UNFREEZE_PROPOSED |
| AUDITOR | AUDIT_DECISION, PLAN_DECISION, CODE_REVIEW_DECISION, RESULT_REVIEW_CONFIRMED, FIX_DECISION, VERIFICATION_CONFIRMED, VERIFICATION_REJECTED, STALL_DECISION, DEPENDENCY_DECISION, ROLLBACK_DECISION, UNFREEZE_APPROVED, LEDGER_RECOVERY_CONFIRMED, OPERATOR_OVERRIDE_CONFIRMED |
| SYSTEM | AUTO_CHECK_STARTED, AUTO_CHECK_PASSED, AUTO_CHECK_FAILED, PR_MERGED, TASK_CLOSED, PROTOCOL_REJECTED, TASK_STALLED, SYSTEM_BOOTSTRAP, ROLLBACK_COMPLETED, SYSTEM_FREEZE_REQUESTED, SYSTEM_FROZEN, SYSTEM_UNFROZEN, EXTERNAL_DEPENDENCY_FAILED, EXTERNAL_DEPENDENCY_RESTORED, BRANCH_SUPERSEDED, PLAN_SUPERSEDED, FIX_PROPOSAL_SUPERSEDED, ARCHIVE_COMPLETED, ARCHIVE_INTEGRITY_FAILED, LEDGER_CORRUPTION_DETECTED, LEDGER_RECOVERY_STARTED, LEDGER_RECOVERY_COMPLETED, ROLE_ACTIVATION_FAILED, ROLE_ACTIVATION_RESTORED, ARTIFACT_INTEGRITY_FAILED, WORKFLOW_SET_DRIFT_DETECTED, ORPHANED_BRANCH_DETECTED, OPERATOR_OVERRIDE_RECORDED, PROTOCOL_DOC_MISSING, PROTOCOL_VERSION_MISMATCH, PROTOCOL_FINGERPRINT_MISMATCH, PROTOCOL_STRUCTURE_CORRUPTED |

---

## РАЗДЕЛ 12. ДОПУСТИМЫЕ state

| Allowed states |
|---|
| PROPOSED |
| AUDIT_PENDING |
| APPROVED |
| REJECTED |
| PLAN_PENDING |
| PLAN_APPROVED |
| PLAN_REJECTED |
| IN_PROGRESS |
| REVIEW_PENDING |
| IMPLEMENTED |
| CHECK_PENDING |
| CHECK_FAILED |
| CHECK_PASSED |
| FIX_PENDING |
| FIX_APPROVED |
| FIX_REJECTED |
| ROLLBACK_PENDING |
| ROLLBACK_IN_PROGRESS |
| RESULT_REVIEWED |
| VERIFIED |
| CLOSED |
| BLOCKED |

---

## РАЗДЕЛ 13. ДОПУСТИМЫЕ decision / result / error_class / next_action / stall_class / infra_scope

| Категория | Значения |
|---|---|
| decision | APPROVE, REJECT, REVISE, CONFIRM, RETRY, ESCALATE, WAIT, RECOVER |
| result | SUCCESS, FAILURE, PARTIAL, BLOCKED, NO_OP |
| next_action | REVIEW_TASK, PROPOSE_TASK, WRITE_PLAN, REVIEW_PLAN, IMPLEMENT_TASK, REVIEW_CODE, MERGE_PR, REVIEW_RESULT, RUN_AUTO_CHECK, PROPOSE_FIX, REVIEW_FIX, IMPLEMENT_FIX, VERIFY_RESULT, CLOSE_TASK, REVIEW_STALL, REVIEW_DEPENDENCY_BLOCK, REVIEW_ROLLBACK, EXECUTE_ROLLBACK, REVIEW_UNFREEZE, EXECUTE_UNFREEZE, VERIFY_LEDGER_RECOVERY, NONE |
| stall_class | EXECUTOR_DELAY, AUDITOR_DELAY, SYSTEM_DELAY, INFRA_DELAY, PROTOCOL_LOOP, ACTIVATION_FAILURE_LOOP |
| infra_scope | CORE, NON_CORE, NONE |

| error_class |
|---|
| TEST_FAILURE |
| LINT_FAILURE |
| BUILD_FAILURE |
| SCHEMA_FAILURE |
| PROTOCOL_FAILURE |
| RUNTIME_FAILURE |
| PROOF_FAILURE |
| CI_FAILURE |
| STALL_FAILURE |
| REVIEW_FAILURE |
| DRIFT_FAILURE |
| POST_MERGE_FAILURE |
| ACTIONS_QUOTA_FAILURE |
| WORKFLOW_DISABLED |
| REPO_WRITE_FAILURE |
| PR_MERGE_BLOCKED |
| BRANCH_PROTECTION_FAILURE |
| GITHUB_API_FAILURE |
| EXTERNAL_DEPENDENCY_FAILURE |
| LEDGER_CORRUPTION |
| SECRET_LEAK |
| ACTIVATION_FAILURE |
| ARTIFACT_INTEGRITY_FAILURE |
| WORKFLOW_SET_DRIFT |
| ARCHIVE_INTEGRITY_FAILURE |
| ORPHANED_BRANCH |
| PROTOCOL_DOC_FAILURE |
| PROTOCOL_VERSION_FAILURE |
| PROTOCOL_FINGERPRINT_FAILURE |
| PROTOCOL_STRUCTURE_FAILURE |
| MODEL_OUTPUT_INVALID |
| MODEL_TIMEOUT |
| MODEL_CONTEXT_FAILURE |
| MODEL_TOOL_FAILURE |
| CODEX_RUNTIME_FAILURE |
| CODESPACES_RUNTIME_FAILURE |
| IDEMPOTENCY_FAILURE |
| ROUTING_LOOP_FAILURE |

---

## РАЗДЕЛ 14. МАТРИЦА ВЛАДЕНИЯ СОСТОЯНИЯМИ

| State | Ownership transition |
|---|---|
| AUDIT_PENDING | EXECUTOR -> AUDITOR |
| PLAN_PENDING | EXECUTOR -> AUDITOR |
| PLAN_APPROVED | AUDITOR -> EXECUTOR |
| REVIEW_PENDING | EXECUTOR -> AUDITOR |
| IMPLEMENTED | AUDITOR -> SYSTEM |
| CHECK_PENDING | SYSTEM -> SYSTEM |
| CHECK_FAILED | SYSTEM -> EXECUTOR |
| CHECK_PASSED | SYSTEM -> AUDITOR |
| FIX_PENDING | EXECUTOR -> AUDITOR |
| FIX_APPROVED | AUDITOR -> EXECUTOR |
| ROLLBACK_PENDING | EXECUTOR -> AUDITOR |
| ROLLBACK_IN_PROGRESS | AUDITOR -> EXECUTOR then SYSTEM |
| RESULT_REVIEWED | AUDITOR -> SYSTEM(NO_OP) or AUDITOR(ANALYSIS) |
| VERIFIED | AUDITOR -> SYSTEM |
| BLOCKED | SYSTEM/AUDITOR -> AUDITOR/SYSTEM |

---

## РАЗДЕЛ 15. TASK IDENTITY RULES

| Rule | Значение |
|---|---|
| 1 | task_id never reused |
| 2 | fix and rollback stay within same task_id |
| 3 | supersession does not create new business identity automatically |
| 4 | new business task requires new TASK_PROPOSED and new task_id |
| 5 | archive preserves task_id integrity as historical unit |

---

## РАЗДЕЛ 16. BRANCH LIFECYCLE

| Stage | Rule |
|---|---|
| CREATE | after PLAN_DECISION(APPROVE) |
| ACTIVE | one branch per task |
| REVIEWED | commit_sha frozen in ledger |
| MERGED | delete branch after PR_MERGED |
| SUPERSEDED | via BRANCH_SUPERSEDED |
| ABANDONED/ORPHANED | detected by watchdog |

---

## РАЗДЕЛ 17. SEMANTIC DUPLICATE RULES

| Категория | Правило |
|---|---|
| General duplicates forbidden | TASK_PROPOSED, IMPLEMENTATION_PLAN, CODE_REVIEW_DECISION, ERROR_FIX_PROPOSED, ROLLBACK_PROPOSED, DEPENDENCY_DECISION, STALL_DECISION |
| Critical system uniqueness | PR_MERGED, AUTO_CHECK_STARTED, AUTO_CHECK_PASSED, AUTO_CHECK_FAILED, TASK_CLOSED, SYSTEM_FROZEN, SYSTEM_UNFROZEN, ROLE_ACTIVATION_FAILED, ROLE_ACTIVATION_RESTORED |
| Critical execution uniqueness | Codespaces role execution step start/fail/complete must be unique within same correlation_id + idempotency_key where applicable |

---

## РАЗДЕЛ 18. ПРАВИЛА МАРШРУТИЗАЦИИ

| Transition | Route |
|---|---|
| TASK_PROPOSED | AUDIT_PENDING, AUDITOR:REVIEW_TASK |
| AUDIT_DECISION(APPROVE) | APPROVED, decision-routed:WRITE_PLAN |
| AUDIT_DECISION(REJECT) | REJECTED, decision-routed:REVIEW_TASK |
| IMPLEMENTATION_PLAN | PLAN_PENDING, AUDITOR:REVIEW_PLAN |
| PLAN_DECISION(APPROVE) | PLAN_APPROVED, decision-routed:IMPLEMENT_TASK |
| PLAN_DECISION(REJECT/REVISE) | PLAN_REJECTED, decision-routed:WRITE_PLAN |
| IMPLEMENTATION_COMPLETED | REVIEW_PENDING, AUDITOR:REVIEW_CODE |
| CODE_REVIEW_DECISION(APPROVE) | IMPLEMENTED, SYSTEM MERGE PATH |
| CODE_REVIEW_DECISION(REJECT/REVISE) | PLAN_APPROVED, decision-routed:IMPLEMENT_TASK |
| PR_MERGED | CHECK_PENDING, SYSTEM:RUN_AUTO_CHECK |
| AUTO_CHECK_PASSED | CHECK_PASSED, AUDITOR:VERIFY_RESULT |
| AUTO_CHECK_FAILED | CHECK_FAILED, EXECUTOR:PROPOSE_FIX |
| RESULT_REVIEW_CONFIRMED(NO_OP) | RESULT_REVIEWED, SYSTEM:RUN_AUTO_CHECK |
| RESULT_REVIEW_CONFIRMED(ANALYSIS) | RESULT_REVIEWED, AUDITOR:VERIFY_RESULT |
| VERIFICATION_CONFIRMED | VERIFIED, decision-routed:CLOSE_TASK |
| VERIFICATION_REJECTED | CHECK_FAILED, decision-routed:PROPOSE_FIX |
| ERROR_FIX_PROPOSED | FIX_PENDING, AUDITOR:REVIEW_FIX |
| FIX_DECISION(APPROVE) | FIX_APPROVED, decision-routed:IMPLEMENT_FIX |
| FIX_DECISION(REJECT/REVISE) | FIX_REJECTED, decision-routed:PROPOSE_FIX |
| ERROR_FIX_COMPLETED | REVIEW_PENDING, AUDITOR:REVIEW_CODE |
| ROLLBACK_PROPOSED | ROLLBACK_PENDING, AUDITOR:REVIEW_ROLLBACK |
| ROLLBACK_DECISION(APPROVE) | ROLLBACK_IN_PROGRESS, decision-routed:EXECUTE_ROLLBACK |
| ROLLBACK_STARTED | ROLLBACK_IN_PROGRESS, AUDITOR:REVIEW_CODE |
| ROLLBACK_COMPLETED | CHECK_PENDING, SYSTEM:RUN_AUTO_CHECK |
| TASK_STALLED | BLOCKED, AUDITOR:REVIEW_STALL |
| EXTERNAL_DEPENDENCY_FAILED | BLOCKED, AUDITOR:REVIEW_DEPENDENCY_BLOCK |
| EXTERNAL_DEPENDENCY_RESTORED | BLOCKED, AUDITOR:REVIEW_DEPENDENCY_BLOCK |
| SYSTEM_FROZEN | BLOCKED, AUDITOR:REVIEW_UNFREEZE |
| SYSTEM_BOOTSTRAP | CLOSED, EXECUTOR:PROPOSE_TASK |
| LEDGER_CORRUPTION_DETECTED | BLOCKED, SYSTEM:VERIFY_LEDGER_RECOVERY |
| LEDGER_RECOVERY_COMPLETED | BLOCKED, AUDITOR:VERIFY_LEDGER_RECOVERY |
| LEDGER_RECOVERY_CONFIRMED | CLOSED/RESTORED, EXECUTOR:REVIEW_TASK |
| ARCHIVE_INTEGRITY_FAILED | BLOCKED, AUDITOR:REVIEW_STALL |
| ARTIFACT_INTEGRITY_FAILED | BLOCKED, AUDITOR:REVIEW_STALL |
| WORKFLOW_SET_DRIFT_DETECTED | BLOCKED, AUDITOR:REVIEW_STALL |
| ORPHANED_BRANCH_DETECTED | BLOCKED, AUDITOR:REVIEW_STALL |
| PROTOCOL_DOC_MISSING | BLOCKED, AUDITOR:REVIEW_STALL |
| PROTOCOL_VERSION_MISMATCH | BLOCKED, AUDITOR:REVIEW_STALL |
| PROTOCOL_FINGERPRINT_MISMATCH | BLOCKED, AUDITOR:REVIEW_STALL |
| PROTOCOL_STRUCTURE_CORRUPTED | BLOCKED, AUDITOR:REVIEW_STALL |

| Любой переход состояния выполняется только после | Значение |
|---|---|
| 1 | Получен допустимый артефакт от соответствующей роли |
| 2 | Артефакт прошел структурную и семантическую валидацию |
| 3 | Требуемое техническое действие успешно выполнено |
| 4 | SYSTEM успешно записал новое событие в главный реестр |

---

## РАЗДЕЛ 19. ТАБЛИЦА МАРШРУТИЗАЦИИ ПРИ ЗАВИСАНИИ

| next_action | Route |
|---|---|
| WRITE_PLAN | EXECUTOR:WRITE_PLAN |
| REVIEW_PLAN | AUDITOR:REVIEW_PLAN |
| IMPLEMENT_TASK | EXECUTOR:IMPLEMENT_TASK |
| REVIEW_CODE | AUDITOR:REVIEW_CODE |
| MERGE_PR | SYSTEM:MERGE_PR |
| RUN_AUTO_CHECK | SYSTEM:RUN_AUTO_CHECK |
| PROPOSE_FIX | EXECUTOR:PROPOSE_FIX |
| IMPLEMENT_FIX | EXECUTOR:IMPLEMENT_FIX |
| VERIFY_RESULT | AUDITOR:VERIFY_RESULT |
| CLOSE_TASK | SYSTEM:CLOSE_TASK |
| EXECUTE_ROLLBACK | EXECUTOR:EXECUTE_ROLLBACK |
| unknown | AUDITOR:REVIEW_STALL |

---

## РАЗДЕЛ 20. ЗАПРЕЩЁННЫЕ ПЕРЕХОДЫ

| № | Запрещенный переход |
|---|---|
| 1 | PROPOSED -> CLOSED |
| 2 | AUDIT_PENDING -> IMPLEMENTED |
| 3 | APPROVED -> IMPLEMENTED without plan |
| 4 | PLAN_APPROVED -> REVIEW_PENDING without branch and PR |
| 5 | REVIEW_PENDING -> CHECK_PENDING without CODE_REVIEW + PR_MERGED |
| 6 | CHECK_FAILED -> CLOSED |
| 7 | FIX_PENDING -> CLOSED |
| 8 | REJECTED -> TASK_CLOSED without new proposal |
| 9 | SYSTEM -> APPROVED |
| 10 | EXECUTOR -> VERIFIED |
| 11 | direct CODE/CONFIG/DOCUMENT write to main |
| 12 | second active branch without BRANCH_SUPERSEDED |
| 13 | approving superseded artifact |
| 14 | merge before CODE_REVIEW_DECISION(APPROVE) |
| 15 | VERIFICATION_CONFIRMED before PR_MERGED and AUTO_CHECK_PASSED |
| 16 | IMPLEMENTATION_COMPLETED from stale branch |
| 17 | ERROR_FIX_COMPLETED from stale branch |
| 18 | ROLLBACK_COMPLETED without ROLLBACK_STARTED |
| 19 | new task while SYSTEM_FROZEN |
| 20 | secrets in repository |
| 21 | MERGE_PR without reviewed SHA == current PR head SHA |
| 22 | RESULT_REVIEW_CONFIRMED for CODE/DOCUMENT/CONFIG |
| 23 | normal progression while workflow drift unresolved |
| 24 | normal progression while orphaned branch unresolved |
| 25 | progression with missing/mismatched protocol canon |
| 26 | NO_OP without semantic proof match |
| 27 | duplicate final rollback/check events |
| 28 | recovery without resume contract |
| 29 | protocol hard-gate mismatch treated as warning-only |
| 30 | прямое изменение состояния системы по одному только текстовому ответу GPT без системной валидации |
| 31 | запись в главный реестр без idempotency_key, если событие относится к повторяемому техническому контуру |
| 32 | продвижение состояния при сбое Codespaces runtime |
| 33 | продвижение состояния, если ответ GPT не прошел структурную проверку |
| 34 | запуск нового смыслового шага при незавершенном цикле активации той же роли по тому же correlation_id |
| 35 | автоматическое выполнение критического действия на основании неполного контекста |
| 36 | трактовка факта запуска runtime как факта успешного выполнения смыслового действия |

---

## РАЗДЕЛ 21. ALLOWED WORKFLOW SET / LEGACY DENYLIST

| Allowed workflows |
|---|
| ledger-protocol-validate.yml |
| ledger-writer.yml |
| role-router.yml |
| executor-notify.yml |
| auditor-notify.yml |
| system-router.yml |
| auto-check.yml |
| watchdog.yml |
| close-task.yml |
| pr-auto-merge.yml |
| rollback-check.yml |
| freeze-control.yml |
| dependency-monitor.yml |
| archive-rotation.yml |
| recovery-check.yml |
| executor-runner-v3_6_rc2.yml |
| auditor-runner-v3_6_rc2.yml |
| executor-ledger-return-v3_6_rc2.yml |
| auditor-ledger-return-v3_6_rc2.yml |

| Denylist |
|---|
| gcs-request-ingress.yml |
| ledger-router.yml |
| analyst-runner.yml |
| executor-real-call-v3_6_rc2.yml |
| auditor-real-call-v3_6_rc2.yml |

| Core workflows |
|---|
| ledger-writer.yml |
| ledger-protocol-validate.yml |
| role-router.yml |
| system-router.yml |
| pr-auto-merge.yml |
| watchdog.yml |
| executor-runner-v3_6_rc2.yml |
| auditor-runner-v3_6_rc2.yml |
| executor-ledger-return-v3_6_rc2.yml |
| auditor-ledger-return-v3_6_rc2.yml |

---

## РАЗДЕЛ 22. МАРШРУТЫ ПО ТИПУ ЗАДАЧИ

| Task type | Route |
|---|---|
| CODE | branch + PR + review + merge + auto-check |
| DOCUMENT | same as CODE |
| CONFIG | same as CODE + risk acceptance + smoke test |
| ANALYSIS | artifact-only, no PR, no code auto-check |
| NO_OP | existence check + semantic proof match |

---

## РАЗДЕЛ 23. ОБРАБОТКА ОШИБОК И ОТКАТ

| Step | Действие |
|---|---|
| 1 | SYSTEM фиксирует сбой |
| 2 | Сбой классифицируется по типу: модель, Codespaces runtime, GitHub, протокол, доказательство результата, проверка, откат |
| 3 | Если ошибка произошла до успешной записи результата шага, состояние задачи не продвигается |
| 4 | Если ошибка требует исправления, EXECUTOR готовит артефакт исправления |
| 5 | AUDITOR проверяет и утверждает исправление |
| 6 | SYSTEM выполняет технические действия |
| 7 | SYSTEM выполняет валидацию и фиксирует событие в реестре |

| Специальное правило | Значение |
|---|---|
| Ошибки GPT-роли и Codespaces runtime не должны маскироваться под обычные ошибки реализации | Mandatory |

| Rollback path | Значение |
|---|---|
| EXECUTOR proposes rollback -> AUDITOR approves -> SYSTEM executes allowed technical actions -> SYSTEM validates and records result | Mandatory |

| Budgets | Значение |
|---|---|
| max_fix_cycles | 3 |
| max_auto_check_retries | 2 |
| max_protocol_retries | 2 |

---

## РАЗДЕЛ 24. ARTIFACT INTEGRITY RECOVERY

| Condition | Route |
|---|---|
| Referenced artifact is missing or broken | ARTIFACT_INTEGRITY_FAILED -> AUDITOR:REVIEW_STALL |

| AUDITOR may decide |
|---|
| REVISE |
| REJECT |
| RECOVER |

---

## РАЗДЕЛ 25. WATCHDOG И SLA

| Action | SLA |
|---|---|
| REVIEW_TASK | 2h |
| WRITE_PLAN | 2h |
| REVIEW_PLAN | 2h |
| IMPLEMENT_TASK | 4h |
| REVIEW_CODE | 2h |
| MERGE_PR | 30m |
| RUN_AUTO_CHECK | 30m |
| PROPOSE_FIX | 1h |
| REVIEW_FIX | 1h |
| IMPLEMENT_FIX | 2h |
| EXECUTE_ROLLBACK | 2h |
| VERIFY_RESULT | 2h |
| REVIEW_RESULT | 2h |
| CLOSE_TASK | 30m |
| REVIEW_STALL | 4h |

| Distinctions |
|---|
| Зависание роли по смысловому шагу |
| Сбой активации роли |
| Сбой Codespaces runtime |
| Зависание технического workflow |
| Повторный цикл без продвижения состояния |

| freeze triggers |
|---|
| repeated stall 3x |
| fix budget exhausted |
| protocol rejected 2x |
| dependency wait timeout 4h |
| secret leak |
| workflow set drift |
| stall decision timeout 4h |
| unresolved CORE infra failure |
| unresolved protocol hard-gate corruption |
| repeated routing loop without state progression |

---

## РАЗДЕЛ 26. WORKFLOW-КОНТРАКТЫ

| Workflow | Contract |
|---|---|
| ledger-writer.yml | append row + route activation |
| ledger-protocol-validate.yml | validate schema, transitions, protocol integrity, artifact semantics |
| pr-auto-merge.yml | reviewed sha match, green checks, synced branch, delete branch, write PR_MERGED |
| rollback-check.yml | must not create alternative final status contour |

| Общие правила | Значение |
|---|---|
| Каждый workflow обязан быть идемпотентным | Mandatory |
| Ни один workflow не должен порождать повторный запуск того же логического контура без проверки idempotency_key / causation_id / correlation_id / state | Mandatory |
| Любой workflow, способный породить рекурсивный цикл, должен быть заблокирован SYSTEM | Mandatory |

---

## РАЗДЕЛ 27. ALLOWED WORKFLOW SET ПРОВЕРКА

| Cold start checks |
|---|
| enabled workflows against allowlist |
| denylist disabled |
| CORE workflow fingerprints valid |
| PROTOCOL.md exists |
| version = v3.7-RC1 |
| anchors present |
| sections present |
| fingerprint valid |
| minimum size threshold met |

---

## РАЗДЕЛ 28. EMERGENCY OPERATOR OVERRIDE POLICY

| Rule | Значение |
|---|---|
| Operator allowed only in emergency modes | Mandatory |
| All actions logged | Mandatory |
| Without OPERATOR_OVERRIDE_CONFIRMED normal progression forbidden | Mandatory |

---

## РАЗДЕЛ 29. ПОЛИТИКА ЧУВСТВИТЕЛЬНЫХ ДАННЫХ

| Rule | Значение |
|---|---|
| Real secrets forbidden | Mandatory |
| Only symbolic references allowed | Mandatory |

---

## РАЗДЕЛ 30. ПОЛИТИКА АРХИВИРОВАНИЯ

| Rule | Значение |
|---|---|
| Closed tasks older than 90 days archived | Mandatory |
| Referential integrity checked before archive | Mandatory |

---

## РАЗДЕЛ 31. ХОЛОДНЫЙ СТАРТ

| Step | Действие |
|---|---|
| 1 | Чтение главного реестра |
| 2 | Проверка набора workflow |
| 3 | Проверка контрольных отпечатков ключевых компонентов |
| 4 | Проверка целостности PROTOCOL.md |
| 5 | Проверка доступности GitHub Codespaces runtime |
| 6 | Проверка возможности безопасного запуска нужной GPT-роли |
| 7 | Только после этого — восстановление или начальная инициализация |

| Failure rule | Значение |
|---|---|
| Если SYSTEM исправен, но Codespaces runtime недоступен, система не должна имитировать нормальную работу | Mandatory |

---

## РАЗДЕЛ 32. МИГРАЦИЯ

| Step | Действие |
|---|---|
| 1 | archive legacy |
| 2 | clean ledger v3.6-RC2 |
| 3 | place PROTOCOL.md |
| 4 | bootstrap |
| 5 | disable legacy API workflows |
| 6 | verify denylist disabled |
| 7 | verify Codespaces runtime availability |
| 8 | verify safe Codex role execution path |

---

## РАЗДЕЛ 33. CERTIFICATION TEST MATRIX

| Test ID | Description |
|---|---|
| T-001 | successful CODE cycle |
| T-002 | plan reject path |
| T-003 | code review reject path |
| T-004 | auto-check failed path |
| T-005 | fix cycle success |
| T-006 | rollback cycle success |
| T-007 | stale branch rejected |
| T-008 | duplicate event rejected |
| T-009 | semantic duplicate fix rejected |
| T-010 | activation delivery fail |
| T-011 | activation restored |
| T-012 | ANALYSIS full cycle |
| T-013 | NO_OP full cycle |
| T-014 | CONFIG without risk acceptance rejected |
| T-015 | artifact missing |
| T-016 | ledger corruption recovery |
| T-017 | freeze on secret leak |
| T-018 | archive integrity success |
| T-019 | workflow drift detected |
| T-020 | merge without reviewed SHA match rejected |
| T-021 | DOCUMENT full cycle |
| T-022 | operator override cycle |
| T-023 | archive integrity fail |
| T-024 | workflow drift resolution |
| T-025 | dependency WAIT timeout |
| T-026 | orphaned branch detected |
| T-027 | STALL_DECISION timeout freeze |
| T-028 | PROTOCOL.md missing on cold start |
| T-029 | fallback polling enable/disable cycle |
| T-030 | fix loop budget exhaustion |
| T-031 | protocol version mismatch |
| T-032 | protocol fingerprint mismatch |
| T-033 | artifact semantic mismatch |
| T-034 | ACTIONS_QUOTA_FAILURE on CORE path |
| T-035 | duplicate AUTO_CHECK final event rejected |
| T-036 | protocol structure corrupted |
| T-037 | CORE workflow fingerprint mismatch |
| T-038 | recovery without resume contract rejected |
| T-039 | NO_OP semantic proof mismatch rejected |
| T-040 | orphaned branch unresolved > 2h escalates freeze |

---

## РАЗДЕЛ 34. SYSTEM EVENT UNIQUENESS RULES

| Категория | Правило |
|---|---|
| critical semantic uniqueness required for | PR_MERGED, AUTO_CHECK_STARTED, AUTO_CHECK_PASSED, AUTO_CHECK_FAILED, TASK_CLOSED, SYSTEM_FROZEN, SYSTEM_UNFROZEN, ROLE_ACTIVATION_FAILED, ROLE_ACTIVATION_RESTORED |

---

## РАЗДЕЛ 35. FULL ARTIFACT SEMANTIC VALIDATION RULES

| validator must check | Значение |
|---|---|
| task_id match | Mandatory |
| parent_event_id match | Mandatory |
| reviewed_ref match | Mandatory |
| reviewed_commit_sha match when required | Mandatory |
| decision_type legal for event_type | Mandatory |
| required fields non-empty | Mandatory |
| flags legal for task_type | Mandatory |
| proof_target present when required | Mandatory |
| rollback_plan present when required | Mandatory |
| task_type route compatibility | Mandatory |

| CONFIG | Значение |
|---|---|
| rollback_plan mandatory | Mandatory |
| CONFIG_RISK_ACCEPTED mandatory before merge | Mandatory |

| NO_OP | Значение |
|---|---|
| proof_ref exists | Mandatory |
| proof_ref semantically matches proof_target | Mandatory |
| proof_target aligns with approved expected_outcome | Mandatory |

---

## РАЗДЕЛ 36. PROTOCOL INTEGRITY GATE

| hard gate checks |
|---|
| PROTOCOL.md exists |
| version matches v3.7-RC1 |
| mandatory sections 1..41 exist |
| mandatory anchors exist |
| minimum size threshold met |
| canonical fingerprint matches |

| failure events |
|---|
| PROTOCOL_DOC_MISSING |
| PROTOCOL_VERSION_MISMATCH |
| PROTOCOL_FINGERPRINT_MISMATCH |
| PROTOCOL_STRUCTURE_CORRUPTED |

All route to:
BLOCKED -> AUDITOR:REVIEW_STALL

---

## РАЗДЕЛ 37. RECOVERY RESUME CONTRACT

| mandatory fields after LEDGER_RECOVERY_COMPLETED |
|---|
| restored_task_id |
| restored_event_id |
| restored_state |
| restored_next_role |
| restored_next_action |
| reconciliation_manifest_ref |
| replayed_event_count |

---

## РАЗДЕЛ 38. CORE VS NON_CORE FAILURE DOMAINS

| CORE |
|---|
| ledger write |
| validator |
| merge |
| routing |
| watchdog |
| cold start |
| recovery |
| codespaces runtime |
| GPT role invocation |
| structured role output intake |
| idempotency and routing loop guards |

| NON_CORE |
|---|
| archive |
| advisory checks |
| optional reporting |
| metrics exporters |

Сбой в ядре — это любой сбой, который может привести к:
- потере корректного состояния
- неверной маршрутизации
- повторному выполнению критического действия
- ложному подтверждению шага
- повреждению главного реестра

Такие сбои ускоренно переводятся в аварийный контур и могут вызывать заморозку системы.

---

## РАЗДЕЛ 39. EMBEDDED MACHINE POLICY LAYER (CANONICAL APPENDIX)

```yaml
policy_version: v3.7-RC1
protocol_doc:
  required_path: governance/PROTOCOL.md
  required_version: v3.7-RC1
  required_sections: 1-41
  required_anchors:
    - "РАЗДЕЛ 18."
    - "РАЗДЕЛ 20."
    - "РАЗДЕЛ 23."
    - "РАЗДЕЛ 25."
    - "РАЗДЕЛ 31."
    - "РАЗДЕЛ 38."
    - "ГРАНИЦЫ ОТВЕТСТВЕННОСТИ GPT-РОЛИ"
  min_chars: 25000

runtime_requirements:
  - codespaces_runtime_available
  - safe_codex_role_execution_available
  - idempotency_controls_enabled
  - routing_loop_guard_enabled
```

---

## РАЗДЕЛ 40. RELEASE CRITERIA / ДОПУСК В БОЕВУЮ СРЕДУ

Полный допуск в боевую среду разрешен только после подтверждения, что система работает в режиме управляемой автоматизации, где:

1. целостность PROTOCOL.md подтверждена  
2. валидатор реализует обязательные разделы протокола  
3. семантическая валидация артефактов полностью реализована  
4. контроль контрольных отпечатков ключевых workflow реализован  
5. резервный режим активации реализован  
6. защита от повторных финальных событий реализована  
7. уникальность системных событий реализована в записи и валидации  
8. тесты T-001..T-040 пройдены  
9. симуляционный контур не содержит неоднозначных состояний  
10. запрещенные legacy-workflow отключены и ключевые workflow защищены  
11. GitHub Codespaces runtime стабильно запускает GPT-роли и корректно обрабатывает их результаты  
12. ошибки GPT, GitHub, Codespaces runtime, инфраструктуры и маршрутизации различаются и правильно фиксируются  
13. критические действия выполняются только системным слоем, а не текстовым ответом GPT  

Примечание:  
система допускается не к полной бесконтрольной автономности, а к управляемой автоматической работе в рамках жестко заданного протокола, проверок и аварийных ограничителей.

---

## РАЗДЕЛ 41. ГРАНИЦЫ ОТВЕТСТВЕННОСТИ GPT-РОЛИ

GPT-роль является интеллектуальным компонентом системы, но не является главным источником состояния и не является окончательным исполнителем критических технических действий.

GPT-роль может:
- анализировать
- формировать предложения
- формировать планы
- готовить тексты артефактов
- формировать решения проверки
- объяснять риски, откат и доказательства результата

GPT-роль не может считаться достаточным основанием для:
- прямого изменения состояния системы
- записи в главный реестр
- слияния в main
- обхода обязательных проверок
- разморозки системы
- восстановления после повреждения реестра
- подтверждения критического результата без системной валидации

Любой ответ GPT-роли считается входом в системный контур проверки, но не самим фактом выполнения шага.

---

## APPENDIX A. CANONICAL OPERATIONAL NOTES

Этот appendix входит в canonical single-file выпуск и предназначен для фиксации подробных пояснений, которые должны быть видимы машинному и человеческому контуру проверки как часть одного и того же канона. Он не отменяет разделы 1–41, а только расширяет их интерпретацию без изменения смысла.

### A.1 Источник истины
- Единственный канонический источник текущего состояния — exchange_ledger.csv и связанные canonical artifacts.
- Любой runtime output, который не материализован в canonical artifact и не проведен через SYSTEM, не считается подтвержденным фактом.
- Любое устное, временное, кешированное или in-memory состояние считается недостоверным.
- Codespaces terminal history, stdout, stderr, local scratch files и временные заметки не являются state truth.

### A.2 Границы роли EXECUTOR
- EXECUTOR пишет только артефакты, изменения рабочего дерева и доказательства результата.
- EXECUTOR не определяет окончательный state.
- EXECUTOR не пишет ledger.
- EXECUTOR не выполняет merge как финальное системное действие.
- EXECUTOR не может трактовать собственный runtime success как semantic completion.

### A.3 Границы роли AUDITOR
- AUDITOR оценивает artifact, diff, proof_ref и checks.
- AUDITOR определяет semantic decision, но не выполняет ledger write.
- AUDITOR не подменяет SYSTEM и не может сам зафиксировать итоговое состояние.
- AUDITOR не должен одобрять superseded artifact.
- AUDITOR обязан указывать next_role_assigned и next_action_assigned только в рамках допустимого route.

### A.4 Границы SYSTEM
- SYSTEM отвечает за schema validation.
- SYSTEM отвечает за transition validation.
- SYSTEM отвечает за invariant enforcement.
- SYSTEM отвечает за append-only ledger.
- SYSTEM отвечает за freeze, unfreeze, recovery, archive и integrity gates.
- SYSTEM не принимает product-semantic decision по содержанию задачи; для этого существует AUDITOR.

### A.5 Hard-gate interpretation
- Protocol mismatch — hard gate.
- Fingerprint mismatch — hard gate.
- Missing sections — hard gate.
- Missing mandatory anchors — hard gate.
- Missing canonical artifact where required — hard gate.
- Attempted state progression after runtime failure — hard gate.
- Missing idempotency on repeatable contour — hard gate.
- Unsafe merge path — hard gate.

### A.6 Runtime failure interpretation
- Codespaces session crash не считается semantic failure задачи, а считается runtime failure.
- Codex CLI auth failure не считается semantic failure задачи, а считается runtime failure.
- Missing command in PATH не считается semantic failure задачи, а считается runtime setup failure.
- Любая такая ошибка должна классифицироваться отдельно и не должна маскироваться под product failure.

### A.7 Merge discipline
- Merge разрешен только после CODE_REVIEW_DECISION(APPROVE).
- Merge разрешен только при reviewed SHA match.
- Merge разрешен только при synced branch.
- Merge разрешен только через системный контур.
- Merge не может выполняться прямым текстовым решением GPT.

### A.8 Ledger discipline
- Ledger append-only.
- Single writer mandatory.
- Every row must be schema-valid.
- Every row must pass transition gate.
- Every row must have protocol_version compatible with active canon.
- Every repeatable technical contour must have idempotency_key.
- Duplicate final events forbidden.

### A.9 Recovery discipline
- Recovery не должен скрывать corruption.
- Recovery не должен invent missing state.
- Recovery обязан фиксировать restored_task_id, restored_event_id, restored_state, restored_next_role, restored_next_action.
- Recovery без reconciliation manifest запрещен.
- Recovery должен завершаться отдельным подтверждением.

### A.10 Archive discipline
- Archive возможен только после referential integrity check.
- Archive не должен ломать artifact_ref.
- Archive не должен ломать proof_ref.
- Archive не должен ломать historical task identity.

### A.11 Why protocol length matters
- Min chars threshold нужен для защиты от partial overwrite.
- Слишком короткий protocol file может означать truncation, corruption, bad update, accidental overwrite или incomplete migration.
- Поэтому appendix intentionally keeps this release materially large and self-describing.

### A.12 Canonical restatement of core law
- No state progression from GPT text alone.
- No ledger write by GPT role.
- No merge by GPT role outside system contour.
- No approval by EXECUTOR.
- No implementation coding by AUDITOR.
- No hidden live-state outside ledger + artifacts.

---

## APPENDIX B. MACHINE-READABLE EXPLANATORY NOTES

B-01. If packet.protocol_version mismatches repo-visible PROTOCOL.md version, role must return BLOCKED.  
B-02. If packet references missing artifact for required step, role must return BLOCKED.  
B-03. If packet contains placeholder identifiers for productive step, role may write only BLOCKED manifest.  
B-04. If current step is proposal authoring but canonical route is invalid, role must not create proposal artifact.  
B-05. If current step is plan authoring but proposal_ref is missing, role must not create plan artifact.  
B-06. If current step implies code mutation without approved plan, route is forbidden.  
B-07. If current step implies merge before review approval, route is forbidden.  
B-08. If current step implies final verification before auto-check passed, route is forbidden.  
B-09. If current step implies direct main write for CODE/CONFIG/DOCUMENT, route is forbidden.  
B-10. If current step implies state trust from terminal stdout, route is forbidden.  
B-11. If current step implies state trust from chat memory, route is forbidden.  
B-12. If current step implies state trust from unreferenced scratch note, route is forbidden.  
B-13. Every actor must operate as if current fact exists only when materialized.  
B-14. Every validator must operate as if missing evidence means missing fact.  
B-15. Every watchdog decision must operate as if unresolved CORE drift is blocking.  
B-16. Every freeze decision must operate as if safety overrides throughput.  
B-17. Every rollback decision must operate as if duplicate final status is forbidden.  
B-18. Every recovery decision must operate as if replay ambiguity is blocking.  
B-19. Every archive decision must operate as if broken references are blocking.  
B-20. Every protocol update must preserve sections 1..41 and mandatory anchors.  
B-21. Every protocol update must keep version marker synchronized with packet generation logic.  
B-22. Every runtime launcher must respect TTY expectations of CLI tools.  
B-23. Every Codespaces launcher must classify auth/setup/PATH failures separately from semantic product failures.  
B-24. Every result manifest must be readable without consulting chat memory.  
B-25. Every canonical artifact must include identifiers sufficient for traceability.  
B-26. Every approval must be attributable to AUDITOR.  
B-27. Every state write must be attributable to SYSTEM.  
B-28. Every operator action must be explicit, scoped and logged.  
B-29. Every role-trigger loop must be protected by correlation_id and idempotency controls.  
B-30. Every runtime contour must prefer deterministic failure over silent drift.  

---

**Статус:** `v3.7-RC1 (RU) | SINGLE-FILE CANONICAL MD | Подготовлен: 2026-04-13`
