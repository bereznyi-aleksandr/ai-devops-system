# BEM-932 WAIT_RUNTIME — Cloudflare deployment runbook

Date: 2026-06-13T15:35:00Z
Status: BLOCKED_REQUIRES_OPERATOR_RUNTIME_ACCESS

## Goal

Close the remaining runtime debt identified by External Auditor Claude:
- deploy the repo-side Worker source to the real Cloudflare Worker;
- run one live Telegram fallback test through `provider-router.yml`;
- produce a full TEST-T02 receipt.

## Preconditions

Operator has Cloudflare account/dashboard or Wrangler access for the running Telegram Worker.

## Files

- Source to deploy: `infrastructure/cloudflare-worker/telegram-webhook.js`
- Router workflow: `.github/workflows/provider-router.yml`
- Router config: `governance/config/provider_config.json`

## Required Cloudflare variables/secrets

- `TELEGRAM_BOT_TOKEN`
- `GH_PAT`
- `GH_REPO`
- optional: `ROUTER_WORKFLOW_ID=provider-router.yml`

The source defaults to `provider-router.yml` if `ROUTER_WORKFLOW_ID` is not set.

## Test

1. Send a live Telegram message to the operator bot.
2. Force or simulate primary provider `gpt_codex` quota exceeded for the same trace.
3. Confirm `provider-router.yml` dispatches `claude.yml`.
4. Confirm receipt has:
   - `provider_selected=claude_code`
   - `fallback_reason=fallback_quota`
   - real `github_run_id`
   - live Telegram `chat_id` and `message_id`.

## Completion

Create/verify:
`governance/proofs/BEM932_TEST_T02_full_live_fallback_receipt.json`

Then request final External Auditor Claude approval.
