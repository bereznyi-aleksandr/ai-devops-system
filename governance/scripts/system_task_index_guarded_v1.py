import json
from pathlib import Path
from collections import Counter

ROOT = Path.cwd()
INDEX_PATH = ROOT / 'governance' / 'runtime' / 'tasks' / 'index.json'

def main() -> int:
    if not INDEX_PATH.exists():
        print(json.dumps({
            "system_task_index_guarded_version": "v1",
            "result": "BLOCKED",
            "error": "index.json not found",
            "index_path": str(INDEX_PATH.relative_to(ROOT)),
        }, ensure_ascii=False, indent=2))
        return 1

    data = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    items = data.get('items', [])

    if not isinstance(items, list):
        print(json.dumps({
            "system_task_index_guarded_version": "v1",
            "result": "BLOCKED",
            "error": "index items is not a list",
            "index_path": str(INDEX_PATH.relative_to(ROOT)),
        }, ensure_ascii=False, indent=2))
        return 1

    task_ids = [str(x.get('task_id', '')).strip() for x in items if str(x.get('task_id', '')).strip()]
    counts = Counter(task_ids)
    dups = sorted([k for k, v in counts.items() if v > 1])

    if dups:
        print(json.dumps({
            "system_task_index_guarded_version": "v1",
            "result": "BLOCKED",
            "error": "duplicate task_id entries detected",
            "duplicate_task_ids": dups,
            "index_path": str(INDEX_PATH.relative_to(ROOT)),
        }, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        "system_task_index_guarded_version": "v1",
        "result": "SUCCESS",
        "index_path": str(INDEX_PATH.relative_to(ROOT)),
        "task_count": len(items),
    }, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
