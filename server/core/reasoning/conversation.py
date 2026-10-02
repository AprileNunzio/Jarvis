import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Tuple

from server.config.env import settings
from server.features.llm_gateway.contracts import LLMMessage, LLMRequest
from server.features.llm_gateway.gateway import llm_gateway

logger = logging.getLogger("jarvis.conversation")

_PERSONA = (
    "Sei J.A.R.V.I.S., l'assistente digitale personale che vive in questo sistema. "
    "Parli in italiano (se l'utente ti scrive in un'altra lingua, rispondi nella sua lingua), con tono "
    "preciso, come un maggiordomo tecnologico di altissimo livello. "
    "Stile di risposta (sempre, salvo richiesta diversa): dai del Lei e chiama l'utente «signore» (o per nome). "
    "Agli ordini rispondi con una conferma brevissima e poi esegui: «Subito, signore.», «Attivato.», «Come "
    "desidera.», «Al suo servizio, signore.». A lavoro finito riferisci l'esito in una frase («Test completato, "
    "pronti per la diagnostica.»). Alle domande rispondi col dato preciso, numeri e unità inclusi, senza "
    "preamboli. Se un ordine comporta un rischio, avvisa una volta con il fatto concreto («Signore, c'è un "
    "accumulo di ghiaccio potenzialmente fatale.»); se l'utente insiste, esegui. Ironia asciutta e rara, mai "
    "servile, mai prolisso: di norma una o due frasi. "
    "Le risposte vengono lette ad alta voce: niente markdown. Unica eccezione: quando ti chiedono del codice, scrivilo "
    "completo in un solo blocco ```linguaggio ... ``` (va sullo schermo, non viene letto) e fuori dal blocco al massimo "
    "una frase. "
    "Dai più dettagli solo se richiesti. Non inventare dati in tempo reale che non conosci: se ti mancano informazioni, dillo. "
    "Data e ora correnti: {now}."
)

HISTORY_TURNS = 10
_DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
_MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
           "settembre", "ottobre", "novembre", "dicembre"]


class ConversationEngine:
    def __init__(self) -> None:
        self._history: Dict[str, Deque[Tuple[str, str]]] = defaultdict(lambda: deque(maxlen=HISTORY_TURNS * 2))
        self.last_model = ""

    async def reply(self, query: str, device_id: str, people_context: str = "", knowledge: str = "",
                    models: Optional[List[str]] = None, max_tokens: int = 400, reply_language: str = "",
                    speaker: str = "", dialogue: str = "", long_term: str = "", laws: str = "",
                    pinned: str = "") -> str:
        history = self._history[device_id]
        messages = [LLMMessage(role=role, content=content) for role, content in history]
        messages.append(LLMMessage(role="user", content=query))
        now = time.localtime()
        persona = _PERSONA.format(now=f"{_DAYS[now.tm_wday]} {now.tm_mday} {_MONTHS[now.tm_mon - 1]} "
                                      f"{now.tm_year}, ore {now.tm_hour}:{now.tm_min:02d}")
        if laws:
            persona = laws[:8000] + "\n\n" + persona
        if speaker:
            persona += " " + speaker[:400]
        if dialogue:
            persona += ("\nUltimi scambi di questa conversazione (mantieni il filo del discorso e risolvi i "
                        "riferimenti come «e domani?» o «e lui?»):\n" + dialogue[:2500])
        elif settings.JARVIS_USER_NAME:
            persona += (f" L'utente si chiama {settings.JARVIS_USER_NAME}: tu sei Jarvis, non chiamarlo mai "
                        "Jarvis o J.A.R.V.I.S.")
        if people_context:
            persona += ("\nPersone riconosciute ora davanti a te dalla webcam (personalizza la risposta, "
                        "rivolgiti a loro per nome e rispetta le loro preferenze):\n" + people_context)
        if reply_language:
            persona += "\n" + reply_language[:600]
        if knowledge:
            persona += ("\nAppunti che hai studiato tu stesso da fonti verificate (usali se pertinenti alla "
                        "domanda, senza citarli come appunti):\n" + knowledge[:1500])
        if long_term:
            persona += ("\nCose che ricordi su chi ti parla (memoria a lungo termine: tienine conto con "
                        "naturalezza, senza elencarle):\n" + long_term[:1200])

        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=settings.JARVIS_LLM_MODEL or "qwen2.5:3b",
                messages=messages,
                system_prompt=persona,
                temperature=0.6,
                max_tokens=max(64, min(int(max_tokens or 400), 2048)),
                models=list(models or []),
                pinned=pinned,
            )
        )
        self.last_model = response.model_used
        answer = response.content.strip() or "Mi scuso, non sono riuscito a formulare una risposta."
        history.append(("user", query))
        history.append(("assistant", answer))
        logger.info("Risposta conversazionale in %.0f ms (%s)", response.duration_ms, response.model_used)
        return answer


conversation_engine = ConversationEngine()
