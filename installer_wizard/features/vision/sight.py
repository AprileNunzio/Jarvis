import re

from state import store

from features.brain import sight as seeing
from features.brain.llm import BrainUnavailable
from features.vision import repair, stills
from features.vision.proxy import frame

HELD = re.compile(r"\bcosa (?:ho|tengo|sto tenendo) in mano\b|\b(?:che )?cos'?è quest[oa]\b|\bche (?:oggetto|cosa) è\b"
                  r"|\briconosci (?:quest[oa]|l'oggetto|quest'oggetto)\b|\bcosa ti (?:sto )?mostr|\bguarda quest[oa]\b", re.I)
READ = re.compile(r"\bleggi(?:mi)? (?:cosa c'è scritto|il testo|l'etichetta|questo foglio|questa etichetta|questo)\b"
                  r"|\bcosa c'è scritto\b", re.I)
SCENE = re.compile(r"\bdescrivi (?:la stanza|la scena|cosa vedi|quello che vedi)\b|\bcosa c'è (?:intorno|nella stanza)\b"
                   r"|\bcosa vedi\b", re.I)
NEED_BRAIN = ("Per riconoscere qualsiasi oggetto mi serve un cervello che vede le immagini: aggiungi nel Cervello "
              "un servizio cloud come GPT-4o, Claude o Gemini, oppure un modello locale come llava.")
HELD_PROMPT = (
    "Guarda la foto della webcam. Identifica l'oggetto che la persona tiene in mano o mostra alla camera (se nessuno, "
    "l'oggetto più in primo piano). Rispondi SOLO con JSON: {\"object\": nome breve in italiano, "
    "\"description\": una o due frasi naturali da leggere ad alta voce, \"details\": [massimo 5 fatti utili, "
    "es. marca, modello, valori nutrizionali, istruzioni d'uso, avvertenze], \"box\": [x, y, larghezza, altezza] "
    "normalizzati tra 0 e 1 dell'oggetto, \"kind\": uno tra food, book, device, medicine, plant, product, "
    "document, tool, other}.")
READ_PROMPT = ("Leggi e trascrivi fedelmente il testo visibile nell'immagine (etichetta, foglio, schermo). Rispondi "
               "SOLO con JSON: {\"text\": testo trascritto, \"summary\": riassunto in una frase, \"box\": [x, y, larghezza, "
               "altezza] normalizzati della zona di testo}.")
SCENE_PROMPT = ("Descrivi in italiano, in due o tre frasi, cosa si vede nella foto della webcam: persone (senza "
                "ipotizzare identità), oggetti principali e ambiente. Rispondi SOLO con JSON: {\"description\": testo, "
                "\"objects\": [{\"label\": nome, \"box\": [x, y, larghezza, altezza] normalizzati}]}.")


def _local_objects() -> list[dict]:
    return [o for o in store.presence.get("objects", []) if not o.get("scenery")]


def annotated(sid: str, title: str, boxes: list[dict], caption: str = "") -> dict:
    return {"type": "annotated", "title": title, "src": stills.url(sid), "boxes": boxes, "caption": caption}


def _local_held() -> tuple[list[str], dict]:
    objects = _local_objects()
    held = [o for o in objects if o.get("held")] or objects
    if not held:
        raise LookupError
    names = list(dict.fromkeys(o["label"] for o in held))
    boxes = [{"box": stills.pixel_box(o["box"]), "label": o["label"], "tone": "ok"} for o in held[:5]]
    return names, {"boxes": [b for b in boxes if b["box"]]}


async def _still() -> tuple[bytes, str]:
    jpeg = await frame()
    if not jpeg:
        raise ValueError("La webcam non è disponibile in questo momento.")
    return jpeg, stills.keep(jpeg)


async def held(text: str) -> tuple[str, dict]:
    jpeg, sid = await _still()
    try:
        data, model = await seeing.look(jpeg, HELD_PROMPT, as_json=True, max_tokens=600)
    except BrainUnavailable:
        try:
            names, extra = _local_held()
        except LookupError:
            return f"Non riesco a riconoscerlo con i miei occhi locali. {NEED_BRAIN}", {"mode": "face"}
        speech = f"Mi sembra {' e '.join(names[:3])}. Per dettagli più precisi: {NEED_BRAIN}"
        return speech, {"mode": "focus", "title": "Cosa ha in mano", "subtitle": "Riconoscimento locale",
                        "panels": [annotated(sid, "Webcam", extra["boxes"], ", ".join(names))]}
    name = str(data.get("object") or "oggetto")[:60]
    box = stills.norm_box(data.get("box") or [])
    details = [str(d)[:160] for d in (data.get("details") or [])][:5]
    panels = [annotated(sid, "Webcam", [{"box": box, "label": name, "tone": "ok"}] if box else [], name)]
    if details:
        panels.append({"type": "list", "title": "Informazioni utili",
                       "items": [{"label": d, "value": "", "status": ""} for d in details]})
    return (str(data.get("description") or f"È {name}.")[:500],
            {"mode": "focus", "title": name.capitalize(), "subtitle": f"Riconosciuto con {model}", "panels": panels})


async def read(text: str) -> tuple[str, dict]:
    jpeg, sid = await _still()
    try:
        data, model = await seeing.look(jpeg, READ_PROMPT, as_json=True, max_tokens=1200)
    except BrainUnavailable:
        return f"Per leggere testi dalla webcam: {NEED_BRAIN}", {"mode": "face"}
    body = str(data.get("text") or "").strip()[:3000]
    if not body:
        return "Non vedo testo leggibile: avvicinalo alla webcam e tienilo fermo.", {"mode": "face"}
    box = stills.norm_box(data.get("box") or [])
    return body[:600], {"mode": "focus", "title": "Testo letto", "subtitle": f"Letto con {model}",
                        "panels": [annotated(sid, "Webcam", [{"box": box, "label": "testo", "tone": "info"}] if box else []),
                                   {"type": "text", "title": str(data.get("summary") or "Trascrizione")[:120], "body": body}]}


async def scene(text: str) -> tuple[str, dict]:
    jpeg, sid = await _still()
    try:
        data, model = await seeing.look(jpeg, SCENE_PROMPT, as_json=True, max_tokens=700)
    except BrainUnavailable:
        raise LookupError
    boxes = [{"box": stills.norm_box(o.get("box") or []), "label": str(o.get("label", ""))[:40], "tone": "info"}
             for o in (data.get("objects") or [])[:8] if isinstance(o, dict)]
    people_line = (store.presence or {}).get("summary", "")
    speech = (people_line + " " if people_line and "non vedo" not in people_line.lower() else "") + str(data.get("description", ""))
    return speech.strip()[:600], {"mode": "focus", "title": "Cosa vedo", "subtitle": f"Analizzato con {model}",
                                  "panels": [annotated(sid, "Webcam", [b for b in boxes if b["box"]])]}


async def answer(text: str) -> tuple[str, dict]:
    if repair.wants(text):
        return await repair.step(text)
    if READ.search(text):
        return await read(text)
    if HELD.search(text):
        return await held(text)
    if SCENE.search(text):
        return await scene(text)
    raise LookupError
