# BEM-548.3 | Provider Adapter Probe Integration

Дата: 2026-05-17 | 14:55 (UTC+3)

## Rule
Provider adapter must write `provider_probe_result`, `provider_selection_decision`, and `provider_selection_audit` for every provider decision.

## Decision matrix
| Claude signal | Selected provider | Reserve |
|---|---|---|
| active/completed | claude | false |
| failed/cancelled/timeout/missing_result_after_ttl | gpt | true |
| unknown/no_signal | claude | false |

## No silent switch
GPT reserve may be selected only after explicit failed/cancelled/timeout/missing_result_after_ttl evidence.
