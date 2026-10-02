import asyncio
import os
import random
import re
import time
from dataclasses import dataclass

from config import DEMO, HEAL_SCRIPT, STEPS_DIR, read_env
from state import store

MAX_ATTEMPTS = 3
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


@dataclass(frozen=True)
class Step:
    id: str
    script: str
    title: str
    description: str
    weight: int
    critical: bool = True
    background: bool = False


STEPS = [
    Step("preflight", "10-preflight.sh", "Analisi del sistema", "Hardware, rete e scelta delle reti neurali", 2),
    Step("system", "20-system.sh", "Componenti di sistema", "Runtime, interfaccia grafica, voce", 10),
    Step("kiosk", "25-kiosk.sh", "Display olografico", "Sessione kiosk dedicata e sicura", 2, critical=False),
    Step("docker", "30-docker.sh", "Motore container", "Docker Engine e isolamento dei servizi", 9),
    Step("display_driver", "33-display-driver.sh", "Driver video", "Driver NVIDIA ufficiale per il display, con ritorno automatico", 2,
         critical=False),
    Step("gpu", "35-gpu.sh", "Accelerazione GPU", "Runtime NVIDIA per l'inferenza", 2, critical=False),
    Step("security", "40-security.sh", "Scudi di sicurezza", "Firewall e hardening del kernel", 2),
    Step("ollama", "50-ollama.sh", "Motore neurale", "Runtime di inferenza locale Ollama", 8),
    Step("voice", "55-voice.sh", "Voce neurale", "Sintesi vocale italiana offline", 4, critical=False),
    Step("bluetooth", "56-bluetooth.sh", "Bluetooth", "Casse, cuffie e microfoni senza fili", 1, critical=False),
    Step("vision", "57-vision.sh", "Visione", "Riconoscimento facciale locale dalla webcam", 3, critical=False),
    Step("ear", "58-ear.sh", "Ascolto vocale", "Riconoscimento del parlato e parola \"Jarvis\"", 4, critical=False),
    Step("music", "59-music.sh", "Riconoscimento musicale", "Brano, artista e album della musica in ascolto", 1,
         critical=False),
    Step("shares", "63-shares.sh", "Condivisioni di rete", "Cartelle visibili da Windows e Mac, memoria con password", 1,
         critical=False),
    Step("office", "64-office.sh", "Ufficio", "LibreOffice, caratteri e librerie per documenti Office, ODF e PDF", 2,
         critical=False, background=True),
    Step("convert3d", "62-convert3d.sh", "Conversione 3D", "Blender e LibreDWG per aprire BLEND, USD e DWG", 1,
         critical=False, background=True),
    Step("models", "60-models.sh", "Reti neurali", "Modello linguistico e memoria semantica", 30),
    Step("soup", "67-soup.sh", "Consolidamento dello studio", "Addestramento con Soup (solo con GPU adatta)", 1,
         critical=False, background=True),
    Step("core", "70-core.sh", "Jarvis Core", "Compilazione dell'orchestratore cognitivo", 20),
    Step("services", "80-services.sh", "Servizi cognitivi", "Core, memoria vettoriale e agenti", 7),
    Step("maintenance", "90-maintenance.sh", "Manutenzione autonoma", "Aggiornamenti di sicurezza e log", 2,
         critical=False),
    Step("warmup", "95-warmup.sh", "Attivazione neurale", "Caricamento delle reti in memoria", 6),
]
STEP_BY_ID = {s.id: s for s in STEPS}
TOTAL_WEIGHT = sum(s.weight for s in STEPS)


def step_catalog() -> list:
    return [{"id": s.id, "title": s.title, "description": s.description, "critical": s.critical,
             "background": s.background} for s in STEPS]


def _record(step: Step) -> dict:
    rec = store.steps.get(step.id)
    if not isinstance(rec, dict):
        rec = {}
    rec.setdefault("status", "pending")
    rec.setdefault("progress", 0)
    rec.setdefault("message", "")
    rec.setdefault("attempts", 0)
    rec.setdefault("error", "")
    rec.setdefault("duration", 0)
    store.steps[step.id] = rec
    return rec


def _recompute_progress() -> None:
    total = 0.0
    for s in STEPS:
        rec = store.steps.get(s.id, {})
        if rec.get("status") in ("done", "skipped", "failed"):
            total += s.weight
        elif rec.get("status") in ("running", "retrying"):
            total += s.weight * rec.get("progress", 0) / 100
    store.progress = min(100.0, total * 100 / TOTAL_WEIGHT)
    store.touch()


async def _read_lines(reader: asyncio.StreamReader):
    buffer = ""
    while True:
        chunk = await reader.read(65536)
        if not chunk:
            break
        buffer += chunk.decode("utf-8", "replace")
        parts = re.split(r"(\r\n|\r|\n)", buffer)
        buffer = parts.pop()
        if len(buffer) > 16384:
            parts += [buffer, "\n"]
            buffer = ""
        for text, sep in zip(parts[0::2], parts[1::2]):
            text = ANSI_RE.sub("", text).strip()
            if text:
                yield text, sep == "\r"
    buffer = ANSI_RE.sub("", buffer).strip()
    if buffer:
        yield buffer, False


