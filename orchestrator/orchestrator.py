import os
import json
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime


class InvalidAgentConfigError(Exception):
    pass


class Orchestrator:

    def __init__(self):
        self.agents_config_path = os.path.join(
            os.path.dirname(__file__), "agents.json"
        )
        self.agents = []
        self.results = []

        self.gcs_bucket = os.getenv("BASELINE_GCS_BUCKET", "barber-agent-state")
        self.gcs_log_object = os.getenv(
            "ORCHESTRATOR_LOG_GCS_OBJECT", "orchestrator-log.json"
        )
        self.log_limit = 50

        self.repo_root = os.path.expanduser("~/ai-devops-system")

        self.allowed_agent_keys = ("name", "script", "enabled")
        self.allowed_run_statuses = ("ok", "failed", "skipped", "disabled")

    # ------------------------------------------------------------------
    # GCP / GCS helpers (same pattern as runtime_engine.py)
    # ------------------------------------------------------------------

    def _get_gcp_access_token(self):
        request = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError("GCP access token not found in metadata response")

        return access_token

    def _gcs_request(self, method, url, data=None, headers=None, timeout=30):
        access_token = self._get_gcp_access_token()
        request_headers = {
            "Authorization": f"Bearer {access_token}",
        }
        if headers:
            request_headers.update(headers)

        request = urllib.request.Request(
            url,
            data=data,
            headers=request_headers,
            method=method,
        )
        return urllib.request.urlopen(request, timeout=timeout)

    # ------------------------------------------------------------------
    # Agent config loading
    # ------------------------------------------------------------------

    def _validate_agent_entry(self, entry, index):
        if not isinstance(entry, dict):
            raise InvalidAgentConfigError(
                f"agent entry at index {index} must be a JSON object"
            )

        name = entry.get("name")
        script = entry.get("script")
        enabled = entry.get("enabled")

        if not isinstance(name, str) or not name:
            raise InvalidAgentConfigError(
                f"agent entry at index {index} missing required string field: name"
            )

        if not isinstance(script, str) or not script:
            raise InvalidAgentConfigError(
                f"agent entry at index {index} missing required string field: script"
            )

        if not isinstance(enabled, bool):
            raise InvalidAgentConfigError(
                f"agent entry at index {index} field 'enabled' must be a boolean"
            )

    def load_agents(self):
        print("ORCHESTRATOR: loading agents from", self.agents_config_path)

        self.agents = []

        if not os.path.isfile(self.agents_config_path):
            raise FileNotFoundError(
                f"agents config not found: {self.agents_config_path}"
            )

        with open(self.agents_config_path, "r", encoding="utf-8") as f:
            raw = f.read()

        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as e:
            raise InvalidAgentConfigError(
                f"agents.json is not valid JSON: {e}"
            ) from e

        if not isinstance(entries, list):
            raise InvalidAgentConfigError("agents.json must contain a JSON array")

        for index, entry in enumerate(entries):
            self._validate_agent_entry(entry, index)

        self.agents = entries
        print(f"Agents loaded: {len(self.agents)}")
        return self.agents

    # ------------------------------------------------------------------
    # Running agents
    # ------------------------------------------------------------------

    def _resolve_script_path(self, script):
        return os.path.join(self.repo_root, script)

    def _run_agent(self, agent):
        name = agent["name"]
        script = agent["script"]

        if not agent.get("enabled", False):
            print(f"Agent skipped (disabled): {name}")
            return {
                "name": name,
                "script": script,
                "status": "disabled",
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "started_at": None,
                "finished_at": None,
                "error": None,
            }

        script_path = self._resolve_script_path(script)

        if not os.path.isfile(script_path):
            print(f"Agent skipped (script not found): {name} -> {script_path}")
            return {
                "name": name,
                "script": script,
                "status": "skipped",
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "started_at": None,
                "finished_at": None,
                "error": f"script_not_found: {script_path}",
            }

        started_at = datetime.utcnow().isoformat() + "Z"
        print(f"Agent starting: {name} ({script_path})")

        try:
            completed = subprocess.run(
                ["python3", script_path],
                capture_output=True,
                text=True,
                timeout=300,
            )
            finished_at = datetime.utcnow().isoformat() + "Z"
            status = "ok" if completed.returncode == 0 else "failed"

            print(f"Agent finished: {name} | exit={completed.returncode} | status={status}")

            if status not in self.allowed_run_statuses:
                raise RuntimeError(f"unsupported run status resolved: {status}")

            return {
                "name": name,
                "script": script,
                "status": status,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "started_at": started_at,
                "finished_at": finished_at,
                "error": None,
            }

        except subprocess.TimeoutExpired:
            finished_at = datetime.utcnow().isoformat() + "Z"
            print(f"Agent timed out: {name}")
            return {
                "name": name,
                "script": script,
                "status": "failed",
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "started_at": started_at,
                "finished_at": finished_at,
                "error": "timeout",
            }

        except Exception as e:
            finished_at = datetime.utcnow().isoformat() + "Z"
            print(f"Agent run error: {name}: {e}")
            return {
                "name": name,
                "script": script,
                "status": "failed",
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "started_at": started_at,
                "finished_at": finished_at,
                "error": str(e),
            }

    def run_all(self):
        print("ORCHESTRATOR: running all agents")

        if not self.agents:
            print("No agents loaded, call load_agents() first")
            return []

        self.results = []

        for agent in self.agents:
            result = self._run_agent(agent)
            self.results.append(result)

        ok_count = sum(1 for r in self.results if r["status"] == "ok")
        failed_count = sum(1 for r in self.results if r["status"] == "failed")
        skipped_count = sum(
            1 for r in self.results if r["status"] in ("skipped", "disabled")
        )

        print(
            f"Run complete: {len(self.results)} agents | "
            f"ok={ok_count} failed={failed_count} skipped={skipped_count}"
        )

        return self.results

    # ------------------------------------------------------------------
    # Collecting results to GCS
    # ------------------------------------------------------------------

    def _load_existing_log(self):
        object_name = urllib.parse.quote(self.gcs_log_object, safe="")
        url = (
            f"https://storage.googleapis.com/storage/v1/b/"
            f"{self.gcs_bucket}/o/{object_name}?alt=media"
        )

        try:
            with self._gcs_request("GET", url, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))

            if not isinstance(payload, list):
                print("Existing orchestrator log is not a list, resetting")
                return []

            return payload

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("Orchestrator log not found in GCS, starting fresh")
                return []
            print("Failed to load existing orchestrator log:", e)
            raise

        except Exception as e:
            print("Failed to load existing orchestrator log:", e)
            raise

    def _build_run_record(self):
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_count": len(self.agents),
            "results": self.results,
        }

    def collect_results(self):
        print("ORCHESTRATOR: collecting results to GCS")

        if not self.results:
            print("No results to collect")
            return

        existing_log = self._load_existing_log()
        existing_log.append(self._build_run_record())
        trimmed_log = existing_log[-self.log_limit:]

        object_name = urllib.parse.quote(self.gcs_log_object, safe="")
        url = (
            f"https://storage.googleapis.com/upload/storage/v1/b/"
            f"{self.gcs_bucket}/o?uploadType=media&name={object_name}"
        )

        data = json.dumps(trimmed_log).encode("utf-8")

        try:
            with self._gcs_request(
                "POST",
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                timeout=30,
            ):
                pass

            print(
                f"Orchestrator log saved to GCS "
                f"(total records: {len(trimmed_log)})"
            )

        except Exception as e:
            print("Failed to save orchestrator log to GCS:", e)
            raise

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self):
        print("Orchestrator Started")
        print("Timestamp:", datetime.utcnow())

        self.load_agents()
        self.run_all()
        self.collect_results()


if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.run()
