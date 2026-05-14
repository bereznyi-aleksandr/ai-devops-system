# INTERNAL AUTONOMY CONTOUR — REFERENCE

Версия: v2.7 | Дата: 2026-05-14
Репозиторий: bereznyi-aleksandr/ai-devops-system
Основная ISA: issue #31

---

## CHANGELOG

| Версия | Дата | Изменения |
|---|---|---|
| v2.7 | 2026-05-14 | BEM-420: /gpt-safe-run primary trigger = workflow_dispatch; repository_dispatch не primary для GPT Runner; deno v4.5; Reference update |
| v2.6 | 2026-05-14 | BEM-409: Deno Safe Entrypoint PRIMARY без token, /gpt-safe-status, rate limit |
| v2.5 | 2026-05-14 | BEM-406: ChatGPT-compatible GPT_DEV_RUN без @mention |
| v2.4 | 2026-05-14 | BEM-402: GPT Full Autonomy Closure — lock/retry/watchdog |
| v2.3 | 2026-05-13 | BEM-395: GPT Developer Runner, anti-hang contract |

---

## 1. ВХОДЫ (ПРИОРИТЕТ)

| Приоритет | Канал | Синтаксис | Кто |
|---|---|---|---|
| **PRIMARY** | **Deno Safe Entrypoint** | `GET /gpt-safe-run?preset=X&trace_id=Y` | **ChatGPT (open URL)** |
| backup | Issue comment (safe) | `GPT_DEV_RUN preset=X trace_id=Y` | ChatGPT (comment tool, ненадёжен) |
| backup | Issue comment (legacy) | `@gpt-dev run preset=X trace_id=Y` | Оператор / Claude PAT MCP |
| backup | Deno fallback POST | `POST /gpt-dev-session` (token required) | Любой |
| backup | workflow_dispatch | GitHub UI / API | Оператор |

---

## 2. DENO SAFE ENTRYPOINT v4.5 (BEM-420)

### Primary trigger: workflow_dispatch

Начиная с v4.5, `/gpt-safe-run` использует **workflow_dispatch** (не repository_dispatch) для запуска `gpt-dev-runner.yml`.

**Почему workflow_dispatch:**
- repository_dispatch запускает workflow только если есть `on: repository_dispatch` триггер — может быть ненадёжен при пустом state
- workflow_dispatch напрямую адресует файл `gpt-dev-runner.yml` с явными `inputs`
- При workflow_dispatch runner получает `inputs.mode`, `inputs.preset`, `inputs.trace_id` без парсинга `client_payload`

### Изменения в deno_webhook.js v4.5

| Что | Было | Стало |
|---|---|---|
| Primary trigger | `triggerRepositoryDispatch(...)` | `triggerWorkflowDispatch(pat, "gpt-dev-runner.yml", "main", {mode, preset, trace_id})` |
| Ответ поле | `dispatch_status` | `workflow_dispatch_status` |
| Ответ поле | `source: "deno_gpt_safe_run"` | `source: "deno_gpt_safe_run_v45"` |
| Ответ поле | — | `trigger_method: "workflow_dispatch"` |
| Health version | `"4.4"` | `"4.5"` |
| repository_dispatch | primary | helper (autonomy-engine, Deno fallback) |

### Endpoint

```
GET /gpt-safe-run?preset=<preset>&trace_id=<trace>
```

**Без token.** Allowlist presets: `developer_runner_selftest`, `fix_internal_contour`, `status`.

### Успешный ответ v4.5

```json
{
  "ok": true,
  "trace_id": "bem420_selftest",
  "preset": "developer_runner_selftest",
  "trigger_method": "workflow_dispatch",
  "workflow_dispatch_status": 204,
  "source": "deno_gpt_safe_run_v45",
  "monitor_url": "/gpt-safe-status?trace_id=bem420_selftest"
}
```

### Ошибка dispatch

```json
{
  "ok": false,
  "error": "workflow_dispatch_failed",
  "workflow_dispatch_status": <HTTP code>,
  "detail": "GitHub workflow_dispatch returned HTTP <code>"
}
```

### Security controls

| Контроль | Реализация |
|---|---|
| Allowlist preset | `SAFE_RUN_PRESETS = { developer_runner_selftest, fix_internal_contour, status }` |
| trace_id validation | regex `[a-zA-Z0-9_]{1,60}` |
| Emergency stop | читает `emergency_stop.json` перед dispatch |
| Active session check | queued/running → 429 |
| In-memory rate limit | 1 раз в 60 сек |
| Произвольный код/patch | АБСОЛЮТНО ЗАПРЕЩЕНО |

### Status endpoint

```
GET /gpt-safe-status?trace_id=<trace>
```

Возвращает: `session`, `lock`, `last_event`, `proof_exists`, `blocker`.

---

## 3. SELF-TEST ACCEPTANCE (BEM-420)

