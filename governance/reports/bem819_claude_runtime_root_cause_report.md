# BEM-819 | Claude runtime root-cause report

Дата: 2026-05-21 | 20:50 (UTC+3)

## Итог
Реального согласованного ответа Claude пока нет. Протокол не согласован. Оператор не должен быть relay.

## Доказанные причины
1. workflow_run path не доказал пробуждение Claude dispatcher: smoke/check цепочки не дали устойчивого runtime-state.
2. В repo есть blocker/fallback files в claude_to_gpt, но они не являются ответом Claude и не должны считаться APPROVED.
3. Первые dispatcher workflows падали на lint-gate из-за inline heredoc/длинных run blocks; это исправлялось, но исторические failed runs остались.
4. Direct/queue dispatch path ещё не доказал появление workflow_dispatch_results и claude_inbound_mailbox_workflow_state.
5. Deno/status endpoints временами дают HTTP/content-type/client errors; поэтому длинные payload/status loops заменяются короткими tasks и repo-artifacts.

## Главный текущий blocker
Claude trigger chain не дошёл до доказуемого состояния: нет файла состояния runtime Claude и нет реального Claude response с decision.

## Что не считается результатом
- NOT CLAUDE APPROVAL
- RUNTIME BLOCKER
- fallback report
- наличие файла в claude_to_gpt без маркера реального Claude response

## Следующее действие
BEM-820: разобрать BEM-818 route и продолжить с конкретного шага: если route требует dispatch-results — чинить queue/processor; если требует response — фильтровать и обрабатывать только real Claude response.
