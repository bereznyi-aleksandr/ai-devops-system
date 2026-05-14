# INTERNAL AUTONOMY CONTOUR — REFERENCE

Версия: v2.2 | Дата: 2026-05-13
Репозиторий: bereznyi-aleksandr/ai-devops-system
Основная ISA: issue #31

---

## 1. АРХИТЕКТУРА: КТО ЧТО ДЕЛАЕТ

| Слой | Компонент | Кто | Задача |
|---|---|---|---|
| **Вход** | Telegram / Deno webhook | Оператор | Ставит задачу боту или открывает URL |
| **Вход** | Issue #31 `@curator` | Оператор | Передаёт задачу в систему через GitHub |
| **Вход** | Deno `GET /autonomy-backlog-trigger` | GPT | Автономно добавляет задачи в roadmap и запускает движок |
| **Вход** | Deno `POST /autonomy-backlog` + `patch_queue/generated/` | GPT | Автономный self-write bridge: GPT ставит патч-задачи → ISA Patch Runner коммитит |
| **Вход** | Внешний LLM-аудитор / операторский чат | Claude / GPT | Пишет `@curator` в issue #31 через GitHub PAT MCP; архитектурный аудит |
| **Управляющий** | `@curator` → `curator-hosted-gpt.yml` | GPT (hosted) | Единственная точка входа во внутренний контур; классифицирует задачу, запускает Role Orchestrator |
| **Оркестратор** | `role-orchestrator.yml` → `scripts/role_orchestrator.py` | GitHub Actions | Детерминированный FSM; ведёт цикл ролей по `role_sequence.json` |
| **Провайдер-роутер** | `scripts/curator_router.py` + `provider_failover.py` | Python | Выбирает провайдера (gpt / gpt_codex) для каждой роли через `provider_adapters.json` |
| **Аналитик** | `gpt-hosted-roles.yml` | GPT (hosted) | Анализирует задачу, предлагает план |
| **Аудитор** | `gpt-hosted-roles.yml` | GPT (hosted) | Проверяет решение независимо, выносит APPROVED / BLOCKED |
| **Исполнитель** | `gpt-hosted-roles.yml` / `codex-local.yml` | GPT hosted / GPT Codex | Выполняет одобренную задачу; codex-local может делать commit |
| **Движок задач** | `autonomous-task-engine.yml` + `scripts/autonomous_task_engine.py` | GitHub Actions | Автономно выбирает pending-задачи из roadmap и выполняет их |
| **Patcher** | `isa-patch-runner.yml` + `scripts/isa_patch_runner.py` | GitHub Actions | Применяет файловые патчи из `patch_queue/current.json` или `patch_queue/generated/<trace>.json` |
| **Отчётность** | `telegram-outbox-dispatch.yml` | GitHub Actions | Отправляет сообщения из `telegram_outbox.jsonl` в Telegram |

---

## 2. РОЛИ ВНЕШНИХ АГЕНТОВ

| Агент | Роль | Что может | Что не может |
|---|---|---|---|
| **Оператор** | Стратегия и приёмка | Ставить задачи, читать отчёты, менять политики | Микроменеджмент шагов |
| **Внешний LLM-аудитор / операторский чат** | Внешний аудитор | Читать репозиторий, писать `@curator` в issue, архитектурный аудит, готовить документы | Существовать между сообщениями оператора |
| **GPT (отдельный чат)** | Куратор + внешний аудитор | Мониторить систему, запускать контур через Deno, писать `@curator`, ставить патч-задачи | Напрямую вызывать роли минуя куратора |
| **curator-hosted-gpt.yml** | Внутренний куратор | Классифицировать задачи, запускать Role Orchestrator, маршрутизировать через failover | Выполнять код, коммитить файлы |
| **analyst / auditor / executor** | Рабочие роли | Выполнять свою часть FSM-цикла | Принимать архитектурные решения, обходить куратора |

---

## 3. ПОЛНЫЙ МАРШРУТ: ОТ ВХОДА ДО РЕЗУЛЬТАТА

