# BEM-932 Protocol v8.3 — APPROVED TO EXECUTE

Date: 2026-06-13
Repository: bereznyi-aleksandr/ai-devops-system
Source document: BEM932_Protocol_v8_3.docx
External auditor: EXTERNAL_AUDITOR_CLAUDE
Status: APPROVED TO EXECUTE

## 0. Core decision

BEM-932 does not replace BEM-931 v3.7. It resumes the approved BEM-931 v3.7 provider-router plan and adds a continuity block before provider-router implementation.

The current execution must start with step 0.0:
1. Commit this canon file into `governance/protocols/BEM932_Protocol_v8_3.md`.
2. Update `governance/roadmap/ACTIVE_QUEUE.json` to version 10.
3. Insert steps 0.1-0.4 before BEM-PROVIDER-001.
4. Keep BEM-PROVIDER-001 active, but scheduled after the 0.1-0.4 continuity block.

## 0bis. Accepted corrections from GPT review

1. Use existing `.github/workflows/claude.yml` for `claude_code`; `.github/workflows/claude-local.yml` does not exist.
2. `provider_router.py` must not scan the entire `governance/codex/results/` directory. It may read only the current trace result plus fresh `provider_status.json` with TTL.
3. Backfill to `execution_log.jsonl` must be explicit: `backfill=true`, `event_at`, `recorded_at`, `source_proof`, `source_sha`.
4. Fallback Telegram notification is idempotent: one `trace_id` -> one fallback notification.
5. `BEM932-EXPERIENCE-FIX` does not block BEM-PROVIDER-001, but blocks final RELEASE / WORKING_CONTOUR_READY.
6. Prompt assembler acceptance is role-specific: Analyst/Auditor/Curator receive their corresponding council rule.
7. Run #51 horizontal exchange requires a small proof file before its SHA is treated as confirmed.

## 0tris. Implementation notes

1. Work from repo source of truth, not from chat/docx.
2. ACTIVE_QUEUE version 10 is mandatory before 1.A.
3. Router returns a strict JSON contract:
   `provider_selected`, `fallback_reason`, `decision_source`, `trace_id`, `ttl_seconds`, `stale_ignored`.
4. `provider-router.yml` includes pre-live tests:
   `stale_quota_ignored`, `same_trace_quota_fallback`, `no_status_primary`.
5. Cloudflare Worker switch uses `ROUTER_WORKFLOW_ID` feature flag for rollback to `codex-local.yml` without code redeploy.
6. SYSTEM_STATUS writer/auditor split: Executor writes; Claude audits.
7. `github_sha=a43c5ed8...` is preliminary until `BEM932_horizontal_exchange_run51_receipt.json` is created.

## 1. Layer map

- v3.5 object/rule/prompt layer: approved base.
- v3.6 working contour RM-01..RM-18: approved, live run `github_run_id=27116441198`.
- v3.6 debt: RM-13 formally PASS but `experience_registry.json` and `experience_loader.py` are broken; must be fixed before final RELEASE.
- v3.7 provider-router plan: approved but not implemented; BEM-PROVIDER-001 resumes from there.
- Telegram/Cloudflare Worker: partially complete; webhook works and currently dispatches to `codex-local.yml`, but must be switched to `provider-router.yml`.

## 2. Roadmap

### 0.0 BEM932-CANON-SYNC
Commit this canon file and update ACTIVE_QUEUE to v10. Must run first.
Acceptance: canon file SHA exists; ACTIVE_QUEUE version=10; source points to this file; BEM-PROVIDER-001 remains active but after 0.1-0.4.

### 0.1 BEM932-CONTINUITY-01
Backfill `governance/logs/execution_log.jsonl` for RM-15..RM-18 and live WRK-C3/run #51.
Each added record uses `backfill=true`, `event_at`, `recorded_at`, `source_proof`, `source_sha`.
Run #51 journal entry must reference `governance/proofs/BEM932_horizontal_exchange_run51_receipt.json`, not a preliminary SHA.

### 0.2 BEM932-CONTINUITY-02
Executor updates `SYSTEM_STATUS.md` to actual repo state. Claude audits separately.

