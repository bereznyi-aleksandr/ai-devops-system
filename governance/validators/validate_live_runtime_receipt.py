import json
from pathlib import Path

FORBIDDEN_KEYS = {"openai_api_key", "api_key", "token", "secret", "pat", "raw_credentials"}
FORBIDDEN_ACTIONS = {"codex_cli", "paid_api_without_operator_gate", "secret_value_write"}
REQUIRED_KEYS = {"trace_id", "timestamp_utc3", "logical_role", "provider_id", "provider_mode",
