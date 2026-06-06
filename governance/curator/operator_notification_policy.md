# BEM-931 | Operator Notification Policy

Updated: 2026-06-06
Owner: Curator
Channel: Telegram
Format: plain-text canon

## Purpose

Operator must not receive raw mailbox noise.

Operator receives only curated, compressed, decision-ready reports.

## Channels

1. mailbox_watcher
   - Reads Claude/GPT mailbox.
   - Updates state and reports.
   - Does not send raw operational messages to operator by default.

2. curator_hourly_report
   - Runs every hour.
   - Reads recent repository changes and mailbox watcher report.
   - Asks Curator to produce a canonical operator report.
   - Sends result to Telegram through governance/telegram_outbox.jsonl.

3. urgent_operator_alert
   - Only for BLOCKED, security, billing, failed autonomous loop, broken Telegram, broken GitHub writes.
   - Must be short and canonical.

## Hourly Report Rule

Every hour Curator sends one report to Telegram.

Report must include:

- header: BEM / task / timestamp
- status: OK / WARNING / BLOCKED
- changes in repository for the last hour
- mailbox decisions for the last hour or latest watcher state
- active tasks or empty queue
- risks
- one next action, only if operator action is required

Report must not include:

- raw mailbox dumps
- secrets
- full tokens
- noisy logs
- repeated stack traces
- internal prompts
- markdown tables unless operator requested

## Canonical Telegram Format

Use plaintext.

Template:

```text
BEM-HOURLY | OPERATOR REPORT | <timestamp UTC+3>

СТАТУС:
<OK / WARNING / BLOCKED>

ИЗМЕНЕНИЯ ЗА ЧАС:
- <item or none>

MAILBOX:
- <decision summary or none>

ACTIVE_QUEUE:
- <state>

РИСКИ:
- <risk or none>

ДЕЙСТВИЕ ОПЕРАТОРА:
<one action or "не требуется">
```

## Mailbox Wake Rule

Mailbox watcher may wake the system by writing state/report.

It should not directly spam operator with each raw message.

Curator converts watcher findings into:
- hourly report, or
- urgent alert if severity requires immediate operator action.

## Urgent Alert Criteria

Send immediate Telegram alert only if:

- decision == BLOCKED
- decision == CHANGE_REQUIRED with HIGH priority
- GitHub write failed
- Telegram dispatch failed
- LLM provider failed
- billing/quota blocks runtime
- security/secrets leakage risk

## Current Implementation Files

- .github/workflows/audit-mailbox-watcher.yml
- scripts/audit_mailbox_watcher.py
- governance/state/audit_mailbox_watcher_state.json
- governance/reports/audit_mailbox_watcher_report.md
- .github/workflows/operator-hourly-curator-report.yml
- governance/telegram_outbox.jsonl
- .github/workflows/telegram-outbox-dispatch.yml
