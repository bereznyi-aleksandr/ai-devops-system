#!/usr/bin/env python3
"""BEM-949 P4 live fallback probe."""
import argparse, hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TASK = "BEM949-P4-LIVE-LLM-FALLBACK"
DEFAULT_MODEL = "gpt-4.1-mini"

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def output_text(data):
    parts = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default="governance/roadmap/ACTIVE_QUEUE.json")
    ap.add_argument("--out", default="governance/proofs/BEM949_p4_live_llm_fallback_receipt.json")
    ap.add_argument("--trace-id", required=True)
    args = ap.parse_args()
    queue_path = Path(args.queue)
    out_path = Path(args.out)
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_QUEUE.tasks must be a list")

    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
    status, blocker, http_status, response_id, text = "BLOCKED", "", None, None, ""
    attempted = False
    if not key:
        blocker = "openai_api_key_not_configured"
    else:
        attempted = True
        req = Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps({
                "model": model,
                "input": "Return exactly: BEM949 P4 live fallback probe acknowledged.",
                "max_output_tokens": 32,
            }).encode("utf-8"),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=60) as response:
                http_status = response.status
                data = json.loads(response.read().decode("utf-8"))
            response_id = data.get("id") if isinstance(data.get("id"), str) else None
            text = output_text(data)
            if 200 <= http_status < 300 and response_id and text:
                status = "OBSERVED_LIVE_FALLBACK"
            else:
                blocker = "openai_response_missing_id_or_output_text"
        except HTTPError as exc:
            http_status, blocker = exc.code, f"openai_api_http_{exc.code}"
        except URLError:
            blocker = "openai_transport_failure"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            blocker = "openai_response_unreadable"

    receipt = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": TASK,
        "receipt_id": "BEM949_p4_live_llm_fallback",
        "created_at": now(),
        "trace_id": args.trace_id,
        "status": status,
        "provider": {
            "name": "openai_responses_api",
            "model": model,
            "model_source": "repository_variable_or_workflow_default",
            "live_call_attempted": attempted,
            "http_status": http_status,
            "response_id": response_id,
            "response_id_type": "openai_responses_id" if response_id else None,
            "output_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
            "output_text_length": len(text),
            "output_text_persisted": False,
        },
        "acceptance": {
            "live_fallback_evidence_observed": status == "OBSERVED_LIVE_FALLBACK",
            "mechanical_fallback_substituted_for_live_evidence": False,
        },
        "blockers": [] if status == "OBSERVED_LIVE_FALLBACK" else [blocker],
        "non_claim": "Live fallback requires 2xx Responses API, response id, and non-empty output text. Secrets and output are not persisted.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    found = False
    for task in tasks:
        if isinstance(task, dict) and task.get("id") == TASK:
            task["status"] = "DONE" if status == "OBSERVED_LIVE_FALLBACK" else "BLOCKED"
            task["completed_at"] = now()
            task["receipt_sha"] = digest(out_path)
            task["receipt_sha_type"] = "sha256_content"
            task["blocker"] = blocker or None
            task["resume_condition"] = None if not blocker else "Restore OpenAI API access, then rerun P4."
            found = True
    if not found:
        raise ValueError("P4 task missing from ACTIVE_QUEUE")
    queue["updated_at"] = now()
    queue_path.write_text(json.dumps(queue, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
