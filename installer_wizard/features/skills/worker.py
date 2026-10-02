import importlib.util
import json
import os
import sys
import time

try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (768 * 2**20, 768 * 2**20))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
except (ImportError, ValueError, OSError):
    pass

_cache: dict = {}


def load(path: str):
    mtime = os.path.getmtime(path)
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    spec = importlib.util.spec_from_file_location(f"skill_{len(_cache)}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _cache[path] = (mtime, module)
    return module


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        started = time.perf_counter()
        try:
            req = json.loads(line)
            out = load(req["path"]).run(req["text"])
            if not isinstance(out, dict):
                out = {"result": out}
            out.setdefault("ok", out.get("result") is not None)
            out["ms"] = round((time.perf_counter() - started) * 1000, 2)
            json.dumps(out)
        except Exception as exc:
            out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
        sys.stdout.write(json.dumps(out, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
