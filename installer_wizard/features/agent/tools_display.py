import time

from state import store

from features.agent.registry import tool
from features.desktop.desk import desk
from features.desktop.screens import screens
from features.models3d import generator, library

AVATAR = {
    "azioni": ["saluto", "annuisce", "disaccordo", "inchino", "cappello", "togli_cappello", "ascolto", "pensa",
               "balla", "canta"],
    "micro": ["blink", "microsorriso", "sopracciglio", "sussulto", "annuisce_lieve"],
    "espressioni": ["neutral", "smile", "sad", "cry", "surprise", "disagree", "angry", "doubt", "think"],
    "inquadrature": ["intera", "mezzo", "primo_piano"],
    "accessori": ["hat", "glasses", "headphones"],
}


def _holo(**action) -> None:
    store.holo_action = {k: v for k, v in action.items() if v not in (None, "")}
    store.version += 1
    store.touch()


@tool("list_widgets", "elenca i widget disponibili e quelli aperti con lo schermo su cui stanno", {})
async def list_widgets() -> str:
    active = {i["id"]: i for i in desk.active()}
    rows = [f"- {m['id']}: {m['name']}{' [aperto, schermo ' + str(active[m['id']].get('screen')) + ']' if m['id'] in active else ''}"
            for m in desk.widgets.values()]
    return f"schermi collegati: {screens.numbers()}\n" + "\n".join(rows)


@tool("show_widget", "apre un widget sul display (data = dati del widget in JSON)",
      {"id": "id del widget", "data": "oggetto JSON", "seconds": "durata (0 = finché non lo chiudo)"})
async def show_widget(id: str, data: dict | None = None, seconds: float = 300) -> str:
    if id not in desk.widgets:
        raise ValueError(f"widget sconosciuto: {id}")
    desk.show(id, data if isinstance(data, dict) else {}, key=f"agent:{id}", ttl=float(seconds) or None)
    return f"widget {id} aperto"


@tool("hide_widget", "chiude un widget", {"id": "id del widget"})
async def hide_widget(id: str) -> str:
    desk.hide(id)
    return f"widget {id} chiuso"


@tool("move_widget", "sposta un widget su un altro schermo (screen = numero, null = automatico)",
      {"id": "id del widget", "screen": "numero schermo"})
async def move_widget(id: str, screen=None) -> str:
    desk.set_screen(id, None if screen in (None, "", "null") else int(screen))
    return f"widget {id} assegnato allo schermo {screen}"


@tool("avatar", "comanda l'ologramma 3D: action (macro o micro), express (emozione), shot (inquadratura), "
      "accessory + state (true/false), color (#rrggbb)",
      {"action": "es. saluto", "express": "es. smile", "shot": "es. primo_piano", "accessory": "hat|glasses|headphones",
       "state": "true/false", "color": "#rrggbb"})
async def avatar(action: str = "", express: str = "", shot: str = "", accessory: str = "", state=True, color: str = "") -> str:
    _holo(play=action, express=express, shot=shot,
          accessory={"name": accessory, "state": str(state).lower() != "false"} if accessory else None,
          tint=color)
    return "ologramma aggiornato"


@tool("avatar_catalog", "elenca azioni, espressioni, inquadrature e accessori dell'ologramma", {})
async def avatar_catalog() -> str:
    return "\n".join(f"{k}: {', '.join(v)}" for k, v in AVATAR.items())


@tool("create_3d", "progetta un oggetto 3D e lo mostra; restituisce la cartella con GLB, STL e OBJ",
      {"subject": "oggetto da modellare"})
async def create_3d(subject: str) -> str:
    meta = await generator.create(subject)
    library.show(meta, f"Ecco {meta['title']} in 3D.")
    folder = library.folder(meta["id"])
    return f"modello «{meta['title']}» creato in {folder}: " + ", ".join(str(folder / f['name']) for f in meta["files"])


@tool("list_models", "elenca i modelli 3D salvati con la loro cartella", {})
async def list_models() -> str:
    rows = [f"- {m['title']} ({m['id']}): {library.folder(m['id'])}" for m in library.listing()[:30]]
    return "\n".join(rows) or "nessun modello"


@tool("show_model", "mostra un modello 3D salvato", {"name": "nome o id del modello"})
async def show_model(name: str) -> str:
    try:
        meta = library.get(name)
    except KeyError:
        meta = library.find(name)
    if not meta:
        raise ValueError("modello non trovato")
    library.show(meta)
    return f"mostro {meta['title']}"


@tool("now", "data e ora attuali", {})
async def now() -> str:
    return time.strftime("%A %d/%m/%Y %H:%M")
