TEMPLATES = [
    {
        "name": "Buonanotte",
        "description": "Dice «buonanotte»: Jarvis chiede conferma, spegne le luci, abbassa le tapparelle, attiva il silenzio e le dice cosa c'è domani.",
        "tags": ["casa", "sera"],
        "triggers": [{"type": "phrase", "phrases": ["buonanotte", "vado a dormire", "notte jarvis"], "reply": "Buonanotte, signore."}],
        "conditions": [],
        "actions": [
            {"type": "confirm", "question": "Spengo tutte le luci e chiudo le tapparelle?", "timeout": 20,
             "yes": [{"type": "ha", "service": "light.turn_off", "entity": "all"},
                     {"type": "ha", "service": "cover.close_cover", "entity": "all", "continue_on_error": True}],
             "no": [{"type": "speak", "text": "Come desidera, lascio tutto com'è."}]},
            {"type": "set", "name": "silenzio_manuale", "value": "on", "scope": "global"},
            {"type": "agent", "prompt": "Dimmi in una frase il primo impegno di domani in agenda, se c'è.", "store": "domani"},
            {"type": "speak", "text": "{{ domani }} Riposi bene, signore.", "force": True},
        ],
    },
    {
        "name": "Benvenuto a casa",
        "description": "Quando arriva dopo che non c'era nessuno: luce all'ingresso se è buio, saluto e meteo.",
        "tags": ["presenza"],
        "triggers": [{"type": "presence", "event": "somebody_home"}],
        "conditions": [{"type": "time", "after": "06:30", "before": "23:30"}],
        "cooldown": 1800,
        "actions": [
            {"type": "if", "conditions": [{"type": "sun", "when": "night"}],
             "then": [{"type": "ha", "service": "light.turn_on", "entity": "light.ingresso", "data": "{\"brightness_pct\": 60}", "continue_on_error": True}]},
            {"type": "speak", "text": "Bentornato, signore. {{ 'Ci sono ' + str(len(people())) + ' persone in casa.' if len(people()) > 1 else '' }}"},
            {"type": "widget", "widget": "weather", "ttl": 60},
        ],
    },
    {
        "name": "Luci al tramonto se c'è qualcuno",
        "description": "Al tramonto, solo se qualcuno è in casa, accende le luci del soggiorno in modo graduale.",
        "tags": ["casa", "sole"],
        "triggers": [{"type": "sun", "event": "sunset", "offset": -15}],
        "conditions": [{"type": "presence", "present": True}],
        "actions": [
            {"type": "repeat", "count": 4, "actions": [
                {"type": "ha", "service": "light.turn_on", "entity": "light.soggiorno", "data": "{\"brightness_pct\": {{ ripetizione * 25 }}}"},
                {"type": "delay", "seconds": 60}]},
        ],
    },
    {
        "name": "Finestra aperta con riscaldamento acceso",
        "description": "Se una finestra resta aperta 3 minuti mentre il riscaldamento è acceso, avvisa e, se non viene chiusa in 5 minuti, spegne il termostato.",
        "tags": ["energia", "sicurezza"],
        "triggers": [{"type": "state", "entity": "binary_sensor.finestra_soggiorno", "to": "on", "for": 180}],
        "conditions": [{"type": "state", "entity": "climate.casa", "op": "==", "value": "heat"}],
        "mode": "restart",
        "actions": [
            {"type": "notify", "title": "Finestra aperta", "text": "Signore, la finestra del soggiorno è aperta con il riscaldamento acceso.", "channels": ["display", "voice", "telegram"]},
            {"type": "wait_state", "entity": "binary_sensor.finestra_soggiorno", "to": "off", "timeout": 300},
            {"type": "if", "conditions": [{"type": "expr", "expr": "scaduto"}],
             "then": [{"type": "ha", "service": "climate.turn_off", "entity": "climate.casa"},
                      {"type": "notify", "text": "Ho spento il riscaldamento: la finestra è ancora aperta.", "channels": ["display", "telegram"]}],
             "else": [{"type": "log", "text": "Finestra chiusa in tempo"}]},
        ],
    },
    {
        "name": "Rapporto del mattino",
        "description": "Nei giorni feriali alle 7:30, appena la vede (entro un'ora e mezza) mostra il meteo e le riassume meteo e agenda.",
        "tags": ["mattina"],
        "triggers": [{"type": "time", "at": "07:30", "days": [0, 1, 2, 3, 4]}],
        "actions": [
            {"type": "wait_event", "name": "person_arrived", "timeout": 5400, "continue": False},
            {"type": "widget", "widget": "weather", "ttl": 120},
            {"type": "agent", "prompt": "Riassumi in due frasi il meteo di oggi e i miei impegni di oggi.", "store": "rapporto"},
            {"type": "speak", "text": "Buongiorno, {{ data.person }}. {{ rapporto }}"},
        ],
    },
    {
        "name": "Componente guasto",
        "description": "Quando un componente di Jarvis si guasta, avvisa su Telegram e chiede all'agente una diagnosi in sola lettura.",
        "tags": ["sistema"],
        "triggers": [{"type": "event", "name": "component_broken"}],
        "cooldown": 900,
        "mode": "queued",
        "actions": [
            {"type": "delay", "seconds": 120},
            {"type": "if", "conditions": [{"type": "expr", "expr": "state('jarvis.component.' + data.component) not in ['ok', 'idle']"}],
             "then": [{"type": "agent", "prompt": "Il componente {{ data.label }} è in stato {{ data.status }}. Diagnostica con soli comandi di lettura e rispondi in due frasi.", "store": "diagnosi"},
                      {"type": "notify", "title": "Guasto: {{ data.label }}", "text": "{{ diagnosi }}", "channels": ["telegram", "display"]}]},
        ],
    },
    {
        "name": "Notifica da webhook",
        "description": "Un altro sistema chiama l'indirizzo web dell'automazione: Jarvis mostra e legge il messaggio ricevuto.",
        "tags": ["integrazioni"],
        "triggers": [{"type": "webhook"}],
        "actions": [{"type": "notify", "title": "{{ data.title or 'Messaggio esterno' }}", "text": "{{ data.text or data }}", "channels": ["display", "voice"]}],
    },
]


def listing() -> list[dict]:
    return [{"index": i, "name": t["name"], "description": t["description"], "tags": t.get("tags", [])} for i, t in enumerate(TEMPLATES)]
