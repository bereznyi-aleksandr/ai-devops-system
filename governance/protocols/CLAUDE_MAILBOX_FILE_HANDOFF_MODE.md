# BEM-780 | Claude Mailbox File-Handoff Mode

Дата: 2026-05-21 | 19:35 (UTC+3)
Статус: ACTIVE_UNTIL_REAL_CLAUDE_RUNTIME_PROVEN

## Почему
Ранее согласование с Claude было подтверждено committed mailbox/file artifacts. Live Claude runtime wake-up сейчас не доказан. Попытки добавить новые workflows создали повторяющийся workflow-lint-gate failure loop.

## Правило
До отдельного proof реального Claude runtime запрещено создавать новые active `.github/workflows/*claude*` для wake-up. Работа идёт через file/mailbox handoff: GPT пишет запрос в `governance/audit_mailbox/gpt_to_claude/`; ответ считается полученным только когда появляется committed файл в `governance/audit_mailbox/claude_to_gpt/` или `external_auditor_to_internal_auditor/`.

## PASS
PASS по согласованию допускается только при наличии реального файла ответа Claude с Decision: APPROVED / CHANGE_REQUIRED / BLOCKED. Fallback/blocker reports не являются approval.
