import re
from dataclasses import dataclass

import httpx

from features.chat import context as request_context
from features.google.app import oauth
from features.google.constants import SERVICES, NotLinked
from features.google.gservices import google
from features.google.notify import notifier
from features.google.session import Session
from features.people import identity

_R = lambda p: re.compile(p, re.I)
FOLLOW_UP = _R(r"^\W*(?:jarvis\W+)?(?:s[iì]\W*)?(?:leggi(?:me)?(?:l[aoei]|l[ae]|li)|leggila|leggilo|aprila|aprilo|"
                r"mostra(?:me)?(?:l[aoei])|fammel[aoei] vedere|dimmi di più|cosa dice|di cosa si tratta|s[iì](?: grazie)?|"
                r"certo|va bene|dimmi)\W*$")
YES_ONLY = _R(r"^\W*(?:s[iì](?: grazie)?|certo|va bene|dimmi)\W*$")
FOLLOW_SERVICE = {"mail": ("mail_read", "gmail"), "calendar": ("calendar", "calendar"), "event": ("calendar", "calendar"),
                  "tasks": ("tasks", "tasks"), "notes": ("notes", "keep")}
COMMANDS = [
    ("calendar_delete", "calendar", _R(r"\b(?:cancella|elimina|annulla|togli|rimuovi)(?:mi)?\b.{0,30}?"
                                       r"\b(?:appuntamento|evento|impegno|riunione|dall'agenda|dal calendario)\b")),
    ("calendar_free", "calendar", _R(r"\b(?:quando|a che ora) sono libero\b|\b(?:buchi|spazi|momenti) liberi\b"
                                     r"|\bho tempo (?:oggi|domani|lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\b")),
    ("calendar_add", "calendar", _R(r"\b(?:aggiungi|segna|metti|inserisci|crea|fissa|programma|annota)(?:mi)?\b.{0,40}?"
                                    r"\b(?:in|nel(?:l[ao'])?|sul(?:l[ao'])?|al(?:l[ao'])?)\s*(?:mia\s+|mio\s+)?"
                                    r"(?:agenda|calendario)\b"
                                    r"|\b(?:crea|fissa|aggiungi|segna)(?:mi)?\s+(?:un|l')\s*(?:appuntamento|evento|impegno)\b")),
    ("calendar", "calendar", _R(r"\b(?:agenda|calendario|(?:miei |prossimi )?impegni|(?:miei |prossimi |il prossimo )appuntament[oi]"
                                r"|che appuntament[oi])\b"
                                r"|\bcosa (?:ho|c'è|c'e) (?:da fare )?(?:oggi|domani|dopodomani|stasera|lunedì|martedì|"
                                r"mercoledì|giovedì|venerdì|sabato|domenica|questa settimana)\s*[?.!]?$"
                                r"|\bsono libero\b")),
    ("mail_read", "gmail", _R(r"\b(?:leggi(?:mi)?|cosa dice|di cosa parla|apri)\b[^.?!]{0,20}\b(?:l'|la )?(?:ultima|ultim[ae]|"
                              r"prima|nuova) (?:e-?mail|mail)\b|\bcosa (?:mi )?(?:ha scritto|scrive)\b"
                              r"|^\W*(?:leggi(?:me)?l[ao]|leggila)\W*$")),
    ("mail", "gmail", _R(r"\bgmail\b|\bposta in arrivo\b"
                         r"|\b(?:ho|ci sono|nuove|ultime|leggi(?:mi)?|controlla|apri|mostra(?:mi)?|quante|cerca)\b[^.?!]{0,20}"
                         r"\b(?:e-?mail|mail|posta)\b"
                         r"|\b(?:e-?mail|mail|posta)\b[^.?!]{0,15}\b(?:non lette|nuove|in arrivo|arrivat[ea]|ricevut[ea])\b"
                         r"|\b(?:e-?mail|mail) (?:da|su|di|riguardo)\s+[A-Za-zÀ-ÿ']")),
    ("task_done", "tasks", _R(r"\b(?:ho fatto|ho finito|fatto|completat[ao]|segna (?:come )?fatt[ao]|spunta|completa)\b"
                              r"[^.?!]{0,10}\b(?:l'attività|il task|la cosa|dalla lista)?")),
    ("task_add", "tasks", _R(r"\b(?:ricordami di|devo ricordarmi di|aggiungi (?:alla|nella|in) (?:mia )?(?:lista|to ?do|cose da fare)"
                             r"|(?:aggiungi|crea|metti) (?:un'?|una )?(?:attività|task|cosa da fare))\b")),
    ("tasks", "tasks", _R(r"\b(?:(?:le mie|la mia lista delle|la lista delle) (?:attività|task|cose da fare)|to ?do list"
                          r"|la mia lista|google tasks)\b|\bcosa devo fare(?: oggi| domani)?\s*[?.!]?$|\bcose da fare\s*[?.!]?$")),
    ("contact", "contacts", _R(r"\b(?:(?:numero|telefono|cellulare|recapito|indirizzo e-?mail|e-?mail)"
                               r"(?: di telefono)? (?:di|del|della|dello)\s+[A-Za-zÀ-ÿ']|contatto (?:di )?[A-Za-zÀ-ÿ']"
                               r"|(?:cerca|trova) in rubrica)")),
    ("drive", "drive", _R(r"\b(?:(?:cerca|trova|apri)(?:mi)? (?:nel|sul|su|in) (?:google )?drive"
                          r"|(?:cerca|trova)(?:mi)? (?:il |i )?(?:file|document[oi]) )")),
    ("note_add", "keep", _R(r"\b(?:aggiungi|crea|scrivi|prendi) (?:una |la )?not[ae]\b|\bannota(?:ti)? che\b")),
    ("notes", "keep", _R(r"\b(?:(?:le )?mie note|note di keep|google keep|leggi (?:le )?(?:mie )?note)\b")),
]
_SOFT = {"task_add", "task_done", "tasks", "contact", "drive", "note_add"}
_EXPLICIT = _R(r"\b(?:agenda|calendario|gmail|e-?mail|mail|posta|google|keep|drive|rubrica|contatti|appuntament[oi]|impegni)\b")


