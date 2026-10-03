import asyncio
import json
import logging
import time
from datetime import datetime

from config import DEMO, STATE_DIR, env_get
from state import store

from features.selftest.checks import CHECKS
from features.selftest.skip import Skip

log = logging.getLogger("jarvis.selftest")
FILE = STATE_DIR / "selftest.json"
TIMEOUT = 90
AFTER_UPDATE = 300
KEEP = 40


def enabled() -> bool:
    return env_get("JARVIS_SELFTEST", "1") != "0"


class SelfTest:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.running = False
        try:
            self.data = json.loads(FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {"history": [], "tested_rev": "", "good_rev": "", "night": ""}
        self._publish()

    def _save(self) -> None:
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(FILE)

    def last(self) -> dict | None:
        return self.data["history"][0] if self.data["history"] else None

    def _publish(self) -> None:
        last = self.last()
        store.selftest = {"running": self.running, "passed": None} if not last else {
            "at": last["at"], "reason": last["reason"], "rev": last["rev"][:7], "passed": last["passed"],
            "failed": [r["label"] for r in last["results"] if r["status"] == "errore"], "running": self.running,
            "sandbox": next((r["detail"] for r in last["results"] if r["key"] == "sandbox"), "")}

    async def _one(self, key: str, label: str, critical: bool, fn) -> dict:
        started = time.time()
        try:
            detail, status = await asyncio.wait_for(fn(), TIMEOUT), "ok"
        except Skip as s:
            detail, status = str(s), "saltato"
        except asyncio.TimeoutError:
            detail, status = f"nessuna risposta in {TIMEOUT} s", "errore"
        except Exception as exc:
            detail, status = str(exc)[:300] or type(exc).__name__, "errore"
        return {"key": key, "label": label, "critical": critical, "status": status, "detail": str(detail)[:700],
                "ms": int((time.time() - started) * 1000)}

    async def run(self, reason: str = "manuale") -> dict:
        async with self.lock:
            self.running = True
            self._publish()
            store.touch()
            try:
                rev = await self._rev()
                results = list(await asyncio.gather(*(self._one(*c) for c in CHECKS)))
            finally:
                self.running = False
            failed = [r for r in results if r["status"] == "errore"]
            report = {"at": time.time(), "reason": reason, "rev": rev, "results": results,
                      "passed": sum(1 for r in results if r["status"] == "ok"), "failed": len(failed),
                      "skipped": sum(1 for r in results if r["status"] == "saltato")}
            previous = self.last()
            self.data["history"] = ([report] + self.data["history"])[:KEEP]
            self.data["tested_rev"] = rev
            critical_ok = not any(r["critical"] for r in failed)
            if critical_ok:
                self.data["good_rev"] = rev
            self._save()
            self._publish()
            store.touch()
            store.event("INFO" if not failed else "WARN",
                        f"Collaudo ({reason}): {report['passed']} superati, {len(failed)} falliti, {report['skipped']} saltati",
                        "selftest")
            await self._react(report, previous, reason)
            return report

    async def _rev(self) -> str:
        if DEMO:
            return "demo"
        import updater
        return await updater.current_rev()

    async def _react(self, report: dict, previous: dict | None, reason: str) -> None:
        before = {r["key"]: r["status"] for r in (previous or {}).get("results", [])}
        broken = [r for r in report["results"] if r["status"] == "errore" and before.get(r["key"]) == "ok"]
        fixed = [r for r in report["results"] if r["status"] == "ok" and before.get(r["key"]) == "errore"]
        critical = [r for r in broken if r["critical"]]
        if reason == "dopo l'aggiornamento" and critical and await self._rollback(report, critical):
            return
        lines = []
        if broken:
            lines.append("⚠️ Non funziona più: " + "; ".join(f"{r['label']} ({r['detail'][:80]})" for r in broken))
        if fixed:
            lines.append("✅ Di nuovo in funzione: " + ", ".join(r["label"] for r in fixed))
        if lines or (reason == "notturno" and report["failed"]):
            if not lines:
                lines.append("Ancora da sistemare: " + ", ".join(r["label"] for r in report["results"] if r["status"] == "errore"))
            await self._tell(f"🧪 Collaudo {reason}: {report['passed']}/{len(report['results'])} superati.\n" + "\n".join(lines))

    async def _rollback(self, report: dict, critical: list) -> bool:
        good = self.data.get("good_rev")
        if DEMO or not good or good == report["rev"] or env_get("JARVIS_SELFTEST_ROLLBACK", "1") == "0":
            return False
        import updater
        names = ", ".join(r["label"] for r in critical)
        with updater.BAD_REVS_FILE.open("a") as fh:
            fh.write(report["rev"] + "\n")
        store.event("ERROR", f"Collaudo: la versione {report['rev'][:7]} ha rotto {names}: torno a {good[:7]}", "selftest")
        await self._tell(f"⏪ La versione {report['rev'][:7]} ha rotto: {names}. Torno alla {good[:7]}, che funzionava, "
                         "e salto questa versione finché non arriva una correzione.")
        code, out = await updater.git("reset", "--hard", good)
        if code != 0:
            store.event("ERROR", f"Ritorno alla versione precedente non riuscito: {out[:200]}", "selftest")
            return False
        await updater.mark_good()
        from health import sh
        await sh("systemctl", "restart", "--no-block", "jarvis-supervisor.service", timeout=10)
        return True

    async def _tell(self, text: str) -> None:
        try:
            from features.telegram.bot import bot
            await bot.notify(text)
        except Exception as exc:
            log.debug("Telegram non disponibile: %s", exc)
        from features.desktop.desk import desk
        desk.show("notice", {"icon": "🧪", "title": "Collaudo", "text": text[:300]}, key="selftest", ttl=600)

    @staticmethod
    def _night(now: datetime, at: str) -> bool:
        try:
            h, m = (int(x) for x in at.split(":"))
        except ValueError:
            h, m = 3, 30
        delta = (now.hour * 60 + now.minute) - (h * 60 + m)
        return 0 <= delta <= 180

    async def loop(self) -> None:
        await asyncio.sleep(90)
        ready_since = 0.0
        while True:
            try:
                if enabled() and store.phase == "READY":
                    ready_since = ready_since or time.time()
                    rev = await self._rev()
                    now = datetime.now()
                    at = env_get("JARVIS_SELFTEST_AT", "03:30")
                    if rev and rev != self.data.get("tested_rev") and time.time() - ready_since > AFTER_UPDATE:
                        await self.run("dopo l'aggiornamento" if self.data.get("tested_rev") else "primo avvio")
                    elif self._night(now, at) and self.data.get("night") != now.strftime("%Y-%m-%d"):
                        self.data["night"] = now.strftime("%Y-%m-%d")
                        await self.run("notturno")
                else:
                    ready_since = 0.0
            except Exception as exc:
                log.warning("Collaudo: %s", exc)
            await asyncio.sleep(60)


selftest = SelfTest()
