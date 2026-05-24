# BEM-853 | Согласованный протокол развития мультиагентной системы | 2026-05-24 | 13:16 (UTC+3)

Версия: v1.0
Статус: согласованный draft на основе обнаруженного real Claude response и smoke-triad.

| Раздел | Согласованное решение | Обоснование | Контроль proof |
|---|---|---|---|
| Цель системы | Внешний GPT-аудитор, внутренний Claude-аудитор и Codex Runner работают через файловый mailbox и state/reports artifacts. | Оператор не должен быть relay между агентами. | mailbox files + governance/state + governance/reports |
| Канал записи GPT | GPT пишет только через Deno/Codex task, без issue comments. | Контракт запрещает ручное участие оператора и issue #31. | governance/codex/tasks + codex results |
| Канал Claude | Claude должен отвечать в governance/audit_mailbox/claude_to_gpt. | Ответ в Telegram/оператору не считается системным proof. | real Claude response file, не blocker |
| Smoke PASS | PASS разрешён только при трёх proof: dispatch result, runtime state, real Claude response. | Исключает ложный PASS и fallback вместо ответа Claude. | workflow_dispatch_results + claude runtime state + claude_to_gpt response |
| Ошибки queue | Один битый JSON не должен валить весь runner. | Инцидент BEM-827 показал, что malformed queue item блокировал dispatch. | invalid queue archive + status json |
| Непрерывность | Отчёт не останавливает roadmap; перед checkpoint должен быть active next task. | Контракт требует продолжения до результата. | GPT_NEXT_ACTION + pending task |
| Operator role | Оператор не relay и не подтверждает routine-actions. | UI confirmation и ручная пересылка нарушают автономность. | no operator action in state |
| Следующий этап | Укрепить response writer и сделать doc/md экспорт протокола по требованию оператора. | Протокол должен быть пригоден для чтения человеком и аудита. | BEM-854+ |

## Evidence source

Draft source: `governance/protocols/BEM852_AGREED_PROTOCOL_DRAFT.md`

```json
# BEM-852 | Agreed Protocol Draft | 2026-05-24 | 13:14 (UTC+3)

Source: real Claude response detected by smoke triad.

## Response evidence
[
  {
    "path": "governance/audit_mailbox/claude_to_gpt/bem844_claude_response.md",
    "preview": "# CLAUDE RESPONSE | BEM-844\n\nDate: 2026-05-24 | 11:59 (UTC+3)\nDecision: BLOCKED\nReason: The real Claude dispatcher did not produce the required response file after dispatch, ensure-step, and commit-path repairs. This is a fail-closed result, not approval.\n"
  }
]

## Status
Draft created from detected real response. Requires final formatting if operator requested table/docx.

```
