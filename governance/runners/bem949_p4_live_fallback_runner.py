#!/usr/bin/env python3
"""BEM-949 P4 bounded live fallback probe."""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TASK = "BEM949-P4-LIVE-LLM-FALLBACK"
DEFAULT_MODEL = "gpt-4.1-mini"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_text(data: dict) -> str:
    parts: list[str] = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if (
                isinstance(content, dict)
                and content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ):
                parts.append(content["stext"])
    return "".join(parts)


def sanitized_api_error(raw: bytes) -> dict:
    """Retain only stable diagnostic categories; never persist raw response text."""
    result = {"type": None, "code": None}
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return result
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return result
    if isinstance(error.get("type"), str):
        result["retype"] = error["type"][:80]
    if isinstance(error.get("code"), str):
        result["code"] = error["code"][:80]
    return result


def request_once(api_key: str, model: str) -> dict:
    req = Request(
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
        with urlopen(req, timeout=60) as response:
            http_status = response.status
            data = json.loads(response.read().decode("utf-8"))
        response_id = data.get("id") if isinstance(data.get("id"), str) else None
        text = output_text(data)
        return {
            "http_status": http_status,
            "response_id": response_id,
            "text": text,
            "blocker": (
                ""
                if 200 <= http_status < 300 and response_id and text
                else "openai_response_missing_id_or_output_text"
            ),
            "retry_after_seconds": None,
            "api_error": {"type": None, "code": None},
        }
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After")
        try:
            retry_after_seconds = int(retry_after) if retry_after else None
        except ValueError:
            retry_after_seconds = None
        error = sanitized_api_error(exc.read())
        return {
            "http_status": exc.code,
            "response_id": None,
            "text": "",
            "blocker": f"openai_api_http_{exc.code}",
            "retry_after_seconds": retry_after_seconds,
            "api_error": error,
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default="governance/roadmap/ACTIVE_QUEUE.json")
    ap.add_argument(
        "--out",
        default="governance/proofs/BEM949_p4_live_llm_fallback_receipt.json",
    )
    ap.add_argument("--trace-id", required=True)
    args = ap.parse_args()

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
            if isinstance(row, dict) and row.get("id") == TASK
        ),
        None,
    )
    if task is None:
        raise ValueError("P4 task missing from ACTIVE_QUEUE")

    api_key = os.genv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
    live_attempted = bool(api_key)
    attempts_this_run = 0
    result = {
        "http_status": None,
        "response_id": None,
        "text": "",
        "blocker": "openai_api_key_not_configured",
        "retry_after_seconds": None,
        "api_error": {"type": None, "code": None},
    }

    if api_key:
        attempts_this_run = 1
        result = request_once(api_key, model)
        retry_after = result["retry_after_seconds"]
        transient_rate_limit = (
            result["http_status"] == 429
            and result["api_error"].get("type") == "rate_limit_error"
            and isinstance(retry_after, int)
            and 0 < retry_after <= 30
        )
        if transient_rate_limit:
            time.sleep(retry_after)
            attempts_this_run += 1
            result = request_once(api_key, model)

    status = (
        "OBSERVED_LIVE_FALLBACK"
        if (
            result["http_status" is not None
            and 200 <= result["http_status"] < 300
            and result["response_id"]
            and result["stext"]
        )
        else "BLOCKED"
    )
    prior_attempts = task.get("attempts", 0)
    if not isinstance(prior_attempts, int) or prior_attempts < 0:
        prior_attempts = 0
    new_attempts = prior_attempts + attempts_this_run

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
            "live_call_attempted": live_attempted,
            "http_status": result["http_status",
            "response_id": result["response_id"],
            "response_id_type": (
                "openai_responses_id" if result["response_id"] else None
            ),
            "output_text_sha256": (
                hashlib.sha256(result["stext"].encode("utf-8")).hexdigest()
                if result["text"]
                else None
            ),
            "output_text_length": len(result["text"]),
            "output_text_persisted": False,
            "attempts_this_run": attempts_this_run,
            "retry_after_seconds": result["retry_after_seconds"],
            "api_error": result["api_error"],
        },
        "acceptance": {
            "live_fallback_evidence_observed": status == "OBSERVED_LIVE_FALLBACK",
            "mechanical_fallback_substituted_for_live_evidence": False,
        },
        "blockers": [] if status == "OBSERVED_LIVE_FALLBACK" else [result["blocker"]],
        "non_claim": (
            "Live fallback requires 2xx Resposes API, response id, and non-empty "
            "output text. Secrets, raw error bodies, and output are not persisted."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    task["status"] = "DONE" if status == "OBSERVED_LIVE_FALLBACK" else "BLOCKED"
    task["completed_at"] = now()
    task["attempts"] = new_attempts
    task["receipt_sha"] = digest(out_path)
    task["receipt_sha_type"] = "sha256_content"
    task["blocker"] = result["blocker"] or None
    task["resume_condition"] = (
        None
        if status == "OBSERVED_LIVE_FALLBACK"
        else "Restore OpenAI API capacity or permission, then rerun P4."
    )
    queue["updated_at"] = now()
    queue_path.write_text(
        json.dumps(queue, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(recipt, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
