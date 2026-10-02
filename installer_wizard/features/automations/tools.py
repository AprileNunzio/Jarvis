import json

from features.agent.registry import tool
from features.automations.bus import bus
from features.automations.engine import engine
from features.automations.library import InvalidAutomation, library


@tool("create_automation", "crea un'automazione complessa (inneschi, condizioni, azioni a più stadi) descritta a parole; "
      "resta disattivata finché l'utente non la attiva", {"description": "cosa deve fare, quando e a quali condizioni"})
async def create_automation(description: str) -> str:
    from features.automations.builder import build
    spec, errors = await build(description)
    if errors:
        return "non valida: " + "; ".join(errors[:4])
    spec["enabled"] = False
    try:
        a = library.add(spec, origin="agente")
    except InvalidAutomation as exc:
        return "non valida: " + "; ".join(exc.errors[:4])
    return f"creata «{a['name']}» (id {a['id']}, disattivata): " + json.dumps(a["triggers"], ensure_ascii=False)[:300]


@tool("list_automations", "elenca le automazioni con stato e ultima esecuzione", {})
async def list_automations() -> str:
    rows = [f"- {a['id']}: {a['name']} [{'attiva' if a.get('enabled', True) else 'disattivata'}] "
            f"esecuzioni {a.get('runs', 0)}, ultima: {a.get('last_status') or 'mai'}" for a in library.all()]
    return "\n".join(rows) or "nessuna automazione"


@tool("run_automation", "esegue subito un'automazione (id o nome)", {"automation": "id o nome"})
async def run_automation(automation: str) -> str:
    try:
        return await engine.start_by_ref(automation, {"type": "manual", "label": "dall'agente"})
    except KeyError:
        return f"nessuna automazione «{automation}»"


@tool("toggle_automation", "attiva o disattiva un'automazione", {"automation": "id o nome", "enabled": "true o false"})
async def toggle_automation(automation: str, enabled="true") -> str:
    try:
        return engine.set_enabled(automation, str(enabled).lower() in ("true", "1", "sì", "si", "on"))
    except KeyError:
        return f"nessuna automazione «{automation}»"


@tool("emit_event", "genera un evento personalizzato che può avviare automazioni", {"name": "nome evento", "data": "dati JSON opzionali"})
async def emit_event(name: str, data="") -> str:
    try:
        payload = json.loads(data) if isinstance(data, str) and data.strip() else (data or {})
    except ValueError:
        payload = {"text": data}
    bus.emit(name, payload if isinstance(payload, dict) else {"value": payload})
    return f"evento {name} generato"
