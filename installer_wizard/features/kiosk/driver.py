import asyncio
import logging
import time
from pathlib import Path

from config import DEMO, STATE_DIR, STEPS_DIR
from state import store

log = logging.getLogger("jarvis.display-driver")
STATE_FILE = STATE_DIR / "display-driver"
VERIFY_FOR = 600
NEEDED_OK = 3
MIN_FPS = 15


def read() -> dict:
    try:
        parts = STATE_FILE.read_text().strip().split("|")
    except OSError:
        return {"state": "", "pkg": "", "note": "", "at": 0}
    parts += [""] * (4 - len(parts))
    return {"state": parts[0], "pkg": parts[1], "note": parts[2], "at": float(parts[3] or 0)}


def write(state: str, pkg: str, note: str) -> None:
    STATE_FILE.write_text(f"{state}|{pkg}|{note}|{int(time.time())}\n")


def boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return ""


def describe() -> str:
    s = read()
    return {"ok": f"driver NVIDIA attivo ({s['pkg']})", "pending-reboot": f"{s['pkg']} installato, attivo dopo il riavvio",
            "verify": f"verifica di {s['pkg']} in corso", "failed": f"tornato al driver libero: {s['note']}",
            "none": f"driver libero: {s['note']}"}.get(s["state"], "driver libero (nessuna prova ancora)")


async def _healthy() -> tuple[bool, str]:
    from health import kiosk_check, sh
    code, _ = await sh("nvidia-smi", "-L", timeout=15)
    if code != 0:
        return False, "il driver NVIDIA non risponde"
    kiosk = await kiosk_check()
    if kiosk.get("status") != "ok":
        return False, f"sessione grafica non partita ({kiosk.get('detail')})"
    local = [d for d in getattr(store, "displays", []) if d.get("client") == "questo server"]
    perf = local[0].get("perf", "") if local else ""
    fps = next((int(p[4:]) for p in perf.split() if p.startswith("fps=") and p[4:].isdigit()), None)
    if fps is None:
        return False, "il display non ha ancora misurato la fluidità"
    if fps < MIN_FPS:
        return False, f"display lento anche con il driver NVIDIA ({fps} fps)"
    return True, f"{fps} fps"


async def _revert(reason: str) -> None:
    from health import sh
    store.event("ERROR", f"Driver video NVIDIA: {reason}. Torno al driver libero", "kiosk")
    try:
        from features.telegram.bot import bot
        await bot.notify(f"⏪ Driver video NVIDIA: {reason}. Torno al driver libero e riavvio.")
    except Exception as exc:
        log.debug("Telegram non disponibile: %s", exc)
    await sh("bash", str(STEPS_DIR / "33-display-driver.sh"), "revert", reason, timeout=600)


async def guard() -> None:
    if DEMO:
        return
    await asyncio.sleep(60)
    good, last = 0, ""
    while True:
        try:
            s = read()
            if s["state"] == "pending-reboot" and s["note"] and s["note"] != boot_id():
                write("verify", s["pkg"], "")
                store.event("INFO", f"Driver video {s['pkg']}: verifica dopo il riavvio", "kiosk")
                s = read()
            if s["state"] == "verify":
                ok, last = await _healthy()
                good = good + 1 if ok else 0
                if good >= NEEDED_OK:
                    write("ok", s["pkg"], last)
                    store.event("INFO", f"Driver video {s['pkg']} attivo e verificato: {last}", "kiosk")
                elif time.time() - s["at"] > VERIFY_FOR:
                    write("verify-failed", s["pkg"], last)
                    await _revert(last or "verifica non superata")
        except Exception as exc:
            log.warning("Controllo del driver video: %s", exc)
        await asyncio.sleep(30)
