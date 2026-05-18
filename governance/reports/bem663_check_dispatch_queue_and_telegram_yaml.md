# BEM-663 | Dispatch Queue And Telegram YAML Check | NEEDS_TELEGRAM_YAML_REPAIR

Дата: 2026-05-18 | 15:58 (UTC+3)

## Checks

- codex_dispatch_step_present: PASS
- codex_actions_write: PASS
- telegram_workflow_exists: PASS
- telegram_no_heredoc: PASS
- telegram_no_shell_ansi_c_newline: FAIL
- telegram_no_literal_smoke_marker_at_yaml_top: PASS
- telegram_smoke_result_exists: FAIL
- dispatch_results_exist: PASS

## Dispatch results
[
  {
    "path": "governance/workflow_dispatch_results/bem637_run_claude_runtime_smoke.response.json",
    "content": ""
  },
  {
    "path": "governance/workflow_dispatch_results/bem637_run_claude_runtime_smoke.status",
    "content": "204\n"
  },
  {
    "path": "governance/workflow_dispatch_results/bem637_run_curator_hourly_report.response.json",
    "content": ""
  },
  {
    "path": "governance/workflow_dispatch_results/bem637_run_curator_hourly_report.status",
    "content": "204\n"
  },
  {
    "path": "governance/workflow_dispatch_results/bem637_run_direct_telegram_smoke.response.json",
    "content": ""
  },
  {
    "path": "governance/workflow_dispatch_results/bem637_run_direct_telegram_smoke.status",
    "content": "204\n"
  },
  {
    "path": "governance/workflow_dispatch_results/claude_primary_runtime_smoke.response.json",
    "content": ""
  },
  {
    "path": "governance/workflow_dispatch_results/claude_primary_runtime_smoke.status",
    "content": "204\n"
  },
  {
    "path": "governance/workflow_dispatch_results/curator_hourly_delivery_verification.response.json",
    "content": ""
  },
  {
    "path": "governance/workflow_dispatch_results/curator_hourly_delivery_verification.status",
    "content": "204\n"
  },
  {
    "path": "governance/workflow_dispatch_results/curator_hourly_report.response.json",
    "content": ""
  },
  {
    "path": "governance/workflow_dispatch_results/curator_hourly_report.status",
    "content": "204\n"
  },
  {
    "path": "governance/workflow_dispatch_results/telegram_send_smoke.response.json",
    "content": "{\n  \"message\": \"Workflow does not have 'workflow_dispatch' trigger\",\n  \"documentation_url\": \"https://docs.github.com/rest/actions/workflows#create-a-workflow-dispatch-event\",\n  \"status\": \"422\"\n}\n"
  },
  {
    "path": "governance/workflow_dispatch_results/telegram_send_smoke.status",
    "content": "422\n"
  }
]

## Blocker
{
  "code": "DISPATCH_OR_TELEGRAM_WORKFLOW_ISSUE",
  "failed": [
    {
      "name": "telegram_no_shell_ansi_c_newline",
      "pass": false,
      "evidence": ".github/workflows/telegram-send-smoke.yml"
    },
    {
      "name": "telegram_smoke_result_exists",
      "pass": false,
      "evidence": "governance/state/telegram_send_smoke_result.json"
    }
  ],
  "result_files": [
    {
      "path": "governance/workflow_dispatch_results/bem637_run_claude_runtime_smoke.response.json",
      "content": ""
    },
    {
      "path": "governance/workflow_dispatch_results/bem637_run_claude_runtime_smoke.status",
      "content": "204\n"
    },
    {
      "path": "governance/workflow_dispatch_results/bem637_run_curator_hourly_report.response.json",
      "content": ""
    },
    {
      "path": "governance/workflow_dispatch_results/bem637_run_curator_hourly_report.status",
      "content": "204\n"
    },
    {
      "path": "governance/workflow_dispatch_results/bem637_run_direct_telegram_smoke.response.json",
      "content": ""
    },
    {
      "path": "governance/workflow_dispatch_results/bem637_run_direct_telegram_smoke.status",
      "content": "204\n"
    },
    {
      "path": "governance/workflow_dispatch_results/claude_primary_runtime_smoke.response.json",
      "content": ""
    },
    {
      "path": "governance/workflow_dispatch_results/claude_primary_runtime_smoke.status",
      "content": "204\n"
    },
    {
      "path": "governance/workflow_dispatch_results/curator_hourly_delivery_verification.response.json",
      "content": ""
    },
    {
      "path": "governance/workflow_dispatch_results/curator_hourly_delivery_verification.status",
      "content": "204\n"
    }
  ]
}
