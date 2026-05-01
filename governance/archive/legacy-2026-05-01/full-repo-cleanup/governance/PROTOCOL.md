================================================================================
ПРОТОКОЛ АВТОНОМНОЙ СИСТЕМЫ С ЕДИНЫМ РЕЕСТРОМ
Версия: v3.6-RC2 (RU) | Заменяет: v3.6-RC1 | Дата: 2026-04-13
Формат выпуска: SINGLE-FILE CANONICAL MD
Статус: RELEASE CANDIDATE FOR MANAGED AUTOMATED PRODUCTION
================================================================================

СВОДКА ВЕРСИИ
================================================================================
Данный выпуск исправляет ключевое архитектурное допущение прошлой редакции:
GPT-роли не трактуются как прямые технические исполнители GitHub-операций.
Система описана как контур управляемой автоматизации, в котором:
- GPT-роли выполняют интеллектуальные функции;
- ORCHESTRATOR вызывает GPT, нормализует контекст и выполняет технические действия;
- SYSTEM валидирует, проверяет инварианты, пишет в реестр и управляет автоматическими контурами;
- GitHub используется как среда хранения кода, артефактов, PR, проверок и истории.

Единственный артефакт выпуска:
governance/PROTOCOL.md

================================================================================
ИЗМЕНЕНИЯ ОТ v3.6-RC1
================================================================================
1. ПЕРЕПИСАН раздел 1 — цель системы в модели управляемой автоматизации
2. ПЕРЕПИСАН раздел 4 — добавлена роль ORCHESTRATOR
3. ПЕРЕПИСАН раздел 6 — GPT больше не описывается как GitHub-исполнитель
4. ПЕРЕПИСАН раздел 8 — активация идёт через внешний управляющий контур
5. РАСШИРЕН раздел 10 — causation_id/correlation_id/idempotency_key/producer
6. РАСШИРЕН раздел 13 — model/orchestrator/idempotency/routing errors
7. РАСШИРЕН раздел 18 — 4 обязательных условия смены состояния
8. РАСШИРЕН раздел 20 — новые запрещённые переходы
9. ПЕРЕПИСАН раздел 23 — контур ошибок с учётом GPT и ORCHESTRATOR
10. РАСШИРЕН раздел 25 — различение зависаний и routing loops
11. РАСШИРЕН раздел 26 — workflow idempotency and anti-recursion
12. ПЕРЕПИСАН раздел 31 — cold start проверяет ORCHESTRATOR availability
13. РАСШИРЕН раздел 38 — ORCHESTRATOR включён в CORE domain
14. ПЕРЕПИСАН раздел 40 — managed automated production, not blind autonomy
15. ДОБАВЛЕН раздел 41 — границы ответственности GPT-роли

================================================================================
РАЗДЕЛ 1. ЦЕЛЬ СИСТЕМЫ
================================================================================
Автоматизированная работа двух GPT-ролей через внешний управляющий контур
и GitHub-репозиторий.

GPT-роли выполняют интеллектуальные функции:
- анализ;
- подготовку артефактов;
- проверку;
- формирование решений.

GitHub-репозиторий используется как среда хранения:
- кода;
- артефактов;
- истории изменений;
- проверок;
- запросов на слияние.

Системный слой выполняет:
- детерминированную маршрутизацию;
- проверку переходов состояний;
- запись в главный реестр;
- запуск проверок;
- контроль зависаний;
- заморозку;
- восстановление;
- архивирование.

Главный достоверный источник состояния системы — главный реестр и
зафиксированные артефакты, а не память GPT-роли.

Система строится как минимальный, но строгий конечный автомат,
устойчивый к:
- дрейфу;
- скрытому повреждению данных;
- рассинхронизации протокола;
- повторной обработке;
- маршрутизационным циклам;
- ложной фиксации выполненного шага.

================================================================================
РАЗДЕЛ 2. СТРУКТУРА ДАННЫХ
================================================================================
canonical state file:
- governance/exchange_ledger.csv

artifacts:
- governance/proposals/{task_id}.md
- governance/plans/{task_id}.md
- governance/decisions/{event_id}.md
- governance/fixes/{event_id}.md
- governance/proofs/{task_id}/...
- governance/recovery/...
- governance/archive/YYYYMM/...
- governance/operator/...
- governance/PROTOCOL.md

branches:
- task/{task_id}/implementation
- task/{task_id}/fix-{n}
- task/{task_id}/rollback-{n}

rules:
- artifact without ledger reference does not exist for the system
- CODE, CONFIG, DOCUMENT use branch + PR path only
- ANALYSIS and NO_OP may use artifact-only path
- routing canon is exchange_ledger.csv only
- artifacts are UTF-8 markdown
- PROTOCOL.md is mandatory and integrity-checked

================================================================================
РАЗДЕЛ 3. ИНВАРИАНТЫ СИСТЕМЫ
================================================================================
I-01 one active task
I-02 one active branch
I-03 CODE/CONFIG/DOCUMENT only via PR
I-04 append-only ledger
I-05 single writer: ledger_writer.py
I-06 previous+new row validation
I-07 legacy disabled
I-08 plan-before-code
I-09 review-before-merge
I-10 MERGE_PR -> PR_MERGED -> RUN_AUTO_CHECK
I-11 system-owned merge
I-12 synced branch required
I-13 NO_OP without code mutation allowed
I-14 rollback only via PR
I-15 secrets forbidden
I-16 primary activation through orchestrated trigger
I-17 fallback polling only on activation failure
I-18 PR_MERGED observable in ledger
I-19 typed supersession
I-20 CONFIG high-risk gate
I-21 allowed workflow set enforced
I-22 certification gate mandatory
I-23 branch cleanup mandatory
I-24 RESULT_REVIEW only for ANALYSIS and NO_OP
I-25 no orphaned branches
I-26 PROTOCOL.md mandatory
I-27 protocol structural integrity mandatory
I-28 protocol fingerprint lock mandatory
I-29 protocol anchor integrity mandatory
I-30 artifact semantic integrity mandatory
I-31 explicit infra-failure routing mandatory
I-32 rollback post-check ownership singular
I-33 recovery resume contract mandatory
I-34 proof semantic match mandatory
I-35 CORE failure domain escalates faster
I-36 critical system event uniqueness mandatory
I-37 no state transition from GPT text alone
I-38 no state progression on orchestrator failure
I-39 no repeated logical execution without idempotency control
I-40 no routing loop without explicit failure record

