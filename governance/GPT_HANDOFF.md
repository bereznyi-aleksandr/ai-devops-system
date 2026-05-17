# GPT HANDOFF — ai-devops-system

**Версия:** 2.0 | **Дата:** 2026-05-17
**Репозиторий:** bereznyi-aleksandr/ai-devops-system

---

## КАК ЧИТАТЬ ЭТОТ ДОКУМЕНТ

Ты — GPT-агент, который продолжает разработку вместо Claude когда у него заканчиваются лимиты.
У тебя есть GitHub MCP (чтение) и Deno Actions (запись через createCodexTask).
Читай этот файл первым в каждом чате.

---

## АРХИТЕКТУРА (v2.0 — BEM-523)

```
GPT Custom → createCodexTask (Deno Action)
  → Deno /codex-task
    → GitHub Actions codex-runner.yml
      → ubuntu-latest (бесплатно, без платного API)
        → Python executor читает objective
        → создаёт/обновляет файлы
        → git commit + push
  → getCodexStatus → completed + SHA
```

### Почему Python, не Codex CLI

Codex CLI требует `OPENAI_API_KEY` с оплатой в OpenAI Platform — это отдельно от подписки ChatGPT. Противоречит требованию "без доп. оплат". Python executor на ubuntu-latest полностью бесплатен.

### Что умеет Python executor

| Паттерн в objective | Действие |
|---|---|
| `Create file <path> with content <text>` | Создать файл с текстом |
| `Update file <path> set <field>=<value>` | Обновить поле в JSON |
| Всегда | Создать proof file + коммит |

### Для сложных задач

Claude (я) выполняю сложную разработку напрямую через GitHub MCP — читаю файлы, пишу коммиты. GPT через Deno канал делает механические операции.

---

## ТЕКУЩИЙ СТАТУС СИСТЕМЫ (2026-05-17)

### Что работает

| Компонент | Статус | Примечание |
|---|---|---|
| Deno webhook | ✅ v4.9 LIVE | /codex-task + /codex-status активны |
| codex-runner.yml | ✅ ubuntu-latest | Python executor, без платного API |
| GitHub MCP (GPT) | ✅ read-only авт. | write через Deno канал |
| Google Cloud VM | ✅ github-runner | runner online, не используется сейчас |
| Role Orchestrator | ✅ workflow_dispatch | |
| Provider Adapter | ✅ | |

### Blockers

| Что | Статус |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Не настроен — claude.yml не выполняет реальный Claude |
| Codex CLI / OPENAI_API_KEY | Не используется — платный API, отказались |

### P0: issue #31 ЗАБЛОКИРОВАН

Лимит 2500 комментариев. Все отчёты только в файлы.

---

## ПРАВИЛА

```
✅ Читать этот файл первым
✅ Для чтения — MCP fetch_file
✅ Для записи — createCodexTask (Deno)
✅ Отчёт по канону BEM

❌ Писать в issue #31
❌ schedule triggers
❌ MCP write-actions (confirm-gate)
❌ Платные API сверх подписки
❌ Просить оператора нажимать кнопки
```

---

## КАК ПИСАТЬ В РЕПО (единственный автономный путь)

```
1. createCodexTask(
     trace_id  = "уникальный_id",
     task_type = "code_patch",
     title     = "название",
     objective = "Create file <path> with content <text>. No issue comments."
   )
2. Ждать 1-3 мин
3. getCodexStatus(trace_id="тот же id")
4. status=completed → fetch_file result
```

Полная документация: `governance/GPT_WRITE_CHANNEL.md`

---

## ДОРОЖНАЯ КАРТА (12 этапов)

| Этап | Название | Статус |
|---|---|---|
| P0 | Governance Bootstrap | ✅ |
| P1 | Internal Contour + Roles | ✅ |
| P2 | Provider Failover | ✅ |
| P3 | File-based Transport | ✅ |
| P4 | Email Storm Fix | ✅ |
| P5 | Provider Adapter | ✅ |
| P6 | Codex Contour | ✅ |
| P7 | GPT Autonomy via Custom GPT | ✅ (Python executor) |
| P8 | Full Role Cycle E2E | 🔄 Следующий |
| P9 | Handoff Protocol Claude↔GPT | ⬜ |
| P10 | Production Stability | ⬜ |
| P11 | Monitoring | ⬜ |

---

## СТРУКТУРА РЕПОЗИТОРИЯ

```
governance/
├── GPT_HANDOFF.md        ← ЧИТАТЬ ПЕРВЫМ
├── GPT_WRITE_CHANNEL.md  ← как писать через Deno
├── tasks/pending/        ← входящие задачи
├── tasks/done/           ← выполненные
├── state/
├── transport/
├── codex/tasks/          ← задачи Deno канала
├── codex/results/        ← результаты
└── reports/

.github/workflows/
├── codex-runner.yml      ← ubuntu-latest, Python executor
├── role-orchestrator.yml
├── provider-adapter.yml
└── claude.yml
```

---

## ПРИ ИСЧЕРПАНИИ ЛИМИТОВ

```
createCodexTask → governance/tasks/pending/handoff_<YYYYMMDD_HHMM>.md
Сообщить: "Лимит. Handoff: <путь>"
```

---

*v2.0 | 2026-05-17 | Claude Sonnet 4.6 | BEM-523*
