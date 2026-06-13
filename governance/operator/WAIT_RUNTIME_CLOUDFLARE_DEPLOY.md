# WAIT_RUNTIME — Cloudflare live deploy handoff

Protocol: BEM-932 v8.3
Task: WAIT_RUNTIME
Status: BLOCKED_REQUIRES_OPERATOR_CLOUDFLARE_DEPLOY
Prepared by: GPT executor
Prepared at: 2026-06-13T09:48:00Z

## What is already done repo-side

| Item | Status |
|---|---|
| provider_config.json | DONE |
| provider_router.py | DONE |
| provider-router.yml | DONE |
| provider-router smoke receipt | PASS |
| Cloudflare Worker source | READY |
| feature flag | ROUTER_WORKFLOW_ID=provider-router.yml |
| rollback flag | ROUTER_WORKFLOW_ID=codex-local.yml |

## Required operator action

Deploy the current repository file to Cloudflare Worker:

`infrastructure/cloudflare-worker/telegram-webhook.js`

Confirm Worker variables:

| Variable | Value |
|---|---|
| TELEGRAM_BOT_TOKEN | existing bot token |
| GH_PAT | GitHub PAT with actions/workflow access |
| GH_REPO | bereznyi-aleksandr/ai-devops-system |
| ROUTER_WORKFLOW_ID | provider-router.yml |

## Live test

1. Send a Telegram message to the bot.
2. Expected first response:
   `⚡ Получено. Передано в provider-router.yml (trace: tg_...)`
3. For forced fallback test, create fresh provider status:
   `providers.gpt_codex.status=quota_exceeded`
4. Expected receipt:
   `governance/proofs/BEM932_provider_router_<trace>.json`
5. Expected provider selection under quota:
   `provider_selected=claude_code`
   `fallback_reason=fallback_quota`

## Boundary note

GPT cannot deploy to the user's Cloudflare account from this environment. Repo-side automation is complete; live runtime deployment remains operator-side unless Cloudflare API credentials are provided in a callable workflow.