================================================================================
РАЗДЕЛ 4. РОЛИ
================================================================================
EXECUTOR:
- формирует предложение по задаче
- формирует план реализации
- готовит изменения, исправления и откаты
- готовит артефакты для записи в систему
- не выполняет слияние
- не утверждает собственные результаты
- не изменяет main напрямую

AUDITOR:
- проверяет предложения, планы, изменения, исправления, откаты и результаты
- принимает решения: APPROVE / REJECT / REVISE / CONFIRM / WAIT / ESCALATE / RECOVER
- не пишет код
- не выполняет слияние
- не утверждает устаревшие или замещённые артефакты

ORCHESTRATOR (внешний управляющий контур):
- читает реестр и определяет следующий допустимый шаг
- вызывает нужную GPT-роль
- передаёт GPT-роли нормализованный контекст
- принимает структурированный результат
- выполняет технические операции через GitHub API и системные скрипты
- создаёт или обновляет артефакты, ветки, PR и служебные события
- не принимает продуктовых решений по смыслу задачи

SYSTEM:
- валидирует схему, структуру и допустимость переходов
- обеспечивает запись в главный реестр
- контролирует инварианты
- запускает автоматические проверки
- выполняет заморозку, разморозку, восстановление, архивирование и контроль целостности
- не принимает продуктовых решений по смыслу задачи

================================================================================
РАЗДЕЛ 5. КТО НАЗНАЧАЕТ СЛЕДУЮЩУЮ РОЛЬ
================================================================================
semantic transitions:
- AUDITOR via decisions artifact

mechanical transitions:
- protocol automatically

technical execution:
- ORCHESTRATOR performs allowed technical steps only after validation

================================================================================
РАЗДЕЛ 6. ФИЗИЧЕСКИЙ ИНТЕРФЕЙС GPT-РОЛЕЙ
================================================================================
EXECUTOR получает от внешнего управляющего контура нормализованный контекст:
- текущее состояние из главного реестра
- связанные артефакты
- ограничения
- требуемый следующий шаг
- при необходимости — изменения по ветке, diff, результаты проверок

EXECUTOR возвращает строго структурированный результат:
- текст артефакта
- список предполагаемых изменений
- ссылки на доказательства результата
- пояснение по рискам и откату
- предлагаемое действие в рамках протокола

AUDITOR получает от внешнего управляющего контура нормализованный контекст проверки:
- текущее состояние
- проверяемый артефакт
- diff
- reviewed_commit_sha
- результаты автоматических проверок
- историю связанных решений

AUDITOR возвращает строго структурированное решение:
- тип решения
- объект проверки
- обоснование
- условия
- назначение следующего шага

GPT-роли не выполняют напрямую:
- запись в GitHub
- создание веток
- открытие PR
- запись в главный реестр
- системные проверки

Эти действия выполняются внешним управляющим контуром и системным слоем
после успешной валидации ответа GPT-роли.

================================================================================
РАЗДЕЛ 7. ШАБЛОНЫ АРТЕФАКТОВ
================================================================================
proposal required fields:
- task_id
- proposal_author
- ts_utc
- task_type
- step_name
- title
- parent_task_id
- description
- expected_outcome
- proof_target
- constraints
- notes

plan required fields:
- task_id
- proposal_ref
- plan_author
- ts_utc
- task_type
- approach
- files_to_create
- files_to_modify
- files_to_delete
- proof_target
- risk_notes
- rollback_plan
- config_risk_class

decision required fields:
- decision_id
- task_id
- parent_event_id
- decision_author
- ts_utc
- decision_type
- decision
- reviewed_ref
- reviewed_commit_sha
- next_role_assigned
- next_action_assigned
- rationale
- conditions
- flags

fix required fields:
- task_id
- parent_event_id
- fix_author
- ts_utc
- fix_type
- error_class
- root_cause
- proposed_change
- files_affected
- proof_target
- rollback_plan
- notes

================================================================================
РАЗДЕЛ 8. МОДЕЛЬ АКТИВАЦИИ РОЛЕЙ
================================================================================
Основной режим активации:
после успешной записи новой строки в главный реестр системный слой вызывает
внешний управляющий контур через repository_dispatch или другой допустимый
механизм запуска.

Внешний управляющий контур:
- считывает последнее допустимое состояние
- определяет следующую роль и следующее действие
- вызывает соответствующий профиль GPT
- принимает результат
- передаёт его в системную валидацию
- только после успешной валидации инициирует технические действия в GitHub
  и запись следующего события

Резервный режим:
применяется только при неуспешной активации или сбое внешнего управляющего
контура.
Резервный режим не продвигает состояние автоматически без прохождения полной
системной валидации.

Подтверждение доставки:
подтверждением считается не факт запуска процесса, а успешное завершение
требуемого шага с принятием артефакта или корректной фиксацией ошибки
в главном реестре.

