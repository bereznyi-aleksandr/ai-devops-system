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
## BEM-875 completed | 2026-05-27
Protocol v1
## BEM-876 completed | 2026-05-28
Protocol v1
## BEM-877 completed | 2026-05-29
Protocol v1
## BEM-878 completed | 2026-05-29
Protocol v1
## BEM-879 completed | 2026-05-29
Protocol v1
## BEM-880 completed | 2026-05-29
Operator approved BEM-879 protocol v1
## BEM-881 completed | 2026-05-29
Operator accepted BEM-880 execution result with response: Да
## BEM-882 completed | 2026-05-29
Readiness audit completed after BEM-881 accepted BEM-880 execution result
## BEM-883 completed | 2026-05-29
Registry schema validation implemented
## BEM-884 completed | 2026-05-29
Operational rule seed implemented
## BEM-885 completed | 2026-05-29
Managed channel message envelope implemented
## BEM-886 completed | 2026-05-29
Workspace promotion checks implemented
## BEM-887 completed | 2026-05-29
Product repository registration template implemented
## BEM-888 completed | 2026-05-29
Integration selftest implemented for BEM-880 baseline
## BEM-889 completed | 2026-05-29
Final repository readiness completed after continuous execution of BEM-883 through BEM-888
## BEM-890 completed | 2026-05-30
Dispatch contour implemented after BEM-889 READY baseline
## BEM-891 completed | 2026-05-30
Worker contour inbox delivery implemented
## BEM-892 completed | 2026-05-30
Worker contour task processing implemented
## BEM-893 completed | 2026-05-30
End-to-end dispatch selftest implemented and passed
## BEM-894 completed | 2026-05-30
Final sending contour readiness completed
## BEM-895 completed | 2026-05-30
Autonomous execution loop implemented
## BEM-896 completed | 2026-05-30
Policy gate implemented for autonomous execution loop
## BEM-897 completed | 2026-05-30
Autonomous cycle report packaging implemented
## BEM-898 completed | 2026-05-30
Repository health dashboard implemented
## BEM-899 completed | 2026-05-30
Final autonomous sending contour readiness completed
## BEM-900 completed | 2026-05-30
Roadmap v1
## BEM-901 completed | 2026-05-30
Pilot readiness scaffold implemented
## BEM-902 completed | 2026-05-30
Business Model Canvas template and evaluator implemented for pilot readiness
## BEM-903 completed | 2026-05-30
Product repository onboarding kit implemented for pilot readiness
## BEM-904 completed | 2026-05-30
Pilot evaluation dashboard and SLA templates implemented
## BEM-905 completed | 2026-05-30
Operator gate reached after maximum autonomous execution of accepted roadmap v1
## BEM-906 completed | 2026-05-30
Prepared detailed external audit report for Claude about protocol v1
## BEM-913 completed | 2026-05-30
Claude external audit remediation validation completed
## BEM-914 completed | 2026-05-30
Prepared system improvement protocol after Claude external audit and BEM-907
## BEM-915 completed | 2026-05-30
Prepared updated system improvement protocol with Telegram Operator Interface layer after operator reported that Telegram bot channel is not working as a real operator interface
## BEM-916 completed | 2026-05-30
Corrected BEM-915 protocol format mistake after operator clarification
## BEM-917 completed | 2026-05-30
Updated unified BEM-916 system improvement protocol after operator remarks about Telegram mechanism
## BEM-917 completed | 2026-05-30
Updated BEM-916 unified system improvement protocol according to operator remarks about Telegram configuration, reporting periodicity and report canon
## BEM-918 completed | 2026-05-30
Prepared detailed working roadmap to turn the system from concept/scaffold into a fully working operational system
## BEM-918 completed | 2026-05-30
Prepared detailed working roadmap to turn the system from concept/scaffold into a fully working system, using existing Telegram/Deno/Codex implementation and Claude v1
## BEM-918-v2 completed | 2026-05-30
Updated the BEM-918 working roadmap after operator remarks about the seven listed mechanisms/components and Telegram entry/exit route
