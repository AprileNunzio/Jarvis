import json
import os
import time
from collections import deque
from datetime import datetime, timezone

from config import LOG_DIR, STATE_DIR

STATE_FILE = STATE_DIR / "state.json"
AUDIT_FILE = LOG_DIR / "audit.jsonl"
INSTALL_LOG = LOG_DIR / "install.log"

PHASES = {
    "INSTALLING": "Installazione di Jarvis OS",
    "BOOTING": "Avvio dei sistemi",
    "UPDATING": "Aggiornamento in corso",
    "READY": "Jarvis operativo",
    "DEGRADED": "Auto-riparazione in corso",
    "ERROR": "Intervento automatico in corso",
}
PERSISTED = ("installed", "installed_at", "boot_count", "steps", "update", "last_good_rev")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self) -> None:
        self.version = 0
        self.phase = "BOOTING"
        self.phase_since = time.time()
        self.installed = False
        self.installed_at = None
        self.boot_count = 0
        self.last_good_rev = ""
        self.steps: dict = {}
        self.current_step = ""
        self.progress = 0.0
        self.message = "Inizializzazione del supervisore…"
        self.detail = ""
        self.last_error = ""
        self.retry_at = 0.0
        self.components: dict = {}
        self.update: dict = {"last_check": None, "local_rev": "", "remote_rev": "", "available": False,
                             "last_result": ""}
        self.system: dict = {}
        self.presence: dict = {"status": "starting", "people": [], "summary": ""}
        self.pipeline_failed = False
        self.greeting: dict = {}
        self.now_playing: dict = {}
        self.audio_rev = ""
        self.study: dict = {}
        self.mind: dict = {}
        self.laws: dict = {}
        self.features_rev = ""
        self.desk: list = []
        self.screens: list = []
        self.displays: list = []
        self.logs: deque = deque(maxlen=800)
        self.events: deque = deque(maxlen=200)
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for key in PERSISTED:
            if key in data:
                setattr(self, key, data[key])

    def save(self) -> None:
        data = {key: getattr(self, key) for key in PERSISTED}
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, STATE_FILE)

    def touch(self) -> None:
        self.version += 1

    def set_phase(self, phase: str, message: str = "") -> None:
        if phase != self.phase:
            self.event("INFO", f"Fase: {PHASES.get(phase, phase)}", "supervisor")
            self.phase = phase
            self.phase_since = time.time()
        if message:
            self.message = message
        self.touch()

    def log(self, line: str, source: str = "install") -> None:
        entry = {"t": time.time(), "src": source, "msg": line}
        self.logs.append(entry)
        try:
            with INSTALL_LOG.open("a", encoding="utf-8") as fh:
                fh.write(f"{now_iso()} [{source}] {line}\n")
        except OSError:
            pass
        self.touch()

    def event(self, level: str, message: str, component: str = "system") -> None:
        entry = {"ts": now_iso(), "level": level, "component": component, "msg": message}
        self.events.append(entry)
        try:
            with AUDIT_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
        self.touch()

    def snapshot(self, admin: bool = False, log_lines: int = 14) -> dict:
        snap = {
            "version": self.version,
            "phase": self.phase,
            "phase_label": PHASES.get(self.phase, self.phase),
            "phase_since": self.phase_since,
            "installed": self.installed,
            "boot_count": self.boot_count,
            "current_step": self.current_step,
            "progress": round(self.progress, 1),
            "message": self.message,
            "detail": self.detail,
            "last_error": self.last_error,
            "retry_in": max(0, int(self.retry_at - time.time())) if self.retry_at else 0,
            "steps": self.steps,
            "components": self.components,
            "system": self.system,
            "presence": self.presence,
            "greeting": self.greeting,
            "now_playing": self.now_playing,
            "audio_rev": self.audio_rev,
            "study": self.study,
            "features_rev": self.features_rev,
            "desk": self.desk,
            "screens": self.screens,
            "displays": self.displays,
            "logs": list(self.logs)[-log_lines:],
        }
        if admin:
            snap["update"] = self.update
            snap["events"] = list(self.events)[-60:]
            snap["last_good_rev"] = self.last_good_rev
        return snap


store = Store()