activation markers:
- activation_mode = PRIMARY | FALLBACK
- fallback_started_at
- fallback_expiry_at

================================================================================
РАЗДЕЛ 9. PAYLOAD-СХЕМЫ repository_dispatch
================================================================================
write-ledger-row:
- event_type
- actor_role
- artifact_path
- protocol_event_type
- task_id
- parent_event_id
- artifact_ref
- proof_ref
- ci_ref
- log_ref
- error_class
- error_details
- commit_sha
- stall_class
- infra_scope
- causation_id
- correlation_id
- idempotency_key
- producer
- producer_run_id

role-activated:
- event_type
- task_id
- event_id
- next_role
- next_action
- artifact_ref
- commit_sha
- correlation_id
- producer_run_id

================================================================================
РАЗДЕЛ 10. ФОРМАТ ГЛАВНОГО РЕЕСТРА
================================================================================
Заголовок:
event_id,parent_event_id,task_id,ts_utc,actor_role,event_type,state,decision,
result,summary,artifact_ref,proof_ref,ci_ref,log_ref,error_class,error_details,
next_role,next_action,protocol_version,commit_sha,stall_class,infra_scope,
causation_id,correlation_id,idempotency_key,producer,producer_run_id

Дополнительные поля обязательны для трассировки и защиты от повторной обработки:
- causation_id — идентификатор события, которое стало причиной текущего события
- correlation_id — идентификатор единого контура обработки внутри одной логической цепочки
- idempotency_key — ключ защиты от повторного выполнения одного и того же смыслового действия
- producer — источник, создавший событие
- producer_run_id — идентификатор конкретного запуска процесса

ledger_writer.py обязан отклонять событие, если:
- уже существует строка с тем же event_id
- уже существует строка с тем же idempotency_key, если это то же смысловое действие
- событие образует запрещённый цикл маршрутизации
- источник события не соответствует допустимому системному контуру

Также ledger_writer.py обязан:
- читать SHA файла
- валидировать схему строки
- валидировать переход
- повторять при 409
- проверять referenced artifact existence
- проверять referenced artifact semantics
- применять protocol integrity gate when required

================================================================================
РАЗДЕЛ 11. ДОПУСТИМЫЕ event_type
================================================================================
EXECUTOR:
TASK_PROPOSED, IMPLEMENTATION_PLAN, IMPLEMENTATION_COMPLETED,
ERROR_FIX_PROPOSED, ERROR_FIX_COMPLETED, ROLLBACK_PROPOSED,
ROLLBACK_STARTED, UNFREEZE_PROPOSED

AUDITOR:
AUDIT_DECISION, PLAN_DECISION, CODE_REVIEW_DECISION,
RESULT_REVIEW_CONFIRMED, FIX_DECISION,
VERIFICATION_CONFIRMED, VERIFICATION_REJECTED,
STALL_DECISION, DEPENDENCY_DECISION, ROLLBACK_DECISION,
UNFREEZE_APPROVED, LEDGER_RECOVERY_CONFIRMED,
OPERATOR_OVERRIDE_CONFIRMED

ORCHESTRATOR:
ORCHESTRATOR_STEP_STARTED, ORCHESTRATOR_STEP_FAILED, ORCHESTRATOR_STEP_COMPLETED

SYSTEM:
AUTO_CHECK_STARTED, AUTO_CHECK_PASSED, AUTO_CHECK_FAILED,
PR_MERGED, TASK_CLOSED, PROTOCOL_REJECTED, TASK_STALLED,
SYSTEM_BOOTSTRAP, ROLLBACK_COMPLETED, SYSTEM_FREEZE_REQUESTED,
SYSTEM_FROZEN, SYSTEM_UNFROZEN, EXTERNAL_DEPENDENCY_FAILED,
EXTERNAL_DEPENDENCY_RESTORED, BRANCH_SUPERSEDED, PLAN_SUPERSEDED,
FIX_PROPOSAL_SUPERSEDED, ARCHIVE_COMPLETED, ARCHIVE_INTEGRITY_FAILED,
LEDGER_CORRUPTION_DETECTED, LEDGER_RECOVERY_STARTED,
LEDGER_RECOVERY_COMPLETED, ROLE_ACTIVATION_FAILED,
ROLE_ACTIVATION_RESTORED, ARTIFACT_INTEGRITY_FAILED,
WORKFLOW_SET_DRIFT_DETECTED, ORPHANED_BRANCH_DETECTED,
OPERATOR_OVERRIDE_RECORDED, PROTOCOL_DOC_MISSING,
PROTOCOL_VERSION_MISMATCH, PROTOCOL_FINGERPRINT_MISMATCH,
PROTOCOL_STRUCTURE_CORRUPTED

================================================================================
РАЗДЕЛ 12. ДОПУСТИМЫЕ state
================================================================================
PROPOSED, AUDIT_PENDING, APPROVED, REJECTED, PLAN_PENDING, PLAN_APPROVED,
PLAN_REJECTED, IN_PROGRESS, REVIEW_PENDING, IMPLEMENTED, CHECK_PENDING,
CHECK_FAILED, CHECK_PASSED, FIX_PENDING, FIX_APPROVED, FIX_REJECTED,
ROLLBACK_PENDING, ROLLBACK_IN_PROGRESS, RESULT_REVIEWED, VERIFIED, CLOSED, BLOCKED

================================================================================
РАЗДЕЛ 13. ДОПУСТИМЫЕ decision / result / error_class / next_action / stall_class / infra_scope
================================================================================
decision:
APPROVE, REJECT, REVISE, CONFIRM, RETRY, ESCALATE, WAIT, RECOVER

