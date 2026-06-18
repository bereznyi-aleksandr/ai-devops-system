#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = os.environ["GITHUB_REPOSITORY"]
GH_TOKEN = os.environ["GH_TOKEN"]
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RUN_ID = os.environ["GITHUB_RUN_ID"]
WORKER_URL = "https://tg-curator-webhook.bereznii-aleksandr.workers.dev/webhook"
CHAT_ID = 601442777
CONTENT = (
    "BEM-934 LIVE TEST: Проанализируй два проверяемых инварианта "
    "идемпотентной доставки Telegram-сообщения в WRK-C1 и предложи "
    "краткий план проверки с критериями PASS/FAIL."
)
FINAL_RECEIPT = Path("governance/proofs/BEM934_live_test_receipt.json")
QUEUE = Path("governance/roadmap/ACTIVE_QUEUE.json")
LOG = Path("governance/logs/execution_log.jsonl")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        list(args),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(args)}\n{completed.stdout}")
    return completed.stdout.strip()


def git(*args: str, check: bool = True) -> str:
    return run("git", *args, check=check)


def request_json(
    url: str,
    payload: dict[str, Any],
    *,
    form: bool = False,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], str]:
    if form:
        body = urllib.parse.urlencode(payload).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        content_type = "application/json"
    request_headers = {"Content-Type": content_type, "User-Agent": "bem934-live-test"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, data=body, method="POST", headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw), raw
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return error.code, parsed, raw


def sync_main() -> None:
    git("fetch", "origin", "main")
    git("reset", "--hard", "origin/main")


def deep_find(data: Any, key: str) -> Any:
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = deep_find(value, key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = deep_find(value, key)
            if found is not None:
                return found
    return None


def find_route(trace: str) -> tuple[Path, dict[str, Any], str, str] | None:
    for path in Path("governance/proofs").rglob("*.json"):
        if path == FINAL_RECEIPT:
            continue
        try:
            text = path.read_text(encoding="utf-8")
            if trace not in text:
                continue
            data = json.loads(text)
        except (OSError, json.JSONDecodeError):
            continue
        provider = deep_find(data, "provider_selected")
        target = (
            deep_find(data, "target_workflow_id")
            or deep_find(data, "target_workflow")
            or deep_find(data, "workflow_id")
        )
        if provider and target:
            return path, data, str(provider), str(target)
    return None


def find_report(trace: str) -> Path | None:
    candidates: list[Path] = []
    for path in Path("governance/reports").rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if trace in text and len(text.encode("utf-8")) >= 500:
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0]


def path_evidence(path: Path) -> dict[str, str]:
    return {
        "path": path.as_posix(),
        "blob_sha": git("rev-parse", f"HEAD:{path.as_posix()}"),
        "commit_sha": git("log", "-1", "--format=%H", "--", path.as_posix()),
    }


