import re
import uuid

DAYS = [{"value": i, "label": d} for i, d in enumerate(["lun", "mar", "mer", "gio", "ven", "sab", "dom"])]
MODES = [{"value": "single", "label": "Singola: ignora se è già in corso"},
         {"value": "restart", "label": "Riavvia: interrompe quella in corso e riparte"},
         {"value": "queued", "label": "In coda: una dopo l'altra"},
         {"value": "parallel", "label": "In parallelo: più esecuzioni insieme"}]
EVENTS = [
    {"value": "person_arrived", "label": "Una persona riconosciuta arriva"},
    {"value": "person_left", "label": "Una persona non si vede più"},
    {"value": "nobody_home", "label": "Non c'è più nessuno"},
    {"value": "somebody_home", "label": "Arriva qualcuno dopo che non c'era nessuno"},
    {"value": "wake", "label": "Qualcuno dice «Jarvis»"},
    {"value": "voice_command", "label": "Qualsiasi richiesta a Jarvis"},
    {"value": "email_new", "label": "Nuova email"},
    {"value": "calendar_soon", "label": "Impegno in agenda tra poco"},
    {"value": "component_broken", "label": "Un componente di Jarvis si guasta"},
    {"value": "component_ok", "label": "Un componente torna a funzionare"},
    {"value": "automation_finished", "label": "Un'altra automazione termina"},
    {"value": "startup", "label": "Avvio di Jarvis"},
    {"value": "custom", "label": "Evento personalizzato (nome sotto)"},
]
SUN = [{"value": "sunrise", "label": "Alba"}, {"value": "sunset", "label": "Tramonto"}]
OPS = [{"value": v, "label": v} for v in ("==", "!=", ">", ">=", "<", "<=", "contiene", "in")]
CHANNELS = [{"value": "display", "label": "Display"}, {"value": "voice", "label": "Voce"},
            {"value": "telegram", "label": "Telegram"}, {"value": "email", "label": "Email"}]

F = lambda key, label, type="text", **kw: {"key": key, "label": label, "type": type, **kw}

TRIGGERS = {
    "time": {"label": "Orario", "icon": "⏰", "fields": [F("at", "Ora", "time", required=True), F("days", "Giorni (vuoto = tutti)", "days")]},
    "interval": {"label": "Ogni N minuti", "icon": "🔁", "fields": [F("minutes", "Ogni quanti minuti", "number", required=True, min=1)]},
    "sun": {"label": "Alba o tramonto", "icon": "🌅", "fields": [F("event", "Quando", "select", options=SUN, required=True),
                                                             F("offset", "Spostamento (minuti, anche negativo)", "number")]},
    "state": {"label": "Cambio di stato di un dispositivo", "icon": "🔌", "fields": [
        F("entity", "Dispositivo o entità", "entity", required=True), F("attribute", "Attributo (vuoto = stato)"),
        F("from", "Da (vuoto = qualsiasi)"), F("to", "A (vuoto = qualsiasi)"), F("above", "Sopra a", "number"),
        F("below", "Sotto a", "number"), F("for", "Per almeno (secondi)", "number", min=0)]},
    "presence": {"label": "Presenze", "icon": "🧍", "fields": [
        F("event", "Quando", "select", required=True, options=[e for e in EVENTS if e["value"] in ("person_arrived", "person_left", "nobody_home", "somebody_home")]),
        F("person", "Persona (vuoto = chiunque)")]},
    "phrase": {"label": "Frase detta a Jarvis", "icon": "🗣", "fields": [
        F("phrases", "Frasi (una per riga, * = qualsiasi parola)", "list", required=True),
        F("reply", "Risposta immediata (vuoto = «Subito, signore.»)")]},
    "event": {"label": "Evento di Jarvis", "icon": "⚡", "fields": [F("name", "Evento", "select", options=EVENTS, required=True),
                                                                 F("custom", "Nome evento personalizzato"),
                                                                 F("filter", "Filtro (espressione, es. data.person == 'Nunzio')")]},
    "template": {"label": "Quando un'espressione diventa vera", "icon": "🧮", "fields": [
        F("expr", "Espressione", "text", required=True, placeholder="num(state('sensor.temperatura')) > 26 and present()"),
        F("for", "Per almeno (secondi)", "number", min=0)]},
    "webhook": {"label": "Chiamata web (webhook)", "icon": "🌐", "fields": [F("key", "Chiave segreta (generata se vuota)")]},
    "manual": {"label": "Solo manuale", "icon": "👆", "fields": []},
}

