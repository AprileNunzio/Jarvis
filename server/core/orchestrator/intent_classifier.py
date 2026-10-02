import json
import logging
from typing import Tuple, Dict
from server.features.llm_gateway.gateway import llm_gateway
from server.features.llm_gateway.contracts import LLMRequest, LLMMessage

logger = logging.getLogger("jarvis.intent_classifier")

INTENT_CATALOG: Dict[str, str] = {
    "HOME_AUTOMATION": "Controllo luci, termostati, serrature, porte, prese smart, scene domotiche, climatizzazione",
    "VISION_SURVEILLANCE": "Telecamere, rilevamento intrusi, cancelli, garage, sorveglianza, persone, veicoli",
    "AUTONOMOUS_PROGRAMMING": "Scrivere codice, creare script, correggere bug, refactoring, generare funzioni",
    "SYSOPS_AUTOMATION": "Gestione server, SSH, servizi systemd, backup, database, rete, DNS, firewall, Docker",
    "GENERAL_INTELLIGENCE": "Domande generiche, conversazione, ragionamento, ricerca informazioni",
}

_SYSTEM_PROMPT_TEMPLATE: str = (
    "Sei il classificatore di intenti di Jarvis, un orchestratore cognitivo autonomo.\n"
    "Analizza la richiesta dell'utente e rispondi con un singolo oggetto JSON valido.\n"
    "Schema obbligatorio:\n"
    '  {{"intent": "<INTENT_NAME>", "confidence": <float 0.0-1.0>, "reasoning": "<breve motivazione>"}}\n\n'
    "Intenti disponibili:\n{catalog}\n\n"
    "Regole:\n"
    "- Scegli l'intent che meglio corrisponde alla richiesta, anche se espressa in modo informale.\n"
    "- Se la richiesta è ambigua, scegli quello più probabile e abbassa la confidence.\n"
    "- Rispondi ESCLUSIVAMENTE con il JSON, nessun altro testo."
)


class LLMIntentClassifier:

    def __init__(self, model_name: str = "qwen2.5:7b") -> None:
        self._model = model_name
        self._system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            catalog="\n".join(f"- {k}: {v}" for k, v in INTENT_CATALOG.items())
        )

    async def classify(self, user_query: str) -> Tuple[str, float]:
        try:
            response = await llm_gateway.generate_completion(
                LLMRequest(
                    model_name=self._model,
                    messages=[LLMMessage(role="user", content=user_query)],
                    system_prompt=self._system_prompt,
                    temperature=0.05,
                    max_tokens=200,
                )
            )
            result = json.loads(self._extract_json(response.content))
            intent = result.get("intent", "GENERAL_INTELLIGENCE")
            confidence = float(result.get("confidence", 0.5))
            if intent not in INTENT_CATALOG:
                logger.warning("LLM returned unknown intent '%s', falling back", intent)
                return self._keyword_fallback(user_query), 0.4
            logger.info("Intent classified: %s (%.2f) — %s", intent, confidence, result.get("reasoning", ""))
            return intent, confidence
        except Exception as exc:
            logger.warning("LLM intent classification failed (%s), using keyword fallback", exc)
            return self._keyword_fallback(user_query), 0.5

    @staticmethod
    def _extract_json(raw: str) -> str:
        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return raw[start : end + 1]
        return raw

    @staticmethod
    def _keyword_fallback(text: str) -> str:
        lowered = text.lower()
        if any(w in lowered for w in ["luce", "luci", "spegni", "accendi", "temperatura", "termostato", "porta"]):
            return "HOME_AUTOMATION"
        if any(w in lowered for w in ["telecamera", "telecamere", "chi c'è", "intruso", "cancello", "garage"]):
            return "VISION_SURVEILLANCE"
        if any(w in lowered for w in ["scrivi codice", "programma", "crea script", "fixa", "correggi errore"]):
            return "AUTONOMOUS_PROGRAMMING"
        if any(w in lowered for w in ["server", "ssh", "backup", "database", "servizio", "docker"]):
            return "SYSOPS_AUTOMATION"
        return "GENERAL_INTELLIGENCE"


intent_classifier = LLMIntentClassifier()
