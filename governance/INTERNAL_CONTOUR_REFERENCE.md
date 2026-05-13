# INTERNAL AUTONOMY CONTOUR — REFERENCE для GPT

Версия: v1.0 | Дата: 2026-05-13
Репозиторий: bereznyi-aleksandr/ai-devops-system
Основная ISA: issue #31

---

## 1. АРХИТЕКТУРА: КТО ЧТО ДЕЛАЕТ

| Слой | Компонент | Кто | Задача |
|---|---|---|---|
| **Вход** | Telegram / Deno webhook | Оператор | Ставит задачу боту или открывает URL |
| **Вход** | Issue #31 `@curator` | Оператор / GPT | Передаёт задачу в систему |
| **Вход** | Deno `GET /autonomy-backlog-trigger` | GPT | Автономно добавляет задачи в roadmap и запускает движок |
| **Управляющий** | `@curator` → `curator-hosted-gpt.yml` | GPT (hosted) | Единственная точка входа; классифицирует задачу, запускает Role Orchestrator |
| **Оркестратор** | `role-orchestrator.yml` → `scripts/role_orchestrator.py` | GitHub Actions | Детерминированный FSM; ведёт цикл ролей по `role_sequence.json` |
| **Провайдер-роутер** | `scripts/curator_router.py` + `provider_failover.py` | Python | Выбирает провайдера (claude / gpt / gpt_codex) для каждой роли |
| **Аналитик** | `analyst.yml` / `gpt-hosted-roles.yml` | Claude Code / GPT | Анализирует задачу, предлагает план |
| **Аудитор** | `auditor.yml` / `gpt-hosted-roles.yml` | Claude Code / GPT | Проверяет решение, выносит APPROVED / BLOCKED |
| **Исполнитель** | `executor.yml` / `gpt-hosted-roles.yml` | Claude Code / GPT | Выполняет задачу, делает commit |
| **Движок задач** | `autonomous-task-engine.yml` + `scripts/autonomous_task_engine.py` | GitHub Actions | Автономно выбирает pending-задачи из roadmap и выполняет их |
| **Patcher** | `isa-patch-runner.yml` + `scripts/isa_patch_runner.py` | GitHub Actions | Применяет файловые патчи из `patch_queue/current.json` |
| **Отчётность** | `telegram-outbox-dispatch.yml` | GitHub Actions | Отправляет готовые сообщения из `telegram_outbox.jsonl` в Telegram |

---

## 2. ПОЛНЫЙ МАРШРУТ: ОТ ВХОДА ДО РЕЗУЛЬТАТА

### 2A. Маршрут через Куратора (канонический)

```
Оператор / GPT
  → issue #31 comment: @curator TYPE: CURATOR_ROADMAP_EXECUTION
        ↓
  curator-hosted-gpt.yml (trigger: issue_comment + @curator)
        ↓
  scripts/curator_entrypoint.py
    → классифицирует TASK_TYPE
    → если CURATOR_ROADMAP_EXECUTION или architecture_change:
        next_action = START_ROLE_ORCHESTRATOR
    → записывает curator_last_decision.json
        ↓
  curator-hosted-gpt.yml шаг: "Dispatch Role Orchestrator"
    → POST /repos/.../actions/workflows/role-orchestrator.yml/dispatches
    → inputs: mode=start, task_type, trace_id, cycle_id
        ↓
  role-orchestrator.yml (trigger: workflow_dispatch)
        ↓
  scripts/role_orchestrator.py
    → читает role_sequence.json → определяет последовательность ролей
    → читает routing.json → определяет провайдера для первой роли
    → dispatch роли через gpt-hosted-roles.yml или analyst.yml
        ↓
  [Цикл ролей по FSM — см. секцию 3]
        ↓
  curator_summary → BEM-отчёт в issue #31
  telegram_outbox.jsonl → Telegram оператору
```

### 2B. Маршрут через Autonomous Task Engine (repo-side)

```
GPT
  → GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/autonomy-backlog-trigger
      ?token=SECRET&mode=production_loop&trace_id=TEST_001&preset=full_chain
        ↓
  Deno v4.2:
    → buildFullChainPreset(traceId) — уникальные task_id через trace_id
    → GitHub Contents API → обновляет roadmap_state.json (3 задачи pending)
    → POST /repos/.../dispatches event_type=autonomy-engine
        ↓
  autonomous-task-engine.yml (trigger: repository_dispatch)
  concurrency: group=autonomy-engine-main (нет параллельных запусков)
        ↓
  scripts/autonomous_task_engine.py --mode production_loop
    → выбирает pending задачи из roadmap_state.json
    → выполняет: create_json_state / append_event
    → коммитит результат
    → обновляет roadmap_state.json: задача → completed
        ↓
  BEM-AUTONOMY-ENGINE report в issue #31
```

