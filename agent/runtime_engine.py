import os
import subprocess
import json
from datetime import datetime


class RuntimeState:

    def __init__(self):
        self.service = None
        self.revision = None
        self.image = None
        self.url = None
        self.environment = None


class BaselineState:

    def __init__(self):
        self.service = None
        self.revision = None
        self.image = None
        self.url = None


class RuntimeEngine:

    def __init__(self):
        self.runtime = RuntimeState()
        self.baseline = BaselineState()

    def observe_runtime(self):
        print("OBSERVE: collecting runtime state")

        try:
            cmd = [
                "gcloud",
                "run",
                "services",
                "describe",
                "barber-app",
                "--region",
                "europe-west1",
                "--format=json"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            data = json.loads(result.stdout)

            self.runtime.service = data["metadata"]["name"]
            self.runtime.url = data["status"]["url"]
            self.runtime.revision = data["status"]["latestReadyRevisionName"]

            container = data["spec"]["template"]["spec"]["containers"][0]
            self.runtime.image = container["image"]

            print("Runtime state collected")

        except Exception as e:
            print("Runtime observation failed:", e)

    def analyze(self):
        print("ANALYZE: comparing runtime with baseline")

        if self.baseline.revision is None:
            print("No baseline defined")
            return "unknown"

        if self.runtime.revision != self.baseline.revision:
            print("Revision drift detected")
            return "drift"

        print("System healthy")
        return "healthy"

    def decide(self, analysis):
        print("DECIDE: selecting action")

        if analysis == "healthy":
            return "no_action"

        if analysis == "drift":
            return "investigate"

        return "collect_state"

    def act(self, action):
        print("ACT:", action)

        if action == "no_action":
            print("System stable")

        elif action == "investigate":
            print("Manual verification required")

        elif action == "collect_state":
            print("Collecting additional system state")

    def run(self):
        print("AI DevOps Runtime Engine Started")
        print("Timestamp:", datetime.utcnow())

        self.observe_runtime()

        analysis = self.analyze()

        action = self.decide(analysis)

        self.act(action)


if __name__ == "__main__":
    engine = RuntimeEngine()
    engine.run()
