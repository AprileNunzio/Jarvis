import asyncio
import time

import httpx

from features.people import people
from config import DEMO, env_get
from state import store

VISION_URL = "http://127.0.0.1:8091"
GREET_AGAIN_AFTER = 20 * 60
UNKNOWN_GREET_AFTER = 5 * 60
STABLE_SECONDS = 1.2
HOLD_SECONDS = 5.0


def _join(names: list) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " e " + names[-1]


def _salutation() -> str:
    h = time.localtime().tm_hour
    if 5 <= h < 13:
        return "Buongiorno"
    if 13 <= h < 18:
        return "Buon pomeriggio"
    return "Buonasera" if 18 <= h < 23 else "Buonanotte"


def describe(people: list) -> str:
    known = sorted({p["name"] for p in people if p["known"]})
    unknown = sum(1 for p in people if not p["known"])
    if not people:
        return "Al momento non vedo nessuno davanti alla webcam."
    parts = []
    if known:
        parts.append(f"Vedo {_join(known)}")
    if unknown:
        who = "una persona che non conosco" if unknown == 1 else f"{unknown} persone che non conosco"
        parts.append(("e " if known else "Vedo ") + who)
    return " ".join(parts) + "."


def merge(visible: list) -> list:
    known: dict = {}
    unknown = []
    for p in visible:
        if not p.get("known"):
            unknown.append(p)
            continue
        seen = known.get(p["slug"])
        if not seen:
            known[p["slug"]] = dict(p)
            continue
        seen["near"] = seen.get("near") or p.get("near")
        seen["since"] = min(seen.get("since", p["since"]), p["since"])
        seen["confidence"] = max(seen.get("confidence", 0), p.get("confidence", 0))
    return [*known.values(), *unknown]


class PresenceMonitor:
    def __init__(self) -> None:
        self.held: dict = {}
        self.unknown_held: tuple = ([], 0.0)
        self.last_seen: dict = {}
        self.greeted: dict = {}
        self.last_unknown_greet = 0.0
        self.greeting_id = 0
        self.observed: dict = {}

    def smooth(self, visible: list) -> list:
        now = time.time()
        people_now = merge(visible)
        for p in people_now:
            if p.get("known"):
                previous = self.held.get(p["slug"])
                since = min(p["since"], previous[0]["since"]) if previous else p["since"]
                self.held[p["slug"]] = ({**p, "since": since}, now)
        self.held = {k: v for k, v in self.held.items() if now - v[1] < HOLD_SECONDS}
        unknown = [p for p in people_now if not p.get("known")]
        if unknown:
            self.unknown_held = (unknown, now)
        elif now - self.unknown_held[1] >= HOLD_SECONDS:
            self.unknown_held = ([], 0.0)
        return [p for p, _ in self.held.values()] + self.unknown_held[0]

    def _greet(self, text: str, names: list) -> None:
        self.greeting_id += 1
        store.greeting = {"id": self.greeting_id, "text": text, "names": names, "at": time.time()}
        store.event("INFO", f"Saluto: {text}", "vision")

    def _evaluate(self, people_list: list) -> None:
        now = time.time()
        stable = [p for p in people_list if now - p["since"] >= STABLE_SECONDS]
        arrivals = []
        for p in stable:
            if not p["known"]:
                continue
            away = now - self.last_seen.get(p["slug"], 0)
            if away > GREET_AGAIN_AFTER and now - self.greeted.get(p["slug"], 0) > GREET_AGAIN_AFTER:
                arrivals.append(p)
        for p in people_list:
            if p["known"]:
                self.last_seen[p["slug"]] = now
                if now - self.observed.get(p["slug"], 0) > 5:
                    self.observed[p["slug"]] = now
                    people.observe(p["slug"], p["name"], now)

        unknown_near = [p for p in stable if not p["known"] and p["near"]]
        newcomers = [p for p in arrivals if p.get("auto")]
        arrivals = [p for p in arrivals if not p.get("auto")]
        for p in newcomers:
            self.greeted[p["slug"]] = now
            self._greet(f"{_salutation()}! Non ci conoscevamo: l'ho aggiunta alla mia memoria come {p['name']}. "
                        "Mi dica pure come si chiama, per esempio: mi chiamo e il suo nome.", [])
        if arrivals:
            names = sorted({p["name"] for p in arrivals})
            for p in arrivals:
                self.greeted[p["slug"]] = now
            text = f"{_salutation()}, {_join(names)}."
            today = {r["slug"]: r for r in people.reminders(days=0)}
            for p in arrivals:
                r = today.get(p["slug"])
                if r and r["type"] == "compleanno":
                    text += f" Tanti auguri di buon compleanno, {p['name'].split()[0]}!"
                elif r and r["type"] == "onomastico":
                    text += " Oggi è il suo onomastico: auguri!"
                elif r:
                    text += f" Le ricordo: {r['title']}."
            if len(stable) > len(arrivals):
                text += " " + describe(stable)
            self._greet(text, names)
            from features.people.welcome import welcome
            from tasks import background
            background(welcome([p["slug"] for p in arrivals]))
            from features.autonomy.engine import autonomy
            autonomy.on_event("arrival")
        elif unknown_near and now - self.last_unknown_greet > UNKNOWN_GREET_AFTER:
            self.last_unknown_greet = now
            if len(stable) > 1:
                text = f"{_salutation()}. {describe(stable)}"
            else:
                text = f"{_salutation()}. Non credo di conoscerti: posso esserti utile?"
            self._greet(text, [])

    async def run(self) -> None:
        if DEMO:
            store.presence = {"status": "ok", "people": [], "summary": describe([])}
            return
        async with httpx.AsyncClient(timeout=3) as client:
            while True:
                if env_get("JARVIS_VISION", "1") == "0":
                    store.presence = {"status": "disabled", "people": [], "summary": ""}
                    await asyncio.sleep(10)
                    continue
                try:
                    data = (await client.get(f"{VISION_URL}/presence")).json()
                    visible = self.smooth(data.get("people", []))
                    previous = store.presence.get("people", [])
                    store.presence = {"status": data.get("status"), "error": data.get("error", ""),
                                      "people": visible, "summary": describe(visible),
                                      "objects": data.get("objects", [])[:20]}
                    if [(p["name"], p["near"]) for p in visible] != [(p["name"], p["near"]) for p in previous]:
                        store.touch()
                    if store.phase in ("READY", "DEGRADED"):
                        self._evaluate(visible)
                        from features.automations.bus import bus as automation_bus
                        automation_bus.presence(visible)
                except (httpx.HTTPError, ValueError, KeyError):
                    if store.presence.get("status") != "offline":
                        store.presence = {"status": "offline", "people": [], "summary": ""}
                        store.touch()
                await asyncio.sleep(0.7)


monitor = PresenceMonitor()
