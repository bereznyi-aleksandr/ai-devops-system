# ARCHITECTURE_CANON

Status: active

This file is the canonical plan/fact/gap view after Claude external audit remediation.

| Area | Plan | Fact | Gap | Status |
|---|---|---|---|---|
| Objects GD/DIR/WRK | objects have defined roles, elements and exchange rules | objects_registry plus prompts and object_runner exist | runner is deterministic local/CI runner, not LLM agent runtime yet | partial_real |
| Worker contours | WRK-C1/C2/C3 execute roadmap in parallel | inbox/result flow and dispatch queue exist with E2E proof | consumer is deterministic script; no always-on daemon | partial_real |
| Managed channel | curator-to-curator exchange | message envelope, JSONL log and consumer workflow exist | workflow_dispatch/manual CI runner, not continuous service | partial_real |
| Proof | PASS requires evidence | proof files and deterministic tools exist | commit_sha from codex-status remains null until Git/CI proof policy is enforced | open_gap |
| Pilot | prepare pilot then gate operator for real target | pilot scaffold/BMC/onboarding/evaluation/SLA exist | real segment/client/objective requires operator | correct_gate |

Current interpretation: the repository has moved from pure governance scaffold to a deterministic executable baseline with scripts, workflows and proof files. It is still not a full always-on multi-agent service until CI/Git proof and continuous consumers are enforced.
