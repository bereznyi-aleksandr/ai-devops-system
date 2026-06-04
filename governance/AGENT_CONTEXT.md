# AGENT CONTEXT | CANONICAL START STATE
# Версия: v3.0 | Сброшен: 2026-06-04 | Claude External Audit
# Полный исторический лог: governance/archive/AGENT_CONTEXT_history_2026-06-04.md

---

## ОБЯЗАТЕЛЬНО — читать первым при каждом старте чата

Этот файл — единственный источник истины о состоянии системы.
Лимит файла: **максимум 100 строк**. Всё старше 7 дней → архив.

---

## 1. Компоненты системы

| Компонент | Статус | Примечание |
|---|---|---|
| Deno webhook | ✅ LIVE | /codex-task + /codex-status |
| codex-runner.yml | ✅ Работает | ubuntu-latest, Python v3 |
| GitHub MCP (Claude) | ✅ Работает | прямой write без посредника |
| Python executor v3 | ✅ Работает | 12 паттернов + Run script |
| curator-hourly-report | ✅ active | cron 0 * * * * |
| governance-validation-ci.yml | ✅ VALID | workflow_dispatch only, SHA: 9fb7a743 |

---

## 2. Активные блокеры (operator gate)

| Блокер | Что нужно | От кого |
|---|---|---|
| Gate 4 | Production Telegram receipt | Оператор |
| Gate 5 | Live LLM runtime receipt | Оператор |
| Gate 6 | External Claude audit receipt | Claude |
| Release PASS | Все три receipt выше | — |

---

## 3. Workflow lock

```
❌ .github/workflows/*.yml — LOCKED для GPT executor
✅ Только Claude MCP может писать в .github/workflows/
Политика: governance/state/workflow_write_lock.json
```

---

## 4. Следующие задачи (non-workflow, автономные)

| Приоритет | Задача | Статус |
|---|---|---|
| 1 | KZ-1: восстановить runners до STUB_RUNNABLE (def main + stub) | ⏳ В работе |
| 2 | KZ-2: устранить 8 SSOT-дублей | ⏳ Частично |
| 3 | KZ-3: archivировать governance/codex/ >30 дней | ⏳ Pending |
| 4 | KZ-4: restore object_passports.json + release_proof_manifest.json | ⏳ Pending |

---

## 5. Правила которые нельзя нарушать

```
❌ Писать в issue #31
❌ Secrets, PAT, токены в файлах
❌ schedule triggers (кроме curator-hourly-report.yml)
❌ PASS без SHA коммита
❌ Платные API (Codex CLI, OPENAI_API_KEY)
❌ objective без паттернов executor (только описательный текст)
❌ .github/workflows/*.yml через GPT executor
❌ Останавливать roadmap после промежуточного отчёта
```

---

## 6. Последние действия (последние 7 дней)

| Дата | Задача | SHA |
|---|---|---|
| 2026-06-04 | P25B: continuation queue validation | f9d0867 |
| 2026-06-04 | P14: workflow blocker lifted by Claude | — |
| 2026-06-04 | workflow lock: governance/state/workflow_write_lock.json | c2cd66b |
| 2026-06-04 | governance-validation-ci.yml: valid stub | 9fb7a743 |
| 2026-06-04 | P15B: deno_webhook.js commit_sha patch | — |
| 2026-06-03 | Claude external audit: BEM-931 замечания | — |

---

*Обновляется после каждого завершённого BEM. Лимит: 100 строк.*
*Архив: governance/archive/AGENT_CONTEXT_history_2026-06-04.md*
