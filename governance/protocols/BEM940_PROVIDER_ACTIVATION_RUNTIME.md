# BEM-940 Provider Activation Runtime

Created: 2026-06-19T03:14:00Z

## Purpose

Replace `provider_activation.py` stub with a runtime activation control layer that reads provider_config, validates role support, writes provider_status, and records auditable activation decisions.

## Roadmap

1. `BEM940-P0-PROVIDER-ACTIVATION` — replace stub with provider activation runtime.
2. `BEM940-P1-PROVIDER-STATUS-INTEGRATION` — materialize provider_status and activation decisions.
3. `BEM940-P2-PROVIDER-ACTIVATION-ROOTER-SMOKE` — prove activated provider aligns with curator_router.
4. `BEM940-P3-FINAL-VERIFY` — final verification and continue to next if stubs remain.

## Non-claim

This does not claim downstream LLM completion. It proves activation decision/status only.
