#!/usr/bin/env python3
import json
import os
import http.client
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
QUEUE = Path("governance/workflow_dispatch_queue")
OUT = Path("governance/state/workflow_dispatch_queue_runner.json")
REPORT = Path("governance/reports/workflow_dispatch_queue_runner.md")
def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return {}
def run_dispatch(owner, repo, workflow, token):
    body = json.dumps({"ref":"main"})
    conn = http.client.HTTPSConnection("api.github.com", timeout=30)
    headers = {"Accept":"application/vnd.github+json", "Authorization":"Bearer " + token, "User-Agent":"ai-devops-system", "X-GitHub-Api-Version":"2022-11-28", "Content-Type":"application/json"}
    conn.request("POST", "/repos/" + owner + "/" + repo + "/actions/workflows/" + workflow + "/dispatches", body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8", errors="ignore")
    return resp.status, raw[:300]
def main():
    repo_full = os.environ.get("GITHUB_REPOSITORY", "bereznyi-aleksandr/ai-devops-system")
    token = os.environ.get("GH_DISPATCH_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
    owner, repo = repo_full.split("/", 1)
    results = []
    QUEUE.mkdir(parents=True, exist_ok=True)
    for path in sorted(QUEUE.glob("*.json")):
        item = load(path)
        if item.get("status") != "queued":
            continue
        workflow = item.get("workflow")
        if not workflow or not token:
            item["status"] = "dispatch_failed"
            item["blocker"] = {"code":"WORKFLOW_OR_TOKEN_MISSING", "workflow":workflow, "has_token":bool(token)}
        else:
            code, preview = run_dispatch(owner, repo, workflow, token)
            item["dispatch_http_status"] = code
            item["dispatch_response_preview"] = preview
            item["status"] = "dispatched" if code in [200,201,202,204] else "dispatch_failed"
            if item["status"] == "dispatch_failed":
                item["blocker"] = {"code":"WORKFLOW_DISPATCH_FAILED", "http_status":code, "response_preview":preview}
        path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
        results.append(item)
    summary = {"schema_version":"workflow_dispatch_queue_runner.v1","status":"completed","results":results,"created_at":"workflow_runtime"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Workflow Dispatch Queue Runner", "", "Status: completed", "", "## Results"]
    for item in results:
        lines.append("- " + str(item.get("queue_id")) + ": " + str(item.get("status")) + " | " + str(item.get("workflow")) + " | http=" + str(item.get("dispatch_http_status")))
    REPORT.write_text(SEP.join(lines) + SEP, encoding="utf-8")
    print(json.dumps({"count": len(results)}, ensure_ascii=False))
if __name__ == "__main__":
    main()
