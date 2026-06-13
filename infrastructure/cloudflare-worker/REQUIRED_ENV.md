# REQUIRED_ENV - Telegram Cloudflare Worker

This Worker can dispatch GitHub Actions only if the Cloudflare Worker has the runtime vars/secrets below.

Live Worker code: `telegram-webhook.js`
Live Wrangler config: `wrangler.toml`

## Non-secret vars

These are already committed in `wrangler.toml`:

```toml
[vars]
GH_REPO = "bereznyi-aleksandr/ai-devops-system"
ALLOWED_CHAT_ID = "601442777"
ROUTER_WORKFLOW_ID = "provider-router.yml"
```

## Secrets

These MUST be set in Cloudflare Worker Settings -> Variables, or with `wrangler secret put`:

- `TELEGRAM_BOT_TOKEN` - Telegram bot token for ack/error replies.
- `GH_PAT` - GitHub token able to call `workflow_dispatch` for the repo.

## GitHub token minimum rights

Fine-grained PAT recommended:

- Repository access: `bereznyi-aleksandr/ai-devops-system` only
- Repository permissions:
  - Actions: `Read and write`
  - Contents: `Read`

Classic PAT minimum fallback: `repo` scope (less preferred).

## Exact commands

From `internal/cloudflare-worker` or the Worker project dir where wrangler is configured:

```bash
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put GH_PAT
wrangler deploy
```

A successful Telegram message will dispatch:

```text
provider-router.yml -> (gpt_codex or claude_code based on router decision)
```

## Current repo status

- `telegram-webhook.js` already dispatches to `env.ROUTER_WORKFLOW_ID`.
- `wrangler.toml` already sets `ROUTER_WORKFLOW_ID=provider-router.yml`.
- No secrets are committed to repository.
