# BEM-889 Delivery manifest

Status: READY

Accepted roadmap: BEM-879 protocol v1.7.

Executed baseline: BEM-880.

Executable hardening: BEM-883 through BEM-888.

Proofs:
- governance/runtime/curator_dispatch/BEM883_REGISTRY_SCHEMA_VALIDATION_PASS.md
- governance/runtime/curator_dispatch/BEM884_OPERATIONAL_RULES_PASS.md
- governance/runtime/curator_dispatch/BEM885_CHANNEL_ENVELOPE_PASS.md
- governance/runtime/curator_dispatch/BEM886_WORKSPACE_PROMOTION_PASS.md
- governance/runtime/curator_dispatch/BEM887_PRODUCT_REPOSITORY_TEMPLATE_PASS.md
- governance/runtime/curator_dispatch/BEM888_INTEGRATION_SELFTEST_PASS.md

Tools:
- governance/tools/validate_registries.py
- governance/tools/validate_workspace_promotion.py
- governance/tools/validate_product_repository_registry.py
- governance/tools/run_bem880_selftest.py

State files:
- governance/state/architecture_registry.json
- governance/state/objects_registry.json
- governance/state/task_registry.json
- governance/state/rule_registry.json
- governance/state/channel_registry.json
- governance/state/workspace_registry.json
- governance/state/workspace_promotion_policy.json
- governance/state/product_repository_registry.json
- governance/state/testing_policy.json
- governance/state/message_envelope_schema.json

Missing: none

Pending backlog: none

Selftest: PASS
