import asyncio
import json
import logging
import time
from datetime import datetime

from config import env_get
from state import store

from features.agent.agent import agent
from features.autonomy import approvals, journal
from features.autonomy.routines import routines

log = logging.getLogger("jarvis.autonomy")
TICK = 30
AUTOPILOT_EVERY = 30 * 60
BROKEN_FOR = 10 * 60
REPORT_AGAIN = 6 * 3600
DIGEST_HOUR = 21
DIAGNOSE = ("Il componente «{label}» è in stato «{status}» da {minutes} minuti: {detail}. Diagnostica il problema usando "
            "SOLO comandi di sola lettura (systemctl status, journalctl -n 50, df -h, free -h, ls, cat dei log) e rispondi "
            "in due o tre frasi: causa probabile e cosa fare. Non modificare nulla.")


def enabled() -> bool:
    return env_get("JARVIS_AUTONOMY", "1") != "0"


class Autonomy:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.last_autopilot = 0.0
        self.reported: dict[str, float] = {}
        self.gaps_seen = time.time()
        self.digest_day = ""
        self.started = False
        self.status = "in avvio"
        agent.on_approval = self.ask_approval

    async def tell(self, text: str, icon: str = "🤖", show: bool = True) -> None:
        try:
            from features.telegram.bot import bot
            await bot.notify(text)
        except Exception as exc:
            log.debug("Telegram non disponibile: %s", exc)
        if show:
            from features.desktop.desk import desk
            desk.show("notice", {"icon": icon, "title": "Jarvis in autonomia", "text": text[:300]},
                      key=f"autonomy:{int(time.time())}", ttl=90)

    async def ask_approval(self, item: dict) -> None:
        from features.desktop.desk import desk
        desk.show("notice", {"icon": "🔐", "title": "Serve la sua approvazione", "level": "warn",
                             "text": f"{item['title']}: {item['summary']}. Di' «approva» o «rifiuta»."},
                  key=f"approval:{item['id']}", ttl=3600)
        journal.write("approvazione", item["title"], f"Chiesta approvazione: {item['summary']}")
        await self.tell(f"🔐 {item['title']}: {item['summary']}. Approva dal pannello (Autonomia) o dimmi «approva».",
                        show=False)

    async def approve(self, aid: str, yes: bool, always: bool = False) -> str:
        item = approvals.take(aid)
        if yes and always and item.get("routine"):
            try:
                routines.update(item["routine"], trusted=True)
                item["trusted"] = True
            except KeyError:
                pass
        from features.desktop.desk import desk
        desk.hide(key=f"approval:{aid}")
        async with self.lock:
            result = await agent.resume(item, yes)
        verdict = "Approvato per sempre" if item.get("trusted") else "Approvato" if yes else "Rifiutato"
        journal.write("approvazione", item["title"], f"{verdict}: {result}")
        return result

    async def run_routine(self, r: dict, why: str = "programmata") -> str:
        async with self.lock:
            steps: list[dict] = []
            started = time.time()
            try:
                result = await agent.run(r["prompt"], steps, auto=r["title"], trusted=bool(r.get("trusted")), routine=r["id"])
            except Exception as exc:
                result = f"Errore: {exc}"
            routines.update(r["id"], last_run=started, last_result=result[:300], runs=r.get("runs", 0) + 1)
        journal.write("routine", r["title"], f"({why}) {result}", steps)
        if not result.startswith("In attesa"):
            await self.tell(f"✅ {r['title']}: {result}")
        return result

    def on_event(self, name: str) -> None:
        if not enabled():
            return
        from tasks import background
        for r in routines.for_event(name):
            background(self.run_routine(r, f"evento: {name}"))

    async def _health(self) -> None:
        now = time.time()
        for key, comp in list((store.components or {}).items()):
            status = comp.get("status")
            if status in ("ok", "idle", None) or now - comp.get("since", now) < BROKEN_FOR:
                continue
            if now - self.reported.get(key, 0) < REPORT_AGAIN:
                continue
            self.reported[key] = now
            steps: list[dict] = []
            prompt = DIAGNOSE.format(label=comp.get("label", key), status=status, detail=comp.get("detail", ""),
                                     minutes=int((now - comp.get("since", now)) / 60))
            async with self.lock:
                result = await agent.run(prompt, steps, auto=f"Diagnosi: {comp.get('label', key)}")
            journal.write("diagnosi", comp.get("label", key), result, steps)
            await self.tell(f"🩺 {comp.get('label', key)} non funziona da un po'. {result}", icon="🩺")

    async def _gaps(self) -> None:
        from features.actions.common import GAPS_FILE
        try:
            gaps = json.loads(GAPS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        fresh = [g for g in gaps if g.get("at", 0) > self.gaps_seen]
        if not fresh:
            return
        self.gaps_seen = max(g["at"] for g in fresh)
        from features.brain.brains import brains
        from features.skills.library import library
        for g in fresh[-2:]:
            if library.needs_algorithm(g["text"]):
                await library.learn(g["text"], brains.config()["deep"])
                journal.write("studio", "Nuova abilità", f"Ho provato a imparare a rispondere a: «{g['text'][:120]}»")
            else:
                journal.write("studio", "Richiesta non soddisfatta", f"«{g['text'][:160]}» — {g.get('reason', '')[:160]}")

    async def _digest(self) -> None:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if now.hour < DIGEST_HOUR or self.digest_day == today:
            return
        self.digest_day = today
        start = now.replace(hour=0, minute=0, second=0).timestamp()
        done = journal.recent(200, start)
        waiting = approvals.pending()
        broken = [c.get("label", k) for k, c in (store.components or {}).items() if c.get("status") not in ("ok", "idle", None)]
        if not done and not waiting and not broken:
            return
        lines = [f"📋 Riepilogo di oggi: {len(done)} attività in autonomia"]
        lines += [f"• {e['title']}: {e['text'][:90]}" for e in done[:8]]
        if waiting:
            lines.append(f"🔐 {len(waiting)} azioni aspettano la sua approvazione")
        if broken:
            lines.append("⚠ Da controllare: " + ", ".join(broken))
        await self.tell("\n".join(lines), icon="📋", show=False)

    async def autopilot(self) -> None:
        for name, step in (("salute", self._health), ("studio", self._gaps), ("riepilogo", self._digest)):
            try:
                await step()
            except Exception as exc:
                log.warning("Autopilota (%s): %s", name, exc)
        self.last_autopilot = time.time()

    async def run(self) -> None:
        await asyncio.sleep(60)
        while True:
            if enabled() and store.phase in ("READY", "DEGRADED"):
                self.status = "attiva"
                if not self.started:
                    self.started = True
                    self.on_event("startup")
                for r in routines.due_now():
                    await self.run_routine(r)
                if time.time() - self.last_autopilot > AUTOPILOT_EVERY:
                    await self.autopilot()
            else:
                self.status = "disattivata" if not enabled() else "in attesa del sistema"
            await asyncio.sleep(TICK)


autonomy = Autonomy()
