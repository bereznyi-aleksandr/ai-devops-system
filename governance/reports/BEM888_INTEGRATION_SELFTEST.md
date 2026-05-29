# BEM-888 Integration selftest

Status: PASS

✅ exists governance/state/registry_schemas.json — governance/state/registry_schemas.json
✅ exists governance/state/rule_registry.json — governance/state/rule_registry.json
✅ exists governance/state/message_envelope_schema.json — governance/state/message_envelope_schema.json
✅ exists governance/messages/managed_channel_messages.jsonl — governance/messages/managed_channel_messages.jsonl
✅ exists governance/state/workspace_promotion_policy.json — governance/state/workspace_promotion_policy.json
✅ exists governance/workspaces/promotion_log.jsonl — governance/workspaces/promotion_log.jsonl
✅ exists governance/state/product_repository_registry.json — governance/state/product_repository_registry.json
✅ exists governance/state/product_repository_registration_schema.json — governance/state/product_repository_registration_schema.json
✅ registry schema count — schemas=8
✅ rule count — rules=12
✅ continuity rule exists — RULE-012
✅ message log nonempty — messages=2
✅ curator routing — curator-to-curator
✅ workspace promotion has main — main PASS promotion
✅ product registry has template — registration_template
✅ product registry has at least one candidate — repositories=1
✅ backlog first five completed — BEM-882-001,BEM-882-002,BEM-882-003,BEM-882-004,BEM-882-005
