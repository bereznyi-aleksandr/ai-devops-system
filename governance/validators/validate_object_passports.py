import json
from pathlib import Path

REQUIRED = {"id", "name", "type", "vertical_level", "prompt_ref", "responsibilities", "reports_to"}


def validate(path="governance/objects/object_passports