---

## 3. FSM ЦИКЛ РОЛЕЙ

### Последовательности (из role_sequence.json)

| task_type | Последовательность |
|---|---|
| `default_development` | analyst → auditor → executor → auditor → curator_summary |
| `architecture_change` | analyst → auditor → executor → auditor → curator_summary |
| `internal_contour_proof` | analyst → auditor → executor → auditor → curator_summary |
| `hotfix` | executor → auditor → curator_summary |
| `audit_only` | auditor → curator_summary |

### Ограничения цикла

| Параметр | Значение |
|---|---|
| `max_role_steps_per_cycle` | 8 |
| `max_cycle_age_minutes` | 30 |
| При превышении шагов | статус → `step_limit_exceeded`, цикл блокируется |
| При timeout цикла | статус → `stale_timeout` |
| Терминальные статусы | completed / blocked / stale_timeout / step_limit_exceeded |

### State файл цикла

```
governance/state/role_cycle_state.json
  cycle_id: cyc_<name>_<timestamp>
  trace_id: <от куратора>
  status: cycle_started → role_dispatched → completed
  current_role: analyst / auditor / executor / curator_summary
  step_count: N
  step_history: [{role, provider, status, timestamp}, ...]
```

---

## 4. ПРОВАЙДЕРЫ И ПЕРЕКЛЮЧЕНИЕ

### Текущая конфигурация (routing.json v6)

| Роль | Активный провайдер | Primary | Reserve | Fallback chain |
|---|---|---|---|---|
| curator | `gpt_hosted_fallback` | claude | gpt_hosted_fallback | gpt_hosted_fallback → gpt |
| analyst | `gpt` | gpt | claude | claude → gpt_codex → codex |
| auditor | `claude` | claude | gpt_codex | gpt_codex → gpt |
| executor | `claude` | claude | gpt_codex | gpt_codex → gpt |

### Текущий статус провайдеров (provider_status.json)

| Провайдер | Статус | Примечание |
|---|---|---|
| `claude` | ✅ ok | Основной для auditor/executor |
| `gpt` | ✅ ok | Основной для analyst; hosted fallback для curator |
| `gpt_codex` | ❌ error | `runner_unavailable` — self-hosted runner не подключён |

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
| `provider_limit` | Переключить немедленно |
| `api_error` (×2 подряд) | Переключить |
| `runner_unavailable` | Переключить, пропустить unhealthy |
| `max_turns` | НЕ переключать (ошибка конфигурации) |
| `config_error` | НЕ переключать (ошибка конфигурации) |
| `permission_error` | НЕ переключать |
| `timeout` | НЕ переключать |

---

## 5. WORKFLOWS

### Активные workflows

| Workflow | Триггер | Провайдер | Назначение |
|---|---|---|---|
| `curator-hosted-gpt.yml` | issue_comment + `@curator` | GPT (OpenAI API) | Единственная точка входа; роутит в Role Orchestrator |
| `role-orchestrator.yml` | workflow_dispatch | Python FSM | Детерминированный цикл ролей |
| `analyst.yml` | issue_comment + `@analyst` | Claude Code | Аналитик (Claude провайдер) |
| `auditor.yml` | issue_comment + `@auditor` | Claude Code | Аудитор (Claude провайдер) |
| `executor.yml` | issue_comment + `@executor` | Claude Code | Исполнитель (Claude провайдер) |
| `gpt-hosted-roles.yml` | workflow_dispatch + `@gpt_analyst/auditor/executor` | GPT (OpenAI API) | Роли через GPT hosted fallback |
| `role-router.yml` | workflow_dispatch / issue_comment TYPE: CURATOR_TO_ROLE | Python | Маршрутизирует роль по routing.json |
| `autonomous-task-engine.yml` | repository_dispatch / schedule `17 * * * *` / issue TYPE: AUTONOMY_ENGINE | Python | Production loop; выполняет roadmap задачи |
| `isa-patch-runner.yml` | issue TYPE: ISA_PATCH_RUNNER / workflow_dispatch | Python | Применяет файловые патчи |
| `telegram-outbox-dispatch.yml` | push к `telegram_outbox.jsonl` / schedule `*/5 * * * *` | Python | Отправляет сообщения в Telegram |
| `curator-hourly-report.yml` | schedule `0 * * * *` / workflow_dispatch | Python | Ежечасный отчёт в Telegram |

### Отключённые / legacy workflows

| Workflow | Статус |
|---|---|
| `telegram-gateway.yml` | DISABLED |
| `telegram-send.yml` | DISABLED |
| `update-status.yml` | DISABLED |
| `gpt-scheduler-tick.yml` | DISABLED |
| `cloud-scheduler-tick.yml` | DISABLED |

