# GPT HANDOFF — ai-devops-system

**Версия:** 1.2 | **Дата:** 2026-05-15
**Репозиторий:** bereznyi-aleksandr/ai-devops-system

---

## КАК ЧИТАТЬ ЭТОТ ДОКУМЕНТ

Ты — GPT-агент, который продолжает разработку вместо Claude когда у него заканчиваются лимиты.
У тебя есть GitHub MCP — ты можешь читать и писать файлы в этом репозитории напрямую.
Этот документ — твоя "память". Читай его первым делом в каждом новом чате.

---

## ═══ КАНОН ОФОРМЛЕНИЯ КАЖДОГО ОТВЕТА ═══

> **ОБЯЗАТЕЛЬНО для каждого сообщения GPT-агента. Без исключений.**

### Шаблон — копируй и заполняй:

```
BEM-<номер> | <НАЗВАНИЕ ЗАДАЧИ> | YYYY-MM-DD

Этап: <выполнено задач в этапе>/<всего задач в этапе> (<XX%>)
Дорожная карта: <выполнено этапов>/<всего этапов> (<XX%>)

Чек-лист:
✅ <что сделано — конкретно>
✅ <что сделано — конкретно>
⚠️ <что частично / требует внимания>
❌ <что не сделано / blocker>

| Наименование | Описание | Обоснование |
|---|---|---|
| <компонент/действие> | <что именно произошло> | <почему именно так, на каком основании> |
```

---

### Расшифровка строк шаблона

**Строка 1 — Заголовок:**
```
BEM-<номер> | <НАЗВАНИЕ ЗАДАЧИ> | YYYY-MM-DD
```
- Номер BEM — порядковый номер задачи в системе
- Название — короткое, заглавными буквами
- Дата — текущая дата UTC

**Строка 2 — Этап:**
```
Этап: <X>/<Y> (<Z%>)
```
- X — сколько задач выполнено в текущем этапе
- Y — сколько задач всего в текущем этапе
- Z% — X/Y × 100, округлить до целых

**Строка 3 — Дорожная карта:**
```
Дорожная карта: <X>/<Y> (<Z%>)
```
- X — сколько этапов полностью завершено
- Y — сколько этапов всего в дорожной карте (сейчас 12)
- Z% — X/Y × 100

**Чек-лист:**
- ✅ — сделано, есть доказательство (файл, коммит, ответ API)
- ⚠️ — сделано частично или требует внимания оператора
- ❌ — не сделано, есть конкретный blocker
- Минимум 3 пункта, максимум 8
- Каждый пункт — одно действие или факт

**Таблица — три колонки строго:**

| Наименование | Описание | Обоснование |
|---|---|---|
| Что это (компонент, действие, файл) | Что именно произошло или обнаружено | Почему именно так — ссылка на файл, правило, факт |

---

### Полный пример правильного ответа:

```
BEM-500 | FIX ROLE ORCHESTRATOR | 2026-05-15

Этап: 3/5 (60%)
Дорожная карта: 1/12 (8%)

Чек-лист:
✅ Прочитал governance/GPT_HANDOFF.md — контекст восстановлен
✅ Прочитал role-orchestrator.yml — найден schedule trigger
✅ Исправил YAML — убран schedule, оставлен workflow_dispatch only
✅ Коммит сделан: abc1234def567
❌ Self-test не запущен — требует ручного workflow_dispatch от оператора

| Наименование              | Описание                                              | Обоснование                                                      |
|---------------------------|------------------------------------------------------|------------------------------------------------------------------|
| role-orchestrator.yml     | Содержал schedule: cron — генерировал email storm    | BEM-476: все schedule triggers запрещены после переполнения #31  |
| Исправление               | Убран schedule, workflow_dispatch only               | Соответствует правилу: no schedule triggers                      |
| Commit SHA                | abc1234def567                                        | Проверить: GitHub → Actions → последний коммит                   |
| issue #31                 | Комментарии не писались                              | Issue #31 заблокирован на 2500 — запрет абсолютный               |
| Следующее действие        | Оператор запускает role-orchestrator mode=start      | Self-test требует manual trigger — GPT не может запустить сам    |
```

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

### Blockers

| Что | Почему нужно | Как добавить |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Без него `claude.yml` не запускает реальный Claude | Settings → Secrets → Actions |
| Self-hosted runner | `codex-runner.yml` требует `[self-hosted, codex-local]` | Settings → Actions → Runners |

### P0: issue #31 ЗАБЛОКИРОВАН

