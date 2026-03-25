import os
import json
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime


class InvalidDecisionContractError(Exception):
    pass


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
        self.saved_at = None


class RuntimeEngine:

    def __init__(self):
        self.runtime = RuntimeState()
        self.baseline = BaselineState()
        self.project_id = os.getenv("GCP_PROJECT", "barber-483016")
        self.region = os.getenv("CLOUD_RUN_REGION", "europe-west4")
        self.service_name = os.getenv("CLOUD_RUN_SERVICE", "barber-app")
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        self.baseline_gcs_bucket = os.getenv("BASELINE_GCS_BUCKET", "barber-agent-state")
        self.baseline_gcs_object = os.getenv("BASELINE_GCS_OBJECT", "baseline.json")
        self.history_gcs_object = os.getenv("HISTORY_GCS_OBJECT", "execution-history.json")
        self.history_limit = 10
        self.history_payload_limit = 5
        self.history = []
        self.allowed_actions = ("no_action", "investigate", "collect_state")
        self.allowed_next_goals = (
            "monitor_runtime_stability",
            "monitor_revision_drift",
            "watch_baseline_consistency",
            "watch_llm_response_reliability",
            "collect_more_state_on_repeat_fallback",
        )
        self.allowed_risky_intents = (
            "none",
            "propose_baseline_update",
            "propose_manual_deploy_review",
            "propose_manual_rollback_review",
        )
        self.allowed_approval_statuses = (
            "not_required",
            "required",
            "granted",
            "rejected",
        )
        self.allowed_repo_observation_statuses = (
            "ready",
            "blocked",
        )
        self.repo_root = os.path.expanduser("~/ai-devops-system")
        self.repo_branch = None
        self.repo_clean_tree = None
        self.repo_target_allowlist = ("agent/runtime_engine.py",)
        self.repo_target_status = None
        self.repo_observation_status = None
        self.repo_action_class = "repo_read_only"
        self.repo_deny_reason = None
        self.llm_test_mode = os.getenv("LLM_TEST_MODE", "off")
        self.last_decision_source = None
        self.last_reason_summary = None
        self.last_next_goal = None
        self.last_risky_intent = None
        self.last_approval_status = None

    def _run_repo_command(self, args):
        completed = subprocess.run(
            args,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()

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

    def observe_repo(self):
        print("REPO: observing repository state")

        self.repo_branch = None
        self.repo_clean_tree = None
        self.repo_target_status = "allowlist_unverified"
        self.repo_observation_status = "blocked"
        self.repo_action_class = "repo_read_only"
        self.repo_deny_reason = None

        print("Repo root:", self.repo_root)

        if not os.path.isdir(self.repo_root):
            self.repo_deny_reason = "repo_root_missing"
            print("Repo allowlist verified: false")
            print("Repo observation status:", self.repo_observation_status)
            print("Repo deny reason:", self.repo_deny_reason)
            return

        git_dir = os.path.join(self.repo_root, ".git")
        if not os.path.exists(git_dir):
            self.repo_deny_reason = "git_metadata_missing"
            print("Repo allowlist verified: false")
            print("Repo observation status:", self.repo_observation_status)
            print("Repo deny reason:", self.repo_deny_reason)
            return

        try:
            branch = self._run_repo_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            if not branch or branch == "HEAD":
                self.repo_deny_reason = "repo_branch_unresolved"
                print("Repo branch: unresolved")
                print("Repo allowlist verified: false")
                print("Repo observation status:", self.repo_observation_status)
                print("Repo deny reason:", self.repo_deny_reason)
                return

            self.repo_branch = branch
            print("Repo branch:", self.repo_branch)

            porcelain = self._run_repo_command(["git", "status", "--porcelain"])
            self.repo_clean_tree = porcelain == ""
            print("Repo clean tree:", str(self.repo_clean_tree).lower())

            allowlist_verified = True
            for relative_path in self.repo_target_allowlist:
                absolute_path = os.path.join(self.repo_root, relative_path)

                if not os.path.isfile(absolute_path):
                    allowlist_verified = False
                    self.repo_deny_reason = f"allowlist_target_missing:{relative_path}"
                    break

            print("Repo allowlist verified:", str(allowlist_verified).lower())

            if not allowlist_verified:
                print("Repo observation status:", self.repo_observation_status)
                print("Repo deny reason:", self.repo_deny_reason)
                return

            self.repo_target_status = "allowlist_verified"

            if not self.repo_clean_tree:
                self.repo_deny_reason = "working_tree_dirty"
                print("Repo observation status:", self.repo_observation_status)
                print("Repo deny reason:", self.repo_deny_reason)
                return

            self.repo_observation_status = "ready"

            if self.repo_observation_status not in self.allowed_repo_observation_statuses:
                raise RuntimeError(
                    f"unsupported repo observation status selected: {self.repo_observation_status}"
                )

            print("Repo observation status:", self.repo_observation_status)

        except subprocess.CalledProcessError as e:
            self.repo_deny_reason = "repo_command_failed"
            print("Repo command failed:", e)
            print("Repo allowlist verified: false")
            print("Repo observation status:", self.repo_observation_status)
            print("Repo deny reason:", self.repo_deny_reason)

        except Exception as e:
            self.repo_deny_reason = "repo_observation_failed"
            print("Repo observation failed:", e)
            print("Repo allowlist verified: false")
            print("Repo observation status:", self.repo_observation_status)
            print("Repo deny reason:", self.repo_deny_reason)

    def load_baseline(self):
        print("BASELINE: loading baseline from GCS")

        object_name = urllib.parse.quote(self.baseline_gcs_object, safe="")
        url = (
            f"https://storage.googleapis.com/storage/v1/b/"
            f"{self.baseline_gcs_bucket}/o/{object_name}?alt=media"
        )

        try:
            with self._gcs_request("GET", url, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.baseline.service = payload.get("service")
            self.baseline.revision = payload.get("revision")
            self.baseline.image = payload.get("image")
            self.baseline.url = payload.get("url")
            self.baseline.saved_at = payload.get("saved_at")

            print("Baseline loaded from GCS")

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("Baseline not found in GCS")
                return

            print("Baseline load failed:", e)
            raise

        except Exception as e:
            print("Baseline load failed:", e)
            raise

    def save_baseline_from_runtime(self):
        print("BASELINE: saving baseline to GCS")

        payload = {
            "service": self.runtime.service,
            "revision": self.runtime.revision,
            "image": self.runtime.image,
            "url": self.runtime.url,
            "saved_at": datetime.utcnow().isoformat() + "Z",
        }

        object_name = urllib.parse.quote(self.baseline_gcs_object, safe="")
        url = (
            f"https://storage.googleapis.com/upload/storage/v1/b/"
            f"{self.baseline_gcs_bucket}/o?uploadType=media&name={object_name}"
        )

        data = json.dumps(payload).encode("utf-8")

        try:
            with self._gcs_request(
                "POST",
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                timeout=30,
            ):
                pass

            self.baseline.service = payload.get("service")
            self.baseline.revision = payload.get("revision")
            self.baseline.image = payload.get("image")
            self.baseline.url = payload.get("url")
            self.baseline.saved_at = payload.get("saved_at")

            print("Baseline saved to GCS")

        except Exception as e:
            print("Baseline save failed:", e)
            raise

    def load_history(self):
        print("HISTORY: loading execution history from GCS")

        object_name = urllib.parse.quote(self.history_gcs_object, safe="")
        url = (
            f"https://storage.googleapis.com/storage/v1/b/"
            f"{self.baseline_gcs_bucket}/o/{object_name}?alt=media"
        )

        try:
            with self._gcs_request("GET", url, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))

            if not isinstance(payload, list):
                raise RuntimeError("execution history payload must be a JSON list")

            self.history = payload[-self.history_limit:]
            print("History loaded from GCS")

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("History not found in GCS")
                self.history = []
                return

            print("History load failed:", e)
            raise

        except Exception as e:
            print("History load failed:", e)
            raise

    def save_history(self):
        print("HISTORY: saving execution history to GCS")

        object_name = urllib.parse.quote(self.history_gcs_object, safe="")
        url = (
            f"https://storage.googleapis.com/upload/storage/v1/b/"
            f"{self.baseline_gcs_bucket}/o?uploadType=media&name={object_name}"
        )

        data = json.dumps(self.history).encode("utf-8")

        try:
            with self._gcs_request(
                "POST",
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                timeout=30,
            ):
                pass

            print("History saved to GCS")

        except Exception as e:
            print("History save failed:", e)
            raise

    def observe_runtime(self):
        print("OBSERVE: collecting runtime state")

        try:
            access_token = self._get_gcp_access_token()
            service_path = (
                f"projects/{self.project_id}/locations/{self.region}/services/{self.service_name}"
            )

            request = urllib.request.Request(
                f"https://run.googleapis.com/v2/{service_path}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                method="GET",
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            containers = data.get("template", {}).get("containers", []) or []
            first = containers[0] if containers else {}

            self.runtime.service = self.service_name
            self.runtime.url = data.get("uri")
            self.runtime.revision = data.get("latestReadyRevision")
            self.runtime.image = first.get("image")

            print("Runtime state collected")

        except Exception as e:
            print("Runtime observation failed:", e)

    def analyze(self):
        print("ANALYZE: comparing runtime with baseline")

        if self.baseline.revision is None:
            print("No baseline defined, creating baseline")
            self.save_baseline_from_runtime()
            return "baseline_created"

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

    def _normalize_llm_content(self, content):
        return self._clean_json_content(content)

    def _parse_llm_decision(self, content):
        print("LLM response parsing started")
        normalized = self._normalize_llm_content(content)
        decision = json.loads(normalized)
        print("LLM response parsed")
        return decision

    def validate_decision(self, decision):
        if not isinstance(decision, dict):
            raise InvalidDecisionContractError("decision must be a JSON object")

        required_keys = ("action", "reason", "next_steps")

        for key in required_keys:
            if key not in decision:
                raise InvalidDecisionContractError(f"missing required key: {key}")

        action = decision.get("action")
        reason = decision.get("reason")
        next_steps = decision.get("next_steps")

        if action not in self.allowed_actions:
            raise InvalidDecisionContractError(f"unsupported action: {action}")

        if not isinstance(reason, str):
            raise InvalidDecisionContractError("reason must be a string")

        if not isinstance(next_steps, list):
            raise InvalidDecisionContractError("next_steps must be a list")

        print("LLM response contract valid")
        return decision

    def _history_payload(self):
        return self.history[-self.history_payload_limit:]

    def _reason_summary_from_llm(self, analysis, decision):
        action = decision.get("action", "unknown_action")
        return f"{analysis}_llm_{action}"

    def _reason_summary_from_fallback(self, analysis, reason):
        normalized_reason = (
            reason.lower()
            .replace(" ", "_")
            .replace(":", "")
            .replace("/", "_")
        )
        return f"{analysis}_fallback_{normalized_reason}"

    def _get_simulated_llm_content(self):
        if self.llm_test_mode == "invalid_json":
            return '{"action": "no_action", "reason": "broken"'

        if self.llm_test_mode == "missing_next_steps":
            return json.dumps({
                "action": "no_action",
                "reason": "Simulated missing next_steps",
            })

        if self.llm_test_mode == "unsupported_action":
            return json.dumps({
                "action": "deploy_now",
                "reason": "Simulated unsupported action",
                "next_steps": [],
            })

        return None

    def ask_anthropic(self, analysis):
        if self.llm_test_mode == "request_error":
            raise urllib.error.HTTPError(
                url="https://api.anthropic.com/v1/messages",
                code=503,
                msg="Simulated request error",
                hdrs=None,
                fp=None,
            )

        simulated_content = self._get_simulated_llm_content()

        if simulated_content is not None:
            decision = self._parse_llm_decision(simulated_content)
            return self.validate_decision(decision)

        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

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
                "saved_at": self.baseline.saved_at,
            },
            "history": self._history_payload(),
        }

        body = {
            "model": self.model,
            "max_tokens": 256,
            "system": (
                "You are a deterministic DevOps decision engine. "
                "Return only valid JSON with keys: action, reason, next_steps. "
                "Allowed action values: no_action, investigate, collect_state."
            ),
            "messages": [
                {"role": "user", "content": json.dumps(user_payload)}
            ],
            "temperature": 0,
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
        decision = self._parse_llm_decision(content)
        return self.validate_decision(decision)

    def _deterministic_fallback(self, analysis):
        if analysis in ("healthy", "baseline_created"):
            return "no_action"

        if analysis == "drift":
            return "investigate"

        return "collect_state"

    def select_fallback_action(self, analysis, reason):
        print("Fallback reason:", reason)
        action = self._deterministic_fallback(analysis)
        print("Fallback action selected:", action)
        self.last_decision_source = "fallback"
        self.last_reason_summary = self._reason_summary_from_fallback(analysis, reason)
        return action

    def decide(self, analysis):
        print("DECIDE: selecting action")

        if self.llm_test_mode != "off":
            print("LLM test mode active:", self.llm_test_mode)

        try:
            decision = self.ask_anthropic(analysis)
            action = decision.get("action")
            self.last_decision_source = "llm"
            self.last_reason_summary = self._reason_summary_from_llm(analysis, decision)
            print("Decision source: llm")
            print("LLM decision:", decision)
            return action

        except urllib.error.HTTPError as e:
            print("LLM request failed:", e)
            print("Decision source: fallback")
            return self.select_fallback_action(analysis, "LLM request failure")

        except json.JSONDecodeError as e:
            print("LLM response parse failed:", e)
            print("Decision source: fallback")
            return self.select_fallback_action(analysis, "invalid JSON response")

        except InvalidDecisionContractError as e:
            print("LLM response contract invalid:", e)
            print("Decision source: fallback")
            return self.select_fallback_action(analysis, "invalid LLM response contract")

        except Exception as e:
            print("LLM decision failed:", e)
            print("Decision source: fallback")
            return self.select_fallback_action(analysis, "unexpected LLM decision error")

    def _recent_history(self, limit):
        return self.history[-limit:]

    def _recent_fallback_count(self, limit=3):
        records = self._recent_history(limit)
        return sum(1 for record in records if record.get("decision_source") == "fallback")

    def _recent_drift_count(self, limit=3):
        records = self._recent_history(limit)
        return sum(1 for record in records if record.get("analysis") == "drift")

    def _recent_non_healthy_count(self, limit=3):
        records = self._recent_history(limit)
        return sum(1 for record in records if record.get("analysis") != "healthy")

    def _last_history_goal(self):
        if not self.history:
            return None
        return self.history[-1].get("next_goal")

    def _deterministic_next_goal(self, analysis, action):
        if analysis == "baseline_created":
            return "watch_baseline_consistency"

        if analysis == "drift":
            return "monitor_revision_drift"

        if self.last_decision_source == "fallback":
            recent_fallback_count = self._recent_fallback_count(limit=3)
            if recent_fallback_count >= 2:
                print("Goal selected from recent fallback trend")
                return "collect_more_state_on_repeat_fallback"
            return "watch_llm_response_reliability"

        if analysis == "healthy" and action == "no_action":
            return "monitor_runtime_stability"

        return "watch_baseline_consistency"

    def select_next_goal(self, analysis, action):
        print("GOAL: selecting next goal")
        next_goal = self._deterministic_next_goal(analysis, action)

        if next_goal not in self.allowed_next_goals:
            raise RuntimeError(f"unsupported next goal selected: {next_goal}")

        self.last_next_goal = next_goal
        print("Next goal selected:", next_goal)
        return next_goal

    def _deterministic_risky_intent(self, analysis, action, next_goal):
        recent_fallback_count = self._recent_fallback_count(limit=3)
        recent_drift_count = self._recent_drift_count(limit=3)
        recent_non_healthy_count = self._recent_non_healthy_count(limit=3)

        if analysis == "baseline_created":
            return "propose_baseline_update"

        if analysis == "drift":
            if recent_fallback_count >= 2 or recent_drift_count >= 2 or recent_non_healthy_count >= 2:
                return "propose_manual_rollback_review"
            return "propose_manual_deploy_review"

        if analysis == "healthy" and action == "no_action" and next_goal == "monitor_runtime_stability":
            return "none"

        return "none"

    def _deterministic_approval_status(self, risky_intent):
        if risky_intent == "none":
            return "not_required"
        return "required"

    def evaluate_approval_boundary(self, analysis, action, next_goal):
        print("APPROVAL: evaluating risk boundary")
        risky_intent = self._deterministic_risky_intent(analysis, action, next_goal)
        approval_status = self._deterministic_approval_status(risky_intent)

        if risky_intent not in self.allowed_risky_intents:
            raise RuntimeError(f"unsupported risky intent selected: {risky_intent}")

        if approval_status not in self.allowed_approval_statuses:
            raise RuntimeError(f"unsupported approval status selected: {approval_status}")

        self.last_risky_intent = risky_intent
        self.last_approval_status = approval_status

        print("Risky intent selected:", risky_intent)
        print("Approval status:", approval_status)

        return risky_intent, approval_status

    def build_history_record(
        self,
        analysis,
        action,
        decision_source,
        reason_summary,
        next_goal,
        risky_intent,
        approval_status,
    ):
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "analysis": analysis,
            "decision_source": decision_source,
            "action": action,
            "reason_summary": reason_summary,
            "runtime_revision": self.runtime.revision,
            "baseline_revision": self.baseline.revision,
            "llm_test_mode": self.llm_test_mode,
            "next_goal": next_goal,
            "risky_intent": risky_intent,
            "approval_status": approval_status,
            "repo_branch": self.repo_branch,
            "repo_clean_tree": self.repo_clean_tree,
            "repo_action_class": self.repo_action_class,
            "repo_observation_status": self.repo_observation_status,
            "repo_deny_reason": self.repo_deny_reason,
        }

    def append_history_record(self, analysis, action):
        print("HISTORY: appending execution record")

        record = self.build_history_record(
            analysis=analysis,
            action=action,
            decision_source=self.last_decision_source,
            reason_summary=self.last_reason_summary,
            next_goal=self.last_next_goal,
            risky_intent=self.last_risky_intent,
            approval_status=self.last_approval_status,
        )

        self.history.append(record)
        self.history = self.history[-self.history_limit:]
        self.save_history()

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
        self.observe_repo()
        self.load_baseline()
        self.load_history()

        analysis = self.analyze()
        action = self.decide(analysis)
        next_goal = self.select_next_goal(analysis, action)
        self.evaluate_approval_boundary(analysis, action, next_goal)
        self.append_history_record(analysis, action)

        self.act(action)


if __name__ == "__main__":
    engine = RuntimeEngine()
    engine.run()
