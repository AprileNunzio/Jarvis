import json

import httpx

from config import DEMO
from state import store

from features.automations.bus import bus


class ActionError(RuntimeError):
    pass


def _desk():
    from features.desktop.desk import desk
    return desk


def _list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").replace("\n", ",").split(",") if v.strip()]


def _json(value) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        out = json.loads(value)
    except ValueError:
        raise ActionError("parametri JSON non validi")
    if not isinstance(out, dict):
        raise ActionError("i parametri JSON devono essere un oggetto")
    return out


def say(text: str, run, force: bool = False, icon: str = "🔊") -> str:
    if not force and bus.states.quiet():
        return "non detto: orario di silenzio"
    _desk().show("notice", {"icon": icon, "title": run.name, "text": text[:300], "announce": True, "speak": text},
                 key=f"auto:{run.id}:{len(run.trace)}", ttl=40)
    return f"detto: «{text[:120]}»"


async def ha(a: dict, run) -> str:
    service = str(a.get("service") or "")
    if "." not in service:
        raise ActionError("servizio non valido: usa dominio.servizio, es. light.turn_on")
    domain, name = service.split(".", 1)
    entities = _list(a.get("entity"))
    from features.home_assistant.home import brain
    if not DEMO and not brain.online:
        raise ActionError("Home Assistant non è collegato")
    plan = {"calls": [{"domain": domain, "service": name, "entity_ids": entities, "data": _json(a.get("data"))}]}
    try:
        from features.habits.service import habits
        habits.mark_commanded(entities if "all" not in entities else [])
    except Exception:
        pass
    result = await brain.execute(plan, f"automazione «{run.name}»", "automazione")
    if not result.get("ok"):
        raise ActionError("; ".join(result.get("errors") or ["comando non riuscito"]))
    return f"{service} su {', '.join(entities) or 'nessun dispositivo'} ({result.get('ms')} ms)"


async def speak(a: dict, run) -> str:
    return say(str(a.get("text") or ""), run, bool(a.get("force")))


async def notify(a: dict, run) -> str:
    text, title = str(a.get("text") or ""), str(a.get("title") or run.name)
    channels = a.get("channels") or ["display"]
    done = []
    if "display" in channels:
        _desk().show("notice", {"icon": "🔔", "title": title, "text": text[:400]}, key=f"auto:{run.id}:n{len(run.trace)}", ttl=120)
        done.append("display")
    if "voice" in channels:
        done.append(say(text, run))
    if "telegram" in channels:
        try:
            from features.telegram.bot import bot
            await bot.notify(f"🔔 {title}\n{text}")
            done.append("telegram")
        except Exception as exc:
            done.append(f"telegram non riuscito: {exc}")
    if "email" in channels:
        to = _list(a.get("to"))
        if not to:
            raise ActionError("manca il destinatario dell'email")
        from features.agent.mailer import send
        done.append(await send(to, title, text, []))
    return "; ".join(done)


async def widget(a: dict, run) -> str:
    wid = str(a.get("widget") or "")
    desk = _desk()
    if wid not in desk.widgets:
        raise ActionError(f"widget sconosciuto «{wid}»")
    ttl = float(a["ttl"]) if a.get("ttl") else None
    desk.show(wid, _json(a.get("data")), key=f"auto:{run.automation}:{wid}", ttl=ttl)
    return f"widget {wid} mostrato"


async def holo(a: dict, run) -> str:
    action = {k: a[k] for k in ("express", "play", "tint") if a.get(k)}
    if a.get("accessory"):
        action["accessory"] = {"name": a["accessory"], "state": True}
    if not action:
        return "niente da fare"
    store.holo_action = action
    store.version += 1
    return "ologramma: " + ", ".join(action)


async def sound(a: dict, run) -> str:
    try:
        from features.sounds.policy import policy
    except ImportError:
        raise ActionError("suoni non disponibili")
    return policy.play(str(a.get("name") or ""), bool(a.get("force")), reason=f"automazione «{run.name}»")


async def agent(a: dict, run) -> str:
    from features.agent.agent import agent as jarvis_agent
    steps: list[dict] = []
    result = await jarvis_agent.run(str(a.get("prompt") or ""), steps, auto=f"Automazione: {run.name}",
                                    trusted=bool(a.get("trusted")))
    if a.get("store"):
        run.vars[str(a["store"])] = result
    return result[:400]


async def email(a: dict, run) -> str:
    from features.agent.mailer import send
    from features.agent.paths import resolve
    files = []
    for p in _list(a.get("attachments")):
        path = resolve(p)
        if not path.exists():
            raise ActionError(f"allegato non trovato: {p}")
        files.append(path)
    return await send(_list(a.get("to")), str(a.get("subject") or run.name), str(a.get("body") or ""), files)


async def http(a: dict, run) -> str:
    method, url = str(a.get("method") or "GET").upper(), str(a.get("url") or "")
    if not url.startswith(("http://", "https://")):
        raise ActionError("indirizzo non valido")
    body = _json(a.get("body")) if a.get("body") else None
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        r = await client.request(method, url, json=body)
    try:
        payload = r.json()
    except ValueError:
        payload = r.text[:4000]
    if a.get("store"):
        run.vars[str(a["store"])] = payload
    if r.status_code >= 400:
        raise ActionError(f"risposta {r.status_code}")
    return f"{method} {url} → {r.status_code}"


async def event(a: dict, run) -> str:
    bus.emit(str(a.get("name") or "custom"), {**_json(a.get("data")), "from_automation": run.automation})
    return f"evento {a.get('name')} generato"


async def log(a: dict, run) -> str:
    text = str(a.get("text") or "")
    store.event("INFO", f"Automazione «{run.name}»: {text[:300]}", "automazioni")
    return text[:200]


LEAF = {"ha": ha, "speak": speak, "notify": notify, "widget": widget, "holo": holo, "sound": sound, "agent": agent,
        "email": email, "http": http, "event": event, "log": log}
