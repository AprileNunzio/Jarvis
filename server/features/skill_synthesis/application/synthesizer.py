import ast
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from server.features.sandbox.domain.spec import Language
from server.features.skill_synthesis.application.ports import ApprovalPort, ToolStore
from server.features.skill_synthesis.application.runner import INPUT_FILE, DynamicToolRunner, ToolRun
from server.features.skill_synthesis.domain.tool import DynamicTool, ToolError

logger = logging.getLogger("jarvis.skill_synthesis")

Completion = Callable[[str, str], Awaitable[str]]

SYSTEM = f"""Sei il fabbricante di strumenti di Jarvis. Scrivi un piccolo script (python o bash) che svolge esattamente
il compito richiesto e lo restituisce come dato strutturato. Contratto obbligatorio dello script:
- legge i parametri dal file JSON /in/{INPUT_FILE} (python: json.load(open("/in/{INPUT_FILE}")); bash: jq non c'è, usa python)
- stampa come ULTIMA riga su stdout un solo oggetto JSON con il risultato (campo "summary" con una frase leggibile)
- può scrivere file solo in /out; usa solo la libreria standard (python: urllib.request per HTTP) senza installare nulla
- se serve internet, dichiara in egress_hosts i nomi host esatti (es. api.open-meteo.com) o *.dominio; nessun altro host
  sarà raggiungibile e non esistono indirizzi IP, localhost o reti private
- niente commenti superflui, nessuna credenziale scritta nel codice
Rispondi SOLO con un oggetto JSON: {{"name": "snake_case", "description": "frase che dice cosa fa lo strumento",
"language": "python" oppure "bash", "parameters": ["nomi dei parametri letti da input.json"],
"egress_hosts": [], "test_input": {{valori realistici dei parametri per questo compito}}, "source": "codice"}}."""


@dataclass(frozen=True)
class SynthesisOutcome:
    ok: bool
    tool: Optional[DynamicTool]
    run: Optional[ToolRun]
    attempts: int
    message: str


class ToolSynthesizer:
    def __init__(
        self,
        complete: Completion,
        runner: DynamicToolRunner,
        store: ToolStore,
        approval: ApprovalPort,
        max_attempts: int = 3,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._complete = complete
        self._runner = runner
        self._store = store
        self._approval = approval
        self._max_attempts = max_attempts
        self._clock = clock

    async def synthesize(self, goal: str, context: Optional[Dict[str, Any]] = None) -> SynthesisOutcome:
        problem, previous = "", ""
        for attempt in range(1, self._max_attempts + 1):
            raw = await self._complete(SYSTEM, self._request(goal, context or {}, problem, previous))
            try:
                tool = self._parse(raw)
                self._static_check(tool)
            except (ToolError, ValueError) as exc:
                problem = f"lo strumento è invalido: {exc}"
                logger.warning("tool attempt %d invalid: %s", attempt, exc)
                continue
            if tool.egress_hosts:
                approved, reason = await self._approval.approve(tool)
                if not approved:
                    return SynthesisOutcome(False, tool, None, attempt, f"accesso a internet non approvato dal consenso: {reason}")
            run = await self._runner.run(tool, tool.test_input)
            if run.ok:
                self._store.save(tool)
                return SynthesisOutcome(True, tool, run, attempt, f"strumento «{tool.name}» creato e verificato")
            previous = tool.source
            problem = self._describe_failure(run)
            logger.warning("tool %s failed attempt %d: %s", tool.name, attempt, problem[:200])
        return SynthesisOutcome(False, None, None, self._max_attempts, f"nessuno strumento funzionante dopo {self._max_attempts} tentativi: {problem}")

    def _request(self, goal: str, context: Dict[str, Any], problem: str, previous: str) -> str:
        parts = [f"Compito: {goal}", f"Contesto: {json.dumps(context, default=str)[:600]}"]
        if problem:
            parts.append(f"Il tentativo precedente è fallito: {problem}")
        if previous:
            parts.append(f"Codice precedente da correggere:\n{previous[:3000]}")
        return "\n\n".join(parts)

    def _parse(self, raw: str) -> DynamicTool:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("risposta senza oggetto JSON")
        data = json.loads(raw[start : end + 1])
        if not isinstance(data, dict):
            raise ValueError("la risposta deve essere un oggetto JSON")
        data["egress_hosts"] = [str(h).lower() for h in data.get("egress_hosts") or []]
        return DynamicTool.from_dict({**data, "created_at": self._clock()})

    @staticmethod
    def _static_check(tool: DynamicTool) -> None:
        if tool.language is Language.PYTHON:
            try:
                ast.parse(tool.source)
            except SyntaxError as exc:
                raise ToolError(f"errore di sintassi alla riga {exc.lineno}: {exc.msg}") from exc
        if INPUT_FILE not in tool.source:
            raise ToolError(f"lo script deve leggere i parametri da /in/{INPUT_FILE}")

    @staticmethod
    def _describe_failure(run: ToolRun) -> str:
        parts = [run.error]
        if run.denied_hosts:
            parts.append(f"host bloccati perché non dichiarati in egress_hosts: {', '.join(run.denied_hosts)}")
        return " | ".join(p for p in parts if p)
