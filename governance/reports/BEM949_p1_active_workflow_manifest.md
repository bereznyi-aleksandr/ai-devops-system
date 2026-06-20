# BEM-949 P1 — Active workflow dispatch manifest

| Workflow | Provider | Dispatch | Required inputs | Runtime evidence |
|---|---|---:|---:|---|
| `.github/workflows/claude.yml` | claude_code | yes | 6 | pending_controlled_trace_P3 |
| `.github/workflows/provider-router.yml` | router | yes | 0 | pending |
| `.github/workflows/role-orchestrator.yml` | orchestrator | yes | 0 | pending_controlled_trace_P3 |
| `.github/workflows/role-router.yml` | router | yes | 1 | pending_controlled_trace_P3 |
| `.github/workflows/gpt-codex-cloud.yml` | gpt_codex_cloud | yes | 0 | pending_live_or_declaim_P4 |
| `.github/workflows/curator.yml` | claude_code | no | 0 | pending_controlled_trace_P3 |
| `.github/workflows/provider-adapter.yml` | adapter | yes | 4 | pending |
