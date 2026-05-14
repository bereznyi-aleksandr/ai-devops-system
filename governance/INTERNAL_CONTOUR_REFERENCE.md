# INTERNAL AUTONOMY CONTOUR — REFERENCE

Версия: v2.4 | Дата: 2026-05-14
Репозиторий: bereznyi-aleksandr/ai-devops-system
Основная ISA: issue #31

---

## CHANGELOG

| Версия | Дата | Изменения |
|---|---|---|
| v2.4 | 2026-05-14 | BEM-402: GPT Full Autonomy Closure — issue_comment entrypoint, lock/retry/watchdog/report contract, Deno fallback без race, self-test acceptance, negative-test acceptance |
| v2.3 | 2026-05-13 | BEM-395: GPT Developer Runner, anti-hang contract |

---

## 1. АРХИТЕКТУРА: КТО ЧТО ДЕЛАЕТ

| Слой | Компонент | Кто | Задача |
|---|---|---|---|
| **Вход** | Telegram / Deno webhook | Оператор | Ставит задачу боту или открывает URL |
| **Вход** | Issue #31 `@curator` | Оператор | Передаёт задачу в систему через GitHub |
| **Вход** | Issue #31 `@gpt-dev run preset=X trace_id=Y` | GPT / Оператор | **BEM-402: Исполняемый entrypoint для GPT Developer Runner** |
| **Вход** | Deno `GET /autonomy-backlog-trigger` | GPT | Автономно добавляет задачи в roadmap и запускает движок |
| **Вход** | Deno `POST /gpt-dev-session` | GPT | Инициирует GPT Developer Runner сессию (Deno fallback) |
| **Вход** | Deno `POST /autonomy-backlog` + `patch_queue/generated/` | GPT | Автономный self-write bridge: GPT ставит патч-задачи → ISA Patch Runner коммитит |
| **Вход** | Внешний LLM-аудитор / операторский чат | Claude / GPT | Пишет `@curator` в issue #31 через GitHub PAT MCP; архитектурный аудит |
| **Управляющий** | `@curator` → `curator-hosted-gpt.yml` | GPT (hosted) | Единственная точка входа во внутренний контур; классифицирует задачу, запускает Role Orchestrator |
| **GPT Dev Entrypoint** | `gpt-dev-entrypoint.yml` | GitHub Actions | **BEM-402: issue_comment триггер; парсит @gpt-dev run; валидирует preset; init → commit → dispatch first step** |
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
| **Внешний LLM-аудитор / операторский чат** | Внешний аудитор | Читать репозиторий, писать `@curator` в issue, писать `@gpt-dev run` в issue #31, архитектурный аудит | Существовать между сообщениями оператора |
| **GPT (отдельный чат)** | Куратор + внешний аудитор | Мониторить систему, запускать контур через Deno или через `@gpt-dev run` в issue #31, писать `@curator`, ставить патч-задачи | Напрямую вызывать роли минуя куратора; вести long-running разработку внутри одного turn |
| **curator-hosted-gpt.yml** | Внутренний куратор | Классифицировать задачи, запускать Role Orchestrator, маршрутизировать через failover | Выполнять код, коммитить файлы |
| **gpt-dev-entrypoint.yml** | Issue Comment Gate | Принять `@gpt-dev run`, валидировать, init, commit, dispatch first step, BEM report | Выполнять step-логику; работать вне issue #31 |
| **gpt-dev-runner.yml** | GPT Developer Runner | Выполнять один atomic step за запуск; читать state, ставить патч-задачи, диспатчить workflows, верифицировать файлы | Выполнять более 1 шага за запуск; зависать в long-running turn |
| **analyst / auditor / executor** | Рабочие роли | Выполнять свою часть FSM-цикла | Принимать архитектурные решения, обходить куратора |

---

## 3. ANTI-HANG CONTRACT (ОБЯЗАТЕЛЕН ДЛЯ ВСЕХ АГЕНТОВ)

> Любая автономная разработка должна следовать этому контракту.
> Silent hang — критическая ошибка. Blocker должен быть явным.

| Правило | Статус |
|---|---|
| Один шаг = один atomic step | ОБЯЗАТЕЛЬНО |
| После каждого шага — BEM report в issue #31 | ОБЯЗАТЕЛЬНО |
| При ошибке → blocker в state + BEM report, не silent wait | ОБЯЗАТЕЛЬНО |
| Long-running разработка внутри одного GPT turn | ЗАПРЕЩЕНО |
| Не более 1 write operation за atomic step | ОБЯЗАТЕЛЬНО |
| Emergency stop проверяется перед каждым шагом | ОБЯЗАТЕЛЬНО |
| Secrets никогда не пишутся в файлы репозитория | АБСОЛЮТНЫЙ ЗАПРЕТ |
| init и step не запускаются одновременно | ОБЯЗАТЕЛЬНО |
| step не запускается до commit init state | ОБЯЗАТЕЛЬНО |

---