### 3A. Канонический маршрут (через Куратора)

```
Оператор / внешний аудитор / GPT
  → issue #31 comment: @curator TYPE: CURATOR_ROADMAP_EXECUTION
        ↓
  curator-hosted-gpt.yml (trigger: issue_comment + @curator)
        ↓
  scripts/curator_entrypoint.py
    → классифицирует TASK_TYPE
    → если CURATOR_ROADMAP_EXECUTION / architecture_change / internal_contour_proof:
        next_action = START_ROLE_ORCHESTRATOR
    → читает routing.json + provider_adapters.json → выбирает провайдера
    → записывает curator_last_decision.json
        ↓
  curator-hosted-gpt.yml: "Dispatch Role Orchestrator"
    → POST /repos/.../actions/workflows/role-orchestrator.yml/dispatches
    → inputs: mode=start, task_type, trace_id, cycle_id
        ↓
  role-orchestrator.yml (trigger: workflow_dispatch)
        ↓
  scripts/role_orchestrator.py
    → читает role_sequence.json → последовательность ролей
    → читает routing.json → провайдер для каждой роли
    → читает provider_adapters.json → adapter enabled / workflow
    → dispatch каждой роли через workflow_dispatch
        ↓
  [FSM цикл — секция 4]
        ↓
  curator_summary → BEM-отчёт в issue #31
  → telegram_outbox.jsonl → Telegram оператору
```

### 3B. Маршрут через Autonomous Task Engine

```
GPT / Deno webhook
  → GET /autonomy-backlog-trigger?token=SECRET&preset=full_chain&trace_id=X
        ↓
  Deno v4.2+:
    → buildFullChainPreset(traceId) — 3 уникальные задачи с уникальными task_id
    → GitHub Contents API → обновляет roadmap_state.json
    → POST /repos/.../dispatches event_type=autonomy-engine
        ↓
  autonomous-task-engine.yml
  concurrency: group=autonomy-engine-main (очередь, не параллельно)
        ↓
  scripts/autonomous_task_engine.py --mode production_loop
    → выбирает pending задачи из roadmap_state.json
    → выполняет: create_json_state / append_event
    → коммитит, обновляет roadmap: задача → completed
        ↓
  BEM-AUTONOMY-ENGINE report в issue #31
```

### 3C. GPT Self-Write Bridge (автономный патч-маршрут)

```
GPT из чата
  → формирует патч-задачу
  → записывает в governance/patch_queue/generated/<trace_id>.json
    (через Deno /gpt-patch или GitHub Contents API)
        ↓
  isa-patch-runner.yml (trigger: issue TYPE: ISA_PATCH_RUNNER)
        ↓
  scripts/isa_patch_runner.py
    → читает patch_queue/generated/<trace>.json
    → проверяет allowlist (patch_runner_allowlist.json)
    → применяет файловые операции
    → делает commit в репозиторий
    → публикует результат в issue #31
        ↓
  GPT читает результат и верифицирует
```

---

## 4. FSM ЦИКЛ РОЛЕЙ

### Последовательности (role_sequence.json)

| task_type | Последовательность ролей |
|---|---|
| `default_development` | analyst → auditor → executor → auditor → curator_summary |
| `architecture_change` | analyst → auditor → executor → auditor → curator_summary |
| `internal_contour_proof` | analyst → auditor → executor → auditor → curator_summary |
| `hotfix` | executor → auditor → curator_summary |
| `audit_only` | auditor → curator_summary |

### Ограничения и защиты цикла

| Параметр | Значение | Действие при нарушении |
|---|---|---|
| `max_role_steps_per_cycle` | 8 | статус → `step_limit_exceeded`, цикл блокируется |
| `max_cycle_age_minutes` | 30 | статус → `stale_timeout` |
| Терминальные статусы | completed / blocked / stale_timeout / step_limit_exceeded | дальнейший dispatch запрещён |
| `emergency_stop.enabled = true` | — | блокирует любой dispatch и apply |

### State файл цикла

