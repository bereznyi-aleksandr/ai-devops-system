# BEM-840 | NEXT CHAT MANDATORY HANDOFF | 2026-05-22 | 06:00 (UTC+3)

## Обязательные правила для нового чата
1. Перед первым ответом прочитать этот handoff, `governance/handoff/GPT_NEXT_ACTION.md`, `governance/protocols/AUTONOMY_CONTINUITY_CONTRACT_EXTENSION.md`, `governance/GPT_WRITE_CHANNEL.md` если файл существует, и `GPT_HANDOFF.md` / `governance/GPT_HANDOFF.md` если они существуют.
2. Отчёт оператору не является остановкой разработки. После любого checkpoint/report немедленно создать или продолжить следующий Deno/Codex task.
3. Если цель не достигнута, запрещено завершать ход как финальный результат. Разрешён только checkpoint с уже созданным следующим active task/pending/watchdog-state.
4. До PASS по Claude-согласованию нужны три доказательства: `workflow_dispatch_results`, `claude_inbound_mailbox_workflow_state` с start/completion, реальный `governance/audit_mailbox/claude_to_gpt` ответ Claude. Файлы `NOT CLAUDE APPROVAL`, `RUNTIME BLOCKER` и fallback не считаются ответом Claude.
5. Если `getCodexStatus` падает два раза подряд, не делать третий запрос. Перейти на короткий `createCodexTask` или repo-artifact recovery.
6. Если Deno payload вызывает UI confirmation или content-type/client error, немедленно перейти на короткие tasks. Оператор не нажимает подтверждения и не является relay.
7. Если есть malformed queue JSON, удалить/архивировать его и продолжить. Один битый JSON не должен валить runner.
8. Запрещено писать в issue #31. Все write-actions только через Deno/Codex/Python executor patterns. No issue comments.

## Текущий контекст работы
Цель: добиться реального ответа Claude и согласовать протокол развития мультиагентной системы.
Текущая цепочка: BEM-827 исправил malformed JSON в `governance/workflow_dispatch_queue`; BEM-837 создал `governance/workflow_dispatch_queue/bem837_claude_response_retry_dispatch.json`; BEM-838 сделал fresh tick; BEM-839 проверяет triad после retry.
Следующее действие нового чата: проверить BEM-839 status, прочитать `governance/state/bem839_verify_after_response_retry_tick.json`, затем чинить первый отсутствующий proof из triad.

## Канон поведения
КОНТРАКТ ПРИНЯТ | YYYY-MM-DD | HH:MM (UTC+3)
▶ Подключаюсь к Deno серверу...
▶ Читаю handoff/contract/write-channel...
▶ Продолжаю незавершённый BEM без ожидания оператора.

