# AGENT_CONTEXT.md | canonical startup context

Updated: 2026-06-18T18:20:00Z
Repository: bereznyi-aleksandr/ai-devops-system

## Startup rule

Read this file first, then `governance/roadmap/ACTIVE_QUEUE.json`, then the current protocol referenced by that queue.

## Autonomous continuation rule

Standing task: `BEM936-AUTONOMOUS-CONTINUATION-GUARD`.

After every task completion:
1. verify the committed proof/receipt exists;
2. mark the task DONE;
3. read `ACTIVE_QUEUE.json` again;
4. if any task is `PENDING`, immediately promote the next task to `IN_PROGRESS`;
5. report: `Следующая задача: <id> — приступаю`;
6. continue execution without waiting for the operator.

Stopping is allowed only when `queue_state=COMPLETE`, `current_task=null`, and there are no `PENDING` or `IN_PROGRESS` tasks.

Validation helper: `governance/runners/autonomous_continuation_guard.py`.

## Current verified state

BEM-934 is closed: roadmap 10/10, `ACTIVE_QUEUE` COMPLETE, release PASS.
BEM-935 is closed: roadmap 4/4, `ACTIVE_QUEUE` COMPLETE, release PASS.
BEM-936 standing continuation guard is written and must govern future roadmap execution.

## Runtime reality

The proven operational route is:

`Operator Telegram -> Cloudflare Worker -> provider-router workflow -> claude.yml -> anthropics/claude-code-action@v1 -> report/proof commit`.

Primary provider for curator, analyst, auditor, and executor is `claude_code`.
Self-hosted Codex is disabled, deprecated, and non-operational.
`gpt_codex_cloud` is reserve only; without OpenAI runtime secrets it is mechanical fallback, not an LLM execution claim.