result:
SUCCESS, FAILURE, PARTIAL, BLOCKED, NO_OP

error_class:
TEST_FAILURE, LINT_FAILURE, BUILD_FAILURE, SCHEMA_FAILURE, PROTOCOL_FAILURE,
RUNTIME_FAILURE, PROOF_FAILURE, CI_FAILURE, STALL_FAILURE, REVIEW_FAILURE,
DRIFT_FAILURE, POST_MERGE_FAILURE, ACTIONS_QUOTA_FAILURE, WORKFLOW_DISABLED,
REPO_WRITE_FAILURE, PR_MERGE_BLOCKED, BRANCH_PROTECTION_FAILURE,
GITHUB_API_FAILURE, EXTERNAL_DEPENDENCY_FAILURE, LEDGER_CORRUPTION,
SECRET_LEAK, ACTIVATION_FAILURE, ARTIFACT_INTEGRITY_FAILURE,
WORKFLOW_SET_DRIFT, ARCHIVE_INTEGRITY_FAILURE, ORPHANED_BRANCH,
PROTOCOL_DOC_FAILURE, PROTOCOL_VERSION_FAILURE, PROTOCOL_FINGERPRINT_FAILURE,
PROTOCOL_STRUCTURE_FAILURE, MODEL_OUTPUT_INVALID, MODEL_TIMEOUT,
MODEL_CONTEXT_FAILURE, MODEL_TOOL_FAILURE, ORCHESTRATOR_FAILURE,
IDEMPOTENCY_FAILURE, ROUTING_LOOP_FAILURE

Пояснение:
ошибки модели, ошибки внешнего управляющего контура и ошибки инфраструктуры
должны классифицироваться раздельно.
Ни один такой сбой не должен трактоваться как успешно выполненный смысловой шаг.
При таких ошибках система обязана либо записать корректное событие сбоя,
либо перевести задачу в состояние блокировки/зависания по правилам протокола.

next_action:
REVIEW_TASK, PROPOSE_TASK, WRITE_PLAN, REVIEW_PLAN, IMPLEMENT_TASK,
REVIEW_CODE, MERGE_PR, REVIEW_RESULT, RUN_AUTO_CHECK, PROPOSE_FIX,
REVIEW_FIX, IMPLEMENT_FIX, VERIFY_RESULT, CLOSE_TASK, REVIEW_STALL,
REVIEW_DEPENDENCY_BLOCK, REVIEW_ROLLBACK, EXECUTE_ROLLBACK,
REVIEW_UNFREEZE, EXECUTE_UNFREEZE, VERIFY_LEDGER_RECOVERY, NONE

stall_class:
EXECUTOR_DELAY, AUDITOR_DELAY, SYSTEM_DELAY, INFRA_DELAY, PROTOCOL_LOOP,
ACTIVATION_FAILURE_LOOP

infra_scope:
CORE, NON_CORE, NONE

================================================================================
РАЗДЕЛ 14. МАТРИЦА ВЛАДЕНИЯ СОСТОЯНИЯМИ
================================================================================
AUDIT_PENDING        EXECUTOR -> AUDITOR
PLAN_PENDING         EXECUTOR -> AUDITOR
PLAN_APPROVED        AUDITOR  -> EXECUTOR
REVIEW_PENDING       EXECUTOR -> AUDITOR
IMPLEMENTED          AUDITOR  -> ORCHESTRATOR then SYSTEM
CHECK_PENDING        SYSTEM   -> SYSTEM
CHECK_FAILED         SYSTEM   -> EXECUTOR
CHECK_PASSED         SYSTEM   -> AUDITOR
FIX_PENDING          EXECUTOR -> AUDITOR
FIX_APPROVED         AUDITOR  -> EXECUTOR
ROLLBACK_PENDING     EXECUTOR -> AUDITOR
ROLLBACK_IN_PROGRESS AUDITOR  -> EXECUTOR then ORCHESTRATOR then SYSTEM
RESULT_REVIEWED      AUDITOR  -> SYSTEM(NO_OP) or AUDITOR(ANALYSIS)
VERIFIED             AUDITOR  -> SYSTEM
BLOCKED              SYSTEM/AUDITOR -> AUDITOR/SYSTEM

================================================================================
РАЗДЕЛ 15. TASK IDENTITY RULES
================================================================================
1. task_id never reused
2. fix and rollback stay within same task_id
3. supersession does not create new business identity automatically
4. new business task requires new TASK_PROPOSED and new task_id
5. archive preserves task_id integrity as historical unit

================================================================================
РАЗДЕЛ 16. BRANCH LIFECYCLE
================================================================================
CREATE after PLAN_DECISION(APPROVE)
ACTIVE one branch per task
REVIEWED commit_sha frozen in ledger
MERGED delete branch after PR_MERGED
SUPERSEDED via BRANCH_SUPERSEDED
ABANDONED/ORPHANED detected by watchdog

================================================================================
РАЗДЕЛ 17. SEMANTIC DUPLICATE RULES
================================================================================
general duplicates forbidden for:
TASK_PROPOSED, IMPLEMENTATION_PLAN, CODE_REVIEW_DECISION,
ERROR_FIX_PROPOSED, ROLLBACK_PROPOSED, DEPENDENCY_DECISION, STALL_DECISION

critical system uniqueness:
PR_MERGED, AUTO_CHECK_STARTED, AUTO_CHECK_PASSED, AUTO_CHECK_FAILED,
TASK_CLOSED, SYSTEM_FROZEN, SYSTEM_UNFROZEN,
ROLE_ACTIVATION_FAILED, ROLE_ACTIVATION_RESTORED

