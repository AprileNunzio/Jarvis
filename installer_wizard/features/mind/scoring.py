import re


QUESTION = re.compile(r"\?\s*$|\b(?:come|cosa|cos'|dove|quando|quanto|quant[aei]|quale|quali|perch[eé]|chi)\b", re.I)
COMMAND = re.compile(r"\b(?:accendi|spegni|metti|alza|abbassa|apri|chiudi|avvia|ferma|imposta|attiva|disattiva|"
                     r"riproduci|mostra|dimmi|ricorda|aggiungi|cerca|chiama|manda|calcola|crea|leggi)\b", re.I)
DURABLE = re.compile(r"\b(?:mi chiamo|il mio|la mia|i miei|le mie|ricorda|preferisc|mi piace|adoro|odio|abito|vivo|"
                     r"lavoro|sono un|sono una|il mio obiettivo|voglio imparare|sto studiando)\b", re.I)
TRANSIENT = re.compile(r"^\W*(?:ciao|grazie|ok|okay|va bene|perfetto|bene|certo|sì|si|no|boh|mah|ahah)\b", re.I)


def clamp(v: float) -> float:
    return round(max(0.0, min(1.0, v)), 2)


def evaluate(said: str, reply: str, intent: str, context_overlap: float) -> dict:
    n = len(said)
    relevance = context_overlap if context_overlap else (0.5 if intent not in ("conversation", "") else 0.3)
    importance = 0.2
    if COMMAND.search(said):
        importance += 0.3
    if QUESTION.search(said):
        importance += 0.2
    if DURABLE.search(said):
        importance += 0.35
    if intent in ("action", "home", "introduce", "voice_id"):
        importance += 0.2
    if n > 80:
        importance += 0.1
    if TRANSIENT.match(said) and n < 25:
        importance -= 0.3
    memorability = 0.0
    if DURABLE.search(said):
        memorability += 0.6
    if intent in ("introduce", "voice_id", "place"):
        memorability += 0.3
    if n < 15 or TRANSIENT.match(said):
        memorability -= 0.3
    return {"relevance": clamp(relevance), "importance": clamp(importance),
            "memorability": clamp(memorability), "overlap": clamp(context_overlap)}
