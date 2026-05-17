# BEM-541.3 | Telegram Outbox Sender Contract

Дата: 2026-05-17 | 14:24 (UTC+3)

## Цель
Довести Telegram reporting от `governance/telegram_outbox.jsonl` до фиксируемого delivery status.

## Pipeline
`curator-hourly-report.yml -> governance/telegram_outbox.jsonl -> sender -> telegram_delivery_result -> governance/transport/results.jsonl`

## Runtime secrets
- Telegram token/chat_id используются только runtime sender environment.
- Токены, chat_id, client_secret и callback URL запрещено писать в repo files.

## Outbox record
```json
{
  "record_type": "telegram_hourly_report",
  "cycle_id": "string",
  "status": "queued_for_sender",
  "message": "string",
  "created_at": "YYYY-MM-DD | HH:MM (UTC+3)",
  "blocker": null
}
```

## Delivery result record
```json
{
  "record_type": "telegram_delivery_result",
  "cycle_id": "string",
  "source": "telegram_sender",
  "status": "sent|sent_synthetic|failed|retry_scheduled",
  "outbox_line": 0,
  "message_hash": "string",
  "attempt": 1,
  "retry_allowed": true,
  "next_retry_at": "YYYY-MM-DD | HH:MM (UTC+3)|null",
  "blocker": null
}
```

## Rules
- No token in files.
- Delivery result must be append-only.
- Failed delivery must include retry fields.
- Hourly workflow may schedule only under contract exception `curator-hourly-report.yml`.