## 4. GPT DEVELOPER RUNNER — ПОЛНЫЙ КОНТРАКТ (BEM-402)

### Назначение

Решает проблему зависания GPT при автономной разработке.
ChatGPT оставляет один комментарий в issue #31 → система сама проходит очередь шагов.
Каждый шаг — отдельный GitHub Actions run (timeout 5 минут).

### Маршрут (основной — issue_comment entrypoint)

```
GPT / Оператор → issue #31 comment:
  @gpt-dev run preset=developer_runner_selftest trace_id=bem402_selftest
    ↓
gpt-dev-entrypoint.yml (issue_comment trigger)
  → parse preset, trace_id
  → validate preset
  → check permissions (AI_SYSTEM_GITHUB_PAT)
  → check emergency_stop
  → duplicate-run guard (trace_id не создаёт дубль)
  → acquire lock → gpt_dev_lock.json
  → init_session() → gpt_dev_session.json status=queued
  → commit init state
  → dispatch first step: repository_dispatch gpt-dev-runner mode=step
  → BEM report в issue #31
    ↓
gpt-dev-runner.yml (repository_dispatch) — timeout 5 min
  → execute_one_step():
      проверить emergency_stop
      взять step из очереди по cursor
      выполнить step_handler
      retry если transient error (max 3 попытки)
      blocker если non-transient или лимит retry
      BEM report → events/gpt_dev_runner.jsonl + issue #31
      обновить cursor в gpt_dev_session.json
      release lock при completed/blocked
      если status=queued → auto-dispatch следующего шага
      если status=completed/blocked → остановиться
```

### Маршрут (Deno fallback)

```
GPT → POST /gpt-dev-session {trace_id, preset}
  → Deno → repository_dispatch gpt-dev-runner mode=init (только init!)
  → gpt-dev-runner.yml mode=init → init_session → commit
  → после commit → dispatch first step (init→step handoff)
```

> ЗАПРЕЩЕНО: Deno не должен запускать init и step одновременно.
> First step диспатчится только после успешного commit init state.

### State lock

```
governance/state/gpt_dev_lock.json
  locked:     true/false
  session_id: gds_<hex>
  trace_id:   <trace>
  locked_at:  ISO timestamp
  expires_at: ISO timestamp (locked_at + 10 минут)
  owner:      gpt_dev_runner
  reason:     session_active
```

Правила:
- Активная session ВСЕГДА ставит lock при init
- completed / blocked ВСЕГДА снимают lock
- Stale lock (TTL 10 мин) автоматически очищается
- Параллельные сессии невозможны при активном lock

### Duplicate-run guard

| Ситуация | Действие |
|---|---|
| trace_id уже в status=queued/running | Вернуть текущую сессию, не создавать дубль |
| trace_id уже в status=completed | Разрешить новый запуск с тем же trace_id |
| trace_id уже в status=blocked | Разрешить новый запуск (re-try сессии) |
| lock занят другим trace_id | BLOCKED: lock_held |

### Retry policy

| Параметр | Значение |
|---|---|
| max_attempts_per_step | 3 |
| Transient errors | 5xx, timeout, connection, push conflict, urlopen error |
| Non-transient errors | invalid preset, missing permissions, emergency_stop, unknown step type |
| После лимита retry | status=blocked, blocker заполнен, BEM report |
| Retry action | status остаётся queued, step_attempts увеличивается |

### Watchdog / Stale session

| Условие | Действие |
|---|---|
| session.status=running и updated_at > 10 мин назад | status=blocked, blocker=stale_step_timeout, BEM report |
| workflow timeout | GitHub Actions kills job (5 min timeout), состояние остаётся в running → watchdog на следующем run |
| Silent hang | ЗАПРЕЩЕНО |

### Report guarantee

После каждого atomic step ОБЯЗАТЕЛЬНО:
1. Обновить `governance/state/gpt_dev_session.json`
2. Append `governance/events/gpt_dev_runner.jsonl`
3. Post BEM-GPT-DEV-RUNNER report в issue #31

### Error contract

Любая ошибка:
```json
{
  "status": "blocked",
  "blocker": {
    "reason":        "<описание>",
    "stage":         "<step_type>",
    "error_excerpt": "<первые 200 символов ошибки>",
    "attempt":       N
  }
}
```

Запрещено: silent fail, вечный queued/running без updated_at, workflow success без report.

### Permissions check

Перед стартом проверяется:
- `AI_SYSTEM_GITHUB_PAT` доступен workflow

Если нет:
- session.status = blocked
- blocker = missing_permissions
- BEM report опубликован

### Emergency stop

Если `governance/state/emergency_stop.json` содержит `enabled=true`:
- step не выполняется
- session.status = blocked
- blocker = emergency_stop:<reason>
- BEM report опубликован

### Cleanup

- Stale sessions: watchdog блокирует при TTL > 10 мин
- Stale locks: автоматически очищаются при acquire_lock если TTL истёк
- История events не удаляется (append-only)
- completed/blocked сессии остаются с финальным статусом

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

