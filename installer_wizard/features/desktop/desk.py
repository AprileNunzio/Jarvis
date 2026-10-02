import asyncio
import glob
import json
import logging
import os
import re
import time
from pathlib import Path

from config import STATE_DIR, WIDGETS_DIR
from features.desktop.screens import screens
from state import store

log = logging.getLogger("jarvis.widgets")

SYSTEM_DIR = WIDGETS_DIR
USER_DIR = STATE_DIR / "widgets"
STATE_FILE = STATE_DIR / "widgets.json"
SIZES = ("s", "m", "l", "full")
FILES = {"widget.js": "application/javascript", "widget.css": "text/css"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")


class Desk:
    def __init__(self) -> None:
        self.widgets: dict[str, dict] = {}
        self.errors: list[dict] = []
        self.signature = ""
        self.instances: dict[str, dict] = {}
        self.sources: dict = {}
        self.prefs = self._load()
        USER_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load() -> dict:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.prefs, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE_FILE)

    def scan(self) -> bool:
        paths = sorted(glob.glob(str(SYSTEM_DIR / "*" / "widget.json")) + glob.glob(str(USER_DIR / "*" / "widget.json")))
        sig = "|".join(f"{p}:{os.path.getmtime(p)}" for p in paths if os.path.exists(p))
        if sig == self.signature:
            return False
        self.signature = sig
        found, errors = {}, []
        for p in paths:
            folder = Path(p).parent
            try:
                m = json.loads(Path(p).read_text(encoding="utf-8"))
                m.setdefault("id", folder.name)
                if not _ID_RE.match(str(m["id"])) or not m.get("name"):
                    raise ValueError("id o nome non validi")
                if not (folder / "widget.js").exists():
                    raise ValueError("manca widget.js")
                if m["id"] in found:
                    raise ValueError("id già usato")
            except (OSError, ValueError, TypeError) as exc:
                errors.append({"path": p, "error": str(exc)[:200]})
                continue
            m["priority"] = max(0, min(100, int(m.get("priority", 50))))
            m["size"] = m.get("size") if m.get("size") in SIZES else "m"
            m.setdefault("icon", "▣")
            m.setdefault("description", "")
            m.setdefault("intents", [])
            m.setdefault("replaces", [])
            m["chrome"] = m.get("chrome", True) is not False
            m["overlay"] = m.get("overlay") is True
            m["source"] = "system" if folder.is_relative_to(SYSTEM_DIR) else (m.get("source") if m.get("source") in ("ai", "user") else "user")
            m["dir"] = str(folder)
            m["has_css"] = (folder / "widget.css").exists()
            m["rev"] = str(int(max(os.path.getmtime(f) for f in folder.glob("widget.*"))))
            found[m["id"]] = m
        new = [w for w in found if w not in self.widgets and self.widgets]
        self.widgets, self.errors = found, errors
        for w in new:
            store.event("INFO", f"Nuovo widget disponibile: {found[w]['name']}", "widgets")
        for e in errors:
            log.warning("Widget non valido %s: %s", e["path"], e["error"])
        self.publish()
        return True

    def enabled(self, wid: str) -> bool:
        return self.prefs.get(wid, {}).get("enabled", True)

    def priority(self, wid: str) -> int:
        p = self.prefs.get(wid, {}).get("priority")
        return int(p) if p is not None else self.widgets.get(wid, {}).get("priority", 50)

    def set_prefs(self, wid: str, body: dict) -> None:
        if wid not in self.widgets:
            raise KeyError(wid)
        rec = self.prefs.setdefault(wid, {})
        if "enabled" in body:
            rec["enabled"] = bool(body["enabled"])
        if "priority" in body:
            rec["priority"] = None if body["priority"] in ("", None) else max(0, min(100, int(body["priority"])))
        self._save()
        self.publish()

    def set_position(self, wid: str, x: float | None, y: float | None) -> None:
        if wid not in self.widgets:
            raise KeyError(wid)
        rec = self.prefs.setdefault(wid, {})
        if x is None or y is None:
            rec.pop("pos", None)
        else:
            rec["pos"] = {"x": max(0.0, min(1.0, float(x))), "y": max(0.0, min(1.0, float(y)))}
        self._save()
        self.publish()

    def set_screen(self, wid: str, screen: int | None) -> None:
        if wid not in self.widgets:
            raise KeyError(wid)
        rec = self.prefs.setdefault(wid, {})
        if screen is None:
            rec.pop("screen", None)
        else:
            rec["screen"] = int(screen)
            rec.pop("pos", None)
        self._save()
        self.publish()

    def screen_hello(self, n: int, x: int, w: int, h: int, local: bool = False, ear: str = "", perf: str = "",
                     client: str = "") -> None:
        screens.perf(client or "?", n, local, w, h, perf)
        if screens.hello(n, x, w, h, local, ear):
            self.publish()

    def position(self, wid: str):
        return self.prefs.get(wid, {}).get("pos") or self.widgets.get(wid, {}).get("pos")

    def show(self, wid: str, data: dict | None = None, key: str | None = None, ttl: float | None = None,
             priority: int | None = None, intent: bool = False) -> None:
        m = self.widgets.get(wid)
        if not m:
            return
        key = key or wid
        ttl = ttl if ttl is not None else m.get("ttl")
        old = self.instances.get(key)
        self.instances[key] = {
            "key": key, "id": wid, "data": data or {}, "priority": priority, "intent": intent,
            "shown_at": old["shown_at"] if old else time.time(),
            "expires_at": time.time() + float(ttl) if ttl else None,
        }
        self.publish()

    def hide(self, wid: str | None = None, key: str | None = None) -> None:
        keys = [key] if key else [k for k, i in self.instances.items() if i["id"] == wid]
        if any(self.instances.pop(k, None) for k in keys):
            self.publish()

    def on_intent(self, intent: str, ui: dict) -> None:
        wanted = {m["id"] for m in self.widgets.values() if intent in m["intents"]}
        self.dismiss_intents(keep=wanted)
        for m in self.widgets.values():
            if m["id"] in wanted:
                panel = next((p for p in ui.get("panels", []) if p.get("type") == m.get("panel_type")), None)
                self.show(m["id"], (panel or {}).get("data") or {"title": ui.get("title", "")}, intent=True)

    def dismiss_intents(self, keep: set | None = None) -> None:
        keys = [k for k, i in self.instances.items() if i.get("intent") and i["id"] not in (keep or set())]
        for k in keys:
            self.instances.pop(k, None)
        if keys:
            self.publish()

    def active(self) -> list[dict]:
        now = time.time()
        out, replaced = [], set()
        items = [i for i in self.instances.values()
                 if (not i["expires_at"] or i["expires_at"] > now) and i["id"] in self.widgets and self.enabled(i["id"])]
        for i in items:
            replaced.update(self.widgets[i["id"]]["replaces"])
        for i in items:
            if i["id"] in replaced:
                continue
            m = self.widgets[i["id"]]
            prio = i["priority"] if i["priority"] is not None else self.priority(i["id"])
            out.append({**i, "priority": prio, "size": m["size"], "name": m["name"], "icon": m["icon"],
                        "rev": m["rev"], "css": m["has_css"], "chrome": m.get("chrome", True),
                        "pos": self.position(i["id"]), "overlay": m.get("overlay", False),
                        "takeover": prio >= 90 and m["size"] == "full"})
        out.sort(key=lambda x: (-x["priority"], -x["shown_at"]))
        wanted = {wid: p["screen"] for wid, p in self.prefs.items() if p.get("screen") is not None}
        return screens.assign(out, wanted)

    def publish(self) -> None:
        store.desk = self.active()
        store.touch()

    def register_source(self, name: str, fn) -> None:
        self.sources[name] = fn

    def _bindings(self) -> None:
        for m in self.widgets.values():
            bind = m.get("bind")
            if not bind:
                continue
            attr, when = (bind, None) if isinstance(bind, str) else (bind.get("attr"), bind.get("when"))
            source = self.sources.get(attr)
            value = source() if source else getattr(store, attr, None) if attr else None
            ok = bool(value) and (not when or (isinstance(value, dict) and all(value.get(k) == v for k, v in when.items())))
            key = f"bind:{m['id']}"
            if ok:
                current = self.instances.get(key)
                if not current or current["data"] != value:
                    self.show(m["id"], value if isinstance(value, dict) else {"value": value}, key=key, ttl=0)
            elif key in self.instances:
                self.hide(key=key)

    def listing(self) -> dict:
        return {"widgets": [{k: v for k, v in m.items() if k != "dir"} | {"enabled": self.enabled(m["id"]),
                             "effective_priority": self.priority(m["id"])}
                            for m in sorted(self.widgets.values(), key=lambda x: -self.priority(x["id"]))],
                "active": self.active(), "errors": self.errors, "user_dir": str(USER_DIR)}

    def file(self, wid: str, name: str) -> Path | None:
        m = self.widgets.get(wid)
        if not m or name not in FILES:
            return None
        path = Path(m["dir"]) / name
        return path if path.exists() else None

    async def run(self) -> None:
        tick = 0
        while True:
            try:
                if tick % 20 == 0:
                    self.scan()
                self._bindings()
                if screens.changed():
                    self.publish()
                expired = [k for k, i in self.instances.items() if i["expires_at"] and i["expires_at"] <= time.time()]
                for k in expired:
                    self.instances.pop(k, None)
                if expired:
                    self.publish()
            except Exception:
                log.exception("Desktop dei widget")
            tick += 1
            await asyncio.sleep(1)


desk = Desk()
