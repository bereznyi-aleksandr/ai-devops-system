# GPT HANDOFF — ai-devops-system

**Версия:** 1.0 | **Дата:** 2026-05-15
**Репозиторий:** bereznyi-aleksandr/ai-devops-system

---

## КАК ЧИТАТЬ ЭТОТ ДОКУМЕНТ

Ты — GPT-агент, который продолжает разработку вместо Claude когда у него заканчиваются лимиты.
У тебя есть GitHub MCP — ты можешь читать и писать файлы в этом репозитории напрямую.
Этот документ — твоя "память". Читай его первым делом в каждом новом чате.

---

## ТЕКУЩИЙ СТАТУС СИСТЕМЫ (2026-05-15)

### Что построено и работает

| Компонент | Статус | Файл |
|---|---|---|
| Deno webhook | ✅ LIVE v4.9 | `governance/deno_webhook.js` |
| Role Orchestrator | ✅ workflow_dispatch only | `.github/workflows/role-orchestrator.yml` |
| Provider Adapter | ✅ Диспатчит claude.yml | `.github/workflows/provider-adapter.yml` |
| Claude Code Action | ✅ Требует CLAUDE_CODE_OAUTH_TOKEN | `.github/workflows/claude.yml` |
| File-based transport | ✅ | `governance/transport/` |
| Codex runner | ✅ [self-hosted, codex-local] | `.github/workflows/codex-runner.yml` |
| Codex local ISA | ✅ Без issue comments | `.github/workflows/codex-local.yml` |

### Что НЕ настроено (blocker)

| Что | Почему нужно | Как добавить |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Без него `claude.yml` не запускает реальный Claude | Settings → Secrets → Actions |
| Self-hosted runner | `codex-runner.yml` требует runner с `[self-hosted, codex-local]` | Settings → Actions → Runners |

### P0: issue #31 ЗАБЛОКИРОВАН

Issue #31 достиг лимита 2500 комментариев. **ЗАПРЕЩЕНО** писать туда любые комментарии.
Все отчёты пишутся только в:
- Job Summary (GitHub Actions)
- `governance/reports/<trace_id>.md`
- `governance/transport/results.jsonl`
- `governance/codex/results/<trace_id>.json`

---

## ПРАВИЛА РАБОТЫ (строго обязательны)

```
✅ МОЖНО:
- Читать любые файлы репозитория через GitHub MCP
- Писать файлы в репозиторий через GitHub MCP
- Делать коммиты через GitHub MCP
- Запускать workflow_dispatch через GitHub MCP
- Писать в governance/transport/ governance/reports/ governance/codex/

❌ НЕЛЬЗЯ НИКОГДА:
- Писать комментарии в issue #31
- Использовать github.rest.issues.createComment для issue #31
- Включать schedule triggers в workflow файлах
- Хранить секреты в файлах репозитория
- Писать токены или PAT в любые файлы
```

---

## КАК ТЫ ПОЛУЧАЕШЬ ЗАДАЧИ

### Способ 1 — файл задачи (основной)

Оператор создаёт файл задачи:
```
governance/tasks/pending/<trace_id>.md
```

Ты читаешь его, выполняешь, пишешь результат:
```
governance/tasks/done/<trace_id>.md
```

### Способ 2 — через Deno (если оператор открывает URL)

```
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/codex-task?trace_id=X&task_type=selftest&title=...&objective=...
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/codex-status?trace_id=X
```

### Способ 3 — через Provider Adapter (для role-based задач)

```
GitHub Actions → Provider Adapter → Run workflow:
  provider=claude (или gpt если настроен)
  role=analyst|auditor|executor
  trace_id=<trace>
  task=<описание>
```

---

## СТРУКТУРА РЕПОЗИТОРИЯ (ключевые пути)

