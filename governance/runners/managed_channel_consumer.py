import json

REQUIRED_FIELDS = ["message_id", "source_object", "target_object", "contour", "role", "payload", "proof_policy"]


def validate_message(message):
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in message:
            errors
