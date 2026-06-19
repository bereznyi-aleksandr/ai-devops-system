# BEM-947 EXTERNAL GATE REQUEST

Created: 2026-06-19T15:37:00Z

Current status: BEM-947 P2 is BLOCKED_REPAIRING. P0 / P1 are DONE. BEM-947 is not PASS.

Target: prove planned -> executed or completed for object dispatch:

```
object_runner -> dispatch_queue -> curator_router -> claude.yml -> executed/completed evidence
```

Required proof:

`governance/proofs/BEM947_live_object_dispatch_executed_<external_gate_trace>.json`

Strict JSON fields:

```json
{
  "status": "completed",
  "protocol": "BEM-947",
  "task_id": "BEM947-P2-LIVE-OBJECT-DISPATCH-RUN",
  "trace_id": "<external_gate_trace>",
  "provider_selected": "claude_code",
  "target_workflow_id": "claude.yml",
  "dispatch_result": "executed",
  "blocker": null,
  "checks": {
    "object_runner_to_dispatch_queue": true,
    "curator_router_to_claude_yml": true,
    "executed_by_claude_yml": true,
    "sha_type_explicit": true
  }
}
```

If blocked, write a BLOCKED proof instead and do not claim PASS.
