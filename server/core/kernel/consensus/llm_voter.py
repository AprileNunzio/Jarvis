import json
from typing import Callable, List, Sequence, Union

from server.core.kernel.consensus.ballot import Ballot, describe_dag
from server.core.kernel.domain.dag import ExecutionDag
from server.features.llm_gateway.contracts import LLMMessage, LLMRequest
from server.features.llm_gateway.gateway import llm_gateway

_ANSWER_FORMAT = 'Rispondi SOLO con un JSON: {"approve": true|false, "reason": "motivo breve"}.'


class LlmVoter:
    def __init__(self, name: str, mandate: str, models: Union[Sequence[str], Callable[[], Sequence[str]]], can_veto: bool = False) -> None:
        self.name = name
        self.can_veto = can_veto
        self._mandate = mandate
        self._models = models if callable(models) else (lambda: list(models))

    async def vote(self, dag: ExecutionDag) -> Ballot:
        models: List[str] = list(self._models())
        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=(models or ["qwen2.5:7b"])[0],
                models=models,
                component=f"consensus_{self.name}",
                messages=[LLMMessage(role="user", content=f"Piano da valutare:\n{describe_dag(dag)}")],
                system_prompt=f"{self._mandate}\n{_ANSWER_FORMAT}",
                temperature=0.0,
                max_tokens=200,
            )
        )
        if response.is_synthetic:
            return Ballot(self.name, False, "no language model answered")
        raw = response.content
        start, end = raw.find("{"), raw.rfind("}")
        try:
            data = json.loads(raw[start : end + 1])
            return Ballot(self.name, data["approve"] is True, str(data.get("reason", ""))[:300])
        except (ValueError, KeyError, TypeError):
            return Ballot(self.name, False, "unreadable vote")
