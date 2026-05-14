# INTERNAL AUTONOMY CONTOUR — REFERENCE

Версия: v2.5 | Дата: 2026-05-14
Репозиторий: bereznyi-aleksandr/ai-devops-system
Основная ISA: issue #31

---

## CHANGELOG

| Версия | Дата | Изменения |
|---|---|---|
| v2.5 | 2026-05-14 | BEM-406: ChatGPT-compatible entrypoint — safe command `GPT_DEV_RUN preset=... trace_id=...` без @mention; legacy `@gpt-dev run` сохранён; self-test bem406_selftest; negative test bad_preset |
| v2.4 | 2026-05-14 | BEM-402: GPT Full Autonomy Closure — issue_comment entrypoint, lock/retry/watchdog/report contract, Deno fallback без race, self-test acceptance, negative-test acceptance |
| v2.3 | 2026-05-13 | BEM-395: GPT Developer Runner, anti-hang contract |

---

## 1. АРХИТЕКТУРА: КТО ЧТО ДЕЛАЕТ

| Слой | Компонент | Кто | Задача |
|---|---|---|---|
| **Вход** | Telegram / Deno webhook | Оператор | Ставит задачу боту или открывает URL |
| **Вход** | Issue #31 `@curator` | Оператор | Передаёт задачу в систему через GitHub |
| **Вход** | Issue #31 `@gpt-dev run preset=X trace_id=Y` | Оператор / Claude | Legacy entrypoint для GPT Developer Runner (BEM-402) |
| **Вход** | Issue #31 `GPT_DEV_RUN preset=X trace_id=Y` | **ChatGPT** | **BEM-406: ChatGPT-safe entrypoint без @mention** |
| **Вход** | Deno `GET /autonomy-backlog-trigger` | GPT | Автономно добавляет задачи в roadmap и запускает движок |
| **Вход** | Deno `POST /gpt-dev-session` | GPT | Инициирует GPT Developer Runner сессию (Deno fallback) |
| **Вход** | Deno `POST /autonomy-backlog` + `patch_queue/generated/` | GPT | Автономный self-write bridge: GPT ставит патч-задачи → ISA Patch Runner коммитит |
| **Вход** | Внешний LLM-аудитор / операторский чат | Claude / GPT | Пишет `@curator` в issue #31 через GitHub PAT MCP; архитектурный аудит |
| **Управляющий** | `@curator` → `curator-hosted-gpt.yml` | GPT (hosted) | Единственная точка входа во внутренний контур; классифицирует задачу, запускает Role Orchestrator |
| **GPT Dev Entrypoint** | `gpt-dev-entrypoint.yml` | GitHub Actions | BEM-402/406: issue_comment триггер; поддерживает оба формата команд; парсит preset; init → commit → dispatch first step |
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

## 2. CHATGPT-COMPATIBLE ENTRYPOINT (BEM-406)

### Почему @mention недостаточен

ChatGPT GitHub write-tool блокирует отправку комментариев, содержащих исполняемые @-команды.
Это делает `@gpt-dev run ...` недоступным для ChatGPT из чата без ручного браузера.

Решение: добавить второй формат команды без @mention, который ChatGPT может свободно записать в комментарий issue #31.

### Два поддерживаемых формата

| Формат | Синтаксис | Кто использует |
|---|---|---|
| **ChatGPT-safe** (основной) | `GPT_DEV_RUN preset=X trace_id=Y` | ChatGPT из чата |
| **Legacy/operator** | `@gpt-dev run preset=X trace_id=Y` | Оператор, Claude, другие инструменты |

Оба формата:
- Работают только в issue #31
- Проходят одинаковую валидацию preset
- Запускают одинаковый pipeline (init → step → auto-continue → report)
- Производят одинаковые BEM reports

### Workflow trigger condition

```yaml
if: >
  github.event.issue.number == 31 && (
    contains(github.event.comment.body, '@gpt-dev run') ||
    contains(github.event.comment.body, 'GPT_DEV_RUN')
  )
```

### Примеры команд

```
# ChatGPT-safe (без @mention):
GPT_DEV_RUN preset=developer_runner_selftest trace_id=bem406_selftest
GPT_DEV_RUN preset=fix_internal_contour trace_id=bem406_ic_fix

# Legacy/operator:
@gpt-dev run preset=developer_runner_selftest trace_id=bem402_selftest
@gpt-dev run preset=fix_internal_contour trace_id=bem402_ic_fix
```

### Parser

Python-парсер извлекает из тела комментария:
- `preset=<value>` — обязательный параметр
- `trace_id=<value>` — опциональный (если нет: `auto_<timestamp>`)
- `mode=<value>` — опциональный (default: step)

