# INTERNAL AUTONOMY CONTOUR — REFERENCE

Версия: v2.6 | Дата: 2026-05-14
Репозиторий: bereznyi-aleksandr/ai-devops-system
Основная ISA: issue #31

---

## CHANGELOG

| Версия | Дата | Изменения |
|---|---|---|
| v2.6 | 2026-05-14 | BEM-409: Deno Safe Entrypoint — GET /gpt-safe-run PRIMARY без token, allowlist-only; GET /gpt-safe-status; BEM-402 race condition fix в initDevSession; rate limit; reference update |
| v2.5 | 2026-05-14 | BEM-406: ChatGPT-compatible entrypoint — safe command GPT_DEV_RUN без @mention |
| v2.4 | 2026-05-14 | BEM-402: GPT Full Autonomy Closure — lock/retry/watchdog/report guarantee |
| v2.3 | 2026-05-13 | BEM-395: GPT Developer Runner, anti-hang contract |

---

## 1. АРХИТЕКТУРА ВХОДОВ (ПРИОРИТЕТ)

| Приоритет | Канал | Синтаксис | Кто | Примечание |
|---|---|---|---|---|
| **PRIMARY** | **Deno Safe Entrypoint** | `GET /gpt-safe-run?preset=X&trace_id=Y` | **ChatGPT (open URL)** | Без token, allowlist-only, надёжный |
| backup | Issue comment (safe) | `GPT_DEV_RUN preset=X trace_id=Y` | ChatGPT (comment tool) | Может не материализоваться |
| backup | Issue comment (legacy) | `@gpt-dev run preset=X trace_id=Y` | Оператор / Claude | Работает через GitHub PAT MCP |
| backup | Deno fallback (POST) | `POST /gpt-dev-session` | Любой (token required) | Требует GPT_WEBHOOK_SECRET |
| backup | workflow_dispatch | GitHub UI / API | Оператор | Ручной запуск |

**Почему Deno Safe Entrypoint PRIMARY:**
- ChatGPT может открыть URL в браузере без ограничений на @mention и write-tool
- Не требует token — публичный endpoint защищён allowlist preset + rate limit + active session check + emergency stop
- Никакого произвольного кода / patch через публичный URL невозможно

---

## 2. DENO SAFE ENTRYPOINT (BEM-409)

### Endpoint

```
GET /gpt-safe-run?preset=<preset>&trace_id=<trace>
```

**Без token.** Доступен публично.

### Allowlist presets

| Preset | Описание |
|---|---|
| `developer_runner_selftest` | Полный self-test: read state → verify → enqueue patch → write report |
| `fix_internal_contour` | Запустить production autonomy loop |
| `status` | Вернуть текущий статус сессии (не запускает runner) |

**Запрещено через /gpt-safe-run:**
- произвольный код
- произвольный patch
- произвольные workflow names
- произвольный JSON body
- произвольный preset вне allowlist

### Security controls

| Контроль | Реализация |
|---|---|
| Allowlist preset | `SAFE_RUN_PRESETS = { developer_runner_selftest, fix_internal_contour, status }` |
| trace_id validation | regex `[a-zA-Z0-9_]{1,60}` |
| Emergency stop | читает `governance/state/emergency_stop.json` перед dispatch |
| Active session check | если status=queued/running → 429 rate limited |
| In-memory rate limit | не чаще 1 раза в 60 секунд (сбрасывается при cold start) |
| Dispatch init only | НЕ диспатчит step одновременно |

### Init → first step handoff

```
GET /gpt-safe-run?preset=developer_runner_selftest&trace_id=bem409_selftest
  → Deno: dispatch repository_dispatch gpt-dev-runner mode=init
  → gpt-dev-runner.yml: init_session → commit gpt_dev_session.json
  → gpt-dev-runner.yml: ТОЛЬКО после commit → dispatch mode=step (first step)
  → gpt-dev-runner.yml: execute_one_step → BEM report → auto-continue
  → ... → completed / blocked
```

**ЗАПРЕЩЕНО: Deno никогда не диспатчит init и step одновременно.**

### Status endpoint

```
GET /gpt-safe-status?trace_id=<trace>
```

Без token. Возвращает:
- `session` — текущий `gpt_dev_session.json`
- `lock` — `gpt_dev_lock.json`
- `last_event` — последняя запись из `gpt_dev_runner.jsonl`
- `proof_exists` — существует ли `gpt_dev_runner_selftest_<trace>.json`
- `blocker` — текущий blocker если есть

### Пример полного цикла для ChatGPT

