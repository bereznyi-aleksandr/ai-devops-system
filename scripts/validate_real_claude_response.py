#!/usr/bin/env python3
import sys
from pathlib import Path
D=Path("governance/audit_mailbox/claude_to_gpt")
real=[]
blockers=[]
if D.exists():
    for p in sorted(D.glob("*")):
        if not p.is_file():
            continue
        txt=p.read_text(encoding="utf-8", errors="ignore")
        up=txt.upper(); low=(p.name+" "+txt).lower()
        bad="NOT CLAUDE APPROVAL" in up or "RUNTIME BLOCKER" in up or "not treat this as claude" in low
        ok=("DECISION:" in up and ("APPROVED" in up or "CHANGE_REQUIRED" in up or "BLOCKED" in up) and ("CLAUDE RESPONSE" in up or "Claude Internal Auditor" in txt))
        if bad:
            blockers.append(str(p))
        elif ok:
            real.append(str(p))
if real:
    print("real_claude_response_found="+real[-1])
    sys.exit(0)
print("real_claude_response_missing; blocker_files="+str(blockers[-5:]))
sys.exit(2)
