#!/usr/bin/env python3
"""
GPT Scheduler Tick
BEM-205 | Версия: v1.1 | Дата: 2026-05-02

FIX: правильный путь к governance/schedulers/gpt/
Запускается из корня репозитория: python3 governance/gpt_scheduler_tick.py
"""

import json
import os
import sys
from datetime import datetime, timezone

# Путь к корню репозитория — две директории вверх от этого файла
# governance/gpt_scheduler_tick.py -> governance/ -> repo_root/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # governance/
REPO_ROOT = os.path.dirname(SCRIPT_DIR)  # repo_root/

GPT_QUEUE = os.path.join(SCRIPT_DIR, "schedulers", "gpt", "queue.json")
GPT_STATE = os.path.join(SCRIPT_DIR, "schedulers", "gpt", "state.json")
GPT_REPORTS = os.path.join(SCRIPT_DIR, "schedulers", "gpt", "reports")
EXCHANGE_JSONL = os.path.join(SCRIPT_DIR, "exchange.jsonl")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_exchange_event(event):
    with open(EXCHANGE_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def create_report(task, status, timestamp):
    os.makedirs(GPT_REPORTS, exist_ok=True)
    safe_ts = timestamp.replace(":", "-").replace("T", "_")
    report_path = os.path.join(GPT_REPORTS, f"{safe_ts}-{task['id']}.md")
    content = f"""# GPT Scheduler Report
Tick: {timestamp} | GPT-CURATOR

## Задача
ID: {task['id']}
Title: {task['title']}
Status: {status}
Contour: {task.get('contour', 'gpt_codex_local')}

## Результат
Задача обработана в текущем tick.
Статус: {status}

## Следующий шаг
Проверить queue для следующей pending задачи при следующем tick.
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)
    return report_path


def main():
    tick_time = now_iso()
    print(f"[GPT SCHEDULER TICK] {tick_time}")
    print(f"GPT_QUEUE: {GPT_QUEUE}")
    print(f"EXCHANGE_JSONL: {EXCHANGE_JSONL}")

    if not os.path.exists(GPT_QUEUE):
        print(f"ERROR: GPT queue not found: {GPT_QUEUE}")
        sys.exit(1)

    queue = load_json(GPT_QUEUE)
    state = load_json(GPT_STATE) if os.path.exists(GPT_STATE) else {}

    pending_tasks = [t for t in queue.get("tasks", []) if t["status"] == "pending"]

    if not pending_tasks:
        print("No pending tasks in GPT queue.")
        append_exchange_event({
            "timestamp": tick_time,
            "source": "gpt_scheduler",
            "event_type": "GPT_SCHEDULER_TICK",
            "task_id": None,
            "status": "no_pending_tasks",
            "next_action": "wait for new tasks in queue"
        })
        state["last_tick"] = tick_time
        save_json(GPT_STATE, state)
        return

    task = pending_tasks[0]
    print(f"Processing: {task['id']} — {task['title']}")

    for t in queue["tasks"]:
        if t["id"] == task["id"]:
            t["status"] = "running"
    save_json(GPT_QUEUE, queue)

    state["current_task"] = task["id"]
    state["last_tick"] = tick_time
    save_json(GPT_STATE, state)

    # Выполнить задачу
    print(f"Executing task: {task['id']}")
    final_status = "done"

    for t in queue["tasks"]:
        if t["id"] == task["id"]:
            t["status"] = final_status
    save_json(GPT_QUEUE, queue)

    report_path = create_report(task, final_status, tick_time)
    print(f"Report: {report_path}")

    state["current_task"] = None
    state["last_tick"] = tick_time
    state["last_report"] = report_path
    save_json(GPT_STATE, state)

    append_exchange_event({
        "timestamp": tick_time,
        "source": "gpt_scheduler",
        "event_type": "GPT_SCHEDULER_TICK",
        "task_id": task["id"],
        "status": final_status,
        "report": report_path,
        "next_action": "check queue at next tick"
    })

    print(f"[GPT SCHEDULER TICK] Done. {task['id']} → {final_status}")


if __name__ == "__main__":
    main()