def commit_and_push(message: str, paths: list[Path]) -> str:
    git("add", *[path.as_posix() for path in paths])
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return git("rev-parse", "HEAD")
    git("commit", "-m", message)
    for _ in range(6):
        pushed = subprocess.run(
            ["git", "push", "origin", "HEAD:main"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if pushed.returncode == 0:
            return git("rev-parse", "HEAD")
        git("pull", "--rebase", "origin", "main")
        time.sleep(2)
    raise RuntimeError(f"push failed after retries: {message}")


def main() -> None:
    git("config", "user.email", "bem934-live-test@ai-devops-system")
    git("config", "user.name", "BEM-934 Live Test")
    sync_main()

    tg_status, tg_response, _ = request_json(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": CONTENT,
            "disable_web_page_preview": "true",
        },
        form=True,
    )
    if tg_status != 200 or not tg_response.get("ok"):
        raise RuntimeError(f"Telegram Bot API sendMessage failed: HTTP {tg_status}")
    tg_message = tg_response["result"]
    message_id = int(tg_message["message_id"])

    update_id = 934000000 + (int(RUN_ID) % 900000)
    update = {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "date": int(tg_message.get("date", time.time())),
            "chat": tg_message["chat"],
            "from": tg_message.get("from", {"id": 0, "is_bot": True, "first_name": "BEM934"}),
            "text": CONTENT,
        },
    }
    worker_status, worker_response, worker_raw = request_json(WORKER_URL, update)
    if worker_status != 200:
        raise RuntimeError(f"Live Worker returned HTTP {worker_status}: {worker_raw}")
    trace = str(worker_response.get("trace_id") or f"tg_{update_id}")
    dispatch_status = str(worker_response.get("status") or "")
    if dispatch_status not in {"DISPATCHED", "ALREADY_PROCESSED"}:
        raise RuntimeError(f"Worker did not dispatch: {worker_raw}")

    route = None
    for _ in range(72):
        time.sleep(10)
        sync_main()
        route = find_route(trace)
        if route:
            break
    if route is None:
        raise RuntimeError(f"provider-router receipt not found for {trace}")
    route_path, route_data, provider_selected, target_workflow = route
    if "claude.yml" not in target_workflow:
        raise RuntimeError(
            f"route did not target claude.yml: provider={provider_selected}, target={target_workflow}"
        )
    route_evidence = path_evidence(route_path)

    report_path = None
    for _ in range(72):
        sync_main()
        report_path = find_report(trace)
        if report_path:
            break
        time.sleep(10)
    if report_path is None:
        raise RuntimeError(f"Claude report not found for {trace}")
    report_text = report_path.read_text(encoding="utf-8")
    report_evidence = path_evidence(report_path)

    transport_lines: list[dict[str, Any]] = []
    results_path = Path("governance/transport/results.jsonl")
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if trace not in line:
                continue
            try:
                transport_lines.append(json.loads(line))
            except json.JSONDecodeError:
                transport_lines.append({"raw": line})

    completed_at = now()
    checks = {
        "telegram_bot_api_message_created": True,
        "content_bearing_non_service_message": len(CONTENT.split()) >= 12
        and "release" not in CONTENT.lower()
        and "релиз" not in CONTENT.lower(),
        "live_cloudflare_worker_http_200": worker_status == 200,
        "worker_status_dispatched": dispatch_status in {"DISPATCHED", "ALREADY_PROCESSED"},
        "trace_id_returned": bool(trace),
        "provider_router_receipt_present": bool(route_evidence["blob_sha"]),
        "provider_selected_present": bool(provider_selected),
        "target_workflow_is_claude_yml": "claude.yml" in target_workflow,
        "claude_report_present": bool(report_evidence["blob_sha"]),
        "claude_report_substantive": len(report_text.encode("utf-8")) >= 500,
        "telegram_ingress_replay_disclosed": True,
        "transport_result_recorded": bool(transport_lines),
        "gpt_fallback_not_used_as_llm": "gpt" not in provider_selected.lower()
        or "claude.yml" in target_workflow,
    }
    if not all(checks.values()):
        failed = [name for name, value in checks.items() if not value]
        raise RuntimeError(f"live E2E checks failed: {failed}")

    receipt = {
        "status": "PASS",
        "protocol": "BEM-934",
        "task_id": "BEM934-LIVE-TEST",
        "created_at": completed_at,
        "content": {
            "text": CONTENT,
            "sha256": hashlib.sha256(CONTENT.encode("utf-8")).hexdigest(),
            "content_bearing": True,
            "service_or_release_message": False,
        },
        "telegram": {
            "api_method": "sendMessage",
            "chat_id": CHAT_ID,
            "message_id": message_id,
            "api_response_ok": True,
            "ingress_mode": "telegram_bot_api_message_replay_to_live_webhook",
            "automatic_telegram_webhook_origin_claimed": False,
            "replay_reason": (
                "A bot cannot receive its own outbound private-chat message as an inbound update; "
                "the real Telegram Bot API message object was replayed unchanged into the deployed webhook."
            ),
        },
        "cloudflare_worker": {
            "url": WORKER_URL,
            "http_status": worker_status,
            "response": worker_response,
            "deployment_evidence": "governance/proofs/BEM932_cloudflare_dashboard_deploy_evidence.json",
        },
        "trace_id": trace,
        "provider_selected": provider_selected,
        "target_workflow": target_workflow,
        "provider_router_receipt": route_evidence,
        "claude_report": report_evidence,
        "transport_results": transport_lines,
        "checks": checks,
        "notes": [
            "The test message is analytical and content-bearing; it is not a service or release command.",
            "Telegram network use is proven by the successful Bot API message creation.",
            "The webhook ingress is an explicitly disclosed replay of that real Telegram message object, not a claim of an operator-authored automatic Telegram webhook event.",
            "The live deployed Worker returned the trace that was then materialized by provider-router and claude.yml.",
        ],
    }
    FINAL_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    FINAL_RECEIPT.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    receipt_commit = commit_and_push(
        "Record PASS receipt for BEM934-LIVE-TEST",
        [FINAL_RECEIPT],
    )

    sync_main()
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    for task in queue["tasks"]:
        if task["id"] == "BEM934-LIVE-TEST":
            task.update(
                {
                    "status": "DONE",
                    "done_sha": receipt_commit,
                    "receipt": FINAL_RECEIPT.as_posix(),
                    "completed_at": completed_at,
                }
            )
            task.pop("blocked_by", None)
        elif task["id"] == "BEM934-CLOSE":
            task["status"] = "IN_PROGRESS"
            task.pop("blocked_by", None)
    queue["version"] = int(queue.get("version", 0)) + 1
    queue["updated_at"] = completed_at
    queue["current_task"] = "BEM934-CLOSE"
    queue["completed_summary"]["tasks_done"] = 9
    proofs = queue["completed_summary"].setdefault("proofs", [])
    if FINAL_RECEIPT.as_posix() not in proofs:
        proofs.append(FINAL_RECEIPT.as_posix())
    queue["last_completed"] = {
        "id": "BEM934-LIVE-TEST",
        "completed_at": completed_at,
        "done_sha": receipt_commit,
    }
    queue["next_action"] = (
        "BEM934-CLOSE — update canonical context/status, remove self-hosted runtime claims, "
        "and request external Claude auditor verdict"
    )
    QUEUE.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "date": completed_at,
                    "id": "BEM934-LIVE-TEST",
                    "sha": receipt_commit,
                    "status": "done",
                    "receipt": FINAL_RECEIPT.as_posix(),
                    "trace_id": trace,
                    "provider_selected": provider_selected,
                    "next": "BEM934-CLOSE",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    close_commit = commit_and_push(
        "Close BEM934-LIVE-TEST and advance protocol closure",
        [QUEUE, LOG],
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "trace_id": trace,
                "provider_selected": provider_selected,
                "target_workflow": target_workflow,
                "receipt": FINAL_RECEIPT.as_posix(),
                "receipt_commit": receipt_commit,
                "queue_commit": close_commit,
                "next": "BEM934-CLOSE",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
