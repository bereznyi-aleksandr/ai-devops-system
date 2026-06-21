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
- `GPT_WEBHOOK_SECRET` — shared secret required by the `POST /gpt-dispatch` endpoint
  (see below). Without this set, `/gpt-dispatch` returns `403 FORBIDDEN` for every call.

Rules:

- Never commit secret values to the repository.
- Never place secret values in workflow inputs, receipts, outbox/inbox JSONL, logs, screenshots, or operator reports.
- Never echo secret values from the Worker or GitHub Actions.
- Rotation, creation, and deletion of live secrets are manual/operator actions in Cloudflare or `wrangler secret put`.
- Repository automation may verify secret names and boundaries, but may not read or mutate live secret values.

## GPT generic dispatch endpoint (BEM-932)

`telegram-webhook.js` exposes a second path beside the Telegram webhook:

```
POST /gpt-dispatch
Headers: x-gpt-secret: <GPT_WEBHOOK_SECRET>
Body:    { "workflow_id": "<any-workflow-file>.yml", "inputs": { ...arbitrary... } }
```

This is the canonical way for a custom GPT (Action/Connector) to trigger
**any** `workflow_dispatch`-capable workflow in this repository directly,
with no GitHub Issue, no comment, no manual Actions UI click. It reuses
the same `dispatchWorkflow()` call already proven by the Telegram path.

Configure as a ChatGPT custom GPT Action with:
- URL: `https://<your-worker-subdomain>.workers.dev/gpt-dispatch`
- Method: `POST`
- Header: `x-gpt-secret: <value matching the Worker's GPT_WEBHOOK_SECRET>`
- Body schema: `{"workflow_id": "string", "inputs": "object"}`

If `GPT_WEBHOOK_SECRET` has never been set via `wrangler secret put GPT_WEBHOOK_SECRET`,
this endpoint is deployed but inert (always 403). Verify it is set before
relying on this path; this is a live-secret check the operator must do
outside the repository, per the audit boundary below.

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
wrangler secret put GPT_WEBHOOK_SECRET
wrangler deploy
```

A successful Telegram message dispatches:

```text
provider-router.yml -> (gpt_codex or claude_code based on router decision)
```

A successful `/gpt-dispatch` call dispatches whatever `workflow_id` was given in the request body.

## Idempotency boundary

Telegram retries reuse the same `update_id`. `telegram-webhook.js` derives a deterministic `trace_id` from that update, and `provider-router.yml` checks `governance/telegram_outbox.jsonl` for the same `trace_id` before appending a fallback notice. Repeated delivery therefore cannot create a duplicate outbox event for the same Telegram update.

`/gpt-dispatch` does not generate a `trace_id` itself - the caller (GPT) must supply one inside `inputs` if the target workflow expects one, and is responsible for using a fresh value per logical task to avoid collisions.

## Current repo status

- `telegram-webhook.js` dispatches Telegram messages to `env.ROUTER_WORKFLOW_ID`.
- `telegram-webhook.js` dispatches `/gpt-dispatch` requests to whatever `workflow_id` is supplied in the request body.
- `wrangler.toml` sets `ROUTER_WORKFLOW_ID=provider-router.yml`.
- Runtime tokens are not committed to the repository.
- `.github/workflows/issue-to-claude-dispatch.yml` is DEPRECATED (2026-06-21) — it duplicated `/gpt-dispatch` via an unnecessary GitHub Issue indirection. Use `/gpt-dispatch` directly.
