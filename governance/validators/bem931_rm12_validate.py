#!/usr/bin/env python3
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
validators = [
    "bem931_rm01_04_validate.py",
    "bem931_rm05_validate.py",
    "bem931_rm06_validate.py",
    "bem931_rm07_validate.py",
    "bem931_rm08_10_validate.py",
    "bem931_rm11_validate.py",
]
for validator in validators:
    subprocess.check_call(["python3", str(ROOT / "governance/validators" / validator)], cwd=ROOT)
subprocess.check_call(["python3", str(ROOT / "governance/runtime/bem931_minimal_governance_loop.py")], cwd=ROOT)
print("PASS: BEM-931 RM12 full minimal governance loop validation chain")
