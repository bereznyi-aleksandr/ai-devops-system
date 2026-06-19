# BEM-947 LIVE GATE REQUEST

Protocol: BEM-947
Task: BEM947-P2-LIVE-GATE-AFTER-YAML-VALIDATION
Created: 2026-06-19T19:09:30Z

## Context

The production workflow `.github/workflows/claude.yml` was repaired after external audit found three indentation defects.

Verified current evidence:
- `.github/workflows/claude.yml` current blob: `df512080669e993f5f0128b1e5e2628d0a4ff368`
- `sha_type`: `git_blob`
- repair commit: `d2843490efc2bb2aafc5fe1044361d5d8be52943`
- `commit_sha_type`: `commit`
- receipt: `governance/proofs/BEM947_claude_yml_three_indent_fix_receipt.json`
- checks in receipt: `exactly_three_indent_fixes=true`, `yaml_validated_by_ruby_psych=true`, `python_heredocs_compile=true`

## Request

Run or validate the live gate for BEM-947 planned→executed closure.

Expected proof path:
`governance/proofs/BEM947_live_object_dispatch_executed_<trace>.json`

Acceptance conditions:
- `status`: `completed`
- `protocol`: `BEM-947`
- `task_id`: `BEM947-P2-LIVE-OBJECT-DISPATCH-RUN`
- `provider_selected`: `claude_code`
- `target_workflow_id`: `claude.yml`
- `dispatch_result`: `executed`
- `blocker`: `null`
- `checks.curator_router_to_claude_yml`: `true`
- `checks.executed_by_claude_yml`: `true`
- `checks.sha_type_explicit`: `true`

If execution is still blocked, write a BLOCKED proof instead of PASS and include the exact blocker.