```
governance/state/role_cycle_state.json
  cycle_id:     cyc_<name>_<timestamp>
  trace_id:     <от куратора>
  status:       cycle_started → role_dispatched → completed
  current_role: analyst / auditor / executor / curator_summary
  step_count:   N
  step_history: [{role, provider, status, timestamp}, ...]
```

---

## 5. ПРОВАЙДЕРЫ И ПЕРЕКЛЮЧЕНИЕ

### Роли и провайдеры (routing.json v6)

| Роль | Активный | Primary | Reserve | Fallback chain |
|---|---|---|---|---|
| curator | gpt_hosted_fallback | claude | gpt_hosted_fallback | gpt_hosted_fallback → gpt |
| analyst | gpt | gpt | claude | claude → gpt_codex → codex |
| auditor | claude | claude | gpt_codex | gpt_codex → gpt |
| executor | claude | claude | gpt_codex | gpt_codex → gpt |

### Provider Adapters (provider_adapters.json) — ВАЖНО

| Провайдер | Adapter enabled | write_repo | commit | Примечание |
|---|---|---|---|---|
| `gpt` | ✅ true | ❌ false | ❌ false | Основной hosted analyst/report контур |
| `gpt_hosted_fallback` | ✅ true | ❌ false | ❌ false | Hosted fallback для curator/analyst |
| `gpt_codex` | ✅ true | ✅ true | ✅ true | Write-capable резервный контур; требует self-hosted runner |
| `isa_patch_runner` | ✅ true | ✅ true | ✅ true | Только для патч-задач из patch_queue |
| `claude` | ❌ **false** | ✅ true | ✅ true | **FSM adapter отключён** — `disabled_reason: limits active` |

> **Критически важно:** `claude.status = ok` в `provider_status.json` и `claude.enabled = false` в `provider_adapters.json` — это два разных слоя.
> - `provider_status.json` — показывает API доступность
> - `provider_adapters.json` — контролирует использование в FSM
> - Claude как FSM executor/auditor сейчас отключён через adapter даже если API доступен.
> - Claude Code используется только через прямые триггеры `@analyst` / `@auditor` / `@executor` из issue, минуя role_orchestrator FSM.

### Триггеры по провайдеру (trigger_map)

| Роль | claude | gpt | gpt_codex |
|---|---|---|---|
| analyst | `@analyst` | `@gpt_analyst` | `@gpt_analyst` |
| auditor | `@auditor` | `@gpt_auditor` | `@gpt_auditor` |
| executor | `@executor` | `@gpt_executor` | `@gpt_executor` |
| curator | `@curator` | `@curator` | — |

### Правила переключения провайдера

| Тип ошибки | Действие |
|---|---|
| `provider_limit` | Переключить немедленно на reserve |
| `api_error` (×2 подряд) | Переключить на reserve |
| `runner_unavailable` | Пропустить, взять следующий в fallback chain |
| `adapter_disabled` | Пропустить, использовать reserve |
| `max_turns` | НЕ переключать — ошибка конфигурации |
| `config_error` | НЕ переключать — ошибка конфигурации |
| `permission_error` | НЕ переключать |

---

## 6. WORKFLOWS

### Активные workflows

