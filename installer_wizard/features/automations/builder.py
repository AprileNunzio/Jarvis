import json

from features.automations.bus import bus
from features.automations.schema import ACTIONS, CONDITIONS, EVENTS, TRIGGERS, validate
from features.automations.templates import TEMPLATES

RULES = (
    "Sei il progettista di automazioni di Jarvis. Trasforma la richiesta in UNA automazione JSON valida, senza testo "
    "fuori dal JSON. Struttura: {{\"name\": str, \"description\": str, \"mode\": \"single|restart|queued|parallel\", "
    "\"cooldown\": secondi, \"variables\": {{}}, \"triggers\": [...], \"conditions\": [...], \"actions\": [...]}}.\n"
    "Ogni elemento ha \"type\" e i suoi campi. Tipi disponibili:\n{catalog}\n"
    "Eventi: {events}.\n"
    "Espressioni e testi possono usare {{{{ ... }}}} con: state('entità'), attr('entità','attributo'), since('entità') "
    "(secondi dall'ultimo cambio), present('nome'), people(), quiet(), hour(), weekday() (0=lunedì), num(x), "
    "data.* (dati dell'innesco), variabili impostate con set. Le azioni annidate (then, else, yes, no, actions, default, "
    "branches, options) sono elenchi di azioni. Usa solo entità esistenti; se non esistono usa nomi plausibili come "
    "light.soggiorno e scrivilo nella descrizione. I testi parlati danno del Lei e chiamano l'utente «signore».\n"
    "Entità conosciute (id = stato):\n{entities}\n\nEsempio di automazione ben fatta:\n{example}"
)


def _fields(spec: dict) -> str:
    return ", ".join(f"{f['key']}" + ("*" if f.get("required") else "") for f in spec["fields"])


def catalog_text() -> str:
    parts = []
    for title, kinds in (("INNESCHI", TRIGGERS), ("CONDIZIONI", CONDITIONS), ("AZIONI", ACTIONS)):
        parts.append(title + ": " + "; ".join(f"{k}({_fields(v)})" for k, v in kinds.items()))
    return "\n".join(parts)


def entities_text(limit: int = 120) -> str:
    rows = bus.states.catalog()[:limit]
    return "\n".join(f"{r['id']} = {r['state']} ({r['name']})" for r in rows) or "(nessuna: Home Assistant non collegato)"


async def build(request: str, current: dict | None = None) -> tuple[dict, list[str]]:
    from features.brain.llm import generate
    system = RULES.format(catalog=catalog_text(), events=", ".join(e["value"] for e in EVENTS),
                          entities=entities_text(), example=json.dumps(TEMPLATES[3], ensure_ascii=False))
    prompt = f"Richiesta: {request}"
    if current:
        prompt += "\nModifica questa automazione esistente secondo la richiesta:\n" + json.dumps(current, ensure_ascii=False)[:4000]
    errors: list[str] = []
    spec: dict = {}
    for attempt in range(3):
        text = prompt if not errors else prompt + "\nLa tua proposta precedente aveva questi errori, correggili:\n- " + \
            "\n- ".join(errors) + "\nProposta precedente:\n" + json.dumps(spec, ensure_ascii=False)[:4000]
        reply = await generate(text, as_json=True, max_tokens=1800, temperature=0.1, kind="deep", system=system, timeout=300)
        spec = reply if isinstance(reply, dict) else {}
        spec, errors = validate(spec)
        if not errors:
            break
    return spec, errors
