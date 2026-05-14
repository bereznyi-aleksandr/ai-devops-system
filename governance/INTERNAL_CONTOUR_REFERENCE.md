# INTERNAL AUTONOMY CONTOUR — REFERENCE

Версия: v2.3 | Дата: 2026-05-13
Репозиторий: bereznyi-aleksandr/ai-devops-system
Основная ISA: issue #31

---

## 1. АРХИТЕКТУРА: КТО ЧТО ДЕЛАЕТ

| Слой | Компонент | Кто | Задача |
|---|---|---|---|
| **Вход** | Telegram / Deno webhook | Оператор | Ставит задачу боту или открывает URL |
| **Вход** | Issue #31 `@curator` | Оператор | Передаёт задачу в систему через GitHub |
| **Вход** | Deno `GET /autonomy-backlog-trigger` | GPT | Автономно добавляет задачи в roadmap и запускает движок |
| **Вход** | Deno `POST /gpt-dev-session` | GPT | Инициирует GPT Developer Runner сессию |
| **Вход** | Deno `POST /autonomy-backlog` + `patch_queue/generated/` | GPT | Автономный self-write bridge: GPT ставит патч-задачи → ISA Patch Runner коммитит |
| **Вход** | Внешний LLM-аудитор / операторский чат | Claude / GPT | Пишет `@curator` в issue #31 через GitHub PAT MCP; архитектурный аудит |
| **Управляющий** | `@curator` → `curator-hosted-gpt.yml` | GPT (hosted) | Единственная точка входа во внутренний контур; классифицирует задачу, запускает Role Orchestrator |
| **GPT Dev Runner** | `gpt-dev-runner.yml` → `scripts/gpt_dev_runner.py` | GitHub Actions | Atomic step runner для GPT разработки; один шаг за запуск, anti-hang |
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
| **GPT (отдельный чат)** | Куратор + внешний аудитор | Мониторить систему, запускать контур через Deno, писать `@curator`, ставить патч-задачи, инициировать dev сессии | Напрямую вызывать роли минуя куратора; вести long-running разработку внутри одного turn |
| **curator-hosted-gpt.yml** | Внутренний куратор | Классифицировать задачи, запускать Role Orchestrator, маршрутизировать через failover | Выполнять код, коммитить файлы |
| **gpt-dev-runner.yml** | GPT Developer Runner | Выполнять один atomic step за запуск; читать state, ставить патч-задачи, диспатчить workflows, верифицировать файлы | Выполнять более 1 шага за запуск; зависать в long-running turn |
| **analyst / auditor / executor** | Рабочие роли | Выполнять свою часть FSM-цикла | Принимать архитектурные решения, обходить куратора |

---

## 3. ANTI-HANG CONTRACT (ОБЯЗАТЕЛЕН ДЛЯ ВСЕХ АГЕНТОВ)

> Любая автономная разработка должна следовать этому контракту.
> Silent hang — критическая ошибка. Blocker должен быть явным.

| Правило | Статус |
|---|---|
| Один шаг = один atomic step | ОБЯЗАТЕЛЬНО |
| После каждого шага — BEM report | ОБЯЗАТЕЛЬНО |
| При ошибке → blocker в state, не silent wait | ОБЯЗАТЕЛЬНО |
| Long-running разработка внутри одного GPT turn | ЗАПРЕЩЕНО |
| Не более 1 write operation за atomic step | ОБЯЗАТЕЛЬНО |
| Emergency stop проверяется перед каждым шагом | ОБЯЗАТЕЛЬНО |
| Secrets никогда не пишутся в файлы репозитория | АБСОЛЮТНЫЙ ЗАПРЕТ |

---

## 4. GPT DEVELOPER RUNNER

### Назначение

Решает проблему зависания GPT при автономной разработке.
GPT инициирует сессию одним вызовом → runner сам проходит очередь шагов.
Каждый шаг — отдельный GitHub Actions run (timeout 5 минут).

### Маршрут

