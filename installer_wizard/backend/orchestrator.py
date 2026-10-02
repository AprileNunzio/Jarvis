import asyncio
import logging
import time

import health
import sysinfo
import updater
from config import DEMO, VERSION
from state import store
from steps import STEPS, run_pipeline

log = logging.getLogger("jarvis.supervisor")

ERROR_RETRY_SECONDS = 120
ERROR_RETRY_MAX = 30 * 60


class Orchestrator:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.busy = False

    async def boot(self) -> None:
        store.boot_count += 1
        store.save()
        pending = None if DEMO else updater.pending()
        if pending:
            base_phase, label = "UPDATING", "Verifica della nuova versione…"
        elif not store.installed:
            base_phase, label = "INSTALLING", "Preparazione dell'installazione…"
        else:
            base_phase, label = "BOOTING", "Verifica e attivazione dei sistemi…"
        store.event("INFO", f"Avvio supervisore v{VERSION} (boot #{store.boot_count})", "supervisor")

        failures = 0
        while True:
            store.set_phase(base_phase, label)
            store.retry_at = 0
            async with self.lock:
                self.busy = True
                try:
                    ok = await run_pipeline()
                except Exception as exc:
                    log.exception("Errore inatteso nella pipeline")
                    store.last_error = f"Errore interno del supervisore: {exc}"
                    store.event("ERROR", store.last_error, "supervisor")
                    ok = False
                finally:
                    self.busy = False
            if ok:
                store.pipeline_failed = False
                break
            store.pipeline_failed = True
            if pending and await updater.finish_pending(False):
                return
            wait = min(ERROR_RETRY_MAX, ERROR_RETRY_SECONDS * 2 ** min(failures, 4))
            failures += 1
            store.retry_at = time.time() + wait
            store.set_phase("ERROR", f"Nuovo tentativo automatico tra {wait // 60} minuti "
                                     f"(tentativo {failures}); verifico anche se esistono correzioni su GitHub")
            await asyncio.sleep(wait)

        if not store.installed:
            store.installed = True
            store.installed_at = time.time()
            store.event("INFO", "Installazione completata", "supervisor")
        if pending:
            await updater.finish_pending(True)
        elif not DEMO:
            await updater.mark_good()
        store.save()
        health.publish(await health.probe_all())
        store.progress = 100
        store.set_phase("READY", "Tutti i sistemi operativi")

    async def converge(self, only: list[str] | None = None, reason: str = "", force: bool = False) -> bool:
        if self.lock.locked():
            return False
        async with self.lock:
            self.busy = True
            previous = store.phase
            if previous in ("READY", "DEGRADED"):
                store.set_phase("DEGRADED", reason or "Manutenzione in corso")
            try:
                ok = await run_pipeline(only=only, force=force)
            finally:
                self.busy = False
            health.publish(await health.probe_all())
            if previous in ("READY", "DEGRADED", "ERROR"):
                store.set_phase("READY" if ok else "DEGRADED",
                                "Tutti i sistemi operativi" if ok else "Intervento non riuscito: nuovo tentativo a breve")
            return ok


orch = Orchestrator()


async def converge_steps(steps: list, reason: str) -> None:
    order = [s.id for s in STEPS]
    await orch.converge(sorted({x for x in steps if x in order}, key=order.index), reason=reason)


async def telemetry_loop() -> None:
    while True:
        try:
            store.system = sysinfo.collect()
            store.touch()
        except Exception as exc:
            log.warning("Telemetria non disponibile: %s", exc)
        await asyncio.sleep(2)
