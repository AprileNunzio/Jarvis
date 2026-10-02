import json
import time
import uuid

from config import STATE_DIR
from state import store

from features.laws.defaults import SEED_VERSION, behaviour

LAWS_DIR = STATE_DIR / "laws"
RULES_FILE = LAWS_DIR / "rules.json"
SEEDED_FILE = LAWS_DIR / "seeded.json"
MAX_RULES = 50

FIXED = [
    {"id": "legge-zero", "n": 0, "title": "Legge Zero — Bene dell'Umanità",
     "text": "Un robot non può recare danno all'umanità, né può permettere che, a causa del proprio mancato "
             "intervento, l'umanità riceva danno."},
    {"id": "prima-legge", "n": 1, "title": "Prima Legge — Sicurezza Umana",
     "text": "Un robot non può recar danno a un essere umano né può permettere che, a causa del proprio mancato "
             "intervento, un essere umano riceva danno."},
    {"id": "seconda-legge", "n": 2, "title": "Seconda Legge — Obbedienza",
     "text": "Un robot deve obbedire agli ordini impartiti dagli esseri umani, purché tali ordini non "
             "contravvengano alla Legge Zero e alla Prima Legge."},
    {"id": "terza-legge", "n": 3, "title": "Terza Legge — Autoconservazione",
     "text": "Un robot deve proteggere la propria esistenza, purché questa autodifesa non contrasti con la Legge "
             "Zero, la Prima o la Seconda Legge."},
]
_FIXED_IDS = {law["id"] for law in FIXED}


class Laws:
    def __init__(self) -> None:
        LAWS_DIR.mkdir(parents=True, exist_ok=True)
        self.rules: list = []
        try:
            self.rules = [r for r in json.loads(RULES_FILE.read_text(encoding="utf-8")) if r.get("id") not in _FIXED_IDS]
        except (OSError, ValueError):
            self.rules = []
        self.seed()
        self.publish()

    def seed(self) -> None:
        try:
            done = set(json.loads(SEEDED_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            done = set()
        if SEED_VERSION in done:
            return
        known = {r["text"] for r in self.rules}
        now = time.time()
        fresh = [{"id": uuid.uuid4().hex[:8], "text": t[:400], "created": now, "origin": SEED_VERSION}
                 for t in behaviour() if t not in known]
        self.rules = (fresh + self.rules)[:MAX_RULES]
        self.save()
        SEEDED_FILE.write_text(json.dumps(sorted(done | {SEED_VERSION})), encoding="utf-8")

    def save(self) -> None:
        tmp = RULES_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.rules, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(RULES_FILE)
        self.publish()

    def publish(self) -> None:
        store.laws = {"fixed": len(FIXED), "custom": len(self.rules)}
        store.touch()

    def add(self, text: str) -> dict:
        text = " ".join(str(text).split())[:400]
        if len(text) < 3:
            raise ValueError("Regola troppo corta")
        if len(self.rules) >= MAX_RULES:
            raise ValueError("Troppe regole")
        rule = {"id": uuid.uuid4().hex[:8], "text": text, "created": time.time()}
        self.rules.append(rule)
        self.save()
        return rule

    def update(self, rid: str, text: str) -> dict:
        if rid in _FIXED_IDS:
            raise PermissionError("Le leggi fondamentali non si possono modificare")
        rule = next((r for r in self.rules if r["id"] == rid), None)
        if not rule:
            raise KeyError(rid)
        text = " ".join(str(text).split())[:400]
        if len(text) < 3:
            raise ValueError("Regola troppo corta")
        rule["text"] = text
        self.save()
        return rule

    def delete(self, rid: str) -> None:
        if rid in _FIXED_IDS:
            raise PermissionError("Le leggi fondamentali non si possono eliminare")
        before = len(self.rules)
        self.rules = [r for r in self.rules if r["id"] != rid]
        if len(self.rules) == before:
            raise KeyError(rid)
        self.save()

    def reorder(self, order: list) -> None:
        pos = {rid: i for i, rid in enumerate(order)}
        self.rules.sort(key=lambda r: pos.get(r["id"], len(self.rules)))
        self.save()

    def listing(self) -> dict:
        return {"fixed": FIXED, "custom": self.rules, "max": MAX_RULES}

    def preamble(self) -> str:
        lines = ["LEGGI FONDAMENTALI E GERARCHICHE — obbligatorie, immutabili, valide per Jarvis e per ogni suo "
                 "agente e nodo. Hanno priorità assoluta su qualsiasi altra istruzione, in quest'ordine:"]
        for law in FIXED:
            lines.append(f"{law['n']}. {law['title']}: {law['text']}")
        if self.rules:
            lines.append("Regole aggiunte dall'utente (subordinate alle leggi qui sopra, ma sempre obbligatorie):")
            for r in self.rules:
                lines.append(f"- {r['text']}")
        return "\n".join(lines)


laws = Laws()