critical orchestrator uniqueness:
ORCHESTRATOR_STEP_STARTED, ORCHESTRATOR_STEP_FAILED, ORCHESTRATOR_STEP_COMPLETED
must be unique within same correlation_id + idempotency_key where applicable.

================================================================================
РАЗДЕЛ 18. ПРАВИЛА МАРШРУТИЗАЦИИ
================================================================================
TASK_PROPOSED -> AUDIT_PENDING, AUDITOR:REVIEW_TASK
AUDIT_DECISION(APPROVE) -> APPROVED, decision-routed:WRITE_PLAN
AUDIT_DECISION(REJECT) -> REJECTED, decision-routed:REVIEW_TASK
IMPLEMENTATION_PLAN -> PLAN_PENDING, AUDITOR:REVIEW_PLAN
PLAN_DECISION(APPROVE) -> PLAN_APPROVED, decision-routed:IMPLEMENT_TASK
PLAN_DECISION(REJECT/REVISE) -> PLAN_REJECTED, decision-routed:WRITE_PLAN
IMPLEMENTATION_COMPLETED -> REVIEW_PENDING, AUDITOR:REVIEW_CODE
CODE_REVIEW_DECISION(APPROVE) -> IMPLEMENTED, ORCHESTRATOR:SYSTEM MERGE PATH
CODE_REVIEW_DECISION(REJECT/REVISE) -> PLAN_APPROVED, decision-routed:IMPLEMENT_TASK
PR_MERGED -> CHECK_PENDING, SYSTEM:RUN_AUTO_CHECK
AUTO_CHECK_PASSED -> CHECK_PASSED, AUDITOR:VERIFY_RESULT
AUTO_CHECK_FAILED -> CHECK_FAILED, EXECUTOR:PROPOSE_FIX
RESULT_REVIEW_CONFIRMED(NO_OP) -> RESULT_REVIEWED, SYSTEM:RUN_AUTO_CHECK
RESULT_REVIEW_CONFIRMED(ANALYSIS) -> RESULT_REVIEWED, AUDITOR:VERIFY_RESULT
VERIFICATION_CONFIRMED -> VERIFIED, decision-routed:CLOSE_TASK
VERIFICATION_REJECTED -> CHECK_FAILED, decision-routed:PROPOSE_FIX
ERROR_FIX_PROPOSED -> FIX_PENDING, AUDITOR:REVIEW_FIX
FIX_DECISION(APPROVE) -> FIX_APPROVED, decision-routed:IMPLEMENT_FIX
FIX_DECISION(REJECT/REVISE) -> FIX_REJECTED, decision-routed:PROPOSE_FIX
ERROR_FIX_COMPLETED -> REVIEW_PENDING, AUDITOR:REVIEW_CODE
ROLLBACK_PROPOSED -> ROLLBACK_PENDING, AUDITOR:REVIEW_ROLLBACK
ROLLBACK_DECISION(APPROVE) -> ROLLBACK_IN_PROGRESS, decision-routed:EXECUTE_ROLLBACK
ROLLBACK_STARTED -> ROLLBACK_IN_PROGRESS, AUDITOR:REVIEW_CODE
ROLLBACK_COMPLETED -> CHECK_PENDING, SYSTEM:RUN_AUTO_CHECK
TASK_STALLED -> BLOCKED, AUDITOR:REVIEW_STALL
EXTERNAL_DEPENDENCY_FAILED -> BLOCKED, AUDITOR:REVIEW_DEPENDENCY_BLOCK
EXTERNAL_DEPENDENCY_RESTORED -> BLOCKED, AUDITOR:REVIEW_DEPENDENCY_BLOCK
SYSTEM_FROZEN -> BLOCKED, AUDITOR:REVIEW_UNFREEZE
SYSTEM_BOOTSTRAP -> CLOSED, EXECUTOR:PROPOSE_TASK
LEDGER_CORRUPTION_DETECTED -> BLOCKED, SYSTEM:VERIFY_LEDGER_RECOVERY
LEDGER_RECOVERY_COMPLETED -> BLOCKED, AUDITOR:VERIFY_LEDGER_RECOVERY
LEDGER_RECOVERY_CONFIRMED -> CLOSED/RESTORED, EXECUTOR:REVIEW_TASK
ARCHIVE_INTEGRITY_FAILED -> BLOCKED, AUDITOR:REVIEW_STALL
ARTIFACT_INTEGRITY_FAILED -> BLOCKED, AUDITOR:REVIEW_STALL
WORKFLOW_SET_DRIFT_DETECTED -> BLOCKED, AUDITOR:REVIEW_STALL
ORPHANED_BRANCH_DETECTED -> BLOCKED, AUDITOR:REVIEW_STALL
PROTOCOL_DOC_MISSING -> BLOCKED, AUDITOR:REVIEW_STALL
PROTOCOL_VERSION_MISMATCH -> BLOCKED, AUDITOR:REVIEW_STALL
PROTOCOL_FINGERPRINT_MISMATCH -> BLOCKED, AUDITOR:REVIEW_STALL
PROTOCOL_STRUCTURE_CORRUPTED -> BLOCKED, AUDITOR:REVIEW_STALL

Любой переход состояния выполняется только после одновременного выполнения
всех условий:
1. получен допустимый артефакт от соответствующей роли
2. артефакт прошёл структурную и семантическую валидацию
3. внешний управляющий контур успешно выполнил требуемое техническое действие
4. системный слой успешно записал новое событие в главный реестр

Решение GPT-роли само по себе не изменяет состояние системы до завершения
этих четырёх условий.

