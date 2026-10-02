import asyncio
import glob
import json
import logging
import os
import re
import shutil
import time
import unicodedata
from pathlib import Path

import psutil

from config import DEMO, FEATURES_DIR, EDITABLE_KEYS, SECRET_KEYS, STATE_DIR, read_env, write_env
from state import store

log = logging.getLogger("jarvis.features")

SYSTEM_DIR = FEATURES_DIR
USER_DIR = STATE_DIR / "features"
STATE_FILE = STATE_DIR / "features.json"
SCAN_EVERY = 20
MODES = ("auto", "1", "0")
CATEGORIES = {
    "assistente": "Assistente",
    "percezione": "Percezione",
    "casa": "Casa e persone",
    "conoscenza": "Conoscenza",
    "comunicazione": "Comunicazione",
    "sistema": "Sistema",
    "altro": "Altro",
}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")
_SETTING_TYPES = {"text", "select", "color", "secret", "number", "bool"}



def _alphabetical(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold().strip()


class Registry:
    def __init__(self) -> None:
        self.features: dict[str, dict] = {}
        self.errors: list[dict] = []
        self.signature = ""
        self.hooks: dict[str, dict] = {}
        self.hw: dict = {}
        self.converge = None
        self.state = self._load_state()
        USER_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_state() -> dict:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self) -> None:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE_FILE)

    def _rec(self, fid: str) -> dict:
        return self.state.setdefault(fid, {})

    def register_hook(self, fid: str, get, set_) -> None:
        self.hooks[fid] = {"get": get, "set": set_}

    def scan(self) -> bool:
        paths = sorted(glob.glob(str(SYSTEM_DIR / "*" / "feature.json")) + glob.glob(str(USER_DIR / "*" / "feature.json")))
        sig = "|".join(f"{p}:{os.path.getmtime(p)}" for p in paths if os.path.exists(p))
        if sig == self.signature:
            return False
        first = not self.signature
        self.signature = sig
        found, errors = {}, []
        for p in paths:
            source = "system" if Path(p).is_relative_to(SYSTEM_DIR) else "user"
            try:
                manifest = self._validate(json.loads(Path(p).read_text(encoding="utf-8")), Path(p).parent.name)
            except (OSError, ValueError, TypeError) as exc:
                errors.append({"path": p, "error": str(exc)[:200]})
                continue
            if manifest["id"] in found and source == "user":
                errors.append({"path": p, "error": f"id «{manifest['id']}» già usato da una funzionalità di sistema"})
                continue
            manifest["source"] = manifest.get("source") if source == "user" and manifest.get("source") in ("ai", "user") \
                else ("user" if source == "user" else "system")
            manifest["dir"] = str(Path(p).parent)
            found[manifest["id"]] = manifest
        new = [f for f in found if f not in self.features]
        self.features, self.errors = found, errors
        for fid in found:
            rec = self._rec(fid)
            if "mode" not in rec:
                rec["mode"] = self._initial_mode(found[fid])
                rec["discovered"] = time.time()
            rec.setdefault("pinned", bool(found[fid].get("pinned")))
        self._save_state()
        if not first:
            for fid in new:
                store.event("INFO", f"Nuova funzionalità disponibile: {found[fid]['name']}", "features")
        for e in errors:
            log.warning("Manifest non valido %s: %s", e["path"], e["error"])
        store.features_rev = sig[-12:] + str(len(found))
        store.touch()
        return True

    @staticmethod
    def _validate(m: dict, folder: str) -> dict:
        if not isinstance(m, dict):
            raise ValueError("il manifest deve essere un oggetto JSON")
        m.setdefault("id", folder)
        if not _ID_RE.match(str(m["id"])):
            raise ValueError("id non valido (minuscole, cifre, - e _)")
        if not str(m.get("name", "")).strip():
            raise ValueError("manca il nome")
        m["category"] = m.get("category") if m.get("category") in CATEGORIES else "altro"
        m.setdefault("icon", "◆")
        m.setdefault("description", "")
        m.setdefault("order", 500)
        toggle = m.get("toggle")
        if toggle is not None:
            if not isinstance(toggle, dict) or not (toggle.get("env") or toggle.get("hook")):
                raise ValueError("toggle deve indicare env oppure hook")
            if toggle.get("env") and not re.match(r"^[A-Z][A-Z0-9_]*$", toggle["env"]):
                raise ValueError("toggle.env non valido")
        for s in m.setdefault("settings", []):
            if not isinstance(s, dict) or not s.get("key") or s.get("type", "text") not in _SETTING_TYPES:
                raise ValueError(f"impostazione non valida: {s}")
            s.setdefault("type", "text")
            s.setdefault("label", s["key"])
        m.setdefault("capabilities", [])
        m.setdefault("requires", {})
        return m

    def _initial_mode(self, m: dict) -> str:
        t = m.get("toggle") or {}
        if t.get("env"):
            value = read_env().get(t["env"], "")
            if t.get("tri") and value in MODES:
                return value
            if value == "0":
                return "0"
        if t.get("hook") and t["hook"] in self.hooks:
            try:
                if not self.hooks[t["hook"]]["get"]():
                    return "0"
            except Exception:
                pass
        return "auto"

    async def probe_hardware(self) -> None:
        vram_gb, gpu_name = 0.0, ""
        if not DEMO and shutil.which("nvidia-smi"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "nvidia-smi", "--query-gpu=name,compute_cap,memory.total", "--format=csv,noheader,nounits",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                out, _ = await asyncio.wait_for(proc.communicate(), 10)
                name, cap, vram = [x.strip() for x in out.decode().splitlines()[0].split(",")]
                if float(cap) >= 5.0:
                    vram_gb, gpu_name = round(float(vram) / 1024, 1), name
            except (OSError, ValueError, IndexError, asyncio.TimeoutError):
                pass
        self.hw = {"ram_gb": round(psutil.virtual_memory().total / 2**30, 1), "cores": psutil.cpu_count() or 1,
                   "vram_gb": vram_gb, "gpu": gpu_name,
                   "video": bool(glob.glob("/dev/video*")) or DEMO}

    def _check_requires(self, m: dict, effective: dict) -> list[str]:
        req, hw, missing = m.get("requires") or {}, self.hw, []
        if req.get("ram_gb") and hw.get("ram_gb", 0) + 0.3 < req["ram_gb"]:
            missing.append(f"servono {req['ram_gb']} GB di RAM (presenti {hw.get('ram_gb')})")
        if req.get("gpu_vram_gb") and hw.get("vram_gb", 0) < req["gpu_vram_gb"]:
            missing.append(f"serve una GPU NVIDIA con almeno {req['gpu_vram_gb']} GB"
                           + (f" (presente {hw['gpu']}, {hw['vram_gb']} GB)" if hw.get("gpu") else " (non presente)"))
        if req.get("cores") and hw.get("cores", 0) < req["cores"]:
            missing.append(f"servono {req['cores']} core")
        if req.get("video") and not hw.get("video"):
            missing.append("nessuna webcam collegata")
        for cmd in req.get("commands", []):
            if not DEMO and not shutil.which(cmd):
                missing.append(f"programma «{cmd}» non installato")
        env = read_env() if req.get("env") else {}
        for key in req.get("env", []):
            if not env.get(key):
                missing.append("da configurare nelle impostazioni")
                break
        for dep in req.get("features", []):
            if dep in self.features and not effective.get(dep, {}).get("enabled"):
                missing.append(f"richiede «{self.features[dep]['name']}» attiva")
        return missing

    def evaluate(self) -> dict:
        effective: dict = {}
        order = sorted(self.features.values(), key=lambda m: len((m.get("requires") or {}).get("features", [])))
        for m in order:
            fid, mode = m["id"], self._rec(m["id"]).get("mode", "auto")
            if not m.get("toggle"):
                effective[fid] = {"enabled": True, "mode": "1", "reason": "Sempre attiva", "fixed": True}
                continue
            missing = self._check_requires(m, effective)
            if mode == "0":
                effective[fid] = {"enabled": False, "mode": mode, "reason": "Disattivata da te"}
            elif mode == "1":
                effective[fid] = {"enabled": True, "mode": mode,
                                  "reason": ("Attivata a tuo rischio: " + "; ".join(missing)) if missing else "Attivata da te",
                                  "risk": bool(missing)}
            else:
                effective[fid] = {"enabled": not missing, "mode": mode,
                                  "reason": ("Automatico: " + "; ".join(missing)) if missing
                                  else "Automatico: attiva, l'hardware è adatto"}
        return effective

    def enabled(self, fid: str) -> bool:
        return self.evaluate().get(fid, {}).get("enabled", True)

    def _current(self, m: dict, env: dict):
        t = m["toggle"]
        if t.get("env"):
            value = env.get(t["env"], t.get("default", "1"))
            return value if t.get("tri") else value != "0"
        hook = self.hooks.get(t.get("hook"))
        return bool(hook["get"]()) if hook else None

    async def sync(self) -> None:
        if store.phase not in ("READY", "DEGRADED"):
            return
        env, effective = read_env(), self.evaluate()
        env_updates, steps, changed = {}, [], []
        for fid, m in self.features.items():
            t = m.get("toggle")
            if not t:
                continue
            eff = effective[fid]
            want = eff["mode"] if t.get("tri") else eff["enabled"]
            current = self._current(m, env)
            if current is None or current == want:
                continue
            if t.get("env"):
                env_updates[t["env"]] = want if t.get("tri") else ("1" if want else "0")
                steps += t.get("apply", [])
            else:
                try:
                    self.hooks[t["hook"]]["set"](want)
                except Exception as exc:
                    log.warning("Aggancio %s non riuscito: %s", fid, exc)
                    continue
            changed.append(f"{m['name']} {'attivata' if (want if not t.get('tri') else eff['enabled']) else 'disattivata'}")
        if env_updates:
            write_env(env_updates)
        for c in changed:
            store.event("INFO", c, "features")
        if steps and self.converge:
            await self.converge(sorted(set(steps)), "Applicazione delle funzionalità")
        if changed:
            store.touch()

    def set_mode(self, fid: str, mode: str) -> None:
        if fid not in self.features:
            raise KeyError(fid)
        if mode not in MODES:
            raise ValueError("Modalità non valida")
        if not self.features[fid].get("toggle"):
            raise ValueError("Questa funzionalità è sempre attiva")
        self._rec(fid)["mode"] = mode
        self._save_state()
        store.touch()

    def set_pinned(self, fid: str, pinned: bool) -> None:
        if fid not in self.features:
            raise KeyError(fid)
        self._rec(fid)["pinned"] = bool(pinned)
        self._save_state()
        store.touch()

    def note_env_change(self, updates: dict) -> None:
        for fid, m in self.features.items():
            t = m.get("toggle") or {}
            if t.get("env") in updates:
                value = updates[t["env"]]
                self._rec(fid)["mode"] = value if value in MODES and t.get("tri") else ("0" if value == "0" else "1")
        self._save_state()

    def note_hook_change(self, fid: str, enabled: bool) -> None:
        if fid in self.features:
            rec = self._rec(fid)
            if not enabled:
                rec["mode"] = "0"
            elif rec.get("mode") == "0":
                rec["mode"] = "auto"
            self._save_state()

    def settings_of(self, fid: str) -> dict:
        m, env, local = self.features[fid], read_env(), self._rec(fid).get("settings", {})
        values = {}
        for s in m["settings"]:
            v = env.get(s["key"], s.get("default", "")) if s.get("env", True) and s["key"].isupper() \
                else local.get(s["key"], s.get("default", ""))
            if s["type"] == "secret" or s["key"] in SECRET_KEYS:
                v = ("••••" + str(v)[-4:]) if v else ""
            values[s["key"]] = v
        return values

    def save_settings(self, fid: str, body: dict) -> tuple[dict, list]:
        m = self.features[fid]
        env_updates, steps, local = {}, [], self._rec(fid).setdefault("settings", {})
        for s in m["settings"]:
            if s["key"] not in body:
                continue
            value = str(body[s["key"]]).strip()
            if (s["type"] == "secret" or s["key"] in SECRET_KEYS) and value.startswith("••••"):
                continue
            if s["type"] == "select" and s.get("options") and value not in [str(o.get("value", o)) if isinstance(o, dict) else str(o) for o in s["options"]]:
                raise ValueError(f"Valore non valido per {s['label']}")
            if "\n" in value or len(value) > 500:
                raise ValueError(f"Valore non valido per {s['label']}")
            if s.get("env", True) and s["key"].isupper():
                if s["key"] not in EDITABLE_KEYS and m["source"] != "system":
                    raise ValueError(f"{s['key']} non è modificabile da una funzionalità esterna")
                env_updates[s["key"]] = value
                steps += s.get("apply", [])
            else:
                local[s["key"]] = value
        self._save_state()
        return env_updates, steps

    def listing(self) -> dict:
        effective = self.evaluate()
        items = []
        for m in sorted(self.features.values(), key=lambda x: _alphabetical(x["name"])):
            rec = self._rec(m["id"])
            items.append({k: v for k, v in m.items() if k not in ("dir",)} | {
                "state": effective[m["id"]], "pinned": rec.get("pinned", False),
                "new": time.time() - rec.get("discovered", 0) < 3 * 86400 and m["source"] != "system",
                "values": self.settings_of(m["id"])})
        return {"features": items, "categories": CATEGORIES, "errors": self.errors, "hardware": self.hw,
                "user_dir": str(USER_DIR)}

    async def run(self) -> None:
        await self.probe_hardware()
        while True:
            try:
                self.scan()
                if int(time.time()) % 300 < SCAN_EVERY:
                    await self.probe_hardware()
                await self.sync()
            except Exception:
                log.exception("Registro delle funzionalità")
            await asyncio.sleep(SCAN_EVERY)


registry = Registry()
