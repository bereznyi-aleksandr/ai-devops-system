import ast
from pathlib import Path

def test_governance_runners_have_main_and_entrypoint():
    runners=sorted(Path("governance/runners").glob("*.py"))
    assert runners, "governance/runners has no python files"
    broken=[]
    for path in runners:
        text=path.read_text(encoding="utf-8", errors="replace")
        try:
            tree=ast.parse(text)
        except SyntaxError as exc:
            broken.append(f"{path}: SyntaxError {exc}")
            continue
        has_main=any(isinstance(n, ast.FunctionDef) and n.name=="main" for n in tree.body)
        has_entry="__main__" in text
        if not has_main or not has_entry:
            broken.append(f"{path}: missing main/__main__")
    assert not broken, "\n".join(broken)
