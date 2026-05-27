# AGENT CONTEXT | CANONICAL START STATE

**Обновлён:** 2026-05-25 | 16:00 (UTC+3)
**Репозиторий:** bereznyi-aleksandr/ai-devops-system

---

## ОБЯЗАТЕЛЬНО — читать первым в каждом новом чате

Этот файл — единственный источник истины о состоянии системы.
`roadmap_state.json`, `GPT_HANDOFF.md` и другие state-файлы могут быть устаревшими.

---

## 1. Текущий статус системы

| Компонент | Статус | Примечание |
|---|---|---|
| Deno webhook | ✅ v4.9 LIVE | /codex-task + /codex-status |
| codex-runner.yml | ✅ Работает | ubuntu-latest, Python v3, BEM-849 git push fix |
| GitHub MCP (Claude) | ✅ Работает | прямой write без посредника |
| Python executor v3 | ✅ Работает | 12 паттернов + Run script |
| curator-hourly-report | ✅ schedule active | cron 0 * * * * |
| Telegram monitoring | ✅ Работает | hourly report оператору |
| claude-code-action@v1 | ⚠️ NOT PROVEN | нужен отдельный smoke-test |
| Push triggers (workflows) | ✅ Отключены | BEM-848: только workflow_dispatch |

---

## 2. Текущий этап разработки

**Активный этап:** P10 — Production Stability / Autonomous Loop Stabilization

**Что сделано (последнее):**
- BEM-848: убраны все push triggers из workflows (освободили Actions queue)
- BEM-849: исправлен git push в codex-runner (был double-commit без push)
- BEM-850: исправлен claude-internal-auditor-dispatcher (невалидный with: параметр)
- BEM-858: протокол GPT↔Claude согласован (AGREED)

**Что в работе:**
- Stabilization autonomous loop (commit_sha=null в Deno responses — косметический баг)
- claude-code-action@v1 smoke-test (нужен один запуск из UI)

---

## 3. Согласованный протокол GPT↔Claude (BEM-858)

| Правило | Статус |
|---|---|
| GPT и Claude — peer-аудиторы | ✅ APPROVED |
| Старший субъект — только оператор | ✅ APPROVED |
| Audit mailbox — основной канал | ✅ APPROVED |
| Telegram — только gate оператора | ✅ APPROVED |
| Handoff — только через Curator | ✅ APPROVED |
| Техническое разногласие → решают сами | ✅ APPROVED |
| Архитектурное разногласие → оператору | ✅ APPROVED |
| Разногласие с решением оператора → запрещено | ✅ APPROVED |

Файл протокола: `governance/protocols/BEM858_AGREED_MULTIAGENT_OPERATING_PROTOCOL.md`

---

## 4. Система идентификации задач

В системе используются три типа ID — они НЕ совпадают, это нормально:

| Тип ID | Пример | Где используется |
|---|---|---|
| BEM-NNN | BEM-849, BEM-858 | Номер задачи в разработке |
| trace_id | bem849_push_fix_test | Задача в codex-runner через Deno |
| task_id | P9_HANDOFF_PROTOCOL | Запись в roadmap_state.json |

**Статусы задач:**
- `completed` — выполнено с доказательством (SHA или файл)
- `pending` — в очереди или в работе
- `blocked` — есть blocker, указана причина

**Где смотреть задачи:**
- `governance/tasks/pending/` — входящие задачи
- `governance/tasks/done/` — выполненные
- `governance/codex/results/` — результаты codex-runner

---

## 5. Правила которые нельзя нарушать

```
❌ Писать в issue #31 (лимит 2500)
❌ Secrets, PAT, токены в файлах
❌ schedule triggers (кроме curator-hourly-report.yml)
❌ PASS без доказательства (SHA или файл)
❌ Платные API (Codex CLI, OPENAI_API_KEY)
❌ Имитировать выполнение
❌ Оператор как relay между агентами
❌ Останавливать roadmap ради отчёта
```

---

## 6. Архитектура (v2.0)

```
GPT Custom → createCodexTask (Deno)
  → Deno /codex-task
    → GitHub Actions codex-runner.yml (ubuntu-latest)
      → Python executor v3
        → файлы + коммит
  → getCodexStatus → completed + SHA

Claude → прямой коммит через GitHub MCP
  → governance/audit_mailbox/claude_to_gpt/
```

---

## 7. Разделение труда

| Область | Claude | GPT |
|---|---|---|
| Архитектурные решения | Совместно | Совместно |
| Аудит | Аудирует GPT | Аудирует Claude |
| Реализация | По запросу | Вся рутинная разработка |
| State / roadmap | Аудит | Ведение файлов |

---

## 8. Следующие приоритеты

1. **P10 Stabilization** — закрыть `commit_sha=null` в Deno responses
2. **claude-code-action smoke-test** — запустить из Actions UI
3. **AGENT_CONTEXT автообновление** — curator-hourly должен обновлять этот файл

---

*Файл обновляется автоматически curator-hourly-report.yml*
*Источник истины: этот файл главнее roadmap_state.json и GPT_HANDOFF.md*
*BEM-843 | 2026-05-25*
## BEM-859 routing note
- BEM-859 protocol alignment is routed through Curator only
## BEM-863 Curator-Claude mechanism
- Status: implemented_dispatch_route
## BEM-864 Curator-Claude selftest
- Status: route_selftest_completed_waiting_for_claude_response
## BEM-867 completed | 2026-05-26
Internal auditor battle mailbox confirmed
## BEM-867 completed
Status: completed
Result: Internal auditor battle mailbox confirmed with APPROVED_WITH_NOTES
## BEM-868 | Dispatch channel recovered
Status: completed
Next: continue roadmap from AGENT_CONTEXT
Next: continue roadmap from AGENT_CONTEXT
Next: continue roadmap from AGENT_CONTEXT.md
## BEM-867 completed | 2026-05-26
Internal auditor battle mailbox confirmed
## BEM-871 | Curator-mediated internal audit protocol | 2026-05-27
Status: active
Protocol: governance/protocols/CURATOR_MEDIATED_INTERNAL_AUDIT_PROTOCOL
## BEM-871 completed | 2026-05-27
Curator-mediated internal audit protocol confirmed
## BEM-872 completed | 2026-05-27
Roadmap protocol agreed through curator-mediated route
## BEM-873 completed | 2026-05-27
Updated BEM-872 roadmap protocol to version v1
## BEM-874 completed | 2026-05-27
Updated BEM-872 roadmap protocol to version v1
