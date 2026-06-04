# P29 | ACTIVE_QUEUE mismatch repair
Status: completed
Date: 2026-06-04

## Finding
Claude audit is correct: GPT used `governance/ACTIVE_QUEUE.json` during P26-P28, while the canonical roadmap queue is `governance/roadmap/ACTIVE_QUEUE.json`.

## Repair
`governance/roadmap/ACTIVE_QUEUE.json` was replaced with the Updated Roadmap pre-KZ-1 order: RM-01, RM-02, RM-03, RM-04, RM-05. RM-01 is PENDING; RM-02..RM-05 wait on dependencies.

## Duplicate queue location
GPT P26-P28 queue path: `governance/ACTIVE_QUEUE.json`. This is not the canonical queue after this repair.

## execution_log check
`governance/logs/execution_log.jsonl` exists: True
P26-P28 matching log lines found: 5

## Workflow lock
Respected. No `.github/workflows/*.yml` files touched.

## Next
RM-01: revoke false PASS from `BEM1284_MINIMAL_GOVERNANCE_LOOP_GATE2.md`.
