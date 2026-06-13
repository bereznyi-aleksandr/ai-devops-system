# BEM-932 Cloudflare runtime unblock

Status: BLOCKED_MISSING_CLOUDFLARE_RUNTIME_CONFIG
Date: 2026-06-13T19:25:00Z

Live Telegram test proved the deployed bot still used the old codex-local path.

Repository state is ready:
- infrastructure/cloudflare-worker/telegram-webhook.js defaults to provider-router.yml
- infrastructure/cloudflare-worker/wrangler.toml sets ROUTER_WORKFLOW_ID=provider-router.yml
- provider router smoke receipt is PASS

Automatic deploy workflow receipt:
- governance/proofs/BEM932_cloudflare_worker_deploy_receipt.json
Status: BLOCKED_MISSING_CLOUDFLARE_RUNTIME_CONFIG

Required secrets for GitHub Actions deploy:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ACCOUNT_ID

Then run:
- .github/workflows/cloudflare-worker-deploy.yml

Then send one live Telegram message and verify that a receipt matching this pattern exists:
- governance/proofs/BEM932_provider_router_tg_*.json
