import json
from pathlib import Path

REQUIRED = {"id", "source", "risk", "rule", "applies_to"}


def validate(path="governance/experience/experience_registry
