import json
from pathlib import Path

REQUIRED_SCHEMA_KEYS = {"message_required_fields", "proof_policy", "allowed_roles"}
REQUIRED_MESSAGE_FIELDS = {"message_id",