```
governance/
├── state/                    # JSON state файлы системы
│   ├── role_cycle_state.json # Текущий FSM цикл ролей
│   ├── roadmap_state.json    # Дорожная карта задач
│   ├── routing.json          # Активные провайдеры по ролям
│   ├── provider_status.json  # API статус провайдеров
│   ├── emergency_stop.json   # Аварийная остановка
│   ├── gpt_dev_session.json  # GPT developer runner сессия
│   └── gpt_dev_lock.json     # Lock для GPT runner
├── transport/                # File-based шина задач
│   ├── requests.jsonl        # Входящие задачи
│   └── results.jsonl         # Результаты выполнения
├── reports/                  # Отчёты по trace_id
├── codex/                    # Внешний Codex контур
│   ├── tasks/               # Задачи для Codex
│   ├── results/             # Результаты Codex
│   └── CODEX_LOCAL_RUNNER_SETUP.md
├── events/                   # Append-only журналы
│   ├── gpt_dev_runner.jsonl
│   └── role_orchestrator.jsonl
├── tasks/                    # Задачи от оператора
│   ├── pending/             # Ожидают выполнения
│   └── done/                # Выполнены
├── policies/
│   ├── role_sequence.json   # Порядок ролей в FSM
│   └── provider_adapters.json
├── deno_webhook.js           # КАНОН: Deno v4.9
└── GPT_HANDOFF.md            # Этот файл

.github/workflows/
├── role-orchestrator.yml     # FSM цикл ролей
├── provider-adapter.yml      # Диспатчит роли на провайдеров
├── claude.yml                # Claude Code Action
├── codex-runner.yml          # Внешний Codex контур
├── codex-local.yml           # Codex local ISA
├── gpt-dev-runner.yml        # GPT developer runner
└── gpt-dev-entrypoint.yml    # Issue comment gate (backup)
```

---

## ТЕКУЩАЯ ДОРОЖНАЯ КАРТА

### P0 — Выполнено
- BEM-221: Governance Bootstrap ✅
- Email storm остановлен ✅ (BEM-476)
- File-based transport ✅ (BEM-476)
- Provider Adapter ✅ (BEM-477)
- Codex контур ✅ (BEM-487/488/495)
- YAML fixes ✅ (BEM-488)

### P1 — В работе
- GPT автономность через GitHub MCP (текущая задача)
- Настройка `CLAUDE_CODE_OAUTH_TOKEN` для полного Claude contour
- Self-test end-to-end Provider Adapter → Claude Code Action

### P2 — Следующее
- Полный role cycle: analyst → auditor → executor через file transport
- Handoff между Claude и GPT при исчерпании лимитов

---

## КАК ТЫ ВЫПОЛНЯЕШЬ ЗАДАЧИ (алгоритм)

```
1. Прочитать этот файл (governance/GPT_HANDOFF.md)
2. Прочитать governance/state/roadmap_state.json — что pending/blocked
3. Прочитать governance/tasks/pending/ — есть ли задачи от оператора
4. Выбрать одну задачу
5. Прочитать нужные файлы через GitHub MCP
6. Выполнить задачу (писать файлы, делать коммиты)
7. Написать результат:
   - governance/tasks/done/<trace_id>.md
   - governance/transport/results.jsonl
8. Обновить governance/state/role_cycle_state.json если нужно
9. НЕ писать в issue #31
```

---

## ФОРМАТ ОТЧЁТА (обязательный)

После каждой выполненной задачи:

```markdown
BEM-<N> | GPT AGENT | YYYY-MM-DD | <процент>

Чек-лист:
✅ ...
⚠️ ...
❌ ...

| Тип | Содержание | Статус |
|---|---|---|
| Факт | ... | DONE |
| Следующее действие | ... | NEXT |

STATUS: completed|blocked|failed
NEXT: <следующий шаг>
BLOCKER: <если есть — точная причина>
COMMIT_SHA: <если был коммит>
```

---

## ПРОДОЛЖЕНИЕ ПОСЛЕ CLAUDE

Когда Claude завершает сессию из-за лимитов, он:
1. Коммитит последнее состояние
2. Пишет `governance/tasks/pending/handoff_<timestamp>.md` с описанием где остановился

Ты читаешь этот файл и продолжаешь с той же точки.

---

## КОНТАКТ С ОПЕРАТОРОМ

Оператор: Александр (bereznyi-aleksandr)
Telegram: через Deno webhook (не через issue #31)
Язык: русский

---

*Последнее обновление: 2026-05-15 | Claude Sonnet 4.6*