```
1. Open URL:
   https://fine-chicken-23.bereznyi-aleksandr.deno.net/gpt-safe-run?preset=developer_runner_selftest&trace_id=bem409_selftest

2. Response: {"ok": true, "dispatch_status": 204, ...}

3. Monitor:
   https://fine-chicken-23.bereznyi-aleksandr.deno.net/gpt-safe-status?trace_id=bem409_selftest

4. PASS when status_summary.status = "completed"
```

### Negative tests

| Тест | URL | Ожидаемый ответ |
|---|---|---|
| Invalid preset | `/gpt-safe-run?preset=bad_preset` | 400 `{ ok: false, error: "invalid_preset" }` |
| Active session | `/gpt-safe-run?preset=X` (когда session running) | 429 `{ ok: false, error: "session_active" }` |
| Emergency stop | `/gpt-safe-run?preset=X` (когда emergency_stop enabled) | 503 `{ ok: false, error: "emergency_stop" }` |
| Rate limited | Два запроса подряд < 60s | 429 `{ ok: false, error: "rate_limited" }` |
| Already completed | Same trace_id, status=completed | 200 `{ ok: true, already: "completed" }` |

---

## 3. РЕЗЕРВНЫЕ ВХОДЫ

### Issue comment — safe format (ChatGPT tool)
```
GPT_DEV_RUN preset=developer_runner_selftest trace_id=bem406_selftest
```
*(Может не материализоваться через ChatGPT GitHub comment tool — использовать Deno Safe Entrypoint)*

### Issue comment — legacy (оператор / Claude PAT MCP)
```
@gpt-dev run preset=developer_runner_selftest trace_id=bem402_selftest
```

### Deno fallback POST (token required)
```
POST /gpt-dev-session
x-gpt-secret: <GPT_WEBHOOK_SECRET>
{"trace_id": "dev_001", "preset": "developer_runner_selftest"}
```

---

## 4. ANTI-HANG CONTRACT

| Правило | Статус |
|---|---|
| Один шаг = один atomic step | ОБЯЗАТЕЛЬНО |
| После каждого шага — BEM report в issue #31 | ОБЯЗАТЕЛЬНО |
| При ошибке → blocker в state + BEM report | ОБЯЗАТЕЛЬНО |
| init и step не запускаются одновременно | ОБЯЗАТЕЛЬНО |
| step не запускается до commit init state | ОБЯЗАТЕЛЬНО |
| Long-running внутри одного GPT turn | ЗАПРЕЩЕНО |
| Silent hang без blocker | ЗАПРЕЩЕНО |
| Secrets в файлы репозитория | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Произвольный код/patch через /gpt-safe-run | АБСОЛЮТНЫЙ ЗАПРЕТ |

---

## 5. GPT DEVELOPER RUNNER

### State файл сессии

```
governance/state/gpt_dev_session.json
  session_id:    gds_<hex12>
  trace_id:      <от инициатора>
  status:        idle / queued / running / completed / blocked
  cursor:        N
  queue:         [{type, ...}, ...]
  current_step:  <type>
  attempts:      N (всего шагов)
  step_attempts: N (попыток текущего шага)
  last_report:   <строка>
  blocker:       null | {reason, stage, error_excerpt, attempt}
  updated_at:    ISO timestamp
```

### State lock

```
governance/state/gpt_dev_lock.json
  locked:     true/false
  session_id: gds_<hex>
  trace_id:   <trace>
  locked_at:  ISO timestamp
  expires_at: ISO timestamp (+10 минут)
  owner:      gpt_dev_runner
```

### Retry policy

| Параметр | Значение |
|---|---|
| max_attempts_per_step | 3 |
| Transient: retry | 5xx, timeout, connection, push conflict |
| Non-transient: block | invalid preset, missing permissions, emergency_stop, unknown step |

### Presets

| Preset | Шаги |
|---|---|
| `developer_runner_selftest` | read system_state → read routing → verify reference → enqueue patch → write report |
| `fix_internal_contour` | read role_cycle → read roadmap → read provider → verify emergency_stop → dispatch autonomy-engine → write report |

---

## 6. SELF-TEST ACCEPTANCE (BEM-409)

### Команда (PRIMARY — ChatGPT открывает URL):

```
GET /gpt-safe-run?preset=developer_runner_selftest&trace_id=bem409_selftest
```

### Мониторинг:

```
GET /gpt-safe-status?trace_id=bem409_selftest
```

### PASS если:

