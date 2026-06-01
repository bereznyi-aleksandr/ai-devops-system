import json


def failover_for_contour(contour, mode):
    if contour not in {"C1", "C2", "C3"}:
        return {"ok": False, "release_pass": False, "error": "unknown contour"}
    if mode == "mock_e2e":
        return {"ok": True, "release_pass": False, "contour": contour, "fallback": "mock"}
    return {"ok": False, "release_pass": False, "error": "mock fallback denied outside mock_e2e"}


def main():
    result = failover_for_contour("C1", "mock_e2e")
    print(json