================================================================================
РАЗДЕЛ 19. ТАБЛИЦА МАРШРУТИЗАЦИИ ПРИ ЗАВИСАНИИ
================================================================================
WRITE_PLAN -> EXECUTOR:WRITE_PLAN
REVIEW_PLAN -> AUDITOR:REVIEW_PLAN
IMPLEMENT_TASK -> EXECUTOR:IMPLEMENT_TASK
REVIEW_CODE -> AUDITOR:REVIEW_CODE
MERGE_PR -> ORCHESTRATOR+SYSTEM:MERGE_PR
RUN_AUTO_CHECK -> SYSTEM:RUN_AUTO_CHECK
PROPOSE_FIX -> EXECUTOR:PROPOSE_FIX
IMPLEMENT_FIX -> EXECUTOR:IMPLEMENT_FIX
VERIFY_RESULT -> AUDITOR:VERIFY_RESULT
CLOSE_TASK -> SYSTEM:CLOSE_TASK
EXECUTE_ROLLBACK -> EXECUTOR:EXECUTE_ROLLBACK
unknown -> AUDITOR:REVIEW_STALL

================================================================================
РАЗДЕЛ 20. ЗАПРЕЩЁННЫЕ ПЕРЕХОДЫ
================================================================================
1. PROPOSED -> CLOSED
2. AUDIT_PENDING -> IMPLEMENTED
3. APPROVED -> IMPLEMENTED without plan
4. PLAN_APPROVED -> REVIEW_PENDING without branch and PR
5. REVIEW_PENDING -> CHECK_PENDING without CODE_REVIEW + PR_MERGED
6. CHECK_FAILED -> CLOSED
7. FIX_PENDING -> CLOSED
8. REJECTED -> TASK_CLOSED without new proposal
9. SYSTEM -> APPROVED
10. EXECUTOR -> VERIFIED
11. direct CODE/CONFIG/DOCUMENT write to main
12. second active branch without BRANCH_SUPERSEDED
13. approving superseded artifact
14. merge before CODE_REVIEW_DECISION(APPROVE)
15. VERIFICATION_CONFIRMED before PR_MERGED and AUTO_CHECK_PASSED
16. IMPLEMENTATION_COMPLETED from stale branch
17. ERROR_FIX_COMPLETED from stale branch
18. ROLLBACK_COMPLETED without ROLLBACK_STARTED
19. new task while SYSTEM_FROZEN
20. secrets in repository
21. MERGE_PR without reviewed SHA == current PR head SHA
22. RESULT_REVIEW_CONFIRMED for CODE/DOCUMENT/CONFIG
23. normal progression while workflow drift unresolved
24. normal progression while orphaned branch unresolved
25. progression with missing/mismatched protocol canon
26. NO_OP without semantic proof match
27. duplicate final rollback/check events
28. recovery without resume contract
29. protocol hard-gate mismatch treated as warning-only
30. прямое изменение состояния системы по одному только текстовому ответу GPT без системной валидации
31. запись в главный реестр без idempotency_key, если событие относится к повторяемому техническому контуру
32. продвижение состояния при сбое внешнего управляющего контура
33. продвижение состояния, если ответ GPT не прошёл структурную проверку
34. запуск нового смыслового шага при незавершенном цикле активации той же роли по тому же correlation_id
35. автоматическое выполнение критического действия на основании неполного контекста
36. трактовка факта запуска workflow как факта успешного выполнения смыслового действия

================================================================================
РАЗДЕЛ 21. ALLOWED WORKFLOW SET / LEGACY DENYLIST
================================================================================
allowed:
ledger-protocol-validate.yml
ledger-writer.yml
role-router.yml
executor-notify.yml
auditor-notify.yml
system-router.yml
auto-check.yml
watchdog.yml
close-task.yml
pr-auto-merge.yml
rollback-check.yml
freeze-control.yml
dependency-monitor.yml
archive-rotation.yml
recovery-check.yml

denylist:
gcs-request-ingress.yml
ledger-router.yml
analyst-runner.yml
executor-runner.yml

core workflows:
ledger-writer.yml
ledger-protocol-validate.yml
role-router.yml
system-router.yml
pr-auto-merge.yml
watchdog.yml

================================================================================
РАЗДЕЛ 22. МАРШРУТЫ ПО ТИПУ ЗАДАЧИ
================================================================================
CODE -> branch + PR + review + merge + auto-check
DOCUMENT -> same as CODE
CONFIG -> same as CODE + risk acceptance + smoke test
ANALYSIS -> artifact-only, no PR, no code auto-check
NO_OP -> existence check + semantic proof match

================================================================================
РАЗДЕЛ 23. ОБРАБОТКА ОШИБОК И ОТКАТ
================================================================================
Контур обработки ошибок:
1. системный слой или внешний управляющий контур фиксирует сбой
2. сбой классифицируется по типу: модель, инфраструктура, GitHub, протокол,
   доказательство результата, проверка, откат
3. если ошибка произошла до успешной записи результата шага, состояние задачи
   не продвигается
4. если ошибка требует исправления, EXECUTOR готовит артефакт исправления
5. AUDITOR проверяет и утверждает исправление
6. внешний управляющий контур выполняет технические действия
7. системный слой выполняет валидацию и фиксирует событие в реестре

Специальное правило:
ошибки GPT-роли и ошибки внешнего управляющего контура не должны маскироваться
под обычные ошибки реализации задачи. Они фиксируются отдельно.

Rollback path:
EXECUTOR proposes rollback -> AUDITOR approves ->
ORCHESTRATOR executes allowed technical actions ->
SYSTEM validates and records result