- Response: `{"ok": true, "dispatch_status": 204}`
- `governance/state/gpt_dev_session.json`:
  - `status = completed`
  - `trace_id = bem409_selftest`
  - `blocker = null`
  - cursor == queue.length
- Создан: `governance/state/gpt_dev_runner_selftest_bem409_selftest.json`
- Обновлён: `governance/events/gpt_dev_runner.jsonl`
- Issue #31 содержит BEM-GPT-DEV-RUNNER reports после каждого шага
- `/gpt-safe-status?trace_id=bem409_selftest` возвращает `proof_exists: true`

---

## 7. STATE LAYER

| Файл | Назначение | Кто пишет |
|---|---|---|
| `governance/state/gpt_dev_session.json` | Сессия runner | gpt_dev_runner.py |
| `governance/state/gpt_dev_lock.json` | State lock | gpt_dev_runner.py |
| `governance/state/gpt_safe_run_rate_limit.json` | Rate limit metadata (BEM-409) | справочный файл |
| `governance/state/emergency_stop.json` | Аварийная остановка | вручную |
| `governance/state/routing.json` | Активный провайдер | curator_router.py |
| `governance/state/roadmap_state.json` | Дорожная карта | Deno / autonomous_task_engine |
| `governance/events/gpt_dev_runner.jsonl` | BEM reports runner | gpt_dev_runner.py |
| `governance/exchange.jsonl` | Append-only журнал | все компоненты |

---

## 8. WORKFLOWS

| Workflow | Триггер | Назначение |
|---|---|---|
| `curator-hosted-gpt.yml` | issue_comment `@curator` | Внутренний контур |
| `gpt-dev-entrypoint.yml` | issue_comment `@gpt-dev run` OR `GPT_DEV_RUN` | Issue comment gate |
| `gpt-dev-runner.yml` | repository_dispatch `gpt-dev-runner` | Atomic step runner |
| `role-orchestrator.yml` | workflow_dispatch | FSM цикл ролей |
| `autonomous-task-engine.yml` | repository_dispatch / schedule | Production loop |
| `isa-patch-runner.yml` | ISA_PATCH_RUNNER | Патч-задачи |

---

## 9. DENO WEBHOOK v4.4

**URL:** `https://fine-chicken-23.bereznyi-aleksandr.deno.net`

| Endpoint | Метод | Token | Назначение |
|---|---|---|---|
| `/gpt-safe-run` | GET | ❌ | **PRIMARY GPT ENTRYPOINT** — allowlist-only |
| `/gpt-safe-status` | GET | ❌ | Read-only статус сессии |
| `/gpt-dev-session` | GET | ✅ | Статус сессии (legacy) |
| `/gpt-dev-session` | POST | ✅ | Deno fallback init (fixed race) |
| `/autonomy-trigger` | GET | ✅ | Trigger engine |
| `/autonomy-backlog-trigger` | GET | ✅ | Backlog + trigger |
| `/autonomy-backlog` | POST | ✅ | Backlog + trigger |
| `/autonomy` | POST | ✅ | Trigger engine |
| `/` | GET | ❌ | Health check |
| `/` | POST | — | Telegram webhook |

---

## 10. ПОЛИТИКИ БЕЗОПАСНОСТИ

| Правило | Статус |
|---|---|
| Произвольный код/patch через /gpt-safe-run | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Хардкод секретов | АБСОЛЮТНЫЙ ЗАПРЕТ |
| Long-running разработка внутри одного GPT turn | ЗАПРЕЩЕНО |
| Silent hang без blocker | ЗАПРЕЩЕНО |
| init и step одновременно | ЗАПРЕЩЕНО |
| Emergency stop enabled=true | Блокирует всё |

---

## 11. QUICK REFERENCE

### ChatGPT → PRIMARY (открыть URL):
```
https://fine-chicken-23.bereznyi-aleksandr.deno.net/gpt-safe-run?preset=developer_runner_selftest&trace_id=bem409_selftest
```

### Мониторинг:
```
https://fine-chicken-23.bereznyi-aleksandr.deno.net/gpt-safe-status?trace_id=bem409_selftest
```

### ChatGPT → backup (comment в issue #31):
```
GPT_DEV_RUN preset=developer_runner_selftest trace_id=bem409_selftest
```

### Аварийная остановка:
```
governance/state/emergency_stop.json: {"enabled": true, "reason": "..."}
```

---

*Версия: v2.6 | 2026-05-14 | внешний аудитор*
*BEM-409: Deno Safe Entrypoint PRIMARY — GET /gpt-safe-run без token, allowlist-only, race condition fix*
