import re

from config import DEMO
from state import store

from features.actions.bluetooth import bluetooth_action
from features.actions.calc import calc_action, try_calc
from features.actions.common import log, note_gap
from features.actions.devices import device_action
from features.actions.diagnose import diagnose_action
from features.actions.files import file_action
from features.actions.packages import package_action
from features.actions.resources import resources_action
from features.actions.sites import site_action, sites_list_action
from features.actions.smb import smb_action
from features.actions.speed import speed_action
from features.actions.updates import updates_action

__all__ = ["CALC", "REFUSAL", "ACTIONISH", "match", "handle", "calc_action", "try_calc", "diagnose_action", "note_gap"]
MAKE = (r"(?!\w*at[oaie]\b)(?:cre[aiou]\w*|fa(?:i|mmi|rmi|resti|rebbe|re)|fammi|gener\w*|costru\w*|realizz\w*"
        r"|progett\w*|svilupp\w*|prepar\w*|pubblic\w*)")
ROUTES = [
    (
        "bluetooth",
        re.compile(
            r"\b(collega|connetti|attacca|usa|scollega|disconnetti|stacca)\w*\b[^.?!]{0,30}"
            r"\b(cuffie|auricolari|cass[ae]|speaker|bluetooth|microfono bluetooth)\b",
            re.I,
        ),
        bluetooth_action,
    ),
    (
        "updates",
        re.compile(
            r"\b(aggiornament[oi]|update|upgrade|nuova versione|aggiorna(ti|rti|re)?\s+(il\s+)?(sistema|jarvis|tutto|pacchetti|software)"
            r"|(installa|applica)\s+(gli\s+)?aggiornamenti|sei aggiornato)\b",
            re.I,
        ),
        updates_action,
    ),
    (
        "speedtest",
        re.compile(
            r"\b(velocit[àa]\s+(della\s+|di\s+)?(connessione|internet|rete|linea|banda|fibra|adsl)"
            r"|speed\s?test|(?:quanto|com'?[èe]|quant'?[èe])\s+(?:(?:va|corre|[èe])\s+)?(?:veloce\s+)?(?:internet|la connessione|la rete|la linea|la fibra|il wi-?fi)(?:\s+veloce)?(?=\s*\?|\s*$|\s+(?:oggi|adesso|ora))"
            r"|test (della |di )?(velocit[àa]|banda|connessione)|banda (disponibile|internet))\b",
            re.I,
        ),
        speed_action,
    ),
    (
        "smb",
        re.compile(
            r"\b(smb|samba|cifs)\b|\b(cartella|directory|share|risorsa)\b[^.?!]{0,40}\bcondivis\w*"
            r"|\bcondivis\w*[^.?!]{0,30}\b(cartella|directory)\b",
            re.I,
        ),
        smb_action,
    ),
    (
        "sites_list",
        re.compile(r"\b(quali|elenca\w*|dove\s+(sono|trovo|vedo|posso\s+vedere)|mostra\w*|lista)\b[^.?!]{0,25}"
                   r"\b(siti|sito\s+che\s+hai|miei\s+siti|tuoi\s+siti)\b", re.I),
        sites_list_action,
    ),
    (
        "site",
        re.compile(
            r"\b" + MAKE + r"\b[^.?!]{0,40}"
            r"\b(sito|pagina web|landing page|homepage|portfolio online)\b",
            re.I,
        ),
        site_action,
    ),
    (
        "file",
        re.compile(
            r"\b(?:" + MAKE + r"|scriv\w*|salva\w*)\b[^.?!]{0,25}\b(un |il |nuovo )?"
            r"(file|documento di testo|file di testo|txt)\b",
            re.I,
        ),
        file_action,
    ),
    (
        "device",
        re.compile(
            r"\b(ip|indirizzo)\b[^.?!]{0,40}\b(del|di|della|dello)\b|\b(cerca|trova|trovami)\b[^.?!]{0,40}"
            r"\b(dispositiv\w*|telefono|smartphone|pc|computer|tv|stampante|device)\b[^.?!]{0,40}"
            r"\b(rete|chiamat\w*|di nome)\b|\b(cerca|trova)\b[^.?!]{0,60}\b(in|nella|sulla) rete\b",
            re.I,
        ),
        device_action,
    ),
    (
        "resources",
        re.compile(
            r"\b(ram|memoria (ram|usata|libera|occupata|disponibile)|spazio (su|sul|del|nel|libero)\s*(disco)?"
            r"|disco (pieno|libero|occupato)|quanto (disco|spazio)|uso (della |del )?(cpu|processore|memoria)"
            r"|carico (del )?(sistema|processore|cpu)|temperatura (della |del )?(cpu|processore|server))\b",
            re.I,
        ),
        resources_action,
    ),
    (
        "package",
        re.compile(
            r"\binstalla(mi)?\s+(il\s+|lo\s+|l'|un\s+)?(programma\s+|pacchetto\s+|software\s+)?(?!gli\b|tutti\b|aggiorn)[a-z0-9][a-z0-9.+\-]{1,40}\b",
            re.I,
        ),
        package_action,
    ),
]


CALC = re.compile(
    r"\d.*\b(calcol\w*|quanto (fa|fanno|vale|valgono|avr[òo]|ottengo|costa|pago|risparmio)|radice|logaritm\w*"
    r"|interess[ei]|rata|mutuo|percentual\w*|media|somma|prodotto|potenza|elevat\w*|moltiplic\w*|divis\w*"
    r"|arrotond\w*|decimal\w*|fattoriale|seno|coseno|tangente|equazion\w*|converti\w*)\b"
    r"|\b(calcol\w*|quanto (fa|vale|avr[òo]))\b.*\d",
    re.I | re.S,
)


REFUSAL = re.compile(
    r"\b(non (ho|possiedo) (la )?(capacit[àa]|accesso|possibilit[àa])|non (posso|riesco a|sono in grado)"
    r"|come (assistente|intelligenza artificiale|ia|ai)\b|non ho (modo|strumenti)|non mi [èe] possibile)",
    re.I,
)
ACTIONISH = re.compile(
    r"\b(controlla|verifica|dimmi|mostrami|elenca|trova|cerca|quant[aieo]|qual[ei]?|che|come)\b.*"
    r"\b(rete|ip|porte?|servizi|processi|dispositiv\w*|wi-?fi|kernel|versione|uptime|acceso|dns|ping"
    r"|log|docker|container|usb|dischi?|partizion\w*|cpu|processore|scheda|gpu|sistema operativo"
    r"|debian|modell[oi]|ollama|router|gateway|interfacc\w*|mac address|hostname|utenti)\b",
    re.I,
)


def match(text: str) -> tuple[str, object] | None:
    if re.search(r"\b(google|drive|keep|gmail|calendario|agenda)\b", text, re.I):
        return None
    for name, pattern, fn in ROUTES:
        if pattern.search(text):
            return name, fn
    return None


async def handle(text: str) -> tuple[str, dict, str] | None:
    if DEMO:
        return None
    found = match(text)
    if not found:
        return None
    name, fn = found
    try:
        speech, ui = await fn(text)
    except LookupError:
        return None
    except Exception as exc:
        log.exception("Azione %s non riuscita", name)
        store.event("WARN", f"Azione {name} non riuscita: {exc}", "actions")
        note_gap(text, f"{name}: {exc}")
        return f"Ho provato, ma l'operazione non è riuscita: {str(exc)[:200]}", {"mode": "face"}, f"azione · {name}"
    return speech, ui, f"azione · {name}"