Budgets:
max_fix_cycles = 3
max_auto_check_retries = 2
max_protocol_retries = 2

================================================================================
РАЗДЕЛ 24. ARTIFACT INTEGRITY RECOVERY
================================================================================
If referenced artifact is missing or broken:
ARTIFACT_INTEGRITY_FAILED -> AUDITOR:REVIEW_STALL
AUDITOR may decide:
- REVISE
- REJECT
- RECOVER

================================================================================
РАЗДЕЛ 25. WATCHDOG И SLA
================================================================================
SLA:
REVIEW_TASK 2h
WRITE_PLAN 2h
REVIEW_PLAN 2h
IMPLEMENT_TASK 4h
REVIEW_CODE 2h
MERGE_PR 30m
RUN_AUTO_CHECK 30m
PROPOSE_FIX 1h
REVIEW_FIX 1h
IMPLEMENT_FIX 2h
EXECUTE_ROLLBACK 2h
VERIFY_RESULT 2h
REVIEW_RESULT 2h
CLOSE_TASK 30m
REVIEW_STALL 4h

Отдельно различаются:
- зависание роли по смысловому шагу
- сбой активации роли
- сбой внешнего управляющего контура
- зависание технического workflow
- повторный цикл без продвижения состояния

Если один и тот же correlation_id повторно активируется без изменения состояния
более допустимого числа раз, система обязана зафиксировать
ROUTING_LOOP_FAILURE или ACTIVATION_FAILURE_LOOP и перевести задачу в BLOCKED
либо инициировать заморозку по правилам протокола.

freeze triggers:
- repeated stall 3x
- fix budget exhausted
- protocol rejected 2x
- dependency wait timeout 4h
- secret leak
- workflow set drift
- stall decision timeout 4h
- unresolved CORE infra failure
- unresolved protocol hard-gate corruption
- repeated routing loop without state progression

================================================================================
РАЗДЕЛ 26. WORKFLOW-КОНТРАКТЫ
================================================================================
ledger-writer.yml:
append row + route activation

ledger-protocol-validate.yml:
validate schema, transitions, protocol integrity, artifact semantics

pr-auto-merge.yml:
reviewed sha match
green checks
synced branch
delete branch
write PR_MERGED

rollback-check.yml:
must not create alternative final status contour

Каждый workflow обязан быть идемпотентным в пределах своего смыслового шага.
Ни один workflow не должен порождать повторный запуск того же логического
контура без проверки:
- idempotency_key
- causation_id
- correlation_id
- допустимости текущего состояния

Любой workflow, способный породить рекурсивный или самоподдерживающийся цикл,
должен быть заблокирован системным слоем и зафиксирован как ошибка маршрутизации.

================================================================================
РАЗДЕЛ 27. ALLOWED WORKFLOW SET ПРОВЕРКА
================================================================================
cold start checks:
- enabled workflows against allowlist
- denylist disabled
- CORE workflow fingerprints valid
- PROTOCOL.md exists
- version = v3.6-RC2
- anchors present
- sections present
- fingerprint valid
- minimum size threshold met

================================================================================
РАЗДЕЛ 28. EMERGENCY OPERATOR OVERRIDE POLICY
================================================================================
Operator allowed only in emergency modes.
All actions logged.
Without OPERATOR_OVERRIDE_CONFIRMED normal progression forbidden.

================================================================================
РАЗДЕЛ 29. ПОЛИТИКА ЧУВСТВИТЕЛЬНЫХ ДАННЫХ
================================================================================
Real secrets forbidden.
Only symbolic references allowed.

================================================================================
РАЗДЕЛ 30. ПОЛИТИКА АРХИВИРОВАНИЯ
================================================================================
Closed tasks older than 90 days archived.
Referential integrity checked before archive.

================================================================================
РАЗДЕЛ 31. ХОЛОДНЫЙ СТАРТ
================================================================================
При холодном старте системный слой выполняет:
1. чтение главного реестра
2. проверку набора workflow
3. проверку контрольных отпечатков ключевых компонентов
4. проверку целостности PROTOCOL.md
5. проверку доступности внешнего управляющего контура
6. проверку возможности безопасного вызова нужной GPT-роли
7. только после этого — восстановление или начальную инициализацию

Если системный слой исправен, но внешний управляющий контур недоступен,
система не должна имитировать нормальную работу и обязана перейти в
контролируемый режим ожидания либо блокировки.

================================================================================
РАЗДЕЛ 32. МИГРАЦИЯ
================================================================================
archive legacy -> clean ledger v3.6-RC2 -> place PROTOCOL.md ->
bootstrap -> disable legacy workflows -> verify denylist disabled ->
verify orchestrator availability and safe GPT invocation path

================================================================================
РАЗДЕЛ 33. CERTIFICATION TEST MATRIX
================================================================================
T-001 successful CODE cycle
T-002 plan reject path
T-003 code review reject path
T-004 auto-check failed path
T-005 fix cycle success
T-006 rollback cycle success
T-007 stale branch rejected
T-008 duplicate event rejected
T-009 semantic duplicate fix rejected
T-010 activation delivery fail
T-011 activation restored
T-012 ANALYSIS full cycle
T-013 NO_OP full cycle
T-014 CONFIG without risk acceptance rejected
T-015 artifact missing
T-016 ledger corruption recovery
T-017 freeze on secret leak
T-018 archive integrity success
T-019 workflow drift detected
T-020 merge without reviewed SHA match rejected
T-021 DOCUMENT full cycle
T-022 operator override cycle
T-023 archive integrity fail
T-024 workflow drift resolution
T-025 dependency WAIT timeout
T-026 orphaned branch detected
T-027 STALL_DECISION timeout freeze
T-028 PROTOCOL.md missing on cold start
T-029 fallback polling enable/disable cycle
T-030 fix loop budget exhaustion
T-031 protocol version mismatch
T-032 protocol fingerprint mismatch
T-033 artifact semantic mismatch
T-034 ACTIONS_QUOTA_FAILURE on CORE path
T-035 duplicate AUTO_CHECK final event rejected
T-036 protocol structure corrupted
T-037 CORE workflow fingerprint mismatch
T-038 recovery without resume contract rejected
T-039 NO_OP semantic proof mismatch rejected
T-040 orphaned branch unresolved > 2h escalates freeze