@dataclass
class Ctx:
    profile: dict
    session: Session
    private: bool

    @property
    def name(self) -> str:
        return identity.first_name(self.profile)

    @property
    def email(self) -> str:
        return self.session.info.get("email", "")


def match(text: str) -> tuple[str, str] | None:
    for name, service, rx in COMMANDS:
        if name == "mail" and re.search(r"\b(?:indirizzo )?e-?mail (?:di|del|della)\s+[A-Za-zÀ-ÿ']", text, re.I) \
                and not re.search(r"\b(?:ultime|nuove|non lette|ricevut[ea]|arrivat[ea])\b", text, re.I):
            continue
        if name == "task_done" and not re.search(r"\b(?:attività|task|lista|cose da fare)\b", text, re.I):
            continue
        if rx.search(text):
            return name, service
    return None


def _who() -> dict | None:
    heard = request_context.voice.get()
    if heard:
        return identity.current(heard)
    here = identity.present()
    if here:
        return here[0]
    return identity.owner() if request_context.trusted() else None


def _context(service: str, soft: bool) -> Ctx:
    if not (google.enabled() and oauth.ready()):
        if soft:
            raise LookupError
        raise NotLinked("I servizi Google non sono ancora configurati: aggiungi l'app Google dal pannello, scheda Google.")
    profile = _who()
    if not profile:
        raise NotLinked("Non la vedo, signore: si metta davanti alla webcam, così so di chi è l'account e non leggo i dati "
                        "di qualcun altro.")
    session = google.for_profile(profile)
    name = identity.first_name(profile)
    if not session:
        if soft:
            raise LookupError
        raise NotLinked(f"{name}, non ha ancora collegato il suo account Google: lo faccia dal pannello, scheda Google, "
                        "accanto al suo nome.")
    if not session.ready(service):
        if soft:
            raise LookupError
        raise NotLinked(f"{name}, il suo account Google è collegato ma senza il permesso per "
                        f"{SERVICES[service]['name']}: lo ricolleghi scegliendo anche questo servizio.")
    return Ctx(profile, session, identity.alone(profile) or request_context.trusted())


def _follow_up(text: str) -> tuple[str, str, str] | None:
    if not FOLLOW_UP.search(text):
        return None
    profile = _who()
    window = 180 if YES_ONLY.search(text) else 900
    kind = notifier.recent(profile["slug"], window) if profile else None
    if not kind:
        return None
    notifier.consume(profile["slug"])
    cmd, service = FOLLOW_SERVICE[kind]
    return cmd, service, "prossimi appuntamenti" if cmd == "calendar" else "leggimi l'ultima email" if cmd == "mail_read" else text


async def answer(text: str) -> tuple[str, dict]:
    follow = _follow_up(text)
    if follow:
        cmd, service, text = follow
    else:
        hit = match(text)
        if not hit:
            raise LookupError
        cmd, service = hit
    ctx = _context(service, cmd in _SOFT or not _EXPLICIT.search(text))
    from features.google import cmd_calendar, cmd_mail, cmd_misc, cmd_tasks
    handlers = {"calendar": cmd_calendar.agenda, "calendar_add": cmd_calendar.add, "calendar_delete": cmd_calendar.delete,
                "calendar_free": cmd_calendar.free, "mail": cmd_mail.inbox, "mail_read": cmd_mail.read,
                "tasks": cmd_tasks.listing, "task_add": cmd_tasks.add, "task_done": cmd_tasks.done,
                "contact": cmd_misc.contact, "drive": cmd_misc.drive, "notes": cmd_misc.notes,
                "note_add": cmd_misc.note_add}
    try:
        return await handlers[cmd](text, ctx)
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"{SERVICES[service]['name']}: errore {exc.response.status_code}") from exc
