import os
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime
from knowledge.knowledge_store import KnowledgeStore


RESULTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "results",
    "code-agent-log.json",
)


class CodeAgent:

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.github_repo = os.getenv("GITHUB_REPO", "")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
        self.results_path = RESULTS_PATH

    def read_file_from_github(self, file_path: str) -> dict:
        if not self.github_repo:
            return {"error": "GITHUB_REPO env var not set", "content": None, "path": file_path}

        url = f"https://api.github.com/repos/{self.github_repo}/contents/{file_path}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        if self.github_token:
            req.add_header("Authorization", f"Bearer {self.github_token}")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            if data.get("encoding") == "base64":
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            else:
                content = data.get("content", "")
            return {"error": None, "content": content, "path": file_path, "sha": data.get("sha")}
        except urllib.error.HTTPError as exc:
            return {"error": f"HTTP {exc.code}: {exc.reason}", "content": None, "path": file_path}
        except Exception as exc:
            return {"error": str(exc), "content": None, "path": file_path}

    def analyze_with_claude(self, file_path: str, file_content: str) -> dict:
        if not self.anthropic_api_key:
            return {"error": "ANTHROPIC_API_KEY env var not set", "suggestion": None}

        ks = KnowledgeStore()
        recent = ks.get_recent(3)
        experience_note = ""
        if recent:
            experience_note = "\nУчти предыдущий опыт: " + str(recent) + "\n"

        prompt = (
            f"You are a code reviewer. Analyze the following file and suggest one concrete "
            f"improvement (a specific code change, not a general comment). "
            f"Respond with JSON: {{\"issue\": \"<short description>\", \"suggestion\": \"<specific change>\", "
            f"\"severity\": \"low|medium|high\"}}.\n"
            f"{experience_note}\n"
            f"File: {file_path}\n\n```\n{file_content[:8000]}\n```"
            f"{experience_note}"
        )

        payload = json.dumps({
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("x-api-key", self.anthropic_api_key)
        req.add_header("anthropic-version", "2023-06-01")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            text = data["content"][0]["text"].strip()
            # Extract JSON from the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                suggestion = json.loads(text[start:end])
            else:
                suggestion = {"issue": "parse error", "suggestion": text, "severity": "low"}
            ks.save_pattern("code_analysis", {"file": file_path, "result": "success"})
            return {"error": None, "suggestion": suggestion}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            return {"error": f"HTTP {exc.code}: {body[:200]}", "suggestion": None}
        except Exception as exc:
            return {"error": str(exc), "suggestion": None}

    def write_file_to_github(self, file_path: str, new_content: str) -> dict:
        if not self.github_repo:
            return {"error": "GITHUB_REPO env var not set", "commit_sha": None}
        if not self.github_token:
            return {"error": "GITHUB_TOKEN env var not set", "commit_sha": None}

        # Step 1: GET current SHA
        read_result = self.read_file_from_github(file_path)
        if read_result["error"]:
            return {"error": f"Failed to read file SHA: {read_result['error']}", "commit_sha": None}

        current_sha = read_result.get("sha")
        if not current_sha:
            return {"error": "Could not retrieve file SHA", "commit_sha": None}

        # Step 2: PUT new content
        branch = os.getenv("GITHUB_TARGET_BRANCH", "main")
        url = f"https://api.github.com/repos/{self.github_repo}/contents/{file_path}"

        payload = json.dumps({
            "message": f"Agent: code improvement in {file_path}",
            "content": base64.b64encode(new_content.encode("utf-8")).decode("utf-8"),
            "sha": current_sha,
            "branch": branch,
        }).encode()

        req = urllib.request.Request(url, data=payload, method="PUT")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Authorization", f"Bearer {self.github_token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            commit_sha = data.get("commit", {}).get("sha")
            return {"error": None, "commit_sha": commit_sha}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            return {"error": f"HTTP {exc.code}: {body[:200]}", "commit_sha": None}
        except Exception as exc:
            return {"error": str(exc), "commit_sha": None}

    def save_result(self, result: dict) -> bool:
        os.makedirs(os.path.dirname(self.results_path), exist_ok=True)
        log = []
        if os.path.exists(self.results_path):
            try:
                with open(self.results_path, "r") as f:
                    existing = json.load(f)
                if isinstance(existing, list):
                    log = existing
            except (json.JSONDecodeError, OSError):
                log = []
        log.append(result)
        try:
            with open(self.results_path, "w") as f:
                json.dump(log, f, indent=2)
            return True
        except OSError as exc:
            print(f"[CodeAgent] Failed to save result: {exc}")
            return False

    def run(self, file_path: str = None) -> dict:
        if file_path is None:
            file_path = os.getenv("CODE_AGENT_FILE", "agent/runtime_engine.py")

        timestamp = datetime.utcnow().isoformat() + "Z"
        result = {
            "timestamp": timestamp,
            "file_path": file_path,
            "status": "started",
            "read": None,
            "analysis": None,
        }

        read_result = self.read_file_from_github(file_path)
        result["read"] = read_result

        if read_result["error"] or not read_result["content"]:
            result["status"] = "read_error"
            self.save_result(result)
            print(f"[CodeAgent] Read error for {file_path}: {read_result['error']}")
            return result

        analysis = self.analyze_with_claude(file_path, read_result["content"])
        result["analysis"] = analysis

        if analysis["error"]:
            result["status"] = "analysis_error"
            print(f"[CodeAgent] Analysis error: {analysis['error']}")
        else:
            result["status"] = "success"
            suggestion = analysis["suggestion"]
            print(f"[CodeAgent] {file_path} — {suggestion.get('severity','?').upper()}: {suggestion.get('issue','')}")
            print(f"[CodeAgent] Suggestion: {suggestion.get('suggestion','')}")

            improved_code = suggestion.get("improved_code", "").strip() if isinstance(suggestion, dict) else ""
            if improved_code:
                print(f"[CodeAgent] Improved code found, writing to GitHub: {file_path}")
                write_result = self.write_file_to_github(file_path, improved_code)
                result["write"] = write_result
                if write_result["error"]:
                    print(f"[CodeAgent] Write error: {write_result['error']}")
                else:
                    print(f"[CodeAgent] Write commit sha: {write_result['commit_sha']}")
            else:
                result["write"] = None

        self.save_result(result)
        return result


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else None
    agent = CodeAgent()
    agent.run(target)
