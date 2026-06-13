# BEM-932 Cloudflare deploy without UI button

Context: Cloudflare deploy button is not active / not available.

The preferred path is now GitHub Actions; the button is not the operational gate.

## Already done

- Worker source is at `infrastructure/cloudflare-worker/telegram-webhook.js`.
- Wrangler config is at `infrastructure/cloudflare-worker/wrangler.toml`.
- Deploy workflow is `.github/workflows/cloudflare-worker-deploy.yml`.
- Receipt is `governance/proofs/BEM932_cloudflare_worker_deploy_receipt.json`.

## Current blocker

The latest deploy attempt returned:

```text
BLOCKED_MISSING_CLOUDFLARE_RUNTIME_CONFIG
```

Required GitHub Actions secrets:

| Secret | Purpose |
|---|---|
| `CLOUDFLARE_API_TOKEN` | Write/deploy Worker via Wrangler |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account target |
| `TELEGRAM_BOT_TOKEN` | Written as Worker secret if present |
| `GH_PAT` | Written as Worker secret if present |

## Operator steps

1. GitHub repo -> Settings -> Secrets and variables -> Actions -> New repository secret.
2. Add `CLOUDFLARE_API_TOKEN`.
3. Add `CLOUDFLARE_ACCOUNT_ID` as the account id, not worker id.
4. If Worker secrets are not already in Cloudflare, add `TELEGRAM_BOT_TOKEN` and `GH_PAT`.
5. Run Actions: `BEM-932 Cloudflare Worker Deploy`.
6. Check `governance/proofs/BEM932_cloudflare_worker_deploy_receipt.json`. PASS means deployed.

## Note

The Cloudflare UI deploy button is not needed for release; the action writes a receipt and is the auditable deploy path.