### Команды оператора после деплоя v4.5:

**1. Проверить health:**
```
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/
Ожидаемо: version = "4.5"
```

**2. Запустить self-test:**
```
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/gpt-safe-run?preset=developer_runner_selftest&trace_id=bem420_selftest
Ожидаемо: {"ok": true, "trigger_method": "workflow_dispatch", "workflow_dispatch_status": 204}
```

**3. Мониторинг:**
```
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/gpt-safe-status?trace_id=bem420_selftest
PASS: status_summary.status = "completed", proof_exists = true
```

**4. Negative test:**
```
GET /gpt-safe-run?preset=bad_preset&trace_id=bem420_bad
Ожидаемо: {"ok": false, "error": "invalid_preset"}
```

---

## 4. ANTI-HANG CONTRACT

| Правило | Статус |
|---|---|
| Один шаг = один atomic step | ОБЯЗАТЕЛЬНО |
| После шага — BEM report в issue #31 | ОБЯЗАТЕЛЬНО |
| Ошибка → blocker, не silent wait | ОБЯЗАТЕЛЬНО |
| init и step одновременно | ЗАПРЕЩЕНО |
| step до commit init | ЗАПРЕЩЕНО |
| Silent hang | ЗАПРЕЩЕНО |
| Secrets в файлы репозитория | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Произвольный код/patch через /gpt-safe-run | АБСОЛЮТНЫЙ ЗАПРЕТ |

---

## 5. GPT DEVELOPER RUNNER

### Presets

| Preset | Шаги |
|---|---|
| `developer_runner_selftest` | read system_state → read routing → verify reference → enqueue patch → write report |
| `fix_internal_contour` | read role_cycle → read roadmap → read provider_status → verify emergency_stop → dispatch autonomy-engine → write report |

### State files

| Файл | Назначение |
|---|---|
| `governance/state/gpt_dev_session.json` | Сессия (status, cursor, queue, blocker) |
| `governance/state/gpt_dev_lock.json` | Lock (locked, session_id, expires_at) |
| `governance/state/emergency_stop.json` | Аварийная остановка |
| `governance/events/gpt_dev_runner.jsonl` | BEM reports (append-only) |
| `governance/state/gpt_dev_runner_selftest_<trace>.json` | Proof file |

---

## 6. DENO WEBHOOK v4.5 — ENDPOINTS

**URL:** `https://fine-chicken-23.bereznyi-aleksandr.deno.net`

| Endpoint | Метод | Token | Trigger | Назначение |
|---|---|---|---|---|
| `/gpt-safe-run` | GET | ❌ | **workflow_dispatch** | PRIMARY GPT entrypoint |
| `/gpt-safe-status` | GET | ❌ | — | Read-only мониторинг |
| `/gpt-dev-session` | GET | ✅ | — | Статус сессии (legacy) |
| `/gpt-dev-session` | POST | ✅ | repository_dispatch | Deno fallback init |
| `/autonomy-trigger` | GET | ✅ | repository_dispatch | autonomy-engine |
| `/autonomy-backlog-trigger` | GET | ✅ | repository_dispatch | Backlog + engine |
| `/autonomy-backlog` | POST | ✅ | repository_dispatch | Backlog + engine |
| `/autonomy` | POST | ✅ | repository_dispatch | Engine direct |
| `/` | GET | ❌ | — | Health check (version: 4.5) |
| `/` | POST | — | — | Telegram webhook |

---

## 7. WORKFLOWS

| Workflow | Триггер | Назначение |
|---|---|---|
| `gpt-dev-runner.yml` | **workflow_dispatch** (primary) + repository_dispatch + issue_comment | GPT Runner — 1 atomic step |
| `gpt-dev-entrypoint.yml` | issue_comment `@gpt-dev run` OR `GPT_DEV_RUN` | Issue comment gate |
| `curator-hosted-gpt.yml` | issue_comment `@curator` | Внутренний контур |
| `autonomous-task-engine.yml` | repository_dispatch / schedule | Production loop |
| `isa-patch-runner.yml` | ISA_PATCH_RUNNER | Патч-задачи |

---

## 8. QUICK REFERENCE

### ChatGPT PRIMARY (открыть URL):
```
https://fine-chicken-23.bereznyi-aleksandr.deno.net/gpt-safe-run?preset=developer_runner_selftest&trace_id=bem420_selftest
```

### Мониторинг:
```
https://fine-chicken-23.bereznyi-aleksandr.deno.net/gpt-safe-status?trace_id=bem420_selftest
```

### Аварийная остановка:
```
governance/state/emergency_stop.json: {"enabled": true, "reason": "..."}
```

---

*Версия: v2.7 | 2026-05-14 | внешний аудитор*
*BEM-420: workflow_dispatch primary, deno v4.5, deploy + self-test выполняет оператор*
