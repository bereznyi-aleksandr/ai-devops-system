# BEM-936 Autonomous Continuation Guard

Created: 2026-06-18T18:20:00Z

## Purpose

Prevent the curator loop from stopping while a roadmap still has work.

This is a standing self-task. It is read at every startup and after every task completion.

## Mandatory loop

1. Read `AGENT_CONTEXT.md`.
2. Read `governance/roadmap/ACTIVE_QUEUE.json`.
3. Select the first task with `status=IN_PROGRESS`; if none, select the first task with `status=PENDING`.
4. Execute the selected task.
5. Verify committed proof/receipt physically exists.
6. Mark the task `DONE` with receipt and sha.
7. If any task is still `PENDING`, immediately promote the next task to `IN_PROGRESS`.
8. Append `execution_log.jsonl`.
9. Report in the mobile canon and include: `Следующая задача: <id> — приступаю`.
10. Stop only when `queue_state=COMPLETE` and `current_task=null`.

## Non-claims

This guard does not claim background execution outside the current chat/tool session.
It defines the mandatory in-repository continuation contract and a validator/repair helper for future sessions.

## Receipt

`governance/proofs/BEM936_autonomous_continuation_guard_receipt.json`
