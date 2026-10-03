import asyncio
import json
import os
import sys

from config import DEMO, JARVIS_DIR
from features.selftest.skip import Skip


async def sandbox_isolation():
    if DEMO or os.name == "nt":
        raise Skip("la sandbox gira solo sul server")
    env = {**os.environ, "PYTHONPATH": str(JARVIS_DIR)}
    proc = await asyncio.create_subprocess_exec(
        "python3", "-m", "sandbox_broker.selfcheck", cwd=str(JARVIS_DIR), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), 90)
    except asyncio.TimeoutError:
        proc.kill()
        raise AssertionError("la sandbox non ha risposto entro 90 secondi")
    try:
        outcome = json.loads(out.decode("utf-8", "replace").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise AssertionError(f"risposta illeggibile: {err.decode('utf-8', 'replace')[-160:] or sys.executable}")
    if not outcome["ok"]:
        raise AssertionError("; ".join(outcome["problems"]))
    return f"codice eseguito in isolamento ({outcome['backend']}): niente rete, disco di sola lettura, utente non root"
