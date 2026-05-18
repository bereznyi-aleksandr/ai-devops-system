# BEM-659 | Diagnose Workflow Trigger Path

Дата: 2026-05-18 | 15:52 (UTC+3)

## Status
needs_dispatch_repair

## Findings
- F1 | telegram-send-smoke.yml no longer contains heredoc markers: PASS | .github/workflows/telegram-send-smoke.yml
- F2 | telegram smoke result exists: FAIL | governance/state/telegram_send_smoke_result.json
- F3 | curator hourly state exists: PASS | governance/state/curator_hourly_report_state.json
- F4 | codex-runner has actions write permission: FAIL | .github/workflows/codex-runner.yml
- F5 | curator hourly keeps allowed schedule: PASS | .github/workflows/curator-hourly-report.yml

## Trigger problem
{
  "code": "PUSH_TRIGGER_FROM_GITHUB_TOKEN_NOT_RELIABLE",
  "suspected": true,
  "message": "Commits made by GitHub Actions token may not trigger other workflows via push. Need explicit workflow_dispatch using actions:write or direct Deno/GitHub PAT dispatch."
}

## Blocker
{
  "code": "WORKFLOW_TRIGGER_PATH_NOT_PROVEN",
  "trigger_problem": {
    "code": "PUSH_TRIGGER_FROM_GITHUB_TOKEN_NOT_RELIABLE",
    "suspected": true,
    "message": "Commits made by GitHub Actions token may not trigger other workflows via push. Need explicit workflow_dispatch using actions:write or direct Deno/GitHub PAT dispatch."
  }
}
