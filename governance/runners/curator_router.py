import json


def route(contour):
    if contour not in {"C1", "C2", "C3"}:
        return {"ok": False, "release_pass": False, "error": "unknown contour"}
    return {"ok": True, "release_pass": False, "contour": contour, "director": f"DIR-{contour}", "curator": f"CUR-{contour}", "worker": f"WRK-{contour}"}


def main():
    result = route("C1")
    print(json
