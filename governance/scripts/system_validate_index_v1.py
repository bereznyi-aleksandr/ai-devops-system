import json
from pathlib import Path
from collections import Counter

ROOT = Path.cwd()
INDEX_PATH = ROOT / 'governance' / 'runtime' / 'tasks' / 'index.json'

def main() -> int:
    report = {
        "system_validate_index_version": "v1",
        "result": "SUCCESS",
        "index_path": str(INDEX_PATH.relative_to(ROOT)),
        "errors": [],
        "warnings": [],
    }

    if not INDEX_PATH.exists():
        report["result"] = "BLOCKED"
        report["errors"].append({
            "type": "INDEX_NOT_FOUND",
            "path": str(INDEX_PATH.relative_to(ROOT)),
        })
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    data = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    items = data.get("items", [])

    if not isinstance(items, list):
        report["result"] = "BLOCKED"
        report["errors"].append({
            "type": "INDEX_ITEMS_NOT_LIST",
        })
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    norm_ids = [str(x.get("task_id", "")).strip() for x in items]
    counts = Counter([x for x in norm_ids if x])
    dups = sorted([k for k, v in counts.items() if v > 1])

    if dups:
        report["result"] = "BLOCKED"
        report["errors"].append({
            "type": "DUPLICATE_TASK_ID",
            "task_ids": dups,
        })

    for idx, item in enumerate(items):
        task_id = str(item.get("task_id", "")).strip()
        registry_path = str(item.get("registry_path", "")).strip()

        if not task_id:
            report["result"] = "BLOCKED"
            report["errors"].append({
                "type": "EMPTY_TASK_ID",
                "index_pos": idx,
            })

        if not registry_path:
            report["result"] = "BLOCKED"
            report["errors"].append({
                "type": "EMPTY_REGISTRY_PATH",
                "index_pos": idx,
                "task_id": task_id,
            })
            continue

        reg_file = ROOT / registry_path
        if not reg_file.exists():
            report["result"] = "BLOCKED"
            report["errors"].append({
                "type": "REGISTRY_FILE_NOT_FOUND",
                "index_pos": idx,
                "task_id": task_id,
                "registry_path": registry_path,
            })
            continue

        try:
            reg_data = json.loads(reg_file.read_text(encoding='utf-8'))
        except Exception as e:
            report["result"] = "BLOCKED"
            report["errors"].append({
                "type": "REGISTRY_JSON_INVALID",
                "index_pos": idx,
                "task_id": task_id,
                "registry_path": registry_path,
                "error": str(e),
            })
            continue

        reg_task_id = str(reg_data.get("task_id", "")).strip()
        if reg_task_id != task_id:
            report["result"] = "BLOCKED"
            report["errors"].append({
                "type": "TASK_ID_MISMATCH",
                "index_pos": idx,
                "index_task_id": task_id,
                "registry_task_id": reg_task_id,
                "registry_path": registry_path,
            })

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "SUCCESS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