CONDITIONS = {
    "and": {"label": "Tutte vere (E)", "icon": "∧", "fields": [F("conditions", "Condizioni", "conditions")]},
    "or": {"label": "Almeno una vera (O)", "icon": "∨", "fields": [F("conditions", "Condizioni", "conditions")]},
    "not": {"label": "Nessuna vera (NON)", "icon": "¬", "fields": [F("conditions", "Condizioni", "conditions")]},
    "time": {"label": "Fascia oraria", "icon": "⏰", "fields": [F("after", "Dopo le", "time"), F("before", "Prima delle", "time"),
                                                          F("days", "Giorni", "days")]},
    "state": {"label": "Stato di un dispositivo", "icon": "🔌", "fields": [
        F("entity", "Dispositivo o entità", "entity", required=True), F("attribute", "Attributo"),
        F("op", "Confronto", "select", options=OPS, default="=="), F("value", "Valore", required=True),
        F("for", "Da almeno (secondi)", "number", min=0)]},
    "presence": {"label": "Presenza", "icon": "🧍", "fields": [F("person", "Persona (vuoto = qualcuno)"),
                                                             F("present", "Presente", "bool", default=True)]},
    "sun": {"label": "Giorno o notte", "icon": "🌗", "fields": [
        F("when", "Quando", "select", required=True, options=[{"value": "day", "label": "È giorno"}, {"value": "night", "label": "È notte"}])]},
    "quiet": {"label": "Orario di silenzio", "icon": "🌙", "fields": [F("active", "Silenzio attivo", "bool", default=True)]},
    "trigger": {"label": "Avviata da un certo innesco", "icon": "🎯", "fields": [F("id", "Id dell'innesco", required=True)]},
    "expr": {"label": "Espressione", "icon": "🧮", "fields": [F("expr", "Espressione", required=True)]},
}

