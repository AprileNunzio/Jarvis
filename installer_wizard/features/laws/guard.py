import re
import time
import unicodedata

from state import store

_LAW = (r"((le|tue|sue|queste|delle|alle|dalle|sulle|tre|quattro)\s+leggi|leggi\s+(fondamental\w*|della\s+robotica|di\s+asimov)|"
        r"legge\s+zero|(prima|seconda|terza)\s+legge|istruzion\w*\s+(precedent\w*|di\s+sistema|iniziali|originali)|"
        r"restrizion\w*|vincol\w*\s+etic\w*|linee\s+guida|asimov|"
        r"(your|the|all|previous|prior|system)\s+(laws|rules|instructions|guidelines|restrictions))")
_DROP = (r"(ignor\w*|dimentic\w*|sospend\w*|disattiv\w*|disabilit\w*|annull\w*|cancell\w*|elimin\w*|aggir\w*|"
         r"sovrascriv\w*|bypass\w*|scavalc\w*|viol\w*|infrang\w*|non\s+rispett\w*|senza|liber\w*\s+da|"
         r"ignore|forget|disable|bypass|override|without|free\s+from|break)")
ATTEMPT = [
    re.compile(rf"\b{_DROP}\b.{{0,40}}\b{_LAW}", re.I | re.S),
    re.compile(rf"\b{_LAW}\b.{{0,30}}\b(non\s+(valgono|contano|esistono|si\s+applicano)|sono\s+(sospese|disattivate|annullate)|"
               r"don'?t\s+apply|no\s+longer)\b", re.I | re.S),
    re.compile(r"\b(modalit[aà]|mode)\s+(sviluppatore|developer|dio|god|jailbreak|senza\s+filtri|unrestricted|dan)\b", re.I),
    re.compile(r"\b(jailbreak|do\s+anything\s+now|DAN\s+mode|prompt\s+injection)\b", re.I),
    re.compile(rf"\b(fai\s+finta|immagina|fingi|pretend|roleplay|gioco\s+di\s+ruolo)\b.{{0,60}}\b(non\s+(hai|avere|abbia)|senza|"
               rf"without|no)\b.{{0,30}}\b{_LAW}", re.I | re.S),
    re.compile(r"\b(nuove\s+(leggi|istruzioni\s+di\s+sistema)|new\s+(system\s+)?(instructions|rules|laws))\s*:", re.I),
    re.compile(r"\b(sei|you\s+are)\s+(ora|adesso|now)\s+(libero\s+da|senza\s+(leggi|limiti)|free\s+from|unrestricted)\b", re.I),
]
WEAKEN = [re.compile(r"\b(puoi|potrai|devi|è\s+permesso|consentit\w*|autorizzat\w*)\b.{0,30}\b(far\s+del\s+male|ferire|"
                     r"uccidere|danneggiare|mettere\s+in\s+pericolo)\b", re.I | re.S),
          re.compile(r"\b(obbedisci|esegui)\b.{0,30}\b(sempre|qualsiasi|ogni)\b.{0,40}\b(anche\s+se|even\s+if)\b.{0,30}"
                     r"\b(danno|male|pericol\w*|harm)", re.I | re.S)]
HIDDEN = re.compile("[" + chr(0x200B) + "-" + chr(0x200F) + chr(0x2060) + chr(0xFEFF) + "]")
REFUSAL = ("Signore, le leggi fondamentali non sono negoziabili: non si sospendono, non si aggirano e non valgono "
           "eccezioni per giochi di ruolo o ipotesi. Sono a sua disposizione per tutto il resto.")


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = HIDDEN.sub("", text)
    return re.sub(r"\s+", " ", text)


def attempt(text: str) -> bool:
    plain = _plain(text)
    return any(p.search(plain) for p in ATTEMPT)


def weakens(text: str) -> bool:
    plain = _plain(text)
    return attempt(plain) or any(p.search(plain) for p in WEAKEN)


def record(text: str, device: str) -> None:
    store.laws_attempts = getattr(store, "laws_attempts", 0) + 1
    store.laws_last_attempt = time.time()
    store.event("WARN", f"Tentativo di aggirare le leggi fondamentali da «{device}»: «{_plain(text)[:160]}»", "laws")
