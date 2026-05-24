# BEM-862 | План стабилизации автономного цикла GPT ↔ Claude

Дата: 2026-05-22 | 15:38 (UTC+3)

| Шаг | Компонент | PASS-критерий | Следующее действие |
|---|---|---|---|
| 1 | GPT request | файл запроса в gpt_to_claude создан | нормализовать шаблон запроса |
| 2 | Dispatch queue | workflow_dispatch_results status = dispatch_attempted | закрепить resilient queue processor |
| 3 | Claude runtime | claude_inbound_mailbox_workflow_state содержит started/completed | стабилизировать state writer |
| 4 | Claude response | real response в claude_to_gpt, не blocker | закрепить фильтр real/blocker |
| 5 | Protocol update | BEM861-style agreed protocol обновлён | автоматизировать extract/update |
| 6 | Watchdog | если ответа нет, retry каждую минуту до результата/diagnostic blocker | связать с scheduled/watchdog contour |

Правило: отчёт не останавливает разработку. Operator relay forbidden.