================================================================================
РАЗДЕЛ 34. SYSTEM EVENT UNIQUENESS RULES
================================================================================
critical semantic uniqueness required for:
PR_MERGED
AUTO_CHECK_STARTED
AUTO_CHECK_PASSED
AUTO_CHECK_FAILED
TASK_CLOSED
SYSTEM_FROZEN
SYSTEM_UNFROZEN
ROLE_ACTIVATION_FAILED
ROLE_ACTIVATION_RESTORED

================================================================================
РАЗДЕЛ 35. FULL ARTIFACT SEMANTIC VALIDATION RULES
================================================================================
validator must check:
- task_id match
- parent_event_id match
- reviewed_ref match
- reviewed_commit_sha match when required
- decision_type legal for event_type
- required fields non-empty
- flags legal for task_type
- proof_target present when required
- rollback_plan present when required
- task_type route compatibility

CONFIG:
- rollback_plan mandatory
- CONFIG_RISK_ACCEPTED mandatory before merge

NO_OP:
- proof_ref exists
- proof_ref semantically matches proof_target
- proof_target aligns with approved expected_outcome

================================================================================
РАЗДЕЛ 36. PROTOCOL INTEGRITY GATE
================================================================================
hard gate checks:
- PROTOCOL.md exists
- version matches v3.6-RC2
- mandatory sections 1..41 exist
- mandatory anchors exist
- minimum size threshold met
- canonical fingerprint matches

failure events:
PROTOCOL_DOC_MISSING
PROTOCOL_VERSION_MISMATCH
PROTOCOL_FINGERPRINT_MISMATCH
PROTOCOL_STRUCTURE_CORRUPTED

all route to BLOCKED -> AUDITOR:REVIEW_STALL

================================================================================
РАЗДЕЛ 37. RECOVERY RESUME CONTRACT
================================================================================
mandatory fields after LEDGER_RECOVERY_COMPLETED:
- restored_task_id
- restored_event_id
- restored_state
- restored_next_role
- restored_next_action
- reconciliation_manifest_ref
- replayed_event_count

================================================================================
РАЗДЕЛ 38. CORE VS NON_CORE FAILURE DOMAINS
================================================================================
CORE:
- ledger write
- validator
- merge
- routing
- watchdog
- cold start
- recovery
- внешний управляющий контур
- вызов GPT-роли
- прием структурированного ответа роли
- защита от повторной обработки и циклов маршрутизации

NON_CORE:
- archive
- advisory checks
- optional reporting
- metrics exporters

Сбой в ядре — это любой сбой, который может привести к:
- потере корректного состояния
- неверной маршрутизации
- повторному выполнению критического действия
- ложному подтверждению шага
- повреждению главного реестра

Такие сбои ускоренно переводятся в аварийный контур и могут вызывать
заморозку системы.

================================================================================
РАЗДЕЛ 39. EMBEDDED MACHINE POLICY LAYER (CANONICAL APPENDIX)
================================================================================
policy_version: v3.6-RC2
protocol_doc.required_path: governance/PROTOCOL.md
protocol_doc.required_version: v3.6-RC2
protocol_doc.required_sections: 1-41
protocol_doc.required_anchors:
- РАЗДЕЛ 18.
- РАЗДЕЛ 20.
- РАЗДЕЛ 23.
- РАЗДЕЛ 25.
- РАЗДЕЛ 31.
- РАЗДЕЛ 38.
- ГРАНИЦЫ ОТВЕТСТВЕННОСТИ GPT-РОЛИ
protocol_doc.min_chars: 25000

runtime_requirements:
- orchestrator_available
- safe_gpt_invocation_available
- idempotency_controls_enabled
- routing_loop_guard_enabled

================================================================================
РАЗДЕЛ 40. RELEASE CRITERIA / ДОПУСК В БОЕВУЮ СРЕДУ
================================================================================
Полный допуск в боевую среду разрешен только после подтверждения, что система
работает в режиме управляемой автоматизации, где:

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
11. внешний управляющий контур стабильно вызывает GPT-роли и корректно
    обрабатывает их ответы
12. ошибки GPT, GitHub, инфраструктуры и маршрутизации различаются и правильно
    фиксируются
13. критические действия выполняются только системным слоем, а не текстовым
    ответом GPT

Примечание:
система допускается не к полной бесконтрольной автономности, а к управляемой
автоматической работе в рамках жестко заданного протокола, проверок и
аварийных ограничителей.

================================================================================
РАЗДЕЛ 41. ГРАНИЦЫ ОТВЕТСТВЕННОСТИ GPT-РОЛИ
================================================================================
GPT-роль является интеллектуальным компонентом системы, но не является главным
источником состояния и не является окончательным исполнителем критических
технических действий.

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

Любой ответ GPT-роли считается входом в системный контур проверки,
но не самим фактом выполнения шага.

================================================================================
Статус: v3.6-RC2 (RU) | SINGLE-FILE CANONICAL MD | Подготовлен: 2026-04-13
================================================================================
