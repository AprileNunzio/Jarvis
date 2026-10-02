import json
import time

from config import STATE_DIR

from features.automations.schema import new_id, validate

FILE = STATE_DIR / "automations.json"
RUNS_FILE = STATE_DIR / "automation_runs.jsonl"
KEEP_RUNS = 400


class InvalidAutomation(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class Library:
    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self.rev = 0
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(FILE.read_text(encoding="utf-8"))
            self.items = {a["id"]: a for a in data if isinstance(a, dict) and a.get("id")}
        except (OSError, ValueError):
            self.items = {}

    def save(self) -> None:
        self.rev += 1
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(list(self.items.values()), ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(FILE)

    def all(self) -> list[dict]:
        return sorted(self.items.values(), key=lambda a: (not a.get("enabled", True), a.get("name", "").lower()))

    def get(self, ref: str) -> dict:
        if ref in self.items:
            return self.items[ref]
        low = str(ref).lower().strip()
        exact = [a for a in self.items.values() if a["name"].lower() == low]
        found = exact or [a for a in self.items.values() if low and low in a["name"].lower()]
        if not found:
            raise KeyError(ref)
        return found[0]

    def add(self, spec: dict, origin: str = "pannello") -> dict:
        a, errors = validate(spec)
        if errors:
            raise InvalidAutomation(errors)
        a["id"] = new_id()
        a.update(created=time.time(), updated=time.time(), origin=origin, runs=0, last_run=0, last_status="", last_error="")
        self.items[a["id"]] = a
        self.save()
        return a

    def update(self, aid: str, spec: dict) -> dict:
        old = self.items[aid]
        merged = {**old, **spec}
        a, errors = validate(merged)
        if errors:
            raise InvalidAutomation(errors)
        for k in ("id", "created", "origin", "runs", "last_run", "last_status", "last_error"):
            a[k] = old.get(k)
        a["updated"] = time.time()
        self.items[aid] = a
        self.save()
        return a

    def patch(self, aid: str, **fields) -> dict:
        self.items[aid].update(fields)
        self.save()
        return self.items[aid]

    def remove(self, aid: str) -> None:
        self.items.pop(aid, None)
        self.save()

    def duplicate(self, aid: str) -> dict:
        src = dict(self.items[aid])
        src["name"] = f"{src['name']} (copia)"
        src["enabled"] = False
        return self.add(src, origin="copia")

    def record(self, run_view: dict) -> None:
        a = self.items.get(run_view["automation"])
        if a:
            a["runs"] = a.get("runs", 0) + (1 if run_view["status"] != "condizioni non soddisfatte" else 0)
            a["last_run"] = run_view["started"]
            a["last_status"] = run_view["status"]
            a["last_error"] = run_view.get("error", "")
            self.save()
        try:
            with RUNS_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(run_view, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    def history(self, limit: int = 100, automation: str = "") -> list[dict]:
        try:
            lines = RUNS_FILE.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        if len(lines) > KEEP_RUNS * 2:
            lines = lines[-KEEP_RUNS:]
            RUNS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out = []
        for line in reversed(lines):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if automation and r.get("automation") != automation:
                continue
            out.append(r)
            if len(out) >= limit:
                break
        return out

    def find_run(self, rid: str) -> dict | None:
        return next((r for r in self.history(KEEP_RUNS) if r.get("id") == rid), None)


library = Library()
