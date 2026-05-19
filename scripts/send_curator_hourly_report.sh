#!/usr/bin/env bash
set -euo pipefail
mkdir -p governance/tmp
MESSAGE_FILE="governance/tmp/curator_hourly_report_message.txt"
RESPONSE_FILE="governance/tmp/curator_hourly_report_response.json"
STATUS_FILE="governance/tmp/curator_hourly_report_delivery.txt"
if [[ ! -s "$MESSAGE_FILE" ]]; then
  echo "missing_message" > "$STATUS_FILE"
  exit 0
fi
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  echo "not_sent_missing_secret" > "$STATUS_FILE"
  printf '{"ok":false,"description":"missing secret"}\n' > "$RESPONSE_FILE"
  exit 0
fi
HTTP_CODE=$(curl -sS -o "$RESPONSE_FILE" -w "%{http_code}" -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode text@"$MESSAGE_FILE")
if [[ "$HTTP_CODE" == "200" ]]; then
  echo "sent" > "$STATUS_FILE"
else
  echo "not_sent_http_${HTTP_CODE}" > "$STATUS_FILE"
fi