async def _run_script(step: Step, action: str, stream: bool) -> tuple[int, str]:
    env = {**os.environ, **read_env()}
    proc = await asyncio.create_subprocess_exec(
        "bash", str(STEPS_DIR / step.script), action,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=env,
    )
    rec = store.steps[step.id]
    last_error = ""
    assert proc.stdout is not None
    async for line, is_progress_bar in _read_lines(proc.stdout):
        if line.startswith("[FAIL]"):
            last_error = line[6:].strip()
        if not stream:
            continue
        if is_progress_bar:
            store.detail = line[:160]
            store.touch()
        elif line.startswith("@@PROGRESS "):
            parts = line.split(" ", 2)
            try:
                rec["progress"] = max(0, min(100, int(parts[1])))
            except (IndexError, ValueError):
                pass
            if len(parts) > 2:
                rec["message"] = parts[2]
                store.message = parts[2]
            _recompute_progress()
        elif line.startswith("@@DETAIL "):
            store.detail = line[9:]
            store.touch()
        else:
            store.log(line[:500], step.id)
    code = await proc.wait()
    return code, last_error


_demo_applied: set = set()


async def _demo_script(step: Step, action: str, stream: bool) -> tuple[int, str]:
    if action == "check":
        return (0 if store.installed or step.id in _demo_applied else 1), ""
    _demo_applied.add(step.id)
    rec = store.steps[step.id]
    for pct in range(0, 101, random.choice((5, 10, 20))):
        await asyncio.sleep(0.15 * step.weight / 4 + 0.1)
        rec["progress"] = pct
        rec["message"] = f"{step.title}: {pct}%"
        store.message = rec["message"]
        if step.id == "models":
            store.detail = f"qwen2.5:3b — {pct * 19 / 1000:.2f}/1.90 GB — 42.0 MB/s — ETA 0m{(100 - pct) // 3:02d}s"
        store.log(f"[INFO] {step.title} — avanzamento {pct}%", step.id)
        _recompute_progress()
    return 0, ""


async def run_step_action(step: Step, action: str, stream: bool = True) -> tuple[int, str]:
    runner = _demo_script if DEMO else _run_script
    return await runner(step, action, stream)


async def heal(step: Step) -> None:
    store.event("WARN", f"Auto-riparazione dopo errore in '{step.title}'", step.id)
    if DEMO or not HEAL_SCRIPT.exists():
        await asyncio.sleep(1)
        return
    proc = await asyncio.create_subprocess_exec(
        "bash", str(HEAL_SCRIPT), step.id, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    assert proc.stdout is not None
    async for raw in proc.stdout:
        store.log(raw.decode("utf-8", "replace").rstrip()[:500], "heal")
    await proc.wait()


async def converge_step(step: Step, force: bool = False) -> bool:
    rec = _record(step)
    store.current_step = step.id
    started = time.time()

    if not force:
        rec.update(status="checking", message="Verifica…")
        store.message = f"Verifica: {step.title}"
        store.detail = ""
        store.touch()
        code, _ = await run_step_action(step, "check", stream=False)
        if code == 0:
            rec.update(status="done", progress=100, message="Operativo", error="")
            _recompute_progress()
            return True

    for attempt in range(1, MAX_ATTEMPTS + 1):
        rec.update(status="running", progress=0, attempts=rec.get("attempts", 0) + 1,
                   message="Avvio…")
        store.message = step.title
        store.detail = ""
        store.event("INFO", f"Esecuzione '{step.title}' (tentativo {attempt}/{MAX_ATTEMPTS})", step.id)
        _recompute_progress()

        code, error = await run_step_action(step, "apply")
        if code == 0:
            check_code, _ = await run_step_action(step, "check", stream=False)
            if check_code == 0:
                rec.update(status="done", progress=100, message="Completato", error="",
                           duration=round(time.time() - started))
                store.event("INFO", f"'{step.title}' completato in {rec['duration']}s", step.id)
                store.save()
                _recompute_progress()
                return True
            error = error or "Verifica finale non superata"

        rec.update(status="retrying", error=error or f"Codice di uscita {code}")
        store.last_error = f"{step.title}: {rec['error']}"
        store.event("ERROR", f"'{step.title}' fallito: {rec['error']}", step.id)
        if attempt < MAX_ATTEMPTS:
            await heal(step)
            await asyncio.sleep(5 * attempt)

    rec.update(status="failed", message="Non riuscito")
    store.save()
    _recompute_progress()
    return False


async def run_pipeline(only: list[str] | None = None, force: bool = False) -> bool:
    for step in STEPS:
        _record(step)
    store.last_error = ""
    ok = True
    for step in STEPS:
        if only and step.id not in only:
            continue
        if step.background and not only:
            rec = store.steps[step.id]
            if rec.get("status") != "done":
                rec.update(status="background", message="In background dopo l'avvio")
            continue
        if not await converge_step(step, force=force):
            if step.critical:
                ok = False
                break
            store.event("WARN", f"Step non critico '{step.title}' non riuscito: si prosegue", step.id)
    store.current_step = ""
    store.detail = ""
    store.save()
    _recompute_progress()
    return ok