```
GPT
  → POST /gpt-dev-session
      trace_id, preset (developer_runner_selftest | fix_internal_contour)
        ↓
  Deno v4.3
    → repository_dispatch event_type=gpt-dev-runner mode=init
    → repository_dispatch event_type=gpt-dev-runner mode=step (autostart)
        ↓
  gpt-dev-runner.yml (timeout 5 min, concurrency=gpt-dev-runner-main)
        ↓
  scripts/gpt_dev_runner.py --mode step
    → execute_one_step():
        проверить emergency_stop
        взять step из очереди по cursor
        выполнить step_handler
        написать BEM report в events/gpt_dev_runner.jsonl
        обновить cursor в gpt_dev_session.json
        если status=queued → auto-dispatch следующего шага
        если status=completed/blocked → остановиться
```

### Поддерживаемые step types

| Step type | Описание |
|---|---|
| `read_state` | Читает JSON файл, возвращает содержимое в report |
| `enqueue_patch_task` | Создаёт файл в `patch_queue/generated/<id>.json` |
| `dispatch_workflow` | Триггерит repository_dispatch (1 write) |
| `verify_file` | Проверяет существование файла |
| `verify_state` | Проверяет JSON файл на ожидаемые поля |
| `write_report` | Записывает итоговый отчёт сессии |

### Presets

| Preset | Шаги |
|---|---|
| `developer_runner_selftest` | read system_state → read routing → verify reference → enqueue patch → write report |
| `fix_internal_contour` | read role_cycle → read roadmap → read provider_status → verify emergency_stop → dispatch autonomy-engine → write report |

### State файл сессии

```
governance/state/gpt_dev_session.json
  session_id: gds_<hex12>
  trace_id:   <от инициатора>
  status:     idle / queued / running / completed / blocked
  cursor:     N (текущий шаг)
  queue:      [{type, ...}, ...]
  current_step: <type>
  attempts:   N
  last_report: <строка>
  blocker:    null | <описание>
  updated_at: ISO timestamp
```

---

## 5. ПОЛНЫЙ МАРШРУТ: ОТ ВХОДА ДО РЕЗУЛЬТАТА

### 5A. Канонический маршрут (через Куратора)

```
Оператор / внешний аудитор / GPT
  → issue #31 comment: @curator TYPE: CURATOR_ROADMAP_EXECUTION
        ↓
  curator-hosted-gpt.yml → curator_entrypoint.py
    → next_action = START_ROLE_ORCHESTRATOR
        ↓
  role-orchestrator.yml → role_orchestrator.py
    → FSM цикл ролей
        ↓
  curator_summary → BEM-отчёт → telegram_outbox → Telegram
```

### 5B. Маршрут через Autonomous Task Engine

```
GPT → GET /autonomy-backlog-trigger?preset=full_chain&trace_id=X
  → Deno → roadmap_state.json + repository_dispatch autonomy-engine
  → autonomous-task-engine.yml → production_loop
  → commit + report в issue #31
```

### 5C. GPT Self-Write Bridge (патч-маршрут)

```
GPT → patch_queue/generated/<trace>.json
  → issue #31 TYPE: ISA_PATCH_RUNNER
  → isa-patch-runner.yml → allowlist check → commit
```

### 5D. GPT Developer Runner (anti-hang маршрут)

```
GPT → POST /gpt-dev-session
  → Deno → repository_dispatch gpt-dev-runner mode=init
         → repository_dispatch gpt-dev-runner mode=step
  → gpt-dev-runner.yml → execute_one_step() → BEM report
  → auto-dispatch следующего шага пока status=queued
  → stop при completed/blocked
```

---

## 6. FSM ЦИКЛ РОЛЕЙ

### Последовательности (role_sequence.json)

| task_type | Последовательность ролей |
|---|---|
| `default_development` | analyst → auditor → executor → auditor → curator_summary |
| `architecture_change` | analyst → auditor → executor → auditor → curator_summary |
| `internal_contour_proof` | analyst → auditor → executor → auditor → curator_summary |
| `hotfix` | executor → auditor → curator_summary |
| `audit_only` | auditor → curator_summary |

### Ограничения цикла

