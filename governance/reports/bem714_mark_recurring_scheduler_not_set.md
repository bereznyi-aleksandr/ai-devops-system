# BEM-714 | Recurring Scheduler Not Set | BLOCKED

Дата: 2026-05-21 | 10:38 (UTC+3)

Причина: выполнена только одиночная проверка mailbox; периодический ChatGPT scheduler не подтвержден.

Blocker: {"code": "RECURRING_CHATGPT_SCHEDULER_NOT_SET", "message": "After BEM-712/BEM-713 only a one-time mailbox check was executed. A recurring ChatGPT Task with every-minute/minimal interval is not confirmed, therefore autonomous polling is not active."}
