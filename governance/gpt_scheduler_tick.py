#!/usr/bin/env python3
"""
GPT Scheduler Tick
BEM-184 | Версия: v1.0 | Дата: 2026-05-02

Читает только governance/schedulers/gpt/queue.json
НЕ трогает cloud queue.
"""

import json
import os
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GPT_QUEUE = os.path.join(REPO_ROOT, "schedulers", "gpt", "queue.json")
GPT_STATE = os.path.join(REPO_ROOT, "schedulers", "gpt", "state.json")
GPT_REPORTS = os.path.join(REPO_ROOT, "schedulers", "gpt", "reports")
EXCHANGE_JSONL = os.path.join(REPO_ROOT, "exchange.jsonl")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_exchange_event(event):
    with open(EXCHANGE_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def create_report(task, status, bem_num):
    os.makedirs(GPT_REPORTS, exist_ok=True)
    report_path = os.path.join(GPT_REPORTS, f"BEM-{bem_num}-{task['id']}.md")
    content = f"""# GPT Scheduler Report
BEM-{bem_num} | GPT-CURATOR | {now_iso()}

## Задача
ID: {task['id']}
Title: {task['title']}
Status: {status}
Contour: {task['contour']}

## Результат
Задача обработана в текущем tick.
Статус: {status}

## Следующий шаг
Проверить queue для следующей pending задачи.
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)
    return report_path


def main():
    print(f"[GPT SCHEDULER TICK] {now_iso()}")

    # Загрузить queue
    if not os.path.exists(GPT_QUEUE):
        print(f"ERROR: GPT queue not found: {GPT_QUEUE}")
        sys.exit(1)

    queue = load_json(GPT_QUEUE)
    state = load_json(GPT_STATE) if os.path.exists(GPT_STATE) else {}

    # Найти первую pending задачу
    pending_tasks = [t for t in queue.get("tasks", []) if t["status"] == "pending"]

    if not pending_tasks:
        print("No pending tasks in GPT queue. Tick complete.")
        append_exchange_event({
            "timestamp": now_iso(),
            "source": "gpt_scheduler",
            "event_type": "GPT_SCHEDULER_TICK",
            "task_id": None,
            "status": "no_pending_tasks",
            "next_action": "wait for new tasks"
        })
        return

    task = pending_tasks[0]
    print(f"Processing task: {task['id']} — {task['title']}")

    # Перевести в running
    for t in queue["tasks"]:
        if t["id"] == task["id"]:
            t["status"] = "running"

    save_json(GPT_QUEUE, queue)
    state["current_task"] = task["id"]
    state["last_tick"] = now_iso()
    save_json(GPT_STATE, state)

    # Выполнить задачу (базовая логика)
    # В реальности здесь будет вызов GPT/Codex
    print(f"Task {task['id']} executed (basic tick logic)")
    final_status = "done"

    # Перевести в done
    for t in queue["tasks"]:
        if t["id"] == task["id"]:
            t["status"] = final_status

    save_json(GPT_QUEUE, queue)

    # Создать отчёт
    bem_num = "184"
    report_path = create_report(task, final_status, bem_num)
    print(f"Report created: {report_path}")

    # Обновить state
    state["current_task"] = None
    state["last_report"] = report_path
    state["last_tick"] = now_iso()
    save_json(GPT_STATE, state)

    # Записать в exchange.jsonl
    append_exchange_event({
        "timestamp": now_iso(),
        "source": "gpt_scheduler",
        "event_type": "GPT_SCHEDULER_TICK",
        "task_id": task["id"],
        "status": final_status,
        "report": report_path,
        "next_action": "check queue for next pending task"
    })

    print(f"[GPT SCHEDULER TICK] Done. Task {task['id']} → {final_status}")


if __name__ == "__main__":
    main()
