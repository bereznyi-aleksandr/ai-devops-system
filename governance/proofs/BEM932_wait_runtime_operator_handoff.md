# BEM-932 WAIT_RUNTIME operator handoff

Status: BLOCKED_REQUIRES_OPERATOR_CLOUDFLARE_DEPLOY
Created by: GPT executor
Date: 2026-06-13

## Required operator action

1. Deploy `infrastructure/cloudflare-worker/telegram-webhook.js` to the live Cloudflare Worker.
2. Set or confirm Cloudflare Worker variable:
   - `ROUTER_WORKFLOW_ID=provider-router.yml`
3. Keep existing required secrets/vars:
   - `TELEGRAM_BOT_TOKEN`
   - `GH_REPO`
   - `GH_PAT`
4. Send a real Telegram message to the bot.
5. Verify a live receipt with:
   - `provider_selected=claude_code` when GPT quota/fallback condition is active
   - `fallback_reason=fallback_quota`
   - GitHub run id present

## Current repo-side state

Repo-side provider router, smoke tests, global status fallback, Codex role integrations, Cloudflare Worker source, release gate and external audit verdict are already recorded.

Release gate remains:
`PASS_REPO_SIDE_RUNTIME_EXCEPTION`

Missing runtime items:
- live Cloudflare Worker deployment confirmation
- live Telegram fallback trace with real quota_exceeded condition
- full external auditor approval after full TEST-T02