---

## 5. SELF-TEST ACCEPTANCE (BEM-402)

### Команда запуска:

```
@gpt-dev run preset=developer_runner_selftest trace_id=bem402_selftest
```

### PASS если:

- `governance/state/gpt_dev_session.json`:
  - `status = completed`
  - `trace_id = bem402_selftest`
  - `blocker = null`
  - cursor дошёл до конца queue
- Создан файл: `governance/state/gpt_dev_runner_selftest_bem402_selftest.json`
- Создан/обновлён файл: `governance/events/gpt_dev_runner.jsonl`
- Issue #31 содержит BEM-GPT-DEV-RUNNER reports после каждого шага
- Silent hang отсутствует

### Negative tests (должны возвращать blocked, не silent fail):

| Тест | Ожидаемый результат |
|---|---|
| `@gpt-dev run preset=invalid_preset` | BLOCKED: invalid_preset |
| Повторный `trace_id=bem402_selftest` при status=queued | Вернуть текущую сессию, не создавать дубль |
| `emergency_stop.json enabled=true` | BLOCKED: emergency_stop |
| `AI_SYSTEM_GITHUB_PAT` не доступен | BLOCKED: missing_permissions |
| Stale lock (TTL истёк) | lock очищается, новая сессия стартует |
| init + step dispatch одновременно | ЗАПРЕЩЕНО: step диспатчится только после commit init |

---

## 6. STATE LAYER (JSON-only, SSOT)

| Файл | Назначение | Кто пишет |
|---|---|---|
| `governance/state/routing.json` | Активный провайдер для каждой роли | curator_router.py |
| `governance/state/provider_status.json` | API доступность провайдеров | provider_probe.py |
| `governance/policies/provider_adapters.json` | FSM adapter enabled / workflow | вручную |
| `governance/state/role_cycle_state.json` | Активный FSM цикл | role_orchestrator.py |
| `governance/state/gpt_dev_session.json` | GPT Developer Runner сессия | gpt_dev_runner.py |
| `governance/state/gpt_dev_lock.json` | **BEM-402: State lock** | gpt_dev_runner.py |
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

## 7. FSM ЦИКЛ РОЛЕЙ

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

## 8. ПРОВАЙДЕРЫ И ПЕРЕКЛЮЧЕНИЕ

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

> `claude.status=ok` в provider_status и `claude.enabled=false` в provider_adapters — разные слои.

### Правила переключения провайдера

| Тип ошибки | Действие |
|---|---|
| `provider_limit` | Переключить немедленно |
| `api_error` (×2) | Переключить |
| `runner_unavailable` | Пропустить, взять следующий |
| `adapter_disabled` | Пропустить, использовать reserve |
| `max_turns`, `config_error`, `timeout` | НЕ переключать |

---

## 9. WORKFLOWS

### Активные workflows

| Workflow | Триггер | Исполнитель | Назначение |
|---|---|---|---|
| `curator-hosted-gpt.yml` | issue_comment + `@curator` | GPT API | Единственная точка входа во внутренний контур |
| **`gpt-dev-entrypoint.yml`** | **issue_comment + `@gpt-dev run`** | GitHub Actions | **BEM-402: Issue comment gate для GPT Developer Runner** |
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
| `/gpt-dev-session` | POST | **Deno fallback**: init only → после commit dispatch first step |
| `/` | POST | Telegram webhook |

### Deno fallback — правила BEM-402

```
POST /gpt-dev-session {trace_id, preset}
  → dispatch mode=init ТОЛЬКО
  → после commit init state → dispatch mode=step (first step)
  ЗАПРЕЩЕНО: одновременный dispatch init + step
  ЗАПРЕЩЕНО: dispatch step до commit init
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
| init и step одновременно | ЗАПРЕЩЕНО |
| step до commit init | ЗАПРЕЩЕНО |
| gpt_codex при runner_unavailable | Пропускать |
| claude adapter disabled → не в FSM | Использовать reserve |
| Emergency stop enabled=true | Блокирует всё |

---

## 12. QUICK REFERENCE

### Запустить GPT Developer Runner (основной способ — BEM-402):
```
# Комментарий в issue #31:
@gpt-dev run preset=developer_runner_selftest trace_id=bem402_selftest
```

### Запустить GPT Developer Runner (Deno fallback):
```
POST /gpt-dev-session
{"trace_id": "dev_001", "preset": "developer_runner_selftest"}
```

### Запустить Role Orchestrator через Куратора:
```
@curator
TYPE: CURATOR_ROADMAP_EXECUTION
TRACE_ID: <id>
TASK_TYPE: internal_contour_proof
ЗАДАЧА: [описание]
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

*Версия: v2.4 | 2026-05-14 | внешний аудитор*
*BEM-402: GPT Full Autonomy Closure — issue_comment entrypoint, lock, retry, watchdog, report guarantee, Deno fallback без race, self-test acceptance*
