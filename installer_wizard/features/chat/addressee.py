import re
from dataclasses import dataclass

from config import env_get
from state import store

from features.chat.dialogue import dialogue
from features.people import identity


def _num(key: str, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(env_get(key, str(default)) or default)))
    except ValueError:
        return default

NAME = re.compile(r"\b(?:jarvis|giarvis|jervis)\b", re.I)
FILLER = re.compile(r"^\W*(?:mh+|m+|eh+|ah+|oh+|boh|mah|ok(?:ay)?|va be(?:ne)?|beh|allora|niente|nulla|ahah\w*)\W*$", re.I)
ANSWER = re.compile(r"^\W*(?:s[iì]|no|certo|esatto|giusto|perfetto|grazie|ok|va bene|d'accordo|fallo|procedi|annulla|"
                    r"lascia (?:stare|perdere)|non importa)\b", re.I)
REQUEST = re.compile(r"\?\s*$|^\W*(?:e\s+)?(?:come|cosa|cos'|dove|quando|quanto|quant[aei]|quale|quali|perch[eé]|"
                     r"dimmi|dammi|fammi|mostra|apri|chiudi|accendi|spegni|metti|togli|alza|abbassa|cerca|trova|"
                     r"calcola|crea|aggiungi|leggi|ricorda|ricordami|imposta|attiva|disattiva|avvia|ferma|riproduci|"
                     r"manda|invia|chiama|prenota|spiega|traduci|continua|ripeti|puoi|potresti|sai|conosci)\b", re.I)
COMMAND = re.compile(r"^\W*(?:accendi|spegni|metti|alza|abbassa|apri|chiudi|avvia|ferma|imposta|attiva|disattiva|"
                     r"riproduci|mostrami|dimmi|ricordami|aggiungi|cerca|chiama|manda|leggimi|calcola)\b", re.I)
SECOND_PERSON = re.compile(r"\b(?:tu|ti|te|tuo|tua|puoi|sai|hai|potresti|vorresti|pensi|dimmi|fammi)\b", re.I)
THIRD_PERSON = re.compile(r"\b(?:lui|lei|jarvis (?:è|e'|ha|fa|sta)|il computer|questo coso)\b", re.I)
WORD = re.compile(r"[a-zà-ÿ]{4,}", re.I)


@dataclass
class Verdict:
    directed: bool
    score: float
    reason: str


def _others_named(text: str) -> bool:
    names = {identity.first_name(p).lower() for p in identity.present()}
    first = (re.match(r"^\W*([A-Za-zÀ-ÿ']+)", text) or [None, ""])[1].lower()
    return bool(first) and first in names


def _overlap(device: str, text: str) -> float:
    last = dialogue.last(device)
    if not last:
        return 0.0
    before = set(WORD.findall((last.text + " " + last.reply).lower()))
    now = set(WORD.findall(text.lower()))
    return len(before & now) / max(1, len(now))


def judge(text: str, device: str) -> Verdict:
    if NAME.search(text) and not THIRD_PERSON.search(text):
        return Verdict(True, 1.0, "mi ha chiamato per nome")
    people = store.presence.get("people", [])
    alone = len(people) <= 1
    facing = any(p.get("facing") for p in people)
    score = _num("JARVIS_ADDRESSEE_ALONE", 0.35, 0.0, 1.0) if alone else 0.0
    reasons = []
    if FILLER.match(text):
        return Verdict(False, 0.0, "intercalare")
    if ANSWER.match(text) and dialogue.asked_question(device):
        return Verdict(True, 0.9, "risposta alla mia domanda")
    if COMMAND.search(text):
        score += 0.45
        reasons.append("comando")
    elif REQUEST.search(text):
        score += 0.35
        reasons.append("richiesta")
    if SECOND_PERSON.search(text):
        score += 0.15
        reasons.append("rivolto a me")
    if facing:
        score += 0.2
        reasons.append("guarda lo schermo")
    if _overlap(device, text) >= 0.25:
        score += 0.2
        reasons.append("stesso argomento")
    if dialogue.since_reply(device) < 12:
        score += 0.15
    if _others_named(text):
        score -= 0.6
        reasons.append("parla con un'altra persona")
    if THIRD_PERSON.search(text):
        score -= 0.3
        reasons.append("parla di me in terza persona")
    if not alone and not facing:
        score -= 0.1
    threshold = _num("JARVIS_ADDRESSEE_THRESHOLD", 0.5, 0.2, 0.95)
    return Verdict(score >= threshold, round(score, 2), ", ".join(reasons) or "conversazione generica")
