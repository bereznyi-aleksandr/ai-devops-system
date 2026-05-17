# BEM-537 | Transport Consumer Contract

Дата: 2026-05-17 | 13:36 (UTC+3)

## Purpose
Defines how internal contour consumer reads `governance/transport/results.jsonl` and converts records into next role decisions.

## Inputs
Append-only JSONL records: intake, analysis, audit, execution, final_result, provider_adapter_result, telegram_hourly_report_synthetic.

## Decision rules
- curator_intake/intake -> next_role from record or analyst by default.
- analysis completed -> auditor.
- audit PASS_TO_EXECUTOR -> executor.
- execution completed -> auditor final.
- final_result completed -> curator closure.
- failed/cancelled/timeout -> curator blocker/failover.

## Outputs
- consumer_decision record in transport.
- role_cycle_state.json update.
- decision artifact under governance/internal_contour/tests.