ACTIONS = {
    "ha": {"label": "Comanda un dispositivo (Home Assistant)", "icon": "🏠", "fields": [
        F("service", "Servizio (es. light.turn_on)", required=True), F("entity", "Dispositivi", "entities"),
        F("data", "Parametri (JSON, es. {\"brightness_pct\": 40})", "json")]},
    "speak": {"label": "Parla", "icon": "🔊", "fields": [F("text", "Testo (anche con {{ espressioni }})", "textarea", required=True),
                                                        F("force", "Anche in orario di silenzio", "bool")]},
    "notify": {"label": "Notifica", "icon": "🔔", "fields": [F("title", "Titolo"), F("text", "Testo", "textarea", required=True),
                                                            F("channels", "Canali", "multi", options=CHANNELS, default=["display"]),
                                                            F("to", "Email destinatario (per il canale email)")]},
    "widget": {"label": "Mostra un widget", "icon": "🪟", "fields": [F("widget", "Widget", "widget", required=True),
                                                                  F("data", "Dati (JSON)", "json"), F("ttl", "Per (secondi)", "number")]},
    "holo": {"label": "Ologramma", "icon": "🧑‍🚀", "fields": [F("express", "Espressione (es. sorriso)"), F("play", "Animazione"),
                                                         F("accessory", "Accessorio (cappello, occhiali, cuffie)"), F("tint", "Colore (#rrggbb)")]},
    "sound": {"label": "Suono", "icon": "🎵", "fields": [F("name", "Suono", "sound", required=True), F("force", "Anche in silenzio", "bool")]},
    "agent": {"label": "Chiedi a Jarvis (agente con strumenti)", "icon": "🤖", "fields": [
        F("prompt", "Cosa deve fare", "textarea", required=True), F("trusted", "Senza chiedere approvazione", "bool"),
        F("store", "Salva la risposta nella variabile")]},
    "email": {"label": "Invia email", "icon": "✉️", "fields": [F("to", "A", required=True), F("subject", "Oggetto", required=True),
                                                             F("body", "Testo", "textarea"), F("attachments", "Allegati (percorsi, uno per riga)", "list")]},
    "http": {"label": "Richiesta web", "icon": "🌐", "fields": [
        F("method", "Metodo", "select", options=[{"value": m, "label": m} for m in ("GET", "POST", "PUT", "DELETE")], default="GET"),
        F("url", "Indirizzo", required=True), F("body", "Corpo (JSON)", "json"), F("store", "Salva la risposta nella variabile")]},
    "delay": {"label": "Attendi", "icon": "⏳", "fields": [F("seconds", "Secondi (o espressione)", required=True)]},
    "wait_state": {"label": "Attendi uno stato", "icon": "⏱", "fields": [
        F("entity", "Dispositivo", "entity", required=True), F("to", "Stato atteso", required=True),
        F("timeout", "Al massimo (secondi)", "number", default=300), F("continue", "Continua anche se scade", "bool", default=True)]},
    "wait_event": {"label": "Attendi un evento", "icon": "⏱", "fields": [
        F("name", "Evento", "select", options=EVENTS, required=True), F("custom", "Nome personalizzato"),
        F("filter", "Filtro (espressione)"), F("timeout", "Al massimo (secondi)", "number", default=300),
        F("continue", "Continua anche se scade", "bool", default=True)]},
    "wait_expr": {"label": "Attendi che un'espressione sia vera", "icon": "⏱", "fields": [
        F("expr", "Espressione", required=True), F("timeout", "Al massimo (secondi)", "number", default=300),
        F("continue", "Continua anche se scade", "bool", default=True)]},
    "confirm": {"label": "Chiedi conferma a voce", "icon": "❓", "fields": [
        F("question", "Domanda", required=True), F("timeout", "Attendi risposta (secondi)", "number", default=60),
        F("yes", "Se risponde sì", "actions"), F("no", "Se risponde no o non risponde", "actions")]},
    "if": {"label": "Se… allora… altrimenti", "icon": "🔀", "fields": [F("conditions", "Se", "conditions"),
                                                                     F("then", "Allora", "actions"), F("else", "Altrimenti", "actions")]},
    "choose": {"label": "Scegli tra più casi", "icon": "🧭", "fields": [F("options", "Casi", "options"), F("default", "Altrimenti", "actions")]},
    "parallel": {"label": "In parallelo", "icon": "⫴", "fields": [F("branches", "Rami", "branches")]},
    "repeat": {"label": "Ripeti", "icon": "🔁", "fields": [
        F("count", "Volte (vuoto se usi mentre/finché)", "number"), F("while", "Mentre (espressione)"),
        F("until", "Finché (espressione)"), F("actions", "Azioni", "actions")]},
    "set": {"label": "Imposta variabile", "icon": "🧷", "fields": [
        F("name", "Nome", required=True), F("value", "Valore (anche {{ espressione }})", required=True),
        F("scope", "Ambito", "select", default="run", options=[{"value": "run", "label": "Solo questa esecuzione"},
                                                              {"value": "global", "label": "Globale (persiste)"}])]},
    "event": {"label": "Genera un evento", "icon": "⚡", "fields": [F("name", "Nome evento", required=True), F("data", "Dati (JSON)", "json")]},
    "run": {"label": "Avvia un'altra automazione", "icon": "▶", "fields": [F("automation", "Automazione", "automation", required=True),
                                                                          F("wait", "Attendi che finisca", "bool")]},
    "toggle": {"label": "Attiva o disattiva un'automazione", "icon": "⏯", "fields": [
        F("automation", "Automazione", "automation", required=True), F("enabled", "Attiva", "bool", default=True)]},
    "respond": {"label": "Risposta a voce alla frase", "icon": "💬", "fields": [F("text", "Testo", required=True)]},
    "log": {"label": "Scrivi nel registro", "icon": "📝", "fields": [F("text", "Testo", required=True)]},
    "stop": {"label": "Ferma l'automazione", "icon": "⏹", "fields": [F("reason", "Motivo"), F("error", "Come errore", "bool")]},
}

