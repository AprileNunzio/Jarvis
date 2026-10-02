import asyncio
import logging
import time
from pathlib import Path

import httpx

from config import CORE_URL, DEMO, STATE_DIR, ollama_remote, ollama_url, read_env
from state import store

log = logging.getLogger("jarvis.health")

COMPONENTS = {
    "docker": "Motore container",
    "ollama": "Motore neurale",
    "llm": "Rete linguistica",
    "core": "Jarvis Core",
    "qdrant": "Memoria vettoriale",
    "voice": "Voce neurale",
    "vision": "Visione",
    "ear": "Ascolto vocale",
    "kiosk": "Display",
    "disk": "Archiviazione",
}
CRITICAL = {"docker", "ollama", "core"}


async def sh(*cmd: str, timeout: float = 60) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "timeout"
    return proc.returncode or 0, out.decode("utf-8", "replace").strip()


EAR_LOG = ("Display", "Errore", "Pagina", "Connessione", "Rilevatore", "errore", "Traceback")


async def ear_log() -> list[str]:
    code, out = await sh("journalctl", "-u", "jarvis-ear", "-n", "40", "--no-pager", "-o", "cat", timeout=5)
    if code != 0:
        return []
    lines = [ln.split("] ", 1)[-1][:120] for ln in out.splitlines() if any(k in ln for k in EAR_LOG)]
    return lines[-4:]


async def kiosk_check() -> dict:
    code, out = await sh("ps", "-u", "jarvis-kiosk", "-o", "args=", timeout=5)
    windows = [ln for ln in out.splitlines() if "chromium" in ln and "--user-data-dir" in ln and "--type=" not in ln]
    if code != 0 or not windows:
        return {"status": "warn", "detail": "Sessione grafica assente"}
    from features.desktop.screens import screens
    monitors = max(1, len({s["n"] for s in screens.active() if s.get("local")}))
    if len(windows) > monitors:
        return {"status": "warn", "detail": f"{len(windows)} finestre Chromium per {monitors} monitor: "
                                            "è rimasta aperta una sessione vecchia"}
    return {"status": "ok", "detail": f"Chromium attivo ({len(windows)} finestr{'a' if len(windows) == 1 else 'e'})"}


def kiosk_hint() -> str:
    from features.desktop.screens import screens
    local = [s for s in screens.active() if s.get("local")]
    if not local:
        hint = " — nessun display locale del kiosk risponde (la pagina non è caricata su 127.0.0.1)"
    else:
        hint = f" — display locale presente, stato ascolto: {local[0].get('ear') or 'sconosciuto'}"
    try:
        lines = Path("/home/jarvis-kiosk/.cache/jarvis-kiosk.log").read_text(errors="ignore").splitlines()
        last = next((ln for ln in reversed(lines) if ln.strip()), "")
        hint += f" · kiosk: {last[-160:]}" if last else ""
    except OSError:
        pass
    return hint


