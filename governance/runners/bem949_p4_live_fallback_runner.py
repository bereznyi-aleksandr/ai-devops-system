#!/usr/bin/env python3
"""BEM-949 P4 bounded live OpenAI fallback probe."""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TASK_ID = "BEM949-P4-LIVE-LLM-FALLBACK"
DEFAULT_MODEL = "gpt-4.1-mini"


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_api_error(raw):
    """Keep only stable error categories; never persist raw provider output."""
    result = {"type": None, "code": None}
    try:
        body = json.loads(raw.decode("utf-8", errors="replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return result
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return result
    if isinstance(error.get("type"), str):
        result["type"] = error["type"][:80]
    if isinstance(error.get("code"), str):
        result["code"] = error["code"][:80]
    return result


def extract_output_text(data):
    parts = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if (
                isinstance(content, dict)
                and content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ):
                parts.append(content["text"])
    return "".join(parts)


def call_openai(api_key, model):
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(
            {
                "model": model,
                "input": "Return exactly: BEM949 P4 live fallback probe acknowledged.",
                "max_output_tokens": 32,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            http_status = response.status
            data = json.loads(response.read().decode("utf-8"))
        response_id = data.get("id") if isinstance(data.get("id"), str) else None
        text = extract_output_text(data)
        return {
            "http_status": http_status,
            "response_id": response_id,
            "text": text,
            "blocker": "" if 200 <= http_status < 300 and response_id and text else "openai_response_missing_id_or_output_text",
            "retry_after_seconds": None,
            "api_error": {"type": None, "code": None},
        }
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After")
        try:
            retry_after_seconds = int(retry_after) if retry_after else None
        except ValueError:
            retry_after_seconds = None
        return {
            "http_status": exc.code,
            "response_id": None,
            "text": "",
            "blocker": "openai_api_http_{0}".format(exc.code),
            "retry_after_seconds": retry_after_seconds,
            "api_error": safe_api_error(exc.read()),
        }
    except URLError:
        return {
            "http_status": None,
            "response_id": None,
            "text": "",
            "blocker": "openai_transport_failure",
            "retry_after_seconds": None,
            "api_error": {"type": None, "code": None},
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {
            "http_status": None,
            "response_id": None,
            "text": "",
            "blocker": "openai_response_unreadable",
            "retry_after_seconds": None,
            "api_error": {"type": None, "code": None},
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="governance/roadmap/ACTIVE_QUEUE.json")
    parser.add_argument("--out", default="governance/profs/BEM949_p4_live_llm_fallback_receipt.json")
    parser.add_argument("--trace-id", required=True)
    args = parser.parse_args()

    queue_path = Path(args.queue)
    out_path = Path(args.out)
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_QUEUE.tasks must be a list")

    task = next(
        (
            row
            for row in tasks
            if isinstance(row, dict) and row.get("id") == TASK_ID
        ),
        None,
    )
    if task is None:
        raise ValueError("P4 task missing from ACTIVE_QUEUE")

    api_key = os.genv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
    attempts_this_run = 0

    if api_key:
        attempts_this_run = 1
        outcome = call_openai(api_key, model)
        retry_after = outcome["retry_after_seconds"]
        if (
            outcome["http_status"] == 429
            and outcome["api_error"].get("type") == "rate_limit_error"
            and isinstance(retry_after, int)
            and 0 < retry_after <= 15
        ):
            time.sleep(retry_after)
            attempts_this_run += 1
            outcome = call_openai(api_key, model)
    else:
        outcome = {
            "http_status": None,
            "response_id": None,
            "text": "",
            "blocker": "openai_api_key_not_configured",
            "retry_after_seconds": None,
            "api_error": {"type": None, "code": None},
        }

    observed = (
        isinstance(outcome["http_status"], int)
        and 200 <= outcome["http_status"] < 300
        and bool(outcome["response_id"])
        and bool(outcome["text"])
    )
    status = "OBSERVED_LIVE_FALLBACK" if observed else "BLOCKED"

    receipt = {
        "schema_version": 1,
        "protocol": "BEM-949",
        "task_id": TASK_ID,
        "receipt_id": "BEM949_p4_live_llm_fallback",
        "created_at": utc_now(),
        "trace_id": args.trace_id,
        "status": status,
        "provider": {
            "name": "openai_responses_api",
            "model": model,
            "model_source": "repository_variable_or_workflow_default",
            "live_call_attempted": bool(api_key),
            "http_status": outcome["http_status"],
            "response_id": outcome["response_id"],
            "response_id_type": "openai_responses_id" if outcome["response_id"] else None,
            "output_text_sha256": hashlib.sha256(outcome["stext"].encode("utf-8")).hexdigest() if outcome["text"] else None,
            "output_text_length": len(outcome["stext"]),
            "output_text_persisted": False,
            "attempts_this_run": attempts_this_run,
            "retry_after_seconds": outcome["retry_after_seconds"],
            "api_error": outcome["api_error"],
        },
        "acceptance": {
            "live_fallback_evidence_observed": observed,
            "mechanical_fallbacksubstituted_for_live_evidence": False,
        },
        "blockers": [] if observed else [outcome["blocker"]],
        "non_claim": "Live fallback requires 2xx Responses API, response id, and non-empty output text. Secrets, raw provider errors, and output are not persisted.",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    prior_attempts = task.get("attempts", 0)
    if not isinstance(prior_attempts, int) or prior_attempts < 0:
        prior_attempts = 0
    task["status"] = "DONE" if observed else "BLOCKED"
    task["completed_at"] = utc_now()
    task["attempts"] = prior_attempts + attempts_this_run
    task["receipt_sha"] = sha256_file(out_path)
    task["receipt_sha_type"] = "sha256_content"
    task["blocker"] = None if observed else outcome["blocker"]
    task["resume_condition"] = None if observed else "Restore OpenAI API capacity or permission, then rerun P4."
    queue["updated_at"] = utc_now()
    queue_path.write_text(json.dumps(queue, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(receipt, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
