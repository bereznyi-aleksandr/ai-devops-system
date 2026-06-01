import json


def assign(test_id="bem1284", preferred="C1"):
    contour = preferred if preferred in {"C1", "C2", "C3"} else "C1"
    return {"ok": True, "release_pass": False, "test_id": test_id, "contour": contour}


def main():
    result = assign()
    print(json