NESTED = {"conditions": "conditions", "then": "actions", "else": "actions", "default": "actions", "actions": "actions",
          "yes": "actions", "no": "actions"}


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def catalog() -> dict:
    return {"triggers": TRIGGERS, "conditions": CONDITIONS, "actions": ACTIONS, "modes": MODES, "events": EVENTS}


def _check_list(items, kinds: dict, where: str, errors: list, depth: int) -> list:
    if depth > 12:
        errors.append(f"{where}: annidamento troppo profondo")
        return []
    if not isinstance(items, list):
        errors.append(f"{where}: serve un elenco")
        return []
    out = []
    for i, it in enumerate(items):
        place = f"{where} {i + 1}"
        if not isinstance(it, dict) or it.get("type") not in kinds:
            errors.append(f"{place}: tipo sconosciuto «{(it or {}).get('type') if isinstance(it, dict) else it}»")
            continue
        it = dict(it)
        it.setdefault("id", new_id())
        spec = kinds[it["type"]]
        for f in spec["fields"]:
            v = it.get(f["key"])
            if f.get("required") and (v is None or v == "" or v == []):
                errors.append(f"{place} ({spec['label']}): manca «{f['label']}»")
            if f["type"] == "time" and v and not re.fullmatch(r"\d{1,2}:\d{2}", str(v)) and "{{" not in str(v):
                errors.append(f"{place}: ora non valida «{v}» (usa HH:MM)")
            if f["type"] in ("conditions", "actions"):
                it[f["key"]] = _check_list(v or [], CONDITIONS if f["type"] == "conditions" else ACTIONS,
                                           f"{place} › {f['label']}", errors, depth + 1)
            if f["type"] == "branches":
                it[f["key"]] = [_check_list(b or [], ACTIONS, f"{place} › ramo {j + 1}", errors, depth + 1)
                                for j, b in enumerate(v or [])]
            if f["type"] == "options":
                it[f["key"]] = [{"conditions": _check_list((o or {}).get("conditions") or [], CONDITIONS,
                                                           f"{place} › caso {j + 1}", errors, depth + 1),
                                 "actions": _check_list((o or {}).get("actions") or [], ACTIONS,
                                                        f"{place} › caso {j + 1}", errors, depth + 1)}
                                for j, o in enumerate(v or [])]
        out.append(it)
    return out


def validate(a: dict) -> tuple[dict, list[str]]:
    errors: list[str] = []
    a = dict(a or {})
    a["name"] = str(a.get("name") or "").strip()[:120]
    if not a["name"]:
        errors.append("Serve un nome")
    a["mode"] = a.get("mode") if a.get("mode") in [m["value"] for m in MODES] else "single"
    a["max"] = max(1, min(50, int(a.get("max") or 10)))
    a["cooldown"] = max(0, int(a.get("cooldown") or 0))
    a["enabled"] = a.get("enabled", True) is not False
    a["variables"] = a.get("variables") if isinstance(a.get("variables"), dict) else {}
    a["triggers"] = _check_list(a.get("triggers") or [], TRIGGERS, "Innesco", errors, 0)
    for t in a["triggers"]:
        if t["type"] == "webhook" and not t.get("key"):
            t["key"] = uuid.uuid4().hex
    a["conditions"] = _check_list(a.get("conditions") or [], CONDITIONS, "Condizione", errors, 0)
    a["actions"] = _check_list(a.get("actions") or [], ACTIONS, "Azione", errors, 0)
    if not a["actions"]:
        errors.append("Serve almeno un'azione")
    a["tags"] = [str(t)[:30] for t in (a.get("tags") or [])][:10]
    a["description"] = str(a.get("description") or "")[:600]
    return a, errors
