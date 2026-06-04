# AGENT CONTEXT | SYSTEM CONFIGURATION
# Версия: v4.0 | 2026-06-04 | Claude External Audit
# РОЛЬ ЭТОГО ФАЙЛА: только конфигурация системы. НЕ является источником задач.
# Источник задач: governance/roadmap/ACTIVE_QUEUE.json
# Лог выполнения: governance/logs/execution_log.jsonl

---

## 1. Компоненты системы

| Компонент | Статус | Примечание |
|---|---|---|
| Deno webhook | ✅ LIVE | /codex-task + /codex-status |
| codex-runner.yml | ✅ Работает | ubuntu-latest, Python v3 |
| GitHub MCP (Claude) | ✅ Работает | прямой write без посредника |
| Python executor v3 | ✅ Работает | паттерны + Run script |
| curator-hourly-report | ✅ active | cron 0 * * * * |
| governance-validation-ci.yml | ✅ VALID | workflow_dispatch only |

---

## 2. Locks и ограничения

| Ограничение | Правило |
|---|---|
| .github/workflows/*.yml | LOCKED — только Claude MCP |
| issue #31 | Запрещено писать |
| schedule triggers | Только curator-hourly-report.yml |
| Платные API | Codex CLI / OPENAI_API_KEY — запрещено |

---

## 3. Протокол GPT ↔ Claude (BEM-858)

| Правило | Статус |
|---|---|
| Peer-аудиторы, равноправны | ✅ |
| Старший субъект — только оператор | ✅ |
| Техническое разногласие → решают сами | ✅ |
| Архитектурное разногласие → оператору | ✅ |
| Claude MCP может вносить прямые fix | ✅ |

---

## 4. Архитектура write-каналов

```
GPT → createCodexTask (Deno) → GitHub Actions → Python executor → commit
Claude → GitHub MCP → прямой commit
```

---

*Этот файл меняется только при изменении архитектуры. Не является логом BEM.*
