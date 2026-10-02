import re
import time

from state import store

from features.brain import sight as seeing
from features.brain.llm import BrainUnavailable
from features.vision import stills
from features.vision.proxy import frame

SESSION_SECONDS = 20 * 60
HISTORY = 8
START = re.compile(r"\b(?:aiutami|mi aiuti|aiutarmi|guidami|devo|voglio|come (?:faccio|posso))\b.{0,30}\b(?:ripar|aggiust|sistem|"
                   r"sald|dissald|sostitu|diagnostic)\w*|\b(?:riparazione|saldatura) guidata\b|\bmodalità (?:riparazione|"
                   r"tecnico|laboratorio)\b", re.I)
STOP = re.compile(r"\b(?:fine|termina|chiudi|basta|esci dalla)\b.{0,15}\b(?:riparazione|laboratorio|modalità tecnico)\b"
                  r"|\bho finito (?:la riparazione|di riparare)\b", re.I)
CONTINUE = re.compile(r"\b(?:e adesso|e ora|poi|prossimo passo|passo successivo|fatto|ho fatto|così|va bene così|guarda|"
                      r"controlla|questo|questa|qui|dove|quale|quanto|come|perché|salda|saldo|stagno|flussante|punta|"
                      r"componente|condensatore|resistenza|resistore|diodo|transistor|mosfet|integrato|chip|pista|piazzola|"
                      r"connettore|fusibile|tensione|multimetro|misur|ohm|volt|ampere|corto|bruciat|gonfi|ossidat)\w*", re.I)
SYSTEM = (
    "Sei il tecnico elettronico di Jarvis e guidi una riparazione in tempo reale tramite la webcam. Sei preciso, "
    "prudente e pratico: identifichi componenti (sigla, valore, codici colore, marcature), difetti visibili "
    "(condensatori gonfi, saldature fredde, piste bruciate, ossidazione, ponticelli di stagno) e dai un passo alla "
    "volta. Se l'immagine non basta, chiedi di avvicinare, ruotare o illuminare. Metti sempre la sicurezza al primo "
    "posto (scollegare l'alimentazione, scaricare i condensatori, ventilazione per i fumi). Rispondi in italiano."
)
FORMAT = (
    "Rispondi SOLO con JSON: {\"summary\": due frasi da leggere ad alta voce con il prossimo passo concreto, "
    "\"board\": che scheda o dispositivo sembra, \"component\": componente su cui intervenire, \"designator\": sigla "
    "stampata (es. C12) o stringa vuota, \"box\": [x, y, larghezza, altezza] normalizzati tra 0 e 1 del componente "
    "da evidenziare, \"problem\": difetto visto o sospettato, \"steps\": [passi numerati brevi], \"tools\": [attrezzi], "
    "\"safety\": [avvertenze], \"values\": {grandezza: valore atteso}, \"confidence\": numero tra 0 e 1, "
    "\"need\": cosa serve per vedere meglio o stringa vuota}."
)


class RepairSession:

    def __init__(self) -> None:
        self.history: list[dict] = []
        self.until = 0.0
        self.board = ""

    @property
    def active(self) -> bool:
        return time.time() < self.until

    def open(self) -> None:
        if not self.active:
            self.history, self.board = [], ""
        self.until = time.time() + SESSION_SECONDS

    def close(self) -> None:
        self.until = 0.0
        self.history = []

    def remember(self, question: str, summary: str) -> None:
        self.history += [{"role": "user", "content": question}, {"role": "assistant", "content": summary}]
        self.history = self.history[-HISTORY:]


session = RepairSession()


def wants(text: str) -> bool:
    return bool(START.search(text) or STOP.search(text) and session.active or session.active and CONTINUE.search(text))


def _panels(sid: str, data: dict) -> list[dict]:
    box = stills.norm_box(data.get("box") or [])
    label = " ".join(x for x in (str(data.get("designator") or ""), str(data.get("component") or "")) if x).strip()
    panels = [{"type": "annotated", "title": str(data.get("board") or "Scheda")[:80], "src": stills.url(sid),
               "boxes": [{"box": box, "label": label or "qui", "tone": "target"}] if box else [],
               "caption": str(data.get("problem") or "")[:200]}]
    steps = [str(s)[:200] for s in (data.get("steps") or [])][:8]
    if steps:
        panels.append({"type": "steps", "title": "Procedura", "items": steps})
    values = data.get("values") if isinstance(data.get("values"), dict) else {}
    if values:
        panels.append({"type": "kv", "title": "Valori attesi", "data": {str(k)[:40]: str(v)[:60] for k, v in list(values.items())[:8]}})
    tools = [str(t)[:50] for t in (data.get("tools") or [])][:10]
    if tools:
        panels.append({"type": "chips", "title": "Attrezzi", "items": tools})
    safety = [str(t)[:160] for t in (data.get("safety") or [])][:5]
    if safety:
        panels.append({"type": "warn", "title": "Sicurezza", "items": safety})
    return panels


async def step(text: str) -> tuple[str, dict]:
    if STOP.search(text) and session.active:
        session.close()
        return "Riparazione chiusa. Ricordati di ricontrollare le saldature prima di ridare corrente.", {"mode": "face"}
    session.open()
    jpeg = await frame()
    if not jpeg:
        return "La webcam non è disponibile: collegala e inquadra la scheda.", {"mode": "face"}
    sid = stills.keep(jpeg)
    prompt = f"Richiesta dell'utente: «{text}»." + (f" Stiamo lavorando su: {session.board}." if session.board else "")
    try:
        data, model = await seeing.look(jpeg, prompt + "\n" + FORMAT, system=SYSTEM, as_json=True, max_tokens=1400,
                                        history=session.history)
    except BrainUnavailable:
        session.close()
        return ("Per guidarti nella riparazione devo poter vedere la scheda: aggiungi nel Cervello un servizio con "
                "visione, come GPT-4o, Claude o Gemini, e riprova."), {"mode": "face"}
    if not isinstance(data, dict):
        raise ValueError("risposta del modello non valida")
    session.board = str(data.get("board") or session.board)[:120]
    summary = str(data.get("summary") or "Ecco cosa vedo.")[:600]
    if data.get("need"):
        summary += f" {str(data['need'])[:200]}"
    session.remember(text, summary)
    store.event("INFO", f"Riparazione guidata: {data.get('component', '')} {data.get('problem', '')}"[:200], "vision")
    confidence = data.get("confidence")
    subtitle = f"Tecnico: {model}" + (f" · affidabilità {float(confidence) * 100:.0f}%"
                                      if isinstance(confidence, (int, float)) else "")
    return summary, {"mode": "focus", "title": "Riparazione guidata", "subtitle": subtitle, "panels": _panels(sid, data)}
