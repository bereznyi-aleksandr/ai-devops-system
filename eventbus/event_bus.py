"""
EventBus — simple file-based event bus backed by results/events.json.

Uses only Python standard library modules.
"""

import json
import os
import time
from pathlib import Path

EVENTS_FILE = Path(__file__).parent.parent / "results" / "events.json"


class EventBus:
    """Read/write events from a local JSON file (results/events.json)."""

    def __init__(self, events_file: Path = EVENTS_FILE):
        self._path = Path(events_file)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> list:
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, events: list) -> None:
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(events, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish(self, event_type: str, payload: dict) -> dict:
        """Append a new event to the events file.

        Returns the stored event record.
        """
        events = self._load()
        event = {
            "event_type": event_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": payload,
        }
        events.append(event)
        self._save(events)
        return event

    def subscribe(self, event_type: str) -> dict | None:
        """Return the most recent event of the given type, or None."""
        events = self._load()
        matches = [e for e in events if e.get("event_type") == event_type]
        return matches[-1] if matches else None

    def clear(self) -> None:
        """Remove all events from the events file."""
        self._save([])
