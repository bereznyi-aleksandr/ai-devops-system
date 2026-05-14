## BEM-SYSTEM-STATUS | RUN RESULT

```text
Trace: system_status_report
Mode: schedule
Time: 2026-05-14T20:01:21Z

ЧЕК-ЛИСТ:
[✅] emergency_stop.enabled = false
[✅] role_state.status = blocked
[✅] last_cycle_id = cyc_ic_b_full_contour_20260512_session
[✅] providers_checked = 3
[✅] relay_events_seen = 5
[✅] report_generated_at = 2026-05-14T20:01:21Z
```

| Subsystem | Status | Detail |
|---|---|---|
| Emergency stop | ✅ clear | - |
| Role FSM | ❌ blocked | last_cycle=cyc_ic_b_full_contour_20260512_session |
| Last role | ❌ blocked | role=auditor provider=gpt_codex |
| Relay | ✅ present | recent_events=5 |

### Providers

| Provider | Status | Last failure | Last role |
|---|---|---|---|
| claude | ✅ ok | - | - |
| gpt | ✅ ok | - | - |
| gpt_codex | ❌ error | runner_unavailable | auditor |

### Recent role events

```json
[
  {
    "event": "ROLE_WATCHDOG_COMPLETED",
    "changed": false,
    "last_cycle_id": "cyc_ic_b_full_contour_20260512_session",
    "status": "blocked",
    "timestamp": "2026-05-14T15:03:40Z"
  },
  {
    "event": "ROLE_ORCHESTRATOR_START",
    "mode": "watchdog",
    "timestamp": "2026-05-14T17:08:39Z"
  },
  {
    "event": "ROLE_WATCHDOG_COMPLETED",
    "changed": false,
    "last_cycle_id": "cyc_ic_b_full_contour_20260512_session",
    "status": "blocked",
    "timestamp": "2026-05-14T17:08:40Z"
  },
  {
    "event": "ROLE_ORCHESTRATOR_START",
    "mode": "watchdog",
    "timestamp": "2026-05-14T19:05:03Z"
  },
  {
    "event": "ROLE_WATCHDOG_COMPLETED",
    "changed": false,
    "last_cycle_id": "cyc_ic_b_full_contour_20260512_session",
    "status": "blocked",
    "timestamp": "2026-05-14T19:05:03Z"
  }
]
```

### Recent provider events

```json
[
  {
    "event": "PROVIDER_FAILOVER_CANDIDATE",
    "role": "analyst",
    "provider": "gpt",
    "fallback_used": false,
    "trace_id": "",
    "task_type": "role_orchestrator",
    "timestamp": "2026-05-12T16:48:38Z"
  },
  {
    "event": "PROVIDER_ADAPTER_SELECTED",
    "role": "analyst",
    "provider": "gpt",
    "workflow": "gpt-hosted-roles.yml",
    "mode": "workflow_dispatch",
    "timestamp": "2026-05-12T16:48:38Z"
  },
  {
    "event": "PROVIDER_FAILOVER_CANDIDATE",
    "role": "auditor",
    "provider": "claude",
    "fallback_used": false,
    "trace_id": "",
    "task_type": "role_orchestrator",
    "timestamp": "2026-05-12T16:48:59Z"
  },
  {
    "event": "PROVIDER_SKIPPED",
    "role": "auditor",
    "provider": "claude",
    "reason": "adapter_disabled",
    "timestamp": "2026-05-12T16:48:59Z"
  },
  {
    "event": "PROVIDER_ADAPTER_SELECTED",
    "role": "auditor",
    "provider": "gpt_codex",
    "workflow": "codex-local.yml",
    "mode": "workflow_dispatch",
    "timestamp": "2026-05-12T16:48:59Z"
  }
]
```

### Recent relay events

```json
[
  {
    "timestamp": "2026-05-05T19:57:46Z",
    "trace_id": "proof_e4_007_issue_comment_ingress_20260505",
    "source": "external_gpt_chat",
    "operation": "append_file",
    "dry_run": false,
    "files": [
      "governance/events/gpt_action_ingress_proof.jsonl"
    ],
    "event": "GPT_RELAY_APPLIED"
  },
  {
    "timestamp": "2026-05-05T20:25:15Z",
    "trace_id": "e5_001_provider_failover_layer_20260505",
    "source": "external_gpt_chat",
    "operation": "update_file",
    "dry_run": true,
    "files": [
      "governance/policies/provider_failover_policy.json",
      "scripts/provider_failover.py",
      "governance/events/provider_failover.jsonl",
      "governance/events/gpt_action_ingress_proof.jsonl"
    ],
    "event": "GPT_RELAY_ACTION_ACCEPTED"
  },
  {
    "timestamp": "2026-05-05T20:25:15Z",
    "trace_id": "e5_001_provider_failover_layer_20260505",
    "source": "external_gpt_chat",
    "operation": "update_file",
    "dry_run": true,
    "files": [
      "governance/policies/provider_failover_policy.json",
      "scripts/provider_failover.py",
      "governance/events/provider_failover.jsonl",
      "governance/events/gpt_action_ingress_proof.jsonl"
    ],
    "event": "GPT_RELAY_DRY_RUN_OK"
  },
  {
    "timestamp": "2026-05-05T20:25:15Z",
    "trace_id": "e5_001_provider_failover_layer_20260505",
    "source": "external_gpt_chat",
    "operation": "update_file",
    "dry_run": false,
    "files": [
      "governance/policies/provider_failover_policy.json",
      "scripts/provider_failover.py",
      "governance/events/provider_failover.jsonl",
      "governance/events/gpt_action_ingress_proof.jsonl"
    ],
    "event": "GPT_RELAY_ACTION_ACCEPTED"
  },
  {
    "timestamp": "2026-05-05T20:25:15Z",
    "trace_id": "e5_001_provider_failover_layer_20260505",
    "source": "external_gpt_chat",
    "operation": "update_file",
    "dry_run": false,
    "files": [
      "governance/policies/provider_failover_policy.json",
      "scripts/provider_failover.py",
      "governance/events/provider_failover.jsonl",
      "governance/events/gpt_action_ingress_proof.jsonl"
    ],
    "event": "GPT_RELAY_APPLIED"
  }
]
```
