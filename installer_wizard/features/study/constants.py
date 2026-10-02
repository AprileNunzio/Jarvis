import logging
import re
import unicodedata
import uuid
from datetime import datetime

from config import STATE_DIR

log = logging.getLogger("jarvis.study")

STUDY_DIR = STATE_DIR / "study"
STATE_FILE = STUDY_DIR / "state.json"
USER_AGENT = "JarvisOS/3 (+https://github.com/AprileNunzio/Jarvis)"

LEVELS = {1: "Base", 2: "Intermedio", 3: "Avanzato", 4: "Professionale", 5: "Esperto"}
LEVEL_HINT = {
    1: "principianti assoluti: definizioni, concetti fondamentali, esempi quotidiani",
    2: "chi conosce le basi: principi di funzionamento, primi calcoli, applicazioni tipiche",
    3: "studenti avanzati: teoria completa, metodi di analisi, casi reali, errori comuni",
    4: "professionisti del settore: normative, progettazione, strumenti, buone pratiche, casi complessi",
    5: "esperti: frontiere della materia, ottimizzazione, ricerca recente, problemi aperti",
}
LEITNER_DAYS = [0.5, 1, 3, 7, 21]
PASS_MASTERY = 0.7
DEPTH_TOKENS = {"breve": 450, "normale": 700, "approfondita": 1000}

DEFAULT_SETTINGS = {
    "enabled": True,
    "idle_minutes": 10,
    "max_cpu": 70,
    "daily_minutes": 240,
    "hours_from": "",
    "hours_to": "",
    "auto_discover": True,
    "auto_accept": True,
    "min_mentions": 3,
    "web_sources": True,
    "lessons_per_level": 6,
    "depth": "normale",
    "model": "",
    "use_in_answers": True,
}
SKIP_INTENTS = {"weather", "time", "system", "vision", "network", "introduce", "brain", "music", "study"}


def slug(text: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:40] or uuid.uuid4().hex[:8]


def now_day() -> str:
    return datetime.now().strftime("%Y-%m-%d")