| Workflow | Триггер | Исполнитель | Назначение |
|---|---|---|---|
| `curator-hosted-gpt.yml` | issue_comment + `@curator` | GPT (OpenAI API) | Единственная точка входа; роутит в Role Orchestrator |
| `role-orchestrator.yml` | workflow_dispatch | Python FSM | Детерминированный цикл ролей |
| `analyst.yml` | issue_comment + `@analyst` | Claude Code | Аналитик — прямой триггер (минует FSM adapter) |
| `auditor.yml` | issue_comment + `@auditor` | Claude Code | Аудитор — прямой триггер |
| `executor.yml` | issue_comment + `@executor` | Claude Code | Исполнитель — прямой триггер |
| `gpt-hosted-roles.yml` | workflow_dispatch + `@gpt_analyst/auditor/executor` | GPT (OpenAI API) | Роли через GPT hosted (основной FSM путь) |
| `codex-local.yml` | `@gpt_analyst/auditor/executor` + self-hosted runner | GPT Codex | Write-capable резервный контур |
| `role-router.yml` | workflow_dispatch / issue TYPE: CURATOR_TO_ROLE | Python | Маршрутизирует роль по routing.json |
| `autonomous-task-engine.yml` | repository_dispatch / schedule `17 * * * *` / issue TYPE: AUTONOMY_ENGINE | Python | Production loop; выполняет roadmap задачи |
| `isa-patch-runner.yml` | issue TYPE: ISA_PATCH_RUNNER / workflow_dispatch | Python | Применяет патчи из patch_queue/ |
| `gpt-action-ingress.yml` | workflow_dispatch | Python | GPT action ingress bridge |
| `telegram-outbox-dispatch.yml` | push к `telegram_outbox.jsonl` / schedule `*/5 * * * *` | Python | Отправляет сообщения в Telegram |
| `curator-hourly-report.yml` | schedule `0 * * * *` / workflow_dispatch | Python | Ежечасный аналитический отчёт в Telegram |

### Отключённые / legacy workflows

| Workflow | Статус |
|---|---|
| `telegram-gateway.yml` | DISABLED |
| `telegram-send.yml` | DISABLED |
| `update-status.yml` | DISABLED |
| `gpt-scheduler-tick.yml` | DISABLED |
| `cloud-scheduler-tick.yml` | DISABLED |

---

## 7. STATE LAYER (JSON-only, SSOT)

| Файл | Назначение | Кто пишет |
|---|---|---|
| `governance/state/routing.json` | Активный провайдер для каждой роли | curator_router.py |
| `governance/state/provider_status.json` | API доступность провайдеров (ok / error / limited) | provider_probe.py |
| `governance/policies/provider_adapters.json` | FSM adapter enabled / workflow mapping | вручную |
| `governance/state/system_state.json` | Текущий этап, режим работы | движок / вручную |
| `governance/state/role_cycle_state.json` | Активный FSM цикл | role_orchestrator.py |
| `governance/state/roadmap_state.json` | Дорожная карта задач (pending / completed / blocked) | Deno / autonomous_task_engine.py |
| `governance/state/emergency_stop.json` | Аварийная остановка (enabled: true/false) | вручную |
| `governance/state/curator_last_decision.json` | Последнее решение куратора | curator_entrypoint.py |
| `governance/exchange.jsonl` | Append-only журнал всех событий | все компоненты |
| `governance/events/provider_failures.jsonl` | Журнал ошибок провайдеров | curator_router.py |
| `governance/events/routing_decisions.jsonl` | Журнал решений роутера | curator_router.py |
| `governance/events/autonomous_development.jsonl` | События автономной разработки | autonomous_task_engine.py |
| `governance/telegram_outbox.jsonl` | Очередь исходящих сообщений в Telegram | curator / движок |
| `governance/processed_events.jsonl` | Защита от дублей | все компоненты |
| `governance/patch_queue/current.json` | Текущая патч-задача (legacy / ручная) | вручную / движок |
| `governance/patch_queue/generated/<trace>.json` | GPT autonomous patch tasks | GPT self-write bridge |

> **Patch Queue разделение:**
> - `current.json` — legacy формат, ручная или движком поставленная задача
> - `generated/<trace>.json` — GPT autonomous patch tasks, каждый файл уникален по trace_id

---

## 8. DENO WEBHOOK (внешний вход для GPT)

**URL:** `https://fine-chicken-23.bereznyi-aleksandr.deno.net`

| Версия | Где |
|---|---|
| `v4.2` | `governance/deno_webhook.js` в репозитории (канон для деплоя) |
| `v4.4-autonomy-session` | Live Deno Deploy — может содержать дополнительные endpoints |

