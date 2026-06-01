import json


def aggregate(reports):
    return {"ok": True, "release_pass": False, "reports_count": len(reports), "summary": "local aggregate complete"}


def main():
    result = aggregate([{"ok": True}])
    print(json
