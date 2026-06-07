# BEM-931 v3.6 — External Audit Request for Claude

Status: RELEASE_PASS_READY_FOR_EXTERNAL_AUDIT

## Canonical evidence

- Release gate: `governance/release/bem931_v36_release_gate.json`
- RM-02 receipt: `governance/proofs/BEM931-V36-RM02_object_passports_receipt.json`
- RM-04 receipt: `governance/proofs/BEM931-V36-RM04_runners_receipt.json`
- RM-15 receipt: `governance/proofs/BEM931-V36-RM15_live_e2e_receipt.json`
- RM-16 receipt: `governance/proofs/BEM931-V36-RM16_multi_contour_receipt.json`
- RM-17 receipt: `governance/proofs/BEM931-V36-RM17_horizontal_exchange_receipt.json`
- Diagnostics: `governance/blockers/bem931_v36_release_repair_diagnostics.json`

## Request

Claude external auditor must verify:

1. RM-15 live E2E chain proves operator → GD curator → DIR curator → WRK curator → analyst → auditor → executor → auditor → curator feedback.
2. RM-16 proves all three default worker contours WRK-C1, WRK-C2, WRK-C3.
3. RM-17 proves horizontal exchange is curator-mediated, not direct role-to-role.
4. RM-18 release gate is PASS with no missing receipts and no failures.
5. No false DONE status is present in ACTIVE_QUEUE.

Expected verdict format:

`APPROVED` or `APPROVED_WITH_NOTES` or `REJECTED.`

If rejected, include exact blocking file/path and required repair.
