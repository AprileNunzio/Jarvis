import json
import logging
from dataclasses import dataclass, field
from typing import List, Mapping, Optional

from server.core.kernel.application.ports import NodeValidator
from server.core.kernel.application.validators import DefaultNodeValidator
from server.core.kernel.domain.node import NodeKind, NodeSpec
from server.core.kernel.domain.outcome import NodeResult, Verdict
from server.features.llm_gateway.contracts import LLMMessage, LLMRequest
from server.features.llm_gateway.gateway import llm_gateway

logger = logging.getLogger("jarvis.self_critique")

_REVIEW_SYSTEM = (
    "Sei un revisore perfezionista. Valuta la qualità dell'output:\n"
    "- Correttezza logica e fattuale\n"
    "- Completezza rispetto al task richiesto\n"
    "- Chiarezza e precisione\n"
    "- Assenza di errori o sviste\n"
    "Sii severo ma costruttivo. Rispondi SOLO con il JSON."
)
_REVIEW_PROMPT = (
    'Rivedi criticamente questo output generato per il task:\n"{task}"\n\nOutput da rivedere:\n{output}\n\n'
    "Rispondi con un JSON valido:\n"
    '{{"score": <1-10>, "issues": ["lista di problemi"], "needs_refinement": true/false, '
    '"refined_output": "output migliorato (solo se needs_refinement=true)"}}'
)


@dataclass(frozen=True)
class CritiqueReport:
    parsed: bool
    score: int = 10
    issues: List[str] = field(default_factory=list)
    needs_refinement: bool = False
    refined_output: str = ""


class SelfCritiqueEngine:
    def __init__(self, model_name: str = "qwen2.5:7b") -> None:
        self._model = model_name

    async def review(self, task: str, output: str) -> CritiqueReport:
        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=self._model,
                messages=[LLMMessage(role="user", content=_REVIEW_PROMPT.format(task=task, output=output))],
                system_prompt=_REVIEW_SYSTEM,
                temperature=0.3,
            )
        )
        raw = response.content.strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            return CritiqueReport(parsed=False)
        try:
            data = json.loads(raw[start : end + 1])
            return CritiqueReport(
                parsed=True,
                score=int(data.get("score", 10)),
                issues=[str(i) for i in data.get("issues", [])],
                needs_refinement=bool(data.get("needs_refinement", False)),
                refined_output=str(data.get("refined_output", "")),
            )
        except (ValueError, TypeError, AttributeError):
            return CritiqueReport(parsed=False)

    async def critique_and_refine(
        self, task: str, draft_output: str, max_refinements: int = 2, quality_threshold: int = 8
    ) -> str:
        current = draft_output
        for attempt in range(1, max_refinements + 1):
            report = await self.review(task, current)
            logger.info("Self-critique %d/%d score=%s issues=%s", attempt, max_refinements, report.score, report.issues)
            if not report.parsed or not report.needs_refinement or report.score >= quality_threshold:
                return current
            if len(report.refined_output.strip()) <= 10:
                return current
            current = report.refined_output
        return current


class LanguageCritic:
    def __init__(self, engine: SelfCritiqueEngine, quality_threshold: int = 6) -> None:
        self._engine = engine
        self._threshold = quality_threshold

    async def judge(self, node: NodeSpec, result: NodeResult) -> Verdict:
        text = result.speech.strip() or str(result.output.get("data", ""))
        report = await self._engine.review(node.description, text)
        if not report.parsed:
            logger.warning("critic output unparseable for node %s: accepting on deterministic checks only", node.node_id)
            return Verdict.accept()
        if report.score < self._threshold:
            return Verdict.reject("quality", "; ".join(report.issues) or f"score {report.score}/10", score=report.score)
        return Verdict.accept()


class CriticGate:
    def __init__(
        self,
        deterministic: Mapping[NodeKind, NodeValidator],
        language_critic: Optional[NodeValidator] = None,
    ) -> None:
        self._base = DefaultNodeValidator()
        self._deterministic = dict(deterministic)
        self._language = language_critic

    async def judge(self, node: NodeSpec, result: NodeResult) -> Verdict:
        verdict = await self._base.judge(node, result)
        if not verdict.accepted:
            return verdict
        specific = self._deterministic.get(node.kind)
        if specific is not None:
            verdict = await specific.judge(node, result)
            if not verdict.accepted:
                return verdict
        if node.kind is NodeKind.REASONING and self._language is not None:
            return await self._language.judge(node, result)
        return Verdict.accept()


self_critique_engine = SelfCritiqueEngine()