---

## 6. STATE LAYER (JSON-only)

| Файл | Назначение |
|---|---|
| `governance/state/routing.json` | Активный провайдер для каждой роли |
| `governance/state/provider_status.json` | Здоровье провайдеров (ok / error / limited) |
| `governance/state/system_state.json` | Текущий этап, режим работы |
| `governance/state/role_cycle_state.json` | Активный FSM цикл |
| `governance/state/roadmap_state.json` | Дорожная карта задач (pending / completed / blocked) |
| `governance/state/emergency_stop.json` | Аварийная остановка (enabled: true/false) |
| `governance/state/curator_last_decision.json` | Последнее решение куратора |
| `governance/state/internal_contour_status.json` | Базовый статус внутреннего контура |
| `governance/exchange.jsonl` | Append-only журнал всех событий |
| `governance/events/provider_failures.jsonl` | Журнал ошибок провайдеров |
| `governance/events/routing_decisions.jsonl` | Журнал решений роутера |
| `governance/events/autonomous_development.jsonl` | События автономной разработки |
| `governance/telegram_outbox.jsonl` | Очередь исходящих сообщений в Telegram |
| `governance/processed_events.jsonl` | Защита от дублей |
| `governance/patch_queue/current.json` | Текущая патч-задача для ISA Patch Runner |

---

## 7. DENO WEBHOOK (внешний вход для GPT)

**URL:** `https://fine-chicken-23.bereznyi-aleksandr.deno.net`
**Версия:** v4.2

| Endpoint | Метод | Назначение |
|---|---|---|
| `/` | GET | Health check (version, github_pat_present, gpt_webhook_secret_present) |
| `/autonomy-trigger` | GET | Запустить autonomous-task-engine (без задач) |
| `/autonomy-backlog-trigger` | GET | Добавить задачи + запустить engine (?preset=full_chain или tasks_b64) |
| `/autonomy-backlog` | POST | То же, JSON body |
| `/autonomy` | POST | Запустить engine без задач, JSON body |
| `/` | POST | Telegram webhook |

### preset=full_chain

Генерирует 3 уникальные задачи через trace_id (BM-354 fix):
- `TC_<safeTrace>_001_JSON` → `governance/state/test_ic_a_<trace>_001.json`
- `TC_<safeTrace>_002_EVENT` → `governance/events/full_chain_autonomy_test.jsonl`
- `TC_<safeTrace>_003_JSON` → `governance/state/test_ic_a_<trace>_003.json`

**Пример вызова:**
```
GET /autonomy-backlog-trigger?token=SECRET&mode=production_loop&trace_id=TEST_001&preset=full_chain
```

---

## 8. ПОЛИТИКИ БЕЗОПАСНОСТИ

| Запрет | Статус |
|---|---|
| Production deploy без approval | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Изменение billing / permissions | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Хардкод секретов (только GitHub Secrets / Deno env) | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Более 1 write operation за цикл | ЗАПРЕЩЕНО |
| Куратор напрямую вызывает роли минуя Role Orchestrator | ЗАПРЕЩЕНО |
| gpt_codex при статусе error/runner_unavailable | ПРОПУСКАТЬ в fallback |
| Emergency stop enabled=true | Блокирует dispatch и apply |

---

## 9. ТЕКУЩИЕ BLOCKERS

| Компонент | Статус | Причина |
|---|---|---|
| `gpt_codex` | ❌ error | Self-hosted runner недоступен |
| IC-B Full Contour Proof | ⏳ в процессе | Запущен через @curator trace=ic_b_full_contour_20260511 |

---

## 10. QUICK REFERENCE ДЛЯ GPT

### Как поставить задачу в движок (без Shell):
```
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/autonomy-backlog-trigger
  ?token=<GPT_WEBHOOK_SECRET>
  &mode=production_loop
  &trace_id=<уникальный_id>
  &preset=full_chain
```

### Как запустить Role Orchestrator через Curator:
```
Issue #31 comment:
@curator

TYPE: CURATOR_ROADMAP_EXECUTION
TRACE_ID: <уникальный_id>
TASK_TYPE: internal_contour_proof

ЗАДАЧА: [описание]
```

### Как переключить провайдера (аварийно):
```
Обновить governance/state/routing.json:
roles.<role>.active = "gpt" | "claude"

Обновить governance/state/provider_status.json:
providers.<name>.status = "ok" | "limited" | "error"
```

### Как остановить систему аварийно:
```
Обновить governance/state/emergency_stop.json:
{"enabled": true, "reason": "причина"}
```

---

*Документ создан: 2026-05-13 | Claude-аудитор*
*Источники: routing.json v6, role_sequence.json v2, provider_status.json, workflows*
