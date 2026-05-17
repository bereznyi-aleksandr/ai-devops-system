# BEM-541.1 | Provider Probe Before Reserve

Дата: 2026-05-17 | 14:22 (UTC+3)

## Правило
Перед выбором GPT reserve система обязана проверить Claude primary. Silent switch to reserve запрещён.

## Источники сигнала Claude
1. Последняя запись transport для provider=`claude`.
2. Последний outcome/status из `claude.yml`, записанный в transport.
3. TTL/missing result после ожидания Claude.

## Decision matrix
| Probe signal | Decision | Обоснование |
|---|---|---|
| active/completed | select_claude_primary | Claude отвечает, reserve не нужен |
| failed/cancelled/timeout/missing_result_after_ttl | select_gpt_reserve | Claude недоступен или лимит/ошибка |
| unknown/no_signal | select_claude_primary_with_probe_required | Нельзя молча уходить в reserve без evidence |

## Audit requirement
Каждый выбор пишет `provider_probe_result` и `provider_selection_decision` в `governance/transport/results.jsonl`.
