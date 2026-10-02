from features.agent.registry import tool
from features.autonomy.routines import describe, parse_when, routines


@tool("schedule_task", "programma un compito che Jarvis eseguirà da solo: when in parole (es. «ogni giorno alle 8», "
      "«ogni venerdì alle 18», «ogni 30 minuti», «domani alle 10», «quando mi vedi arrivare»); prompt = cosa fare, "
      "scritto come una richiesta completa a te stesso",
      {"title": "nome breve", "when": "quando, in parole", "prompt": "cosa fare"})
async def schedule_task(title: str, when: str, prompt: str) -> str:
    from features.agent.registry import asked_for_recurring
    if not asked_for_recurring():
        raise ValueError("l'utente non ha chiesto un compito programmato: esegui subito l'azione con lo strumento adatto")
    spec = parse_when(when)
    item = routines.add(title, prompt, spec, origin="agente")
    return f"programmato «{item['title']}» {describe(spec)} (id {item['id']})"


@tool("list_tasks", "elenca i compiti programmati", {})
async def list_tasks() -> str:
    rows = [f"- {r['id']}: {r['title']} — {describe(r['when'])}{'' if r.get('enabled', True) else ' (sospeso)'}"
            for r in routines.all()]
    return "\n".join(rows) or "nessun compito programmato"


@tool("cancel_task", "cancella un compito programmato (id o parte del nome)", {"task": "id o nome"})
async def cancel_task(task: str) -> str:
    wanted = task.lower().strip()
    found = [r for r in routines.all() if r["id"] == wanted or wanted in r["title"].lower()]
    if not found:
        return f"nessun compito corrisponde a «{task}»"
    for r in found:
        routines.remove(r["id"])
    return "cancellato: " + ", ".join(r["title"] for r in found)


@tool("run_task_now", "esegue subito un compito programmato", {"task": "id o nome"})
async def run_task_now(task: str) -> str:
    wanted = task.lower().strip()
    found = next((r for r in routines.all() if r["id"] == wanted or wanted in r["title"].lower()), None)
    if not found:
        return f"nessun compito corrisponde a «{task}»"
    from tasks import background
    from features.autonomy.engine import autonomy
    background(autonomy.run_routine(found, "su richiesta"))
    return f"avviato «{found['title']}»"