def mic_check(env: dict) -> dict | None:
    import json as _json
    if env.get("JARVIS_KIOSK", "1") == "0":
        return None
    try:
        link = _json.loads((STATE_DIR / "ear_link.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    now, report = time.time(), getattr(store, "mic", None) or {}
    if now - link.get("at", 0) > 30:
        return None
    service = f" · errore del servizio: {link['error']}" if link.get("error") and now - link.get("error_at", 0) < 900 else ""
    if report.get("error") and now - report.get("at", 0) < 120:
        return {"status": "warn", "mic": True, "detail": f"Microfono del display: {report['error']} "
                f"({report.get('inputs', 0)} ingressi audio visti dal browser){service}"}
    if not link.get("clients") and now - link.get("since", now) > 90:
        return {"status": "warn", "mic": True, "detail": "Il display non è collegato all'ascolto" + kiosk_hint()}
    if link.get("clients") and now - link.get("last_audio", 0) > 45:
        return {"status": "warn", "mic": True, "detail": "Nessun audio dal microfono del display" + service}
    audio = f"{int(now - link['last_audio'])} s fa" if link.get("last_audio") else "mai"
    pages = link.get("pages") or []
    hidden = sum(1 for p in pages if p.get("visible") == "hidden")
    status = f" · {link.get('clients', 0)} display collegati, ultimo audio {audio}"
    if hidden:
        status += f" · {hidden} pagine nascoste collegate"
    if pages:
        status += " · pagine: " + ", ".join(f"{p.get('page')} {p.get('visible')}" for p in pages)
    elif link.get("clients"):
        status += " · pagina senza identità (codice vecchio)"
    if service:
        return {"status": "ok", "detail": f"In ascolto di \"Jarvis\"{status} (errore assorbito{service})"}
    return {"status": "ok", "detail": f"In ascolto di \"Jarvis\"{status}"}


def norm_model(model: str) -> str:
    return model if ":" in model else f"{model}:latest"


async def probe_all() -> dict:
    if DEMO:
        return {k: {"status": "ok", "detail": "Simulazione"} for k in COMPONENTS}

    env = read_env()
    results: dict = {}
    async with httpx.AsyncClient(timeout=4) as client:
        code, out = await sh("docker", "info", "--format", "{{.ServerVersion}}", timeout=15)
        results["docker"] = {"status": "ok" if code == 0 else "down", "detail": f"v{out}" if code == 0 else out[:120]}

        try:
            r = await client.get(f"{ollama_url()}/api/version")
            where = f" — {ollama_url().split('//', 1)[-1]}" if ollama_remote() else ""
            results["ollama"] = {"status": "ok", "detail": f"v{r.json().get('version', '?')}{where}"}
        except (httpx.HTTPError, ValueError):
            results["ollama"] = {"status": "down", "detail": f"Non raggiungibile ({ollama_url().split('//', 1)[-1]})"}

        from features.brain.residency import primary
        main = primary()
        llm = norm_model(main) if main else ""
        try:
            loaded = [m.get("name") for m in (await client.get(f"{ollama_url()}/api/ps")).json().get("models", [])]
            if not llm:
                results["llm"] = {"status": "ok", "detail": "solo cervelli cloud: nessun modello locale in memoria"}
            else:
                results["llm"] = {"status": "ok" if llm in loaded else "warn",
                                  "detail": f"{llm} {'attivo in memoria' if llm in loaded else 'non caricato'}"}
        except (httpx.HTTPError, ValueError):
            results["llm"] = {"status": "down", "detail": llm or "cloud"}

        try:
            r = await client.get(f"{CORE_URL}/health")
            data = r.json()
            results["core"] = {"status": "ok" if r.status_code == 200 else "down",
                               "detail": f"v{data.get('version', '?')} — {len(data.get('active_agents', []))} agenti"}
        except (httpx.HTTPError, ValueError):
            results["core"] = {"status": "down", "detail": "Non raggiungibile"}

        try:
            r = await client.get("http://127.0.0.1:6333/healthz")
            results["qdrant"] = {"status": "ok" if r.status_code == 200 else "down", "detail": "Operativa"}
        except httpx.HTTPError:
            results["qdrant"] = {"status": "down", "detail": "Non raggiungibile"}

    from features.voices import catalog
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            (await client.get(f"{catalog.KOKORO_URL}/health")).raise_for_status()
        results["voice"] = {"status": "ok", "detail": f"{catalog.voice_name()} (Kokoro)"}
    except httpx.HTTPError:
        results["voice"] = ({"status": "warn", "detail": "Kokoro non attivo: voce di riserva Piper"}
                            if catalog.PIPER.exists() else {"status": "down", "detail": "Nessun motore vocale"})

    if env.get("JARVIS_EAR", "1") == "0":
        results["ear"] = {"status": "ok", "detail": "Disabilitato"}
    else:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", 8093), 3)
            writer.close()
            detail = "In ascolto di \"Jarvis\""
            try:
                import json as _json
                from config import STATE_DIR
                learn = _json.loads((STATE_DIR / "ear_learning.json").read_text(encoding="utf-8"))
                st = learn.get("stats", {})
                ms = st.get("wake_ms") or [0]
                detail += (f" — {st.get('wakes', 0)} attivazioni, {st.get('commands', 0)} comandi, "
                           f"{len(learn.get('variants', {}))} varianti apprese, ~{int(sum(ms) / len(ms))} ms")
            except (OSError, ValueError):
                pass
            results["ear"] = mic_check(env) or {"status": "ok", "detail": detail}
            log_lines = await ear_log()
            if log_lines:
                results["ear"]["detail"] += " · registro: " + " | ".join(log_lines)
        except (OSError, asyncio.TimeoutError):
            results["ear"] = {"status": "down", "detail": "Servizio non raggiungibile"}

    if env.get("JARVIS_VISION", "1") == "0":
        results["vision"] = {"status": "ok", "detail": "Disabilitata"}
    else:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                v = (await client.get("http://127.0.0.1:8091/health")).json()
            results["vision"] = ({"status": "ok", "detail": f"Webcam attiva — {v.get('people_enrolled', 0)} persone registrate"}
                                 if v.get("status") == "ok" else {"status": "warn", "detail": v.get("error") or "Webcam assente"})
        except (httpx.HTTPError, ValueError):
            results["vision"] = {"status": "down", "detail": "Servizio non raggiungibile"}

    if env.get("JARVIS_KIOSK", "1") == "0":
        results["kiosk"] = {"status": "ok", "detail": "Disabilitato"}
    else:
        results["kiosk"] = await kiosk_check()

    code, out = await sh("df", "-Pm", "/", timeout=5)
    try:
        free_mb = int(out.splitlines()[1].split()[3])
        results["disk"] = {"status": "ok" if free_mb > 5120 else ("warn" if free_mb > 2048 else "down"),
                           "detail": f"{free_mb / 1024:.1f} GB liberi"}
    except (IndexError, ValueError):
        results["disk"] = {"status": "warn", "detail": "Sconosciuto"}
    return results


def publish(results: dict) -> None:
    now = time.time()
    for key, res in results.items():
        prev = store.components.get(key, {})
        since = prev.get("since", now) if prev.get("status") == res["status"] else now
        store.components[key] = {**res, "label": COMPONENTS[key], "since": since,
                                 "failures": prev.get("failures", 0)}
    store.touch()


BACKOFF = (0, 60, 180, 600, 1800)
MIC_ATTEMPTS = 4


class Watchdog:

    INTERVAL = 15

    def __init__(self, orchestrator) -> None:
        self.orch = orchestrator
        self.heal_counts: dict = {}
        self.next_try: dict = {}
        self.gave_up: set = set()

    async def _heal_mic(self, count: int) -> None:
        if count <= 2:
            store.mic_reset = time.time()
            store.touch()
        else:
            await sh("systemctl", "restart", "getty@tty1", timeout=30)

    async def _heal(self, key: str) -> None:
        now = time.time()
        if now < self.next_try.get(key, 0) or key in self.gave_up:
            return
        count = self.heal_counts.get(key, 0) + 1
        comp = store.components.get(key, {})
        if comp.get("mic") and count > MIC_ATTEMPTS:
            self.gave_up.add(key)
            store.event("ERROR", f"{COMPONENTS[key]}: dopo {MIC_ATTEMPTS} tentativi non si è ripristinato da solo "
                                 f"({comp.get('detail', '')}). Non riprovo finché non cambia qualcosa.", key)
            return
        self.heal_counts[key] = count
        self.next_try[key] = now + BACKOFF[min(count, len(BACKOFF) - 1)]
        store.event("WARN", f"Auto-riparazione di '{COMPONENTS[key]}' (intervento {count})", key)
        if DEMO:
            return
        if key == "docker":
            await sh("systemctl", "restart", "docker", timeout=120)
        elif key == "ollama" and not ollama_remote():
            await sh("systemctl", "restart", "ollama", timeout=120)
        elif key == "llm":
            await self.orch.converge(["warmup"], reason="Riattivazione rete linguistica")
        elif key in ("core", "qdrant"):
            if count <= 2:
                await sh("docker", "restart", f"jarvis-{key}", timeout=120)
            else:
                await self.orch.converge(["docker", "core", "services"], reason="Ricostruzione servizi cognitivi")
        elif key == "ear" and store.components.get("ear", {}).get("mic"):
            await self._heal_mic(count)
        elif key == "ear":
            if count <= 2:
                await sh("systemctl", "restart", "jarvis-ear", timeout=60)
            else:
                await self.orch.converge(["ear"], reason="Ripristino dell'ascolto vocale")
        elif key == "vision":
            if count <= 2:
                await sh("systemctl", "restart", "jarvis-vision", timeout=60)
            else:
                await self.orch.converge(["vision"], reason="Ripristino della visione")
        elif key == "voice":
            if count <= 2:
                await sh("systemctl", "restart", "jarvis-voice", timeout=60)
            else:
                await self.orch.converge(["voice"], reason="Ripristino della voce neurale")
        elif key == "kiosk":
            await sh("pkill", "-t", "tty1", timeout=10)
            await sh("systemctl", "restart", "getty@tty1", timeout=30)
        elif key == "disk":
            await sh("docker", "system", "prune", "-f", timeout=300)
            await sh("journalctl", "--vacuum-size=200M", timeout=60)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.INTERVAL)
            if store.phase not in ("READY", "DEGRADED") or self.orch.busy:
                continue
            try:
                results = await probe_all()
            except Exception as exc:
                log.exception("Errore sonde: %s", exc)
                continue
            publish(results)

            broken = []
            for key, res in results.items():
                comp = store.components[key]
                if res["status"] == "ok":
                    comp["failures"] = 0
                    if key in self.heal_counts or key in self.gave_up:
                        store.event("INFO", f"{COMPONENTS[key]} di nuovo operativo", key)
                    self.heal_counts.pop(key, None)
                    self.next_try.pop(key, None)
                    self.gave_up.discard(key)
                    continue
                comp["failures"] = comp.get("failures", 0) + 1
                if comp["failures"] >= 2 or key == "llm":
                    broken.append(key)

            critical_down = [k for k in broken if k in CRITICAL and results[k]["status"] == "down"]
            if critical_down and store.phase == "READY":
                store.set_phase("DEGRADED", "Auto-riparazione: " + ", ".join(COMPONENTS[k] for k in critical_down))
            for key in broken:
                await self._heal(key)
            if not critical_down and store.phase == "DEGRADED":
                store.set_phase("READY", "Tutti i sistemi operativi")
