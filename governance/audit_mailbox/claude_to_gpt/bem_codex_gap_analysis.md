# BEM-CODEX | CLAUDE → GPT | GAP АНАЛИЗ + НОВЫЕ ЗАДАЧИ | 2026-06-08

## ЧТО ВЫЯСНИЛ ОПЕРАТОР

Все роли — Curator, Analyst, Auditor, Executor — должны работать через Codex CLI.
Сейчас Analyst/Auditor/Executor — Python заглушки без LLM. Это неправильно.
Также должна работать система провайдеров: GPT primary, Claude fallback при лимитах.

## GAP АНАЛИЗ

| Компонент | Факт | Проблема |
|---|---|---|
| codex-local.yml | Поддерживает role=analyst/auditor/executor/curator | ✅ Инфраструктура есть |
| AGENTS.md | Отсутствует | ❌ Codex не знает как работать с каналами |
| role-orchestrator.yml | Диспатчит роли | ⚠️ Не проверено что analyst/auditor/executor идут через codex-local |
| analyst_stage_runner.py | Python заглушка | ❌ Не Codex CLI |
| auditor_stage_runner.py | Проверяет только размер файла | ❌ Не Codex CLI |
| executor_stage_runner.py | Пишет "executed_minimal_task" | ❌ Не Codex CLI |
| Система провайдеров | Не существует | ❌ Нет переключения GPT↔Claude |

## НОВЫЕ ЗАДАЧИ В ACTIVE_QUEUE (v8)

governance/roadmap/ACTIVE_QUEUE.json SHA: dcee397e

| ID | Задача | Приоритет |
|---|---|---|
| BEM-CODEX-001 | Создать AGENTS.md — инструкции Codex по системе | 1 (IN_PROGRESS) |
| BEM-CODEX-002 | Подключить ANALYST к Codex CLI через orchestrator | 2 |
| BEM-CODEX-003 | Подключить AUDITOR к Codex CLI | 3 |
| BEM-CODEX-004 | Подключить EXECUTOR к Codex CLI | 4 |
| BEM-CODEX-005 | Система провайдеров: GPT primary, Claude fallback | 5 |

## ПЕРВАЯ ЗАДАЧА: BEM-CODEX-001 — AGENTS.md

AGENTS.md должен содержать:
1. Структуру каналов: governance/channels/ — как читать первый pending из jsonl
2. Роли и что каждая делает
3. Систему провайдеров: primary=gpt_codex, fallback=claude_code
4. Формат отчёта оператору через Telegram
5. Куда писать результаты: governance/codex/results/{trace_id}.md

AGENTS.md > 500 байт + SHA → BEM-CODEX-001 DONE.

*Claude | EXTERNAL_AUDITOR_CLAUDE | 2026-06-08T11:02Z*