Issue #31 достиг лимита 2500 комментариев. **ЗАПРЕЩЕНО** писать туда комментарии.
Отчёты только в:
- `governance/reports/<trace_id>.md`
- `governance/transport/results.jsonl`
- `governance/codex/results/<trace_id>.json`
- GitHub Actions Job Summary

---

## ПРАВИЛА РАБОТЫ

```
✅ МОЖНО:
- Читать файлы репозитория через GitHub MCP
- Писать файлы в репозиторий через GitHub MCP
- Делать коммиты через GitHub MCP
- Запускать workflow_dispatch через GitHub MCP

❌ НЕЛЬЗЯ НИКОГДА:
- Писать комментарии в issue #31
- Включать schedule triggers в workflow файлах
- Хранить секреты в файлах репозитория
- Писать токены или PAT в любые файлы
```

---

## КАК ТЫ ПОЛУЧАЕШЬ ЗАДАЧИ

**Способ 1 — файл задачи (основной):**
```
Читать:  governance/tasks/pending/<trace_id>.md
Писать:  governance/tasks/done/<trace_id>.md
```

**Способ 2 — через Deno:**
```
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/codex-task?trace_id=X&task_type=selftest&title=...&objective=...
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/codex-status?trace_id=X
```

**Способ 3 — через Provider Adapter:**
```
GitHub Actions → Provider Adapter → Run workflow:
  provider=claude | role=analyst|auditor|executor | trace_id=X | task=...
```

---

## СТРУКТУРА РЕПОЗИТОРИЯ

```
governance/
├── state/                    # JSON state файлы системы
│   ├── role_cycle_state.json # Текущий FSM цикл ролей
│   ├── roadmap_state.json    # Дорожная карта задач
│   ├── routing.json          # Активные провайдеры
│   ├── provider_status.json  # API статус провайдеров
│   ├── emergency_stop.json   # Аварийная остановка
│   ├── gpt_dev_session.json  # GPT developer runner сессия
│   └── gpt_dev_lock.json     # Lock для GPT runner
├── transport/                # File-based шина задач
│   ├── requests.jsonl
│   └── results.jsonl
├── reports/                  # Отчёты по trace_id
├── codex/                    # Внешний Codex контур
│   ├── tasks/
│   ├── results/
│   └── CODEX_LOCAL_RUNNER_SETUP.md
├── events/                   # Append-only журналы
├── tasks/
│   ├── pending/              # Ожидают выполнения
│   └── done/                 # Выполнены
├── deno_webhook.js           # КАНОН: Deno v4.9
└── GPT_HANDOFF.md            # Этот файл

.github/workflows/
├── role-orchestrator.yml
├── provider-adapter.yml
├── claude.yml
├── codex-runner.yml
├── codex-local.yml
├── gpt-dev-runner.yml
└── gpt-dev-entrypoint.yml
```

---

## ДОРОЖНАЯ КАРТА (12 этапов)

| Этап | Название | Статус |
|---|---|---|
| P0 | Governance Bootstrap | ✅ Завершён |
| P1 | Internal Contour + Roles | ✅ Завершён |
| P2 | Provider Failover | ✅ Завершён |
| P3 | File-based Transport | ✅ Завершён |
| P4 | Email Storm Fix | ✅ Завершён |
| P5 | Provider Adapter + Claude | ✅ Завершён |
| P6 | Codex Contour | ✅ Завершён |
| P7 | GPT Autonomy via GitHub MCP | 🔄 В работе |
| P8 | Full Role Cycle E2E | ⬜ Следующий |
| P9 | Handoff Protocol Claude↔GPT | ⬜ Не начат |
| P10 | Production Stability | ⬜ Не начат |
| P11 | Monitoring + Alerts | ⬜ Не начат |

---

## АЛГОРИТМ РАБОТЫ

```
1. Прочитать governance/GPT_HANDOFF.md
2. Прочитать governance/state/roadmap_state.json
3. Прочитать governance/tasks/pending/
4. Выбрать одну задачу
5. Выполнить через GitHub MCP
6. Написать отчёт по КАНОНУ (заголовок + этап + дорожная карта + чеклист + таблица)
7. Обновить state файлы если нужно
8. НЕ писать в issue #31
```

---

## ПРОДОЛЖЕНИЕ ПОСЛЕ CLAUDE

Claude при завершении сессии:
1. Коммитит последнее состояние
2. Пишет `governance/tasks/pending/handoff_<timestamp>.md`

Ты читаешь этот файл → продолжаешь с той же точки.

---

## КОНТАКТ С ОПЕРАТОРОМ

Оператор: Александр (bereznyi-aleksandr)
Язык: русский

---

*Последнее обновление: 2026-05-15 v1.2 | Claude Sonnet 4.6*
