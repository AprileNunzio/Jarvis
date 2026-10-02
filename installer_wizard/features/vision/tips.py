import asyncio
import time
from datetime import date

from config import env_get
from state import store

from features.people import identity

FOOD = {"banana": 89, "mela": 52, "arancia": 47, "panino": 250, "pizza": 266, "ciambella": 452, "torta": 350,
        "hot dog": 290, "broccolo": 34, "carota": 41}
DRINKS = {"bottiglia", "tazza", "bicchiere da vino"}
STEADY = 2
REPEAT_AFTER = 30 * 60


class ObjectTips:

    def __init__(self) -> None:
        self.streak: dict[str, int] = {}
        self.shown: dict[str, float] = {}
        self.drinks: dict[str, int] = {}
        self.day = date.today()

    def _tip(self, label: str, who: str) -> dict | None:
        if label in FOOD:
            return {"icon": "🍽", "title": label.capitalize(), "text": f"Circa {FOOD[label]} kcal ogni 100 g. Buon appetito{who}!"}
        if label in DRINKS:
            self.drinks[who] = self.drinks.get(who, 0) + 1
            return {"icon": "💧", "title": "Idratazione", "text": f"{self.drinks[who]}° bevanda di oggi{who}. Ottimo così!"}
        if label == "libro":
            return {"icon": "📖", "title": "Buona lettura", "text": "Mi dica «annota che sono a pagina…» e lo ricordo io."}
        if label == "spazzolino":
            return {"icon": "🪥", "title": "Due minuti", "text": "Mi dica «timer di 2 minuti» e la avviso io."}
        if label == "orsacchiotto":
            return {"icon": "🧸", "title": "Che compagnia!", "text": "Salutamelo."}
        if label == "cellulare":
            return {"icon": "📱", "title": "Telefono", "text": "Puoi parlarmi anche da Telegram quando sei fuori casa."}
        return None

    def check(self) -> None:
        if date.today() != self.day:
            self.day, self.drinks = date.today(), {}
        held = {o["label"] for o in store.presence.get("objects", []) if o.get("held")}
        self.streak = {label: self.streak.get(label, 0) + 1 for label in held}
        profile = next(iter(identity.present()), None)
        who = f", {identity.first_name(profile)}" if profile else ""
        now = time.time()
        for label, count in self.streak.items():
            if count != STEADY or now - self.shown.get(label, 0) < REPEAT_AFTER:
                continue
            tip = self._tip(label, who)
            if tip:
                from features.desktop.desk import desk
                self.shown[label] = now
                desk.show("notice", tip, key=f"object:{label}", ttl=25)

    async def run(self) -> None:
        while True:
            if env_get("JARVIS_OBJECT_TIPS", "1") != "0" and store.presence.get("status") == "ok":
                self.check()
            await asyncio.sleep(1.5)


tips = ObjectTips()
