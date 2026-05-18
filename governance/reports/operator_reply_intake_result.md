# BEM-602 | Operator Reply Intake Result

## Status
blocked

## HTTP
getUpdates: 409
getWebhookInfo: 200
webhook_active: True

## Record
null

## Blocker
{
  "code": "TELEGRAM_WEBHOOK_ACTIVE",
  "message": "Webhook is active; polling getUpdates may not receive replies reliably."
}
