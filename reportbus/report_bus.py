import json
import os
import tempfile
from datetime import datetime


REPORTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "results",
    "reports.json",
)


class ReportBus:

    def __init__(self, reports_path: str = None):
        self.reports_path = reports_path or REPORTS_PATH

    def _load(self) -> list:
        if not os.path.exists(self.reports_path):
            return []
        try:
            with open(self.reports_path, "r") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, reports: list) -> None:
        os.makedirs(os.path.dirname(self.reports_path), exist_ok=True)
        dir_name = os.path.dirname(self.reports_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(reports, f, indent=2)
            os.replace(tmp_path, self.reports_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def write(self, agent_name: str, action: str, result, policy_rule=None, anomaly=None) -> dict:
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": agent_name,
            "action": action,
            "result": result,
            "policy_rule": policy_rule,
            "anomaly": anomaly,
        }
        reports = self._load()
        reports.append(entry)
        self._save(reports)
        return entry

    def read_recent(self, limit: int = 10) -> list:
        reports = self._load()
        return reports[-limit:] if len(reports) > limit else reports

    def read_by_agent(self, agent_name: str, limit: int = 5) -> list:
        reports = self._load()
        filtered = [r for r in reports if r.get("agent") == agent_name]
        return filtered[-limit:] if len(filtered) > limit else filtered

    def detect_anomalies(self) -> list:
        reports = self._load()
        agents: dict = {}
        for r in reports:
            name = r.get("agent")
            if name:
                agents.setdefault(name, []).append(r.get("result"))

        anomalous = []
        for agent_name, results in agents.items():
            last3 = results[-3:]
            if len(last3) == 3 and len(set(str(x) for x in last3)) == 1:
                anomalous.append(agent_name)
        return anomalous
