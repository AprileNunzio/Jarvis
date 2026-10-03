import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from features.presentation.application.ports import Completion, ImageFinder, ModelBuilder
from features.presentation.domain.plan import PlanError, parse_plan, side_effects
from features.presentation.domain.stage import ImageAsset, to_ui, to_widget

logger = logging.getLogger("jarvis.presentation")

IMAGE_TIMEOUT_SECONDS = 14.0
MAX_ANSWER_CHARS = 3500

SYSTEM = """Sei il regista dei contenuti di Jarvis. Hai la domanda dell'utente e la risposta già pronta; decidi tu come
mostrarla sullo schermo nel modo migliore, scegliendo forma, dimensioni e colonne. Non ripetere inutilmente: scegli le
forme che aiutano davvero a capire.

Rispondi SOLO con un JSON:
{"mode": "focus" | "face", "title": "titolo breve", "subtitle": "facoltativo", "speech": "1-2 frasi da leggere ad alta voce, senza markdown",
 "blocks": [ ... ]}

mode "face": per risposte brevi o di conversazione: niente schermo, solo la voce (blocks vuoto).
mode "widget": per ciò che si vuole avere a colpo d'occhio mentre si fa altro (un dato, un riepilogo, un promemoria,
  un elenco breve, una piccola immagine): una scheda piccola sul desktop, da 1 a 2 blocchi tra text, list, kv, image.
mode "focus": per spiegazioni, lezioni, confronti, procedure, codice, cose da vedere: schermo a pannelli.
La dimensione segue l'importanza: poco importante e breve = face, da tenere d'occhio = widget, da studiare = focus.

Blocchi (da 1 a 6; ognuno ha "type", "title" facoltativo e "span" da 3 a 12 colonne; le righe sono da 12 colonne):
- {"type":"text","body":"testo organizzato in paragrafi brevi","span":7}
- {"type":"steps","title":"Passaggi","items":["primo passo","secondo passo"]}  per procedure e lezioni in sequenza
- {"type":"list","items":["punto","punto"]}  per elenchi di punti chiave
- {"type":"table","columns":["voce","A","B"],"rows":[["..","..",".."]]}  per confronti e dati
- {"type":"kv","items":[{"k":"nome","v":"valore"}]}  per schede tecniche e definizioni
- {"type":"quote","body":"frase importante","source":"fonte"}
- {"type":"code","language":"python","content":"codice completo"}  se serve codice
- {"type":"image","query":"cosa cercare, in inglese e specifico","caption":"didascalia","cutout":false,"span":5}
  una foto o un disegno reale scaricato da fonti libere; usalo per oggetti, luoghi, esseri viventi, simboli e schemi.
  "cutout": true toglie lo sfondo, utile per oggetti isolati su sfondo chiaro.
- {"type":"model3d","subject":"nome dell'oggetto"}  ricostruzione 3D colorata e ruotabile, solo per oggetti semplici
  e solidi (componenti, utensili, mobili, solidi geometrici) che si disegnano bene con forme primitive.

Criteri:
- Metti testo e immagine in due colonne (per esempio 7 + 5) quando l'immagine chiarisce il testo.
- Un oggetto semplice da ricostruire: preferisci model3d (eventualmente con una scheda "kv"); un oggetto reale complesso: image.
- Una sequenza di operazioni: steps. Un confronto: table. Una definizione con dati: kv.
- Usa solo fatti presenti nella risposta o conoscenza sicura; non inventare numeri.
- Pochi blocchi ben scelti sono meglio di molti: niente riempitivi.
- Scrivi nella lingua dell'utente."""


@dataclass(frozen=True)
class Presentation:
    speech: str
    ui: Dict[str, Any]
    widget: Optional[Dict[str, Any]] = None


class PresentationPlanner:
    def __init__(self, complete: Completion, images: ImageFinder, models: ModelBuilder, attempts: int = 2) -> None:
        self._complete = complete
        self._images = images
        self._models = models
        self._attempts = attempts

    async def compose(self, question: str, reply: str) -> Optional[Presentation]:
        plan = await self._plan(question, reply)
        if plan is None:
            return None
        assets = await self._fetch_images(plan)
        subject = side_effects(plan)
        if subject:
            self._models.request(subject)
        if plan.mode == "widget":
            return Presentation(plan.speech, {"mode": "face"}, to_widget(plan, assets))
        return Presentation(plan.speech, to_ui(plan, assets))

    async def _plan(self, question: str, reply: str):
        request = f"Domanda dell'utente:\n{question[:600]}\n\nRisposta già pronta:\n{reply[:MAX_ANSWER_CHARS]}"
        problem = ""
        for attempt in range(1, self._attempts + 1):
            prompt = request if not problem else f"{request}\n\nIl piano precedente era invalido: {problem}\nCorreggilo."
            try:
                raw = await self._complete(SYSTEM, prompt)
                return parse_plan(raw, fallback_speech=reply)
            except (PlanError, ValueError) as exc:
                problem = str(exc)
                logger.warning("presentation plan attempt %d rejected: %s", attempt, problem)
            except Exception as exc:
                logger.warning("presentation planning unavailable: %s", exc)
                return None
        return None

    async def _fetch_images(self, plan) -> Mapping[int, ImageAsset]:
        wanted = [(i, b) for i, b in enumerate(plan.blocks) if b.type == "image"]
        if not wanted:
            return {}

        async def one(block) -> Optional[ImageAsset]:
            try:
                return await asyncio.wait_for(self._images.find(block.fields["query"], block.fields["cutout"]), IMAGE_TIMEOUT_SECONDS)
            except Exception as exc:
                logger.info("image %r not available: %s", block.fields["query"], exc)
                return None

        found: List[Optional[ImageAsset]] = await asyncio.gather(*(one(b) for _, b in wanted))
        return {index: asset for (index, _), asset in zip(wanted, found) if asset}
