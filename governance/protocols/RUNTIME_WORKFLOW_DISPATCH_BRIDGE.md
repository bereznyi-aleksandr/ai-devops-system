# BEM-538.2 | Runtime Workflow Dispatch Bridge Contract

Дата: 2026-05-17 | 13:43 (UTC+3)

## Цель
Разрешить настоящую workflow-level orchestration проверку: GPT/Deno запускает `codex-runner.yml`, а внутри него безопасный bridge запускает `role-orchestrator.yml` и `provider-adapter.yml` через GitHub workflow_dispatch.

## Разрешённый bridge
Preferred path:
`createCodexTask -> codex-runner.yml -> GITHUB_TOKEN with actions:write -> GitHub Actions workflow_dispatch -> role-orchestrator.yml/provider-adapter.yml -> transport/state`

## Требования
- Не хранить PAT/secrets в файлах.
- Использовать runtime `GITHUB_TOKEN`.
- `codex-runner.yml` должен иметь `permissions: actions: write, contents: write`.
- Target workflows должны иметь `workflow_dispatch` inputs.
- No issue #31 comments.
- No schedule triggers except approved `curator-hourly-report.yml`.

## Fallback если bridge недоступен
Если `actions: write` отсутствует или GitHub запрещает nested dispatch, BEM-538.3 должен завершиться точным blocker: `WORKFLOW_DISPATCH_BRIDGE_MISSING`.

## Current inspection
```json
{
  "codex_runner_exists": true,
  "codex_contents_write": true,
  "codex_actions_write": false,
  "role_dispatch_ready": true,
  "provider_dispatch_ready": true,
  "bridge_mode": "needs_codex_runner_actions_write_permission"
}
```
