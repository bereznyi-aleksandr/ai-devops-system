# REQUIRED_ENV — Telegram Cloudflare Worker

This Worker can dispatch GitHub Actions only when the Cloudflare Worker has the runtime variables and secrets below.

Live Worker code: `telegram-webhook.js`  
Live Wrangler config: `wrangler.toml`

## Non-secret variables

These values may be committed in `wrangler.toml`:

```toml
[vars]
GH_REPO = "bereznyi-aleksandr/ai-devops-system"
ALLOWED_CHAT_ID = "601442777"
ROUTER_WORKFLOW_ID = "provider-router.yml"
```

## Live runtime secret boundary

The following values are live runtime secrets and MUST exist only in Cloudflare Worker secret storage:

- `TELEGRAM_BOT_TOKEN` — Telegram bot token for acknowledgement/error replies.
- `GH_PAT` — fine-grained GitHub token allowed to call `workflow_dispatch` for this repository.
- `AI_SYSTEM_GITHUB_PAT` — accepted runtime alias for `GH_PAT`.

Rules:

- Never commit secret values to the repository.
- Never place secret values in workflow inputs, receipts, outbox/inbox JSONL, logs, screenshots, or operator reports.
- Never echo secret values from the Worker or GitHub Actions.
- Rotation, creation, and deletion of live secrets are manual/operator actions in Cloudflare or `wrangler secret put`.
- Repository automation may verify secret names and boundaries, but may not read or mutate live secret values.

## Manual and audit boundary

Repo-side/manual audits are offline and secret-free:

- They inspect committed Worker code, workflows, documentation, receipts, and redacted metadata only.
- They must not call Telegram or GitHub using live credentials.
- A manual/live probe is permitted only after an operator intentionally supplies runtime access outside the repository.
- A missing live secret is reported as a runtime boundary, not repaired by writing a token into source control.

## GitHub token minimum rights

Fine-grained PAT recommended:

- Repository access: `bereznyi-aleksandr/ai-devops-system` only
- Repository permissions:
  - Actions: `Read and write`
  - Contents: `Read`

Classic PAT minimum fallback: `repo` scope (less preferred).

## Exact runtime commands

Run from the Worker project directory where Wrangler is configured:

```bash
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put GH_PAT
wrangler deploy
```

A successful Telegram message dispatches:

```text
provider-router.yml -> (gpt_codex or claude_code based on router decision)
```

## Idempotency boundary

Telegram retries reuse the same `update_id`. `telegram-webhook.js` derives a deterministic `trace_id` from that update, and `provider-router.yml` checks `governance/telegram_outbox.jsonl` for the same `trace_id` before appending a fallback notice. Repeated delivery therefore cannot create a duplicate outbox event for the same Telegram update.

## Current repo status

- `telegram-webhook.js` dispatches to `env.ROUTER_WORKFLOW_ID`.
- `wrangler.toml` sets `ROUTER_WORKFLOW_ID=provider-router.yml`.
- Runtime tokens are not committed to the repository.
