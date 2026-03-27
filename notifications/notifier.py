import json
import os
from datetime import datetime, timezone

NOTIFICATIONS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "results", "notifications.json"
)

CRITICAL_EVENT_TYPES = {
    "drift_detected",
    "agent_failure",
    "orchestrator_error",
    "critical",
}


class Notifier:
    def __init__(self, notifications_file: str = NOTIFICATIONS_FILE):
        self.notifications_file = os.path.abspath(notifications_file)
        os.makedirs(os.path.dirname(self.notifications_file), exist_ok=True)

    def _load(self) -> list:
        if os.path.exists(self.notifications_file):
            with open(self.notifications_file, "r") as f:
                return json.load(f)
        return []

    def _save(self, records: list) -> None:
        with open(self.notifications_file, "w") as f:
            json.dump(records, f, indent=2)

    def notify(self, event_type: str, message: str) -> dict:
        record = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event_type": event_type,
            "message": message,
            "critical": event_type in CRITICAL_EVENT_TYPES,
        }
        records = self._load()
        records.append(record)
        self._save(records)
        return record


if __name__ == "__main__":
    import py_compile, sys

    py_compile.compile(__file__, doraise=True)
    n = Notifier()
    r = n.notify("drift_detected", "Revision drift detected in runtime engine")
    assert r["critical"] is True
    assert r["event_type"] == "drift_detected"
    assert "timestamp" in r
    print(f"NOTIFIER OK: event_type={r['event_type']}, critical={r['critical']}, ts={r['timestamp']}")
