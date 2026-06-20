# AGENT_CONTEXT

Updated: 2026-06-20T09:56:30Z
Repository: bereznyi-aleksandr/ai-devops-system
Active protocol: BEM-948
Roadmap: 1/5 complete (20%)
Current task: BEM948-P1-AGENT-CONTEXT-SYNC
Release: BLOCKED_BUILDING

Contract: read ACTIVE_QUEUE; execute IN_PROGRESS then PENDING; verify evidence; update queue and execution_log; immediately take the next task. HTTP 204 is dispatched, never completed. PASS requires task-specific completed proof with no conflicting report. Defects open autorepair.

Primary: claude_code via .github/workflows/claude.yml.
Permanent bridge: object_runner.py -> dispatch_consumer.py -> dispatch_executor.py -> claude.yml.
Reserve: gpt_codex_cloud; without configured OpenAI runtime is hechanical_fallback.

BEM-948 P0 DONE. Trace: bem948_p0_live_object_e2e_turn24_20260620T0950Z.
P0 receipt: governance/proofs/BEM948_p0_final_verification_receipt.json.
Execution commit: 3bf9f8e257cd113ed4436d966ebf2b2ea7b859bd (commit).
Claude default turn budget: 24. Validation: governance/proofs/BEM948_claude_yaml_validation_receipt.json.
P1 active; P2-P4 pending.

Canonical: ACTIVE_QUEUE.json; provider_config.json; BEM948 P0 final receipt; BEM948 Claude YAML validation; BEM948 turn24 executed proof; trace report; execution_log.jsonl.
Final BEM-948 PASS requires P0-P3 evidence and a fail-closed P4 validator.