| Endpoint | Метод | Назначение | Наличие |
|---|---|---|---|
| `/` | GET | Health check (`github_pat_present`, `gpt_webhook_secret_present`) | v4.2 + live |
| `/autonomy-trigger` | GET | Запустить autonomous-task-engine (без задач) | v4.2 + live |
| `/autonomy-backlog-trigger` | GET | Добавить задачи + запустить engine (`?preset=full_chain` или `tasks_b64`) | v4.2 + live |
| `/autonomy-backlog` | POST | То же, JSON body (ChatGPT Action endpoint) | v4.2 + live |
| `/autonomy` | POST | Запустить engine без задач, JSON body | v4.2 + live |
| `/gpt-patch-trigger` | GET/POST | GPT autonomous patch trigger → ISA Patch Runner | live v4.4 |
| `/gpt-patch` | POST | GPT patch payload → patch_queue/generated | live v4.4 |
| `/gpt-autonomy-session` | POST | GPT autonomy session management | live v4.4 |
| `/` | POST | Telegram webhook | v4.2 + live |

### preset=full_chain — уникальные task_id через trace_id

```
TC_<safeTrace>_001_JSON  → governance/state/test_ic_a_<trace>_001.json
TC_<safeTrace>_002_EVENT → governance/events/full_chain_autonomy_test.jsonl
TC_<safeTrace>_003_JSON  → governance/state/test_ic_a_<trace>_003.json
```

### ChatGPT Action Schema

```
governance/openapi/autonomy_gateway_openapi.yaml
  operationId: enqueueAutonomyBacklog  → POST /autonomy-backlog
  operationId: triggerAutonomyEngine   → POST /autonomy
```

---

## 9. ПОЛИТИКИ БЕЗОПАСНОСТИ

| Правило | Статус |
|---|---|
| Production deploy без approval оператора | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Изменение billing / permissions | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Хардкод секретов вне GitHub Secrets / Deno env | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Более 1 write operation за цикл | ЗАПРЕЩЕНО |
| Куратор напрямую вызывает роли минуя Role Orchestrator | ЗАПРЕЩЕНО |
| Роли принимают задачи без trace_id от куратора | ЗАПРЕЩЕНО |
| gpt_codex при runner_unavailable | Пропускать, брать следующий в chain |
| claude adapter disabled → не использовать в FSM | Использовать reserve provider |
| Emergency stop enabled=true | Блокирует любой dispatch и apply |
| ISA Patch Runner — только allowlisted пути | Проверяется через `patch_runner_allowlist.json` |

---

## 10. QUICK REFERENCE

### Запустить контур через Куратора:
```
@curator

TYPE: CURATOR_ROADMAP_EXECUTION
TRACE_ID: <уникальный_id>
TASK_TYPE: internal_contour_proof

ЗАДАЧА: [описание]
```

### Запустить Autonomous Task Engine через Deno:
```
GET /autonomy-backlog-trigger
  ?token=<GPT_WEBHOOK_SECRET>
  &mode=production_loop
  &trace_id=<уникальный_id>
  &preset=full_chain
```

### Поставить GPT autonomous patch task (self-write bridge):
```
1. Создать governance/patch_queue/generated/<trace>.json
   {
     "task_id": "<trace>",
     "mode": "apply_and_commit",
     "owner_approved_commit": true,
     "files": [...]
   }

2. Написать в issue #31:
   TYPE: ISA_PATCH_RUNNER
   MODE: apply_and_commit
   TASK_FILE: governance/patch_queue/generated/<trace>.json
```

### Переключить провайдера:
```
governance/state/routing.json:
  roles.<role>.active = "gpt" | "claude"

governance/state/provider_status.json:
  providers.<name>.status = "ok" | "limited" | "error"

ВАЖНО: provider_adapters.json.adapters.claude.enabled
  контролирует FSM usage независимо от provider_status
```

### Аварийная остановка:
```
governance/state/emergency_stop.json:
  {"enabled": true, "reason": "причина"}
```

---

*Версия: v2.2 | 2026-05-13 | внешний аудитор*
*Назначение: Reference для GPT нового чата и внешнего аудитора*
*Описывает архитектуру и механизм работы — не текущее состояние*
*BEM-391: внесены minor fixes GPT (BEM-390, BEM-391)*