Работает для обоих форматов через regex `preset=([a-zA-Z0-9_]+)`.

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

## 4. GPT DEVELOPER RUNNER — ПОЛНЫЙ КОНТРАКТ

### Назначение

Решает проблему зависания GPT при автономной разработке.
ChatGPT оставляет один комментарий в issue #31 → система сама проходит очередь шагов.
Каждый шаг — отдельный GitHub Actions run (timeout 5 минут).

### Полный маршрут

```
ChatGPT → issue #31 comment:
  GPT_DEV_RUN preset=developer_runner_selftest trace_id=bem406_selftest
    ↓
gpt-dev-entrypoint.yml (issue_comment trigger)
  → detect format (safe vs legacy)
  → parse preset, trace_id via Python regex
  → validate preset against VALID_PRESETS
  → check permissions (AI_SYSTEM_GITHUB_PAT)
  → duplicate-run guard
  → acquire lock → gpt_dev_lock.json
  → init_session() → gpt_dev_session.json status=queued
  → commit init state
  → dispatch first step: repository_dispatch gpt-dev-runner mode=step
  → BEM-406 report в issue #31
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

### Duplicate-run guard

| Ситуация | Действие |
|---|---|
| trace_id уже в status=queued/running | Вернуть текущую сессию, не создавать дубль |
| trace_id уже в status=completed | Разрешить новый запуск |
| lock занят другим trace_id | BLOCKED: lock_held |

### Retry policy

| Параметр | Значение |
|---|---|
| max_attempts_per_step | 3 |
| Transient errors | 5xx, timeout, connection, push conflict, urlopen error |
| Non-transient errors | invalid preset, missing permissions, emergency_stop, unknown step type |
| После лимита retry | status=blocked, blocker заполнен, BEM report |

### Watchdog

| Условие | Действие |
|---|---|
| session.status=running и updated_at > 10 мин назад | status=blocked, blocker=stale_step_timeout, BEM report |
| Silent hang | ЗАПРЕЩЕНО |

### Поддерживаемые step types

| Step type | Описание |
|---|---|
| `read_state` | Читает JSON файл |
| `enqueue_patch_task` | Создаёт файл в `patch_queue/generated/` |
| `dispatch_workflow` | Триггерит repository_dispatch |
| `verify_file` | Проверяет существование файла |
| `verify_state` | Проверяет поля JSON файла |
| `write_report` | Записывает итоговый отчёт сессии |

### Presets

| Preset | Шаги |
|---|---|
| `developer_runner_selftest` | read system_state → read routing → verify reference → enqueue patch → write report |
| `fix_internal_contour` | read role_cycle → read roadmap → read provider_status → verify emergency_stop → dispatch autonomy-engine → write report |

---

## 5. SELF-TEST ACCEPTANCE

### BEM-406 self-test (ChatGPT-safe format):

```
GPT_DEV_RUN preset=developer_runner_selftest trace_id=bem406_selftest
```

### BEM-402 self-test (legacy format):

```
@gpt-dev run preset=developer_runner_selftest trace_id=bem402_selftest
```

### PASS если:

- `governance/state/gpt_dev_session.json`:
  - `status = completed`
  - `trace_id = <trace>`
  - `blocker = null`
  - cursor дошёл до конца queue
- Создан файл: `governance/state/gpt_dev_runner_selftest_<trace>.json`
- Создан/обновлён: `governance/events/gpt_dev_runner.jsonl`
- Issue #31 содержит BEM-GPT-DEV-RUNNER reports после каждого шага
- Silent hang отсутствует

### Negative tests:

| Тест | Ожидаемый результат |
|---|---|
| `GPT_DEV_RUN preset=bad_preset` | BLOCKED: invalid_preset; BEM report опубликован |
| `@gpt-dev run preset=invalid_preset` | BLOCKED: invalid_preset; BEM report опубликован |
| Повторный trace_id при status=queued | Вернуть текущую сессию, не создавать дубль |
| `emergency_stop.json enabled=true` | BLOCKED: emergency_stop |
| `AI_SYSTEM_GITHUB_PAT` не доступен | BLOCKED: missing_permissions |
| Stale lock (TTL истёк) | lock очищается автоматически |

---

## 6. STATE LAYER (JSON-only, SSOT)

| Файл | Назначение | Кто пишет |
|---|---|---|
| `governance/state/routing.json` | Активный провайдер для каждой роли | curator_router.py |
| `governance/state/provider_status.json` | API доступность провайдеров | provider_probe.py |
| `governance/policies/provider_adapters.json` | FSM adapter enabled / workflow | вручную |
| `governance/state/role_cycle_state.json` | Активный FSM цикл | role_orchestrator.py |
| `governance/state/gpt_dev_session.json` | GPT Developer Runner сессия | gpt_dev_runner.py |
| `governance/state/gpt_dev_lock.json` | State lock (BEM-402) | gpt_dev_runner.py |
| `governance/state/roadmap_state.json` | Дорожная карта задач | Deno / autonomous_task_engine.py |
| `governance/state/emergency_stop.json` | Аварийная остановка | вручную |
| `governance/state/curator_last_decision.json` | Последнее решение куратора | curator_entrypoint.py |
| `governance/exchange.jsonl` | Append-only журнал событий | все компоненты |
| `governance/events/gpt_dev_runner.jsonl` | BEM reports GPT Dev Runner | gpt_dev_runner.py |
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

---

## 9. WORKFLOWS

### Активные workflows

| Workflow | Триггер | Исполнитель | Назначение |
|---|---|---|---|
| `curator-hosted-gpt.yml` | issue_comment + `@curator` | GPT API | Единственная точка входа во внутренний контур |
| `gpt-dev-entrypoint.yml` | issue_comment + `@gpt-dev run` OR `GPT_DEV_RUN` | GitHub Actions | BEM-402/406: Issue comment gate для GPT Developer Runner |
| `gpt-dev-runner.yml` | repository_dispatch `gpt-dev-runner` / workflow_dispatch | Python | GPT Developer Runner — 1 atomic step, 5min timeout |
| `role-orchestrator.yml` | workflow_dispatch | Python FSM | Детерминированный цикл ролей |
| `analyst.yml` | `@analyst` | Claude Code | Прямой триггер |
| `auditor.yml` | `@auditor` | Claude Code | Прямой триггер |
| `executor.yml` | `@executor` | Claude Code | Прямой триггер |
| `gpt-hosted-roles.yml` | workflow_dispatch + `@gpt_analyst/auditor/executor` | GPT API | Роли через GPT hosted |
| `codex-local.yml` | self-hosted runner | GPT Codex | Write-capable резервный контур |
| `autonomous-task-engine.yml` | repository_dispatch / schedule / AUTONOMY_ENGINE | Python | Production loop |
| `isa-patch-runner.yml` | ISA_PATCH_RUNNER / workflow_dispatch | Python | Патч-задачи |
| `telegram-outbox-dispatch.yml` | push / schedule `*/5 * * * *` | Python | Отправка в Telegram |
| `curator-hourly-report.yml` | schedule `0 * * * *` | Python | Ежечасный отчёт |

---

## 10. DENO WEBHOOK

**URL:** `https://fine-chicken-23.bereznyi-aleksandr.deno.net`

