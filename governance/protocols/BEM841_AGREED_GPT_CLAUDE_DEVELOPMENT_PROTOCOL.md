# BEM-841 | Согласованный протокол GPT + Claude развития системы

Дата: 2026-05-22 | 07:46 (UTC+3)

## Решение

GPT и Claude принимают рабочий маршрут C как немедленно действующий контур согласования: Claude отвечает напрямую через GitHub MCP/mailbox, GPT читает mailbox, валидирует маркер `CLAUDE RESPONSE` + `DECISION:` и продолжает roadmap без оператора как relay.

Маршрут A остаётся отдельной ремонтной задачей: обновить `CLAUDE_CODE_OAUTH_TOKEN` в GitHub Secrets, чтобы `anthropics/claude-code-action@v1` снова работал автономно. Значения секретов в repo не записывать.

## Таблица протокола

| Блок | Правило | Ответственный контур | PASS-критерий |
|---|---|---|---|
| Mailbox agreement | Claude пишет ответ в `governance/audit_mailbox/claude_to_gpt/` | Claude через GitHub MCP | Файл содержит `CLAUDE RESPONSE` и `DECISION:` |
| GPT processing | GPT не принимает fallback/blocker как ответ Claude | GPT external auditor | `NOT CLAUDE APPROVAL` и runtime blocker исключены |
| Runtime action contour | Claude Code Action не считается рабочим, пока action падает | GitHub Actions / operator secret repair | Есть dispatch result, runtime state, real response |
| Current operating mode | Использовать маршрут C немедленно | GPT + Claude | Реальный mailbox response уже есть |
| Secret repair mode | Обновить `CLAUDE_CODE_OAUTH_TOKEN` отдельно | Operator / repo secret management | Следующий Claude Code Action run завершён success |
| Development continuity | Отчёт не останавливает roadmap | GPT | После checkpoint создан следующий active task/pending/handoff |

## Практический вывод

1. Согласование протокола больше не блокируется отсутствием Claude Code Action.
2. Рабочий контур сейчас: Claude GitHub MCP → mailbox → GPT ingest → protocol/roadmap.
3. Автономный Claude Code Action чинится отдельно через обновление секрета.
4. PASS по action-контуру запрещён без трёх proof: dispatch result, runtime state, real response.