| Параметр | Значение | Действие |
|---|---|---|
| `max_role_steps_per_cycle` | 8 | step_limit_exceeded → цикл блокируется |
| `max_cycle_age_minutes` | 30 | stale_timeout |
| `emergency_stop.enabled = true` | — | блокирует любой dispatch и apply |

---

## 7. ПРОВАЙДЕРЫ И ПЕРЕКЛЮЧЕНИЕ

### Роли и провайдеры (routing.json v6)

| Роль | Активный | Primary | Reserve |
|---|---|---|---|
| curator | gpt_hosted_fallback | claude | gpt_hosted_fallback |
| analyst | gpt | gpt | claude |
| auditor | claude | claude | gpt_codex |
| executor | claude | claude | gpt_codex |

### Provider Adapters (provider_adapters.json)

| Провайдер | Adapter enabled | write / commit | Примечание |
|---|---|---|---|
| `gpt` | ✅ | ❌ / ❌ | Основной hosted analyst контур |
| `gpt_hosted_fallback` | ✅ | ❌ / ❌ | Hosted fallback curator |
| `gpt_codex` | ✅ | ✅ / ✅ | Write-capable; требует self-hosted runner |
| `isa_patch_runner` | ✅ | ✅ / ✅ | Только для patch_queue задач |
| `claude` | ❌ **false** | ✅ / ✅ | FSM adapter отключён (limits active) |

> `claude.status=ok` в provider_status и `claude.enabled=false` в provider_adapters — разные слои. Claude как FSM роль отключён через adapter даже если API доступен.

### Правила переключения провайдера

| Тип ошибки | Действие |
|---|---|
| `provider_limit` | Переключить немедленно |
| `api_error` (×2) | Переключить |
| `runner_unavailable` | Пропустить, взять следующий |
| `adapter_disabled` | Пропустить, использовать reserve |
| `max_turns`, `config_error`, `timeout` | НЕ переключать |

---

## 8. WORKFLOWS

### Активные workflows

| Workflow | Триггер | Исполнитель | Назначение |
|---|---|---|---|
| `curator-hosted-gpt.yml` | issue_comment + `@curator` | GPT API | Единственная точка входа |
| `gpt-dev-runner.yml` | repository_dispatch `gpt-dev-runner` / workflow_dispatch | Python | GPT Developer Runner — 1 atomic step, 5min timeout |
| `role-orchestrator.yml` | workflow_dispatch | Python FSM | Детерминированный цикл ролей |
| `analyst.yml` | `@analyst` | Claude Code | Прямой триггер (минует FSM adapter) |
| `auditor.yml` | `@auditor` | Claude Code | Прямой триггер |
| `executor.yml` | `@executor` | Claude Code | Прямой триггер |
| `gpt-hosted-roles.yml` | workflow_dispatch + `@gpt_analyst/auditor/executor` | GPT API | Роли через GPT hosted |
| `codex-local.yml` | self-hosted runner | GPT Codex | Write-capable резервный контур |
| `role-router.yml` | workflow_dispatch / CURATOR_TO_ROLE | Python | Маршрутизация по routing.json |
| `autonomous-task-engine.yml` | repository_dispatch / schedule `17 * * * *` / AUTONOMY_ENGINE | Python | Production loop |
| `isa-patch-runner.yml` | ISA_PATCH_RUNNER / workflow_dispatch | Python | Патч-задачи |
| `telegram-outbox-dispatch.yml` | push / schedule `*/5 * * * *` | Python | Отправка в Telegram |
| `curator-hourly-report.yml` | schedule `0 * * * *` | Python | Ежечасный отчёт |

---

## 9. STATE LAYER (JSON-only, SSOT)

