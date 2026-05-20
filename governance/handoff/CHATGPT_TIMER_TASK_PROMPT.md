# ChatGPT Scheduled Task Prompt | Mailbox Monitor

Версия: v1.0-2026-05-20

Название задачи: AI DevOps mailbox monitor

Расписание: каждые 1 минуту; если ChatGPT не позволит 1 минуту, установить минимально доступный интервал.

Prompt для задачи:
```
КОНТРАКТ ПРИНЯТ. Это scheduled monitor task для ai-devops-system.
Каждый запуск:
1. Выполни Deno healthCheck.
2. Проверь active agreements и mailbox по BEM-699: governance/agreements/active/bem699_multiagent_protocol_v2_operator_remarks.json и governance/audit_mailbox/claude_to_gpt/.
3. Если найден новый ответ Claude с APPROVED / CHANGE_REQUIRED / BLOCKED — зафиксируй результат через Codex task, подготовь следующий шаг и краткий отчет оператору.
4. Если ответа нет — ничего не отправляй оператору, только при необходимости обнови state no_new_mail.
5. Не пиши issue comments. Не запускай roadmap implementation без явной команды оператора resume. Roadmap paused сохраняется.
```
