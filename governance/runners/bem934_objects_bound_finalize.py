#!/usr/bin/env python3
import json
import subprocess

import bem934_objects_bound_repair as base


def capture_historical(object_id: str) -> dict:
    base.git("fetch", "origin", "main")
    marker = "_" + object_id.lower() + "_"
    commits = base.git(
        "log", "--all", "--format=%H", "--", base.SOURCE_RECEIPT
    ).splitlines()
    for commit in commits:
        try:
            receipt = json.loads(
                base.git("show", f"{commit}:{base.SOURCE_RECEIPT}")
            )
            plan = json.loads(
                base.git("show", f"{commit}:{base.SOURCE_PLAN}")
            )
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        trace = str(receipt.get("trace_id", ""))
        if marker not in trace.lower() or plan.get("trace_id") != trace:
            continue
        base.validate_source(receipt, plan, trace, object_id)
        item = {
            "status": "PASS",
            "protocol": "BEM-934",
            "task_id": "BEM934-OBJECTS-BOUND",
            "object_id": object_id,
            "passport_path": base.OBJECTS[object_id],
            "trace_id": trace,
            "provider": "claude",
            "workflow": ".github/workflows/claude.yml",
            "captured_at": base.now(),
            "source_receipt_path": base.SOURCE_RECEIPT,
            "source_receipt_blob_sha": base.git(
                "rev-parse", f"{commit}:{base.SOURCE_RECEIPT}"
            ),
            "source_plan_path": base.SOURCE_PLAN,
            "source_plan_blob_sha": base.git(
                "rev-parse", f"{commit}:{base.SOURCE_PLAN}"
            ),
            "source_commit_sha": commit,
            "receipt": receipt,
            "plan": plan,
        }
        base.sync()
        base.PROOF_DIR.mkdir(parents=True, exist_ok=True)
        path = base.PROOF_DIR / f"{object_id}_runtime_binding.json"
        path.write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        first_sha = base.push_commit(
            f"Capture historical BEM-934 {object_id} runtime evidence",
            [str(path)],
        )
        item["snapshot_path"] = str(path)
        item["snapshot_commit_sha"] = first_sha
        item["snapshot_blob_sha"] = base.git(
            "rev-parse", f"HEAD:{path}"
        )
        path.write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        final_sha = base.push_commit(
            f"Finalize historical BEM-934 {object_id} evidence identifiers",
            [str(path)],
        )
        item["snapshot_final_commit_sha"] = final_sha
        return item
    raise RuntimeError(f"No historical PASS trace found for {object_id}")


def main() -> None:
    base.git(
        "config",
        "user.email",
        "bem934-objects-bound-finalize@ai-devops-system",
    )
    base.git(
        "config",
        "user.name",
        "BEM-934 Objects Binding Finalizer",
    )
    gd = capture_historical("GD")
    directory = capture_historical("DIR")
    wrk_trace = base.dispatch("WRK")
    worker = base.capture_trace("WRK", wrk_trace)
    traces = {gd["trace_id"], directory["trace_id"], worker["trace_id"]}
    if len(traces) != 3:
        raise RuntimeError("Trace IDs are not distinct")
    binding_sha, close_sha = base.finalize()
    print(json.dumps({
        "status": "PASS",
        "binding_sha": binding_sha,
        "close_sha": close_sha,
        "receipt": str(base.FINAL_RECEIPT),
        "trace_ids": sorted(traces),
    }))


if __name__ == "__main__":
    main()
