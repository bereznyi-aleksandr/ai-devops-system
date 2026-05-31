import json
from pathlib import Path

FORBIDDEN_KEYS = {"token", "secret", "pat", "api_key", "bot_token", "webhook_secret_value"}
REQUIRED_KEYS = {"trace_id", "timestamp_utc3", "webhook_route", "telegram_envelope_ref", "managed_channel_ref", "target_curator", "receipt_status", "proof_ref"}


def validate_receipt(payload):
    errors = []
    missing = sorted(REQUIRED_KEYS -
