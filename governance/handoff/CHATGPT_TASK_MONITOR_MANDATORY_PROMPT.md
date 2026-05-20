# Mandatory ChatGPT Task Monitor Prompt

Использовать после каждого Claude-mailbox request:

```text
Создай или обнови повторяющуюся задачу.

Название: AI DevOps Claude mailbox monitor.

Расписание: каждые 1 минуту. Если интервал 1 минута недоступен, установи минимально доступный повторяющийся интервал.

Инструкция:
КОНТРАКТ ПРИНЯТ. Это scheduled monitor task для ai-devops-system.

Каждый запуск:
1. Выполни Deno healthCheck.
2. Проверь active agreements: governance/agreements/active/.
3. Проверь mailbox Claude → GPT: governance/audit_mailbox/claude_to_gpt/ и governance/audit_mailbox/external_auditor_to_internal_auditor/.
4. Если найден новый ответ Claude с APPROVED / CHANGE_REQUIRED / BLOCKED — создай Codex task для фиксации результата, обнови active agreement и подготовь следующий шаг согласования.
5. Если ответа нет — не отправляй оператору длинный отчёт; при необходимости зафиксируй no_new_mail в state.
6. Roadmap implementation не запускать без явной команды оператора resume.
7. No issue comments.
```