### 0.3 BEM932-EXPERIENCE-FIX
Restore:
- `governance/experience/experience_registry.json`
- `governance/runtime/experience_loader.py`
Acceptance: `json.load` and `ast.parse` OK; test error creates an experience record.
This does not block BEM-PROVIDER-001 but blocks final RELEASE.

### 0.4 BEM932-PROOF-RUN51
Create `governance/proofs/BEM932_horizontal_exchange_run51_receipt.json` with:
`status`, `run_id`, `github_sha`, `trace_id`, `source_contour=WRK-C1`, `target_contour=WRK-C2`, `verified_at`.

### 1.A BEM-PROVIDER-001-A
Create `governance/config/provider_config.json`:
- roles: curator, analyst, auditor, executor
- primary: `gpt_codex`
- fallback: `claude_code`
- fallback_on: `quota_exceeded`, `rate_limit`, `provider_unavailable`
Acceptance: valid JSON >200 bytes, ACTIVE_QUEUE v10.

### 1.B BEM-PROVIDER-001-B
Create `scripts/provider_router.py`.
Acceptance: `ast.parse` OK, >300 bytes, `def main()`, `if __name__ == "__main__"`, returns dict with strict JSON contract fields.

### 1.C BEM-PROVIDER-001-C
Create `.github/workflows/provider-router.yml`.
Inputs: `role`, `task`, `trace_id`, `chat_id`, `message_id`.
Job1: provider_router.py. Job2: dispatch `codex-local.yml` or existing `claude.yml`. Job3: proof receipt.

### 1.C2 BEM932-ROUTER-TESTS
Add test job before live dispatch:
- stale quota ignored
- same trace quota fallback
- no status primary

### 1.D BEM-PROVIDER-001-D
Switch Cloudflare Worker through `ROUTER_WORKFLOW_ID`, not hard-coded workflow id. Rollback by changing variable only.

### 1.E BEM-PROVIDER-001-E
Honest outbox: fallback notification before result. Idempotent by trace_id.

### 1.FINAL BEM-PROVIDER-001-FINAL
After 1.C2 passes: live Telegram test with simulated quota. Expected `provider_selected=claude_code`, `fallback_reason=fallback_quota`, real `github_run_id`.

### 2.1 BEM-CODEX-001
Create root `AGENTS.md` with six sections from v3.7.

### 2.2 BEM-CODEX-002
Connect Analyst via `provider-router.yml` and prompt assembler.

### 2.3 BEM-CODEX-003
Connect Auditor via `provider-router.yml`.

### 2.4 BEM-CODEX-004
Connect Executor via `provider-router.yml`.

### 2.5 BEM-CODEX-005
Curator returns Telegram final report; receipt records inbound/outbound message_id.

### 3.1 BEM-CF-001-COMPLETE
Complete Cloudflare Worker route to provider-router and verify `getWebhookInfo` plus response under one second.

### 4.1 TEST-T02
Live Telegram E2E through provider-router and real LLM roles.

### 4.2 RELEASE
WORKING_CONTOUR_READY only after Claude approval, live-tested fallback, and 0.3 experience fix.

### 5.1 BEM932-COUNCIL-RULES
Add council rules to `governance/registry/rule_registry.json`.

### 5.2 BEM932-COUNCIL-PROFILES
Add dynamic rule refs to `element_prompt_profiles.json`.

### 5.3 BEM932-PROMPT-ASSEMBLER
Create `scripts/prompt_assembler.py`.

### 5.4 BEM932-COUNCIL-VERIFY
Run one test task and compare before/after output.

### 6.1 BEM932-CLOSE-01
Update `SYSTEM_STATUS.md` after 1.x-5.x.

### 6.2 BEM932-CLOSE-02
Update `governance/AGENT_CONTEXT.md`.

### 6.3 BEM932-CLOSE-03
Send final Telegram report in contract A8 format.

## 3. Closure rule

Do not close roadmap unless:
- ACTIVE_QUEUE v10 tasks are DONE with SHA;
- receipts/proofs exist;
- provider fallback has been live-tested;
- RM-13 experience mechanism works;
- Claude approves RELEASE.
