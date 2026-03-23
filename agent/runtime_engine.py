import os
import subprocess
import json
import urllib.request
import urllib.error
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
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

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

    def _clean_json_content(self, content):
        cleaned = content.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return cleaned.strip()

    def ask_anthropic(self, analysis):
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

        system_prompt = (
            "You are a deterministic DevOps decision engine. "
            "Return only valid JSON with keys: action, reason, next_steps. "
            "Allowed action values: no_action, investigate, collect_state."
        )

        user_payload = {
            "analysis": analysis,
            "runtime": {
                "service": self.runtime.service,
                "revision": self.runtime.revision,
                "image": self.runtime.image,
                "url": self.runtime.url,
            },
            "baseline": {
                "service": self.baseline.service,
                "revision": self.baseline.revision,
                "image": self.baseline.image,
                "url": self.baseline.url,
            },
        }

        body = {
            "model": self.model,
            "max_tokens": 256,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": json.dumps(user_payload)}
            ],
            "temperature": 0
        }

        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")

        payload = json.loads(raw)
        content = payload["content"][0]["text"]
        cleaned = self._clean_json_content(content)
        return json.loads(cleaned)

    def decide(self, analysis):
        print("DECIDE: selecting action")

        try:
            decision = self.ask_anthropic(analysis)
            action = decision.get("action")

            if action not in ("no_action", "investigate", "collect_state"):
                raise ValueError(f"Unsupported action: {action}")

            print("LLM decision:", decision)
            return action

        except Exception as e:
            print("LLM decision failed, fallback to deterministic path:", e)

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