| Файл | Назначение | Кто пишет |
|---|---|---|
| `governance/state/routing.json` | Активный провайдер для каждой роли | curator_router.py |
| `governance/state/provider_status.json` | API доступность провайдеров | provider_probe.py |
| `governance/policies/provider_adapters.json` | FSM adapter enabled / workflow | вручную |
| `governance/state/role_cycle_state.json` | Активный FSM цикл | role_orchestrator.py |
| `governance/state/gpt_dev_session.json` | GPT Developer Runner сессия | gpt_dev_runner.py |
| `governance/state/roadmap_state.json` | Дорожная карта задач | Deno / autonomous_task_engine.py |
| `governance/state/emergency_stop.json` | Аварийная остановка | вручную |
| `governance/state/curator_last_decision.json` | Последнее решение куратора | curator_entrypoint.py |
| `governance/exchange.jsonl` | Append-only журнал событий | все компоненты |
| `governance/events/gpt_dev_runner.jsonl` | BEM reports GPT Dev Runner | gpt_dev_runner.py |
| `governance/events/provider_failures.jsonl` | Журнал ошибок провайдеров | curator_router.py |
| `governance/events/routing_decisions.jsonl` | Журнал решений роутера | curator_router.py |
| `governance/telegram_outbox.jsonl` | Очередь исходящих в Telegram | curator / движок |
| `governance/processed_events.jsonl` | Защита от дублей | все компоненты |
| `governance/patch_queue/current.json` | Текущая патч-задача (legacy) | вручную / движок |
| `governance/patch_queue/generated/<trace>.json` | GPT autonomous patch tasks | GPT self-write bridge |

---

## 10. DENO WEBHOOK

**URL:** `https://fine-chicken-23.bereznyi-aleksandr.deno.net`

| Версия | Где |
|---|---|
| `v4.3` | `governance/deno_webhook.js` в репозитории (канон) |
| `v4.4+` | Live Deno Deploy (может отличаться) |

| Endpoint | Метод | Назначение |
|---|---|---|
| `/` | GET | Health check |
| `/autonomy-trigger` | GET | Запустить engine (query params) |
| `/autonomy-backlog-trigger` | GET | Backlog + trigger (`?preset=full_chain`) |
| `/autonomy-backlog` | POST | Backlog + trigger (JSON body) |
| `/autonomy` | POST | Запустить engine (JSON body) |
| `/gpt-dev-session` | GET | Статус GPT dev сессии |
| `/gpt-dev-session` | POST | Инициировать GPT dev сессию + запустить runner |
| `/` | POST | Telegram webhook |

### GPT Developer Runner — запуск через Deno

```
POST /gpt-dev-session
x-gpt-secret: <GPT_WEBHOOK_SECRET>
Content-Type: application/json

{
  "trace_id": "my_dev_trace_001",
  "preset": "developer_runner_selftest"
}
```

---

## 11. ПОЛИТИКИ БЕЗОПАСНОСТИ

| Правило | Статус |
|---|---|
| Production deploy без approval | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Изменение billing / permissions | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Хардкод секретов | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Long-running разработка внутри одного GPT turn | ЗАПРЕЩЕНО |
| Silent hang без blocker записи | ЗАПРЕЩЕНО |
| Более 1 write operation за atomic step | ЗАПРЕЩЕНО |
| Куратор обходит Role Orchestrator | ЗАПРЕЩЕНО |
| gpt_codex при runner_unavailable | Пропускать |
| claude adapter disabled → не в FSM | Использовать reserve |
| Emergency stop enabled=true | Блокирует всё |

---

## 12. QUICK REFERENCE

### Запустить Role Orchestrator через Куратора:
```
@curator
TYPE: CURATOR_ROADMAP_EXECUTION
TRACE_ID: <id>
TASK_TYPE: internal_contour_proof
ЗАДАЧА: [описание]
```

### Запустить GPT Developer Runner (anti-hang):
```
POST /gpt-dev-session
{"trace_id": "dev_001", "preset": "developer_runner_selftest"}
```

### Запустить Autonomous Task Engine:
```
GET /autonomy-backlog-trigger?token=SECRET&mode=production_loop&trace_id=X&preset=full_chain
```

### Поставить GPT patch task:
```
governance/patch_queue/generated/<trace>.json
→ issue #31: TYPE: ISA_PATCH_RUNNER MODE: apply_and_commit TASK_FILE: ...
```

### Аварийная остановка:
```
governance/state/emergency_stop.json: {"enabled": true, "reason": "..."}
```

---

*Версия: v2.3 | 2026-05-13 | внешний аудитор*
*BEM-395: добавлен GPT Developer Runner, anti-hang contract*
