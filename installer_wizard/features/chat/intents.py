import re

from features.chat.templates import predictable

INTENTS = [
    ("weather", re.compile(r"\b(meteo|previsioni|piover[àa]|piove|nevicher[àa]|temperatura (fuori|esterna)"
                           r"|(che|com'?[eè]|come sar[àa]|com'?era) (il )?tempo|tempo (fa|far[àa]))\b", re.I)),
    ("music", re.compile(r"\b(che canzone|che brano|chi canta|come si chiama (questa|la) canzone"
                         r"|cosa (sto|stiamo) ascoltando|che musica [èe]|cosa sta suonando)\b", re.I)),
    ("study", re.compile(r"\b(cosa stai studiando|stai studiando|cosa (hai|stai) (studiato|imparando|imparato)"
                         r"|i tuoi studi|come vanno (i tuoi )?studi)\b", re.I)),
    ("brain", re.compile(r"\b(cervello|neuroni|la tua (mente|memoria)|mostrami (la )?(mente|memoria)|cosa ricordi)\b", re.I)),
    ("system", re.compile(r"\b(stato (del |dei )?sistem[ai]|diagnostica|come stanno i sistemi|risorse del sistema|stato di salute)\b", re.I)),
    ("camera", re.compile(r"\b(abilita|attiva|accendi|apri|avvia|metti|mostra(?:mi)?|fammi vedere|chiudi|disattiva|spegni|nascondi|ferma)\b"
                           r"[^.?!]*\b(web\s?cam|fotocamera)\b", re.I)),
    ("vision", re.compile(r"\b(chi (vedi|c'[eè]|hai davanti)|mi vedi|mi riconosci|chi sono( io)?|cosa vedi)\b", re.I)),
    ("network", re.compile(r"\b(scansiona (la )?rete|dispositivi (in|della|nella|di) rete|chi (è|e') connesso"
                            r"|cosa c'?[èe] in rete|rete di casa|dispositivi connessi)\b", re.I)),
    ("place", re.compile(r"\b(abito|vivo|mi trovo|ci troviamo|siamo|la casa [èe]|la mia casa [èe])\s+(a|ad|in)\s+[A-Za-zÀ-ÿ']"
                          r"|\b(dove (sei|siamo|ti trovi|ci troviamo)|qual [èe] la (tua|nostra) posizione)\b", re.I)),
    ("introduce", re.compile(r"\b(mi chiamo|il mio nome [èe]|chiamami)\s+\w", re.I)),
    ("voices", re.compile(r"\b(?:(?:scarica|installa|aggiungi|prendi|procurati|impara)(?:ti)?\s+(?:la\s+|una\s+|le\s+)?voc[ei]"
                           r"|(?:che|quali)\s+(?:voci|lingue)\s+(?:hai|parli|conosci|sai)|in\s+che\s+lingue\s+(?:parli|sai)"
                           r"|download\s+(?:the\s+|a\s+)?\w*\s*voice|which\s+languages\s+(?:do\s+you|can\s+you))\b", re.I)),
    ("time", re.compile(r"\b(che ore sono|che ora [èe]|che giorno [èe]|che data [èe])\b", re.I)),
]


def detect_intent(text: str) -> str:
    for name, pattern in INTENTS:
        if pattern.search(text):
            return name
    return "conversation"


def predict(text: str) -> dict:
    intent = detect_intent(text)
    tpl = predictable(intent)
    return {"intent": intent, "skeleton": tpl["skeleton"] if tpl else None,
            "expected_ms": tpl["avg_ms"] if tpl else None}
