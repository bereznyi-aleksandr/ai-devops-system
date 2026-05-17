# BEM-531 | Internal Role Contour Improvement Roadmap v2

Дата: 2026-05-17 | 12:45 (UTC+3)

## Статус
Roadmap обновлена по замечаниям внешнего аудитора Claude.

## Объект
Внутренний контур разработки мультиагента. Это не внешний GPT autonomy contour.

## Целевая архитектура BEM-531
GPT / Claude external audit branches -> curator -> internal roles -> GitHub Actions -> file transport -> role state -> curator closure.

Telegram webhook branch признаётся частью общей большой архитектуры, но исключается из scope BEM-531, чтобы не усложнять текущую доработку. Подключение Telegram branch откладывается на отдельный будущий этап после PASS внутреннего контура.

## Принципы
- Curator is the single entry point for BEM-531 scope.
- Claude is external audit branch, not default developer.
- GPT performs autonomous development through Deno + Python executor v3.
- No issue #31 comments.
- No schedule triggers.
- No secrets in files.
- No paid OpenAI API.
- Reports do not stop roadmap execution.

## Количество этапов
7 этапов.

## Этапы

### 1. BEM-531.00 — Cleanup preflight
Цель: проанализировать весь репозиторий и заархивировать мусор, не нарушив внешний автономный контур и внутренний role-based контур.

Задачи:
1. inventory active files: workflows, state, transport, protocols, reports, tasks;
2. identify stale pending tasks, failed/superseded artifacts, legacy blockers and obsolete proofs/results;
3. move obsolete files only to governance/archive with MANIFEST;
4. verify Deno/codex-runner/Python executor v3 remain intact;
5. verify active internal contour files remain intact.

PASS:
- archive manifest exists;
- cleanup report exists;
- active external contour validation PASS;
- active internal contour validation PASS;
- blocker=null.

### 2. BEM-531.01 — Curator intake
Цель: формализовать curator как единую точку входа для GPT and Claude branches в рамках BEM-531.

Задачи:
1. define curator intake schema;
2. define curator FSM: RECEIVED -> TRIAGED -> ASSIGNED -> WAITING_ROLE -> REVIEWING -> CLOSED;
3. define source normalization for GPT and Claude;
4. reserve Telegram source field as deferred, not active scope;
5. define next_role assignment rules.

PASS:
- curator intake contract exists;
- sample GPT intake record exists;
- sample Claude intake record exists;
- Telegram marked deferred;
- blocker=null.

### 3. BEM-531.1 — Role state + agent lifecycle
Цель: нормализовать role_cycle_state.json и добавить lifecycle агентов.

Задачи:
1. define role state schema;
2. fields: cycle_id, source, curator_status, active_role, current_task, handoff, history, blocker, timestamps;
3. add agent lifecycle: CANDIDATE -> ACTIVE -> RETIRED;
4. preserve backward compatibility;
5. generate schema report and normalized state.

PASS:
- role state schema report exists;
- role_cycle_state.json normalized;
- lifecycle CANDIDATE/ACTIVE/RETIRED present;
- blocker=null.

### 4. BEM-531.2 — Transport contract + failure handling
Цель: стандартизировать file transport не только для happy path, но и для ошибок.

Задачи:
1. define intake, handoff, analysis, audit, execution, final_result records;
2. define failure records: role_timeout, role_failed, validation_failed, executor_failed;
3. define retry/escalation fields;
4. create sample JSONL records;
5. create validator proof.

PASS:
- transport protocol exists;
- sample records exist;
- failure handling documented;
- validator proof exists;
- blocker=null.

### 5. BEM-531.3 — Workflow audit: orchestrator + provider adapter
Цель: объединённо проверить role-orchestrator.yml и provider-adapter.yml.

Задачи:
1. audit role-orchestrator triggers;
2. confirm no schedule triggers;
3. confirm no issue #31 dependency;
4. confirm curator is called first;
5. audit provider adapter routing;
6. audit failure handling;
7. audit no secrets leakage and no paid API by default;
8. patch if required.

PASS:
- workflow audit report exists;
- no schedule triggers;
- curator-first routing confirmed or patched;
- provider adapter policy confirmed or patched;
- blocker=null.

### 6. BEM-531.4 — Synthetic E2E two-level test
Цель: доказать внутренний контур в два уровня: минимальный и полный.

Задачи:
1. minimal E2E: curator -> executor -> result;
2. verify minimal E2E state and transport;
3. full E2E: curator -> analyst -> auditor -> executor -> curator closure;
4. verify full E2E role artifacts, state, transport and final PASS.

PASS:
- minimal E2E PASS with SHA;
- full E2E PASS with SHA;
- role_cycle_state updated;
- transport result appended;
- blocker=null.

### 7. BEM-531.5 — Contour status file
Цель: создать простой machine-readable status вместо UI/dashboard.

Задачи:
1. create governance/state/contour_status.json;
2. include current_cycle, active_role, next_role, last_result, last_commit, blocker, updated_at;
3. generate from role_cycle_state and transport;
4. create status report.

PASS:
- governance/state/contour_status.json exists;
- status report exists;
- blocker=null.

## PASS всей BEM-531 roadmap
- all 7 stages completed with commit SHA;
- cleanup completed safely;
- curator intake defined;
- role state normalized with lifecycle;
- transport contract includes failure handling;
- workflows audited and patched if required;
- minimal and full E2E completed;
- contour_status.json exists;
- blocker=null.


---

## Result
BEM-531 PASS. Internal role-based contour roadmap completed.

Evidence:
- BEM-531.00 cleanup: fed8d7d0854a3055959e287638422dfc4eeae597
- BEM-531.01 curator intake: b26ddc22d7f20e507aec67484735a7f2fc7cca0c
- BEM-531.1 role state lifecycle: 5d26e973ed67f61dca308db081d745e044d431f5
- BEM-531.2 transport failure contract: b464c7f5c5f5a05b354218c6194263e7d46a41b9
- BEM-531.3 workflow audit: 82ced4dbdc37890c97ee4522aae77b525cb8b184
- BEM-531.4 synthetic E2E: 9005e6c1bf5e87a0c77df2734f23806902419269
- BEM-531.5 contour status: final commit

Blocker: null