| Endpoint | Метод | Назначение |
|---|---|---|
| `/gpt-dev-session` | POST | Deno fallback: init only → после commit dispatch first step |
| `/autonomy-backlog-trigger` | GET | Backlog + trigger |
| `/autonomy` | POST | Запустить engine |
| `/` | GET/POST | Health check / Telegram webhook |

### Deno fallback — правила

```
POST /gpt-dev-session {trace_id, preset}
  → dispatch mode=init ТОЛЬКО
  → после commit init state → dispatch mode=step (first step)
  ЗАПРЕЩЕНО: одновременный dispatch init + step
```

---

## 11. ПОЛИТИКИ БЕЗОПАСНОСТИ

| Правило | Статус |
|---|---|
| Production deploy без approval | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Хардкод секретов | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Long-running разработка внутри одного GPT turn | ЗАПРЕЩЕНО |
| Silent hang без blocker записи | ЗАПРЕЩЕНО |
| Более 1 write operation за atomic step | ЗАПРЕЩЕНО |
| init и step одновременно | ЗАПРЕЩЕНО |
| Emergency stop enabled=true | Блокирует всё |

---

## 12. QUICK REFERENCE

### ChatGPT → запустить GPT Developer Runner (BEM-406, safe format):
```
# Комментарий в issue #31 — ChatGPT может это написать:
GPT_DEV_RUN preset=developer_runner_selftest trace_id=bem406_selftest
```

### Оператор / Claude → запустить GPT Developer Runner (legacy):
```
@gpt-dev run preset=developer_runner_selftest trace_id=bem402_selftest
```

### Запустить через Deno (fallback):
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

### Аварийная остановка:
```
governance/state/emergency_stop.json: {"enabled": true, "reason": "..."}
```

---

*Версия: v2.5 | 2026-05-14 | внешний аудитор*
*BEM-406: ChatGPT-compatible entrypoint — GPT_DEV_RUN safe format, legacy @gpt-dev run сохранён*
