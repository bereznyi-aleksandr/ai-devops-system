import json
from pathlib import Path
from typing import Dict, List

ROOT = Path.cwd()
INDEX_PATH = ROOT / "governance" / "runtime" / "tasks" / "index.json"
NOTIFY_DIR = ROOT / "governance" / "runtime" / "notifications"

ROLE_BUCKET_ORDER = [
    ("EXECUTOR", "AWAITING_EXECUTOR"),
    ("AUDITOR", "AWAITING_AUDITOR"),
    ("SYSTEM", "AWAITING_SYSTEM"),
]


class NotifyError(RuntimeError):
    pass


def read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_target(items: List[Dict[str, object]]) -> Dict[str, object] | None:
    for role, bucket in ROLE_BUCKET_ORDER:
        candidates = [x for x in items if str(x.get("status_bucket", "")).strip() == bucket]
        if not candidates:
            continue
        candidates.sort(
            key=lambda x: (
                str(x.get("last_event_ts", "")).strip(),
                str(x.get("task_id", "")).strip(),
            ),
            reverse=True,
        )
        item = candidates[0]
        item["_notify_role"] = role
        return item
    raise NotifyError("No notification target found in index")


def main() -> int:
    if not INDEX_PATH.exists():
        raise NotifyError(f"Index not found: {INDEX_PATH}")

    index_doc = read_json(INDEX_PATH)
    items = index_doc.get("items", [])
    if not isinstance(items, list):
        raise NotifyError("Index items is not a list")

    target = pick_target(items)
    if target is None:
        print(json.dumps({
            'system_role_notify_version': 'v1',
            'result': 'NO_TARGET',
            'index_path': str(INDEX_PATH.relative_to(ROOT)),
            'notification_created': False
        }, ensure_ascii=False, indent=2))
        return 0

    role = str(target.get("_notify_role", "")).strip()
    task_id = str(target.get("task_id", "")).strip()
    next_action = str(target.get("next_action", "")).strip()
    current_state = str(target.get("current_state", "")).strip()
    status_bucket = str(target.get("status_bucket", "")).strip()
    registry_path = str(target.get("registry_path", "")).strip()
    last_event_ts = str(target.get("last_event_ts", "")).strip()

    role_dir = NOTIFY_DIR / role.lower()
    role_dir.mkdir(parents=True, exist_ok=True)

    out_path = role_dir / f"{task_id}.notify.json"
    payload = {
        "system_role_notify_version": "v1",
        "result": "SUCCESS",
        "task_id": task_id,
        "role": role,
        "next_action": next_action,
        "current_state": current_state,
        "status_bucket": status_bucket,
        "registry_path": registry_path,
        "last_event_ts": last_event_ts,
        "notification_path": str(out_path.relative_to(ROOT)),
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
