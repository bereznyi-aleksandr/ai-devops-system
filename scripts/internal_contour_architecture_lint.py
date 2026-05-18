#!/usr/bin/env python3
import json
from pathlib import Path
SEP = bytes.fromhex("0a").decode("ascii")
STATE_OUT = Path("governance/state/internal_contour_architecture_lint.json")
REPORT_OUT = Path("governance/reports/internal_contour_architecture_lint.md")
def exists(path):
    p = Path(path)
    return p.exists() and p.stat().st_size > 0
def load_json(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except:
        return {}
def check(name, ok, evidence, severity="high", note=""):
    return {"name": name, "pass": bool(ok), "evidence": evidence, "severity": severity, "note": note}
def main():
    checks = []
    checks.append(check("role_communication_canon_exists", exists("governance/protocols/ROLE_COMMUNICATION_CANON.md"), "governance/protocols/ROLE_COMMUNICATION_CANON.md"))
    checks.append(check("role_execution_evidence_canon_exists", exists("governance/protocols/ROLE_EXECUTION_EVIDENCE_CANON.md"), "governance/protocols/ROLE_EXECUTION_EVIDENCE_CANON.md"))
    checks.append(check("bem605_internal_auditor_package_exists", exists("governance/internal_contour/auditor/inbox/bem625_bem605_hourly_report_internal_auditor_review.json"), "governance/internal_contour/auditor/inbox/bem625_bem605_hourly_report_internal_auditor_review.json"))
    checks.append(check("bem605_mailbox_misroute_annotated", exists("governance/audit_mailbox/meta/bem625_bem605_mailbox_misroute_annotation.json"), "governance/audit_mailbox/meta/bem625_bem605_mailbox_misroute_annotation.json"))
    checks.append(check("auditor_to_auditor_mailbox_lane_exists", Path("governance/audit_mailbox/internal_auditor_to_external_auditor").exists(), "governance/audit_mailbox/internal_auditor_to_external_auditor"))
    route = load_json("governance/provider_gates/bem610_provider_route_decision.json")
    required_route = ["provider_checked", "primary_provider", "reserve_provider", "selected_provider", "reserve_used", "reason"]
    for key in required_route:
        checks.append(check("provider_route_has_" + key, key in route, "governance/provider_gates/bem610_provider_route_decision.json"))
    # Old gpt_to_claude mailbox files are allowed only when annotated or when they are auditor-to-auditor. Existing BEM-605 is annotated as historical misroute.
    old = Path("governance/audit_mailbox/gpt_to_claude/bem605_hourly_report_template_review_request.md")
    annotated = exists("governance/audit_mailbox/meta/bem625_bem605_mailbox_misroute_annotation.json")
    checks.append(check("historical_bem605_mailbox_misroute_not_unannotated", (not old.exists()) or annotated, str(old), note="Old misroute must be annotated and superseded."))
    # Deno must be labeled transport, not internal executor.
    role_canon = Path("governance/protocols/ROLE_COMMUNICATION_CANON.md").read_text(encoding="utf-8", errors="ignore") if Path("governance/protocols/ROLE_COMMUNICATION_CANON.md").exists() else ""
    checks.append(check("deno_labeled_transport_not_executor", "Deno является внешним транспортным адаптером" in role_canon, "governance/protocols/ROLE_COMMUNICATION_CANON.md"))
    failed = [x for x in checks if not x.get("pass")]
    status = "pass" if not failed else "failed"
    blocker = None if not failed else {"code":"INTERNAL_CONTOUR_ARCHITECTURE_LINT_FAILED", "failed": failed}
    result = {"schema_version":"internal_contour_architecture_lint.v1", "status": status, "checks": checks, "blocker": blocker, "created_at":"workflow_runtime"}
    STATE_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATE_OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + SEP, encoding="utf-8")
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Internal Contour Architecture Lint", "", "Status: " + status, "", "## Checks"]
    for x in checks:
        lines.append("- " + x["name"] + ": " + ("PASS" if x.get("pass") else "FAIL") + " | " + x.get("evidence", ""))
    lines.append("")
    lines.append("## Blocker")
    lines.append("null" if blocker is None else json.dumps(blocker, ensure_ascii=False, indent=2))
    REPORT_OUT.write_text(SEP.join(lines) + SEP, encoding="utf-8")
    print(json.dumps({"status": status, "failed": len(failed)}, ensure_ascii=False))
if __name__ == "__main__":
    main()
